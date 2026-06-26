from __future__ import annotations

import asyncio
import json
import logging
import re
from contextlib import asynccontextmanager
from copy import deepcopy
from dataclasses import dataclass, field
from html.parser import HTMLParser
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from datetime import UTC, datetime
from functools import lru_cache
from http import HTTPStatus
from time import perf_counter
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import httpx
import jwt
from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from packaging import version
from sqlalchemy.exc import OperationalError
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from ...core.auth import create_access_token, decode_access_token
from ...core.config import settings
from ...core.db import create_engine, create_session_factory
from ...core.model_prices import (
    build_group_price_payloads,
    build_models_dev_price_index,
)
from ...core.protocol_reachability import conversion_matrix
from ...core.time_zone import resolve_time_zone
from ...models import (
    AdminLoginRequest,
    AdminProfileUpdateRequest,
    AdminProfileUpdateResponse,
    AdminPasswordChangeRequest,
    AdminProfile,
    AppInfo,
    AuthTokenResponse,
    ChannelConfig,
    ChannelModelSyncRequest,
    ChannelModelSyncResponse,
    ConfigBackupDump,
    ConfigImportResult,
    ErrorResponse,
    GatewayApiKey,
    GatewayApiKeyCreate,
    GatewayApiKeyUpdate,
    ModelGroup,
    ModelGroupCandidatesRequest,
    ModelGroupCandidatesResponse,
    ModelGroupCreate,
    ModelGroupEnsureFromSiteRequest,
    ModelGroupEnsureFromSiteResponse,
    ModelGroupUpdate,
    ModelPriceItem,
    ModelPriceListResponse,
    ModelPriceUpdate,
    OverviewDailyPoint,
    OverviewModelAnalytics,
    OverviewSummary,
    ProtocolKind,
    PublicBranding,
    RequestLogDetail,
    RequestLogItem,
    RequestLogLifecycleStatus,
    RequestLogPage,
    RequestLogSortMode,
    RequestLogStatusFilter,
    RoutingStrategy,
    CronjobItem,
    CronjobRunResult,
    CronjobUpdate,
    SettingItem,
    SettingsUpdate,
    SiteBatchImportRequest,
    SiteBatchImportResult,
    SiteConfig,
    SiteCreate,
    SiteModelFetchItem,
    SiteModelFetchRequest,
    SiteModelTestRequest,
    SiteModelTestResult,
    SiteRuntimeSummary,
    SiteUpdate,
    VersionCheckResult,
    normalize_upstream_headers_config_json,
    normalize_upstream_param_override_config_json,
)
from ...persistence.admin_repository import AdminRepository
from ...persistence.backup_store import BackupStore
from ...persistence.channel_store import ChannelStore
from ...persistence.shared import (
    SETTING_CIRCUIT_BREAKER_COOLDOWN,
    SETTING_CIRCUIT_BREAKER_MAX_COOLDOWN,
    SETTING_CIRCUIT_BREAKER_THRESHOLD,
    SETTING_HEALTH_MIN_SAMPLES,
    SETTING_HEALTH_PENALTY_WEIGHT,
    SETTING_HEALTH_WINDOW_SECONDS,
    SETTING_LATEST_VERSION,
    SETTING_LATEST_VERSION_URL,
    SETTING_RELAY_LOG_BODY_ENABLED,
    SETTING_RELAY_LOG_KEEP_PERIOD,
    SETTING_SITE_LOGO_URL,
    SETTING_SITE_NAME,
    SETTING_TIME_ZONE,
    SETTING_UPSTREAM_HEADERS_CONFIG,
    SETTING_UPSTREAM_PARAM_OVERRIDE_CONFIG,
    SETTING_VERSION_CHECK_AT,
)
from ...persistence.repositories import (
    GatewayApiKeyRepository,
    GroupRepository,
    ModelPriceRepository,
    RequestLogStore,
    SettingsRepository,
)
from ...persistence.cronjob_store import CronjobSpec, CronjobStore
from ...persistence.entities import AdminUserEntity
from ..converters import (
    can_reach_protocol,
    convert_request,
    convert_response,
    convert_stream_iterator,
    needs_conversion,
)
from ..router import GatewayRouter, RouteSelection, RouteTarget
from ..cronjob_runner import CronjobAlreadyRunningError, CronjobRunner
from ..upstreams import (
    UpstreamRequest,
    build_upstream_headers,
    build_upstream_request,
    resolve_channel_api_key,
    resolve_channel_model_list_url,
    resolve_upstream_proxy_url,
)

TASK_REQUEST_LOG_PRUNE = "request_log_prune"
TASK_MODEL_PRICE_SYNC = "model_price_sync"
TASK_REQUEST_LOG_STATS_PERSIST = "request_log_stats_persist"
TASK_VERSION_CHECK = "version_check"
TASK_CHANNEL_MODEL_SYNC = "channel_model_sync"

GENERIC_USER_AGENT_TOKENS = (
    "python-httpx",
    "python/httpx",
    "python-requests",
    "python/requests",
    "python/http",
    "aiohttp",
    "httpcore",
    "urllib",
)

ANTHROPIC_FORWARD_HEADER_PREFIXES = (
    "anthropic-",
    "x-anthropic-",
    "x-claude-code-",
    "x-claude-remote-",
    "x-stainless-",
)
ANTHROPIC_FORWARD_HEADERS = frozenset(
    {
        "x-app",
        "x-app-name",
        "x-app-ver",
        "x-client-app",
        "x-environment-runner-version",
    }
)

CRONJOB_SPECS = (
    CronjobSpec(
        id=TASK_REQUEST_LOG_PRUNE,
        name="请求日志清理",
        description="按日志保留天数清理过期请求日志",
        default_interval_hours=1,
    ),
    CronjobSpec(
        id=TASK_MODEL_PRICE_SYNC,
        name="模型价格同步",
        description="从 models.dev 同步模型价格",
        default_interval_hours=24,
    ),
    CronjobSpec(
        id=TASK_REQUEST_LOG_STATS_PERSIST,
        name="请求日志统计落库",
        description="归档请求日志统计数据",
        default_interval_hours=1,
    ),
    CronjobSpec(
        id=TASK_VERSION_CHECK,
        name="版本检测",
        description="检测 GitHub releases 是否有新版本",
        default_interval_hours=24,
    ),
    CronjobSpec(
        id=TASK_CHANNEL_MODEL_SYNC,
        name="渠道模型同步",
        description="按周期拉取上游模型并同步模型组成员",
        default_interval_hours=24,
        default_enabled=False,
    ),
)

logger = logging.getLogger(__name__)

INTEGER_SETTING_KEYS = {
    SETTING_RELAY_LOG_KEEP_PERIOD,
    SETTING_CIRCUIT_BREAKER_THRESHOLD,
    SETTING_CIRCUIT_BREAKER_COOLDOWN,
    SETTING_CIRCUIT_BREAKER_MAX_COOLDOWN,
    SETTING_HEALTH_WINDOW_SECONDS,
    SETTING_HEALTH_MIN_SAMPLES,
}
FLOAT_SETTING_KEYS = {SETTING_HEALTH_PENALTY_WEIGHT}
BOOLEAN_SETTING_KEYS = {SETTING_RELAY_LOG_BODY_ENABLED}


@lru_cache(maxsize=1)
def _read_system_version() -> str:
    from lens_api import __version__

    return __version__


class AppState:
    def __init__(self) -> None:
        self.http = self._create_http_client()
        self.engine = create_engine(settings.database_url)
        self.session_factory = create_session_factory(self.engine)
        self.admin_repo = AdminRepository(self.session_factory)
        self.settings_repo = SettingsRepository(self.session_factory)
        self.gateway_api_key_repo = GatewayApiKeyRepository(self.session_factory)
        self.group_repo = GroupRepository(self.session_factory)
        self.model_price_repo = ModelPriceRepository(self.session_factory)
        self.request_log_store = RequestLogStore(
            self.session_factory,
            settings_repo=self.settings_repo,
            gateway_key_repo=self.gateway_api_key_repo,
        )

        self.cronjob_store = CronjobStore(self.session_factory)
        self.channel_store = ChannelStore(self.session_factory)
        self.backup_store = BackupStore(self.session_factory)
        self.router = GatewayRouter()
        self.cronjob_runner = CronjobRunner(
            store=self.cronjob_store,
            specs=CRONJOB_SPECS,
            handlers={
                TASK_REQUEST_LOG_PRUNE: self.request_log_store.prune_request_logs,
                TASK_MODEL_PRICE_SYNC: self._sync_model_prices,
                TASK_REQUEST_LOG_STATS_PERSIST: self.request_log_store.persist_request_log_stats,
                TASK_VERSION_CHECK: self._check_version_update,
                TASK_CHANNEL_MODEL_SYNC: self._sync_channel_models,
            },
            time_zone_provider=self._runtime_time_zone,
            logger=logger,
        )

    @staticmethod
    def _create_http_client() -> httpx.AsyncClient:
        timeout = httpx.Timeout(
            timeout=settings.request_timeout_seconds,
            connect=settings.connect_timeout_seconds,
        )
        limits = httpx.Limits(
            max_connections=settings.max_connections,
            max_keepalive_connections=settings.max_keepalive_connections,
        )
        return httpx.AsyncClient(timeout=timeout, limits=limits)

    async def _runtime_time_zone(self) -> ZoneInfo:
        runtime = await self.settings_repo.get_runtime_settings()
        return resolve_time_zone(str(runtime["time_zone"]))

    async def _sync_model_prices(self) -> None:
        from .tasks import _sync_group_prices

        await _sync_group_prices(self, overwrite_existing=True)

    async def _sync_channel_models(self) -> None:
        from .model_sync import sync_channel_models

        await sync_channel_models(self, dry_run=False)

    async def _check_version_update(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(
                    "https://api.github.com/repos/dyedd/lens/releases/latest",
                    headers={"Accept": "application/vnd.github.v3+json"},
                )
                response.raise_for_status()
                data = response.json()

                latest_version = data.get("tag_name", "").lstrip("v")
                release_url = data.get("html_url", "")

                current_version = _read_system_version()

                if latest_version and version.parse(latest_version) > version.parse(
                    current_version
                ):
                    await self.settings_repo.upsert_settings(
                        [
                            SettingItem(
                                key=SETTING_LATEST_VERSION, value=latest_version
                            ),
                            SettingItem(
                                key=SETTING_LATEST_VERSION_URL, value=release_url
                            ),
                            SettingItem(
                                key=SETTING_VERSION_CHECK_AT,
                                value=datetime.now(UTC).isoformat(),
                            ),
                        ]
                    )
                else:
                    await self.settings_repo.upsert_settings(
                        [
                            SettingItem(
                                key=SETTING_VERSION_CHECK_AT,
                                value=datetime.now(UTC).isoformat(),
                            ),
                            SettingItem(key=SETTING_LATEST_VERSION, value=""),
                            SettingItem(key=SETTING_LATEST_VERSION_URL, value=""),
                        ]
                    )
        except (httpx.HTTPError, ValueError, version.InvalidVersion) as exc:
            logger.warning("版本检查失败: %s", exc)


@dataclass(slots=True)
class RoutingPlan:
    requested_group_name: str | None
    resolved_group_name: str | None
    requested_group: ModelGroup | None
    resolved_group: ModelGroup | None
    strategy: RoutingStrategy
    route_targets: list[RouteTarget] | None
    use_model_matching: bool
    cursor_key: str | None = None


@dataclass(slots=True)
class UpstreamResult:
    response: Response
    status_code: int
    is_stream: bool = False
    first_token_latency_ms: int = 0
    upstream_model_name: str | None = None
    input_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_write_input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    input_cost_usd: float = 0.0
    output_cost_usd: float = 0.0
    total_cost_usd: float = 0.0
    request_content: str | None = None
    response_content: str | None = None
    stream_capture: StreamCapture | None = None


@dataclass(slots=True)
class AttemptLog:
    channel_id: str
    channel_name: str
    credential_id: str | None
    credential_name: str
    model_name: str | None
    status_code: int | None
    success: bool
    duration_ms: int
    error_message: str | None = None
    reasoning_effort: str | None = None


@dataclass(frozen=True, slots=True)
class _RequestDeadline:
    started_at: float
    timeout_seconds: float

    def remaining_seconds(self) -> float | None:
        if self.timeout_seconds <= 0:
            return None
        return max(self.timeout_seconds - (perf_counter() - self.started_at), 0.0)

    def expired(self) -> bool:
        remaining = self.remaining_seconds()
        return remaining is not None and remaining <= 0

    def message(self) -> str:
        timeout_seconds = float(max(self.timeout_seconds, 0))
        if timeout_seconds.is_integer():
            timeout_label = str(int(timeout_seconds))
        else:
            timeout_label = f"{timeout_seconds:.3f}".rstrip("0").rstrip(".")
        return f"Gateway request timed out after {timeout_label}s"


class UpstreamRequestError(HTTPException):
    def __init__(
        self,
        status_code: int,
        detail: Any,
        *,
        router_status_code: int | None,
        error_type: str = "upstream_error",
        skip_route_failure: bool = False,
        stop_fallback: bool = False,
        request_content: str | None = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.router_status_code = router_status_code
        self.error_type = error_type
        self.skip_route_failure = skip_route_failure
        self.stop_fallback = stop_fallback
        self.request_content = request_content


def _attempt_logs_to_dicts(attempts: list[AttemptLog]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for attempt in attempts:
        item = {
            "channel_id": attempt.channel_id,
            "channel_name": attempt.channel_name,
            "credential_id": attempt.credential_id,
            "credential_name": attempt.credential_name,
            "model_name": attempt.model_name,
            "status_code": attempt.status_code,
            "success": attempt.success,
            "duration_ms": attempt.duration_ms,
            "error_message": attempt.error_message,
        }
        if attempt.reasoning_effort is not None:
            item["reasoning_effort"] = attempt.reasoning_effort
        items.append(item)
    return items


@dataclass(slots=True)
class StreamCapture:
    capture_body: bool
    saw_first_chunk: bool = False
    chat_expected_choices: int = 1
    chat_finished_choices: set[int] = field(default_factory=set)
    first_token_latency_ms: int = 0
    response_content_chunks: list[str] = field(default_factory=list)
    client_response_content_chunks: list[str] = field(default_factory=list)
    event_buffer: str = ""
    event_format: str | None = None
    completed: bool = False
    client_disconnected: bool = False
    first_token_update_task: asyncio.Task[None] | None = None
    parse_errors: list[str] = field(default_factory=list)
    input_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_write_input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    resolved_model: str | None = None
    errors: list[str] = field(default_factory=list)
    request_log_id: int | None = None
    stream_started_at: float = 0.0
    client_to_close: httpx.AsyncClient | None = None
    deadline: _RequestDeadline | None = None
    error_status_code: int | None = None


app_state = AppState()

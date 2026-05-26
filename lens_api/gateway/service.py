from __future__ import annotations

import asyncio
import json
import logging
import re
from contextlib import asynccontextmanager
from copy import deepcopy
from dataclasses import dataclass, field
from collections.abc import AsyncIterator, Mapping
from datetime import UTC, datetime
from functools import lru_cache
from time import perf_counter
from typing import Any
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
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from packaging import version
from sqlalchemy.exc import OperationalError
from starlette.background import BackgroundTask

from ..api import create_app
from ..core.auth import create_access_token, decode_access_token
from ..core.config import settings
from ..core.db import create_engine, create_session_factory
from ..core.model_prices import build_group_price_payloads, build_models_dev_price_index
from ..core.time_zone import resolve_time_zone
from ..models import (
    AdminLoginRequest,
    AdminProfileUpdateRequest,
    AdminProfileUpdateResponse,
    AdminPasswordChangeRequest,
    AdminProfile,
    AppInfo,
    AuthTokenResponse,
    ChannelConfig,
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
    ModelGroupStats,
    ModelGroupUpdate,
    ModelPriceItem,
    ModelPriceListResponse,
    ModelPriceUpdate,
    OverviewDailyPoint,
    OverviewDashboardData,
    OverviewMetrics,
    OverviewModelAnalytics,
    OverviewPerformanceMetrics,
    OverviewSummary,
    ProtocolKind,
    PublicBranding,
    RequestLogDetail,
    RequestLogItem,
    RequestLogLifecycleStatus,
    RequestLogPage,
    RequestLogSortMode,
    RequestLogStatusFilter,
    RoutePreviewRequest,
    RoutingStrategy,
    CronjobItem,
    CronjobRunResult,
    CronjobUpdate,
    SettingItem,
    SettingsUpdate,
    SiteConfig,
    SiteCreate,
    SiteModelFetchItem,
    SiteModelFetchRequest,
    SiteModelTestRequest,
    SiteModelTestResult,
    SiteRuntimeSummary,
    SiteUpdate,
    VersionCheckResult,
)
from ..persistence.admin_store import AdminStore
from ..persistence.backup_store import BackupStore
from ..persistence.channel_store import ChannelStore
from ..persistence.domain_store import (
    SETTING_CIRCUIT_BREAKER_COOLDOWN,
    SETTING_CIRCUIT_BREAKER_MAX_COOLDOWN,
    SETTING_CIRCUIT_BREAKER_THRESHOLD,
    SETTING_HEALTH_MIN_SAMPLES,
    SETTING_HEALTH_PENALTY_WEIGHT,
    SETTING_HEALTH_WINDOW_SECONDS,
    SETTING_LATEST_VERSION,
    SETTING_LATEST_VERSION_URL,
    SETTING_MODEL_LIST_COMPAT_MODE_ENABLED,
    SETTING_RELAY_LOG_KEEP_PERIOD,
    SETTING_SITE_LOGO_URL,
    SETTING_SITE_NAME,
    SETTING_TIME_ZONE,
    SETTING_VERSION_CHECK_AT,
    DomainStore,
)
from ..persistence.cronjob_store import CronjobSpec, CronjobStore
from .converters import (
    convert_request,
    convert_response,
    convert_stream_iterator,
    needs_conversion,
)
from .router import RoundRobinRouter, RouteTarget
from .cronjob_runner import CronjobAlreadyRunningError, CronjobRunner
from .upstreams import (
    append_channel_url_path,
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


@lru_cache(maxsize=1)
def _read_system_version() -> str:
    from lens_api import __version__

    return __version__


class AppState:
    def __init__(self) -> None:
        self.http = self._create_http_client()
        self.engine = create_engine(settings.database_url)
        self.session_factory = create_session_factory(self.engine)
        self.admin_store = AdminStore(self.session_factory)
        self.domain_store = DomainStore(self.session_factory)
        self.cronjob_store = CronjobStore(self.session_factory)
        self.store = ChannelStore(self.session_factory)
        self.backup_store = BackupStore(self.session_factory)
        self.router = RoundRobinRouter()
        self.cronjob_runner = CronjobRunner(
            store=self.cronjob_store,
            specs=CRONJOB_SPECS,
            handlers={
                TASK_REQUEST_LOG_PRUNE: self.domain_store.prune_request_logs,
                TASK_MODEL_PRICE_SYNC: lambda: _sync_group_prices(
                    self, overwrite_existing=True
                ),
                TASK_REQUEST_LOG_STATS_PERSIST: self.domain_store.persist_request_log_stats,
                TASK_VERSION_CHECK: self._check_version_update,
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
        runtime = await self.domain_store.get_runtime_settings()
        return resolve_time_zone(str(runtime["time_zone"]))

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
                    await self.domain_store.upsert_settings(
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
                    await self.domain_store.upsert_settings(
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


@dataclass
class RoutingPlan:
    requested_group_name: str | None
    resolved_group_name: str | None
    requested_group: ModelGroup | None
    resolved_group: ModelGroup | None
    strategy: RoutingStrategy
    route_targets: list[RouteTarget] | None
    use_model_matching: bool
    cursor_key: str | None = None


@dataclass
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


@dataclass
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


class UpstreamRequestError(HTTPException):
    def __init__(
        self,
        status_code: int,
        detail: Any,
        *,
        router_status_code: int | None,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.router_status_code = router_status_code


@dataclass
class StreamCapture:
    saw_first_chunk: bool = False
    first_token_latency_ms: int = 0
    response_content_chunks: list[str] = field(default_factory=list)
    client_response_content_chunks: list[str] = field(default_factory=list)
    completed: bool = False
    client_disconnected: bool = False
    drain_task: asyncio.Task[None] | None = None
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
    last_persisted_first_token_latency_ms: int = 0


async def _startup_app_state(state: AppState) -> None:
    if not settings.auth_secret_key.strip():
        raise RuntimeError("LENS_AUTH_SECRET_KEY is required")
    resolve_time_zone(None)
    if state.http.is_closed:
        state.http = state._create_http_client()
    await state.domain_store.fail_running_request_logs()


async def _close_app_state(state: AppState) -> None:
    if not state.http.is_closed:
        await state.http.aclose()
    await state.engine.dispose()


app_state = AppState()


def _overview_window_minutes(
    days: int, daily_points: list[OverviewDailyPoint], time_zone_name: str
) -> int:
    time_zone = resolve_time_zone(time_zone_name)
    now = datetime.now(time_zone)
    if days == -1:
        start_at = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return max(int((now - start_at).total_seconds() // 60), 1)
    if days > 0:
        return max(days * 24 * 60, 1)
    if daily_points:
        try:
            start_at = datetime.strptime(daily_points[0].date, "%Y%m%d").replace(
                tzinfo=time_zone
            )
        except ValueError:
            return max(len(daily_points) * 24 * 60, 1)
        return max(int((now - start_at).total_seconds() // 60), 1)
    return 0


@asynccontextmanager
async def _managed_lifespan(state: AppState):
    await _startup_app_state(state)
    await state.cronjob_runner.start()
    try:
        yield
    except asyncio.CancelledError:
        # Uvicorn on Windows cancels the lifespan receive loop during Ctrl+C; treat as normal shutdown.
        pass
    finally:
        await state.cronjob_runner.stop()
        await _close_app_state(state)


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with _managed_lifespan(app_state):
        yield


auth_scheme = HTTPBearer(auto_error=False)


def _database_error_response(exc: OperationalError) -> JSONResponse:
    message = str(exc.orig if hasattr(exc, "orig") else exc).lower()
    if "database is locked" in message:
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        detail = "Database is busy, please retry"
    else:
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        detail = "Database operation failed"
    return JSONResponse(status_code=status_code, content={"detail": detail})


def _apply_router_runtime_settings(runtime: dict[str, Any]) -> None:
    app_state.router.configure_health_scoring(
        health_window_seconds=int(runtime["health_window_seconds"]),
        health_penalty_weight=float(runtime["health_penalty_weight"]),
        health_min_samples=int(runtime["health_min_samples"]),
    )


async def handle_operational_error(_: Request, exc: OperationalError) -> JSONResponse:
    return _database_error_response(exc)


async def dynamic_cors_middleware(request: Request, call_next):
    response = await call_next(request)
    try:
        runtime = await app_state.domain_store.get_runtime_settings()
        _apply_router_runtime_settings(runtime)
    except OperationalError as exc:
        return _database_error_response(exc)
    allow_origins = runtime["cors_allow_origins"]
    origin = request.headers.get("origin", "")
    if allow_origins == ["*"]:
        response.headers["access-control-allow-origin"] = "*"
    elif origin and origin in allow_origins:
        response.headers["access-control-allow-origin"] = origin
        response.headers["vary"] = "Origin"
    response.headers["access-control-allow-credentials"] = "true"
    response.headers["access-control-allow-methods"] = "*"
    response.headers["access-control-allow-headers"] = "*"
    return response


async def cors_preflight(path: str, request: Request) -> Response:
    try:
        runtime = await app_state.domain_store.get_runtime_settings()
        _apply_router_runtime_settings(runtime)
    except OperationalError as exc:
        return _database_error_response(exc)
    allow_origins = runtime["cors_allow_origins"]
    origin = request.headers.get("origin", "")
    headers = {
        "access-control-allow-credentials": "true",
        "access-control-allow-methods": "*",
        "access-control-allow-headers": request.headers.get(
            "access-control-request-headers", "*"
        ),
    }
    if allow_origins == ["*"]:
        headers["access-control-allow-origin"] = "*"
    elif origin and origin in allow_origins:
        headers["access-control-allow-origin"] = origin
        headers["vary"] = "Origin"
    return Response(status_code=204, headers=headers)


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(auth_scheme),
):
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )

    try:
        payload = decode_access_token(credentials.credentials, settings)
        username = payload.get("sub")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from exc

    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )

    admin = await app_state.admin_store.get_by_username(username)
    if admin is None or admin.is_active != 1:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin not found"
        )

    return admin


async def get_current_gateway_key(request: Request) -> GatewayApiKey:
    authorization = request.headers.get("authorization", "")
    x_api_key = request.headers.get("x-api-key", "")
    x_goog_api_key = request.headers.get("x-goog-api-key", "")

    secret = ""
    if authorization.lower().startswith("bearer "):
        secret = authorization[7:].strip()
    elif x_api_key:
        secret = x_api_key.strip()
    elif x_goog_api_key:
        secret = x_goog_api_key.strip()

    if not secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing gateway API key"
        )

    try:
        gateway_key = await app_state.domain_store.get_gateway_api_key_by_secret(secret)
    except OperationalError as exc:
        response = _database_error_response(exc)
        raise HTTPException(
            status_code=response.status_code, detail=response.body.decode()
        ) from exc

    if gateway_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid gateway API key"
        )

    if not gateway_key.enabled:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Gateway API key is disabled",
        )

    if _is_gateway_key_expired(gateway_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Gateway API key has expired",
        )

    if (
        gateway_key.max_cost_usd > 0
        and gateway_key.spent_cost_usd >= gateway_key.max_cost_usd
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Gateway API key has reached the max balance",
        )

    return gateway_key


def _is_gateway_key_expired(gateway_key: GatewayApiKey) -> bool:
    if not gateway_key.expires_at:
        return False
    try:
        expires_at = datetime.fromisoformat(
            gateway_key.expires_at.replace("Z", "+00:00")
        )
    except ValueError:
        return True
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at <= datetime.now(UTC)


def _gateway_key_allows_model(
    gateway_key: GatewayApiKey, model_name: str | None
) -> bool:
    if not gateway_key.allowed_models:
        return True
    if not model_name:
        return True
    normalized_allowed = {
        item.strip().lower() for item in gateway_key.allowed_models if item.strip()
    }
    return model_name.strip().lower() in normalized_allowed


async def healthz() -> dict[str, str]:
    return {"status": "ok"}


async def public_branding() -> PublicBranding:
    branding = await app_state.domain_store.get_branding_settings()
    return PublicBranding(
        site_name=branding["site_name"], logo_url=branding["site_logo_url"]
    )


async def app_info(_: Any = Depends(get_current_admin)) -> AppInfo:
    runtime = await app_state.domain_store.get_runtime_settings()
    return AppInfo(
        system_version=_read_system_version(),
        site_name=str(runtime["site_name"]),
        logo_url=str(runtime["site_logo_url"]),
        time_zone=str(runtime["time_zone"]),
    )


async def check_version(_: Any = Depends(get_current_admin)) -> VersionCheckResult:
    current_version = _read_system_version()

    settings = await app_state.domain_store.list_settings()
    settings_dict = {s.key: s.value for s in settings}

    latest_version = settings_dict.get(SETTING_LATEST_VERSION, "")
    latest_url = settings_dict.get(SETTING_LATEST_VERSION_URL, "")
    checked_at = settings_dict.get(SETTING_VERSION_CHECK_AT, "")

    has_update = False
    if latest_version:
        try:
            has_update = version.parse(latest_version) > version.parse(current_version)
        except version.InvalidVersion:
            logger.warning(
                "Invalid version string when comparing %r vs %r",
                latest_version,
                current_version,
            )

    return VersionCheckResult(
        current_version=current_version,
        latest_version=latest_version if has_update else "",
        release_url=latest_url if has_update else "",
        has_update=has_update,
        checked_at=checked_at,
    )


async def login(payload: AdminLoginRequest) -> AuthTokenResponse:
    user = await app_state.admin_store.authenticate(payload.username, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    access_token, expires_in = create_access_token(user.username, settings)
    return AuthTokenResponse(access_token=access_token, expires_in=expires_in)


async def current_admin(admin=Depends(get_current_admin)) -> AdminProfile:
    return AdminProfile(id=admin.id, username=admin.username)


async def update_profile(
    payload: AdminProfileUpdateRequest, admin=Depends(get_current_admin)
) -> AdminProfileUpdateResponse:
    normalized_username = payload.username.strip()
    if not normalized_username:
        raise HTTPException(status_code=400, detail="Username is required")

    try:
        updated_admin = await app_state.admin_store.update_profile(
            admin.username,
            normalized_username,
            payload.current_password,
            payload.new_password,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Admin not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    access_token, expires_in = create_access_token(updated_admin.username, settings)
    return AdminProfileUpdateResponse(
        access_token=access_token,
        expires_in=expires_in,
        profile=AdminProfile(id=updated_admin.id, username=updated_admin.username),
    )


async def change_password(
    payload: AdminPasswordChangeRequest, admin=Depends(get_current_admin)
) -> Response:
    try:
        await app_state.admin_store.update_password(
            admin.username, payload.current_password, payload.new_password
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(status_code=204)


async def list_sites(_: Any = Depends(get_current_admin)) -> list[SiteConfig]:
    return await app_state.store.list_sites()


async def site_runtime_summaries(
    _: Any = Depends(get_current_admin),
) -> list[SiteRuntimeSummary]:
    return await app_state.domain_store.list_site_runtime_summaries()


async def create_site(
    payload: SiteCreate, _: Any = Depends(get_current_admin)
) -> SiteConfig:
    try:
        return await app_state.store.create_site(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def update_site(
    site_id: str, payload: SiteUpdate, _: Any = Depends(get_current_admin)
) -> SiteConfig:
    try:
        return await app_state.store.update_site(site_id, payload)
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail=f"Site not found: {site_id}"
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def delete_site(site_id: str, _: Any = Depends(get_current_admin)) -> Response:
    try:
        await app_state.store.delete_site(site_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail=f"Site not found: {site_id}"
        ) from exc
    return Response(status_code=204)


async def fetch_site_models(
    payload: SiteModelFetchRequest, _: Any = Depends(get_current_admin)
) -> list[SiteModelFetchItem]:
    try:
        previews = await app_state.store.fetch_models_preview(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    items: list[SiteModelFetchItem] = []
    seen: set[tuple[str, str]] = set()
    for preview in previews:
        credential = next(
            item
            for item in payload.credentials
            if (item.id or "") == preview["credential_id"]
        )
        channel = ChannelConfig(
            id="preview",
            name=preview["credential_name"] or "preview",
            protocol=payload.protocol,
            base_url=payload.base_url,
            api_key=credential.api_key,
            headers=payload.headers,
            model_patterns=[],
            keys=[
                {
                    "id": preview["credential_id"],
                    "key": credential.api_key,
                    "remark": preview["credential_name"],
                    "enabled": True,
                }
            ],
            models=[],
            channel_proxy=payload.channel_proxy,
            param_override="",
            match_regex=payload.match_regex,
        )
        for model_name in await _fetch_upstream_models(channel):
            key = (preview["credential_id"], model_name)
            if key in seen:
                continue
            seen.add(key)
            items.append(
                SiteModelFetchItem(
                    credential_id=preview["credential_id"],
                    credential_name=preview["credential_name"],
                    model_name=model_name,
                )
            )
    return items


async def test_site_model(
    payload: SiteModelTestRequest, _: Any = Depends(get_current_admin)
) -> SiteModelTestResult:
    channel = _model_test_channel(payload)
    text = payload.prompt.strip()
    if payload.protocol == ProtocolKind.OPENAI_CHAT:
        body = {
            "model": payload.model_name,
            "messages": [{"role": "user", "content": text}],
            "max_tokens": 64,
            "stream": False,
        }
    elif payload.protocol == ProtocolKind.OPENAI_RESPONSES:
        body = {
            "model": payload.model_name,
            "input": text,
            "max_output_tokens": 64,
            "stream": False,
        }
    elif payload.protocol == ProtocolKind.OPENAI_EMBEDDING:
        body = {
            "model": payload.model_name,
            "input": text,
        }
    elif payload.protocol == ProtocolKind.ANTHROPIC:
        body = {
            "model": payload.model_name,
            "messages": [{"role": "user", "content": text}],
            "max_tokens": 64,
            "stream": False,
        }
    elif payload.protocol == ProtocolKind.GEMINI:
        body = {
            "model": payload.model_name,
            "contents": [{"role": "user", "parts": [{"text": text}]}],
            "generationConfig": {"maxOutputTokens": 64},
            "stream": False,
        }
    else:
        raise HTTPException(
            status_code=500, detail=f"Unsupported protocol={payload.protocol.value}"
        )
    try:
        body = _apply_param_override(channel, body)
        body["stream"] = False
    except UpstreamRequestError as exc:
        return SiteModelTestResult(
            success=False,
            status_code=exc.status_code,
            latency_ms=0,
            model_name=payload.model_name,
            credential_id=payload.credential.id,
            error_message=_format_channel_error(exc.detail),
        )
    return await _call_model_test_channel(
        channel=channel,
        body=body,
        model_name=payload.model_name,
        credential_id=payload.credential.id,
    )


async def router_snapshot(_: Any = Depends(get_current_admin)) -> dict[str, Any]:
    channels = await app_state.store.list()
    return app_state.router.snapshot(channels).model_dump(mode="json")


async def overview_metrics(_: Any = Depends(get_current_admin)) -> OverviewMetrics:
    metrics = await app_state.domain_store.get_overview_metrics()
    sites = await app_state.store.list_sites()
    protocols = [protocol for site in sites for protocol in site.protocols]
    return metrics.model_copy(
        update={
            "enabled_channels": sum(
                1 for protocol in protocols if protocol.enabled
            ),
            "total_channels": len(protocols),
        }
    )


async def overview_summary(
    days: int = 7,
    _: Any = Depends(get_current_admin),
) -> OverviewSummary:
    return await app_state.domain_store.get_overview_summary(
        days=days,
    )


async def overview_daily(
    days: int = 0,
    _: Any = Depends(get_current_admin),
) -> list[OverviewDailyPoint]:
    return await app_state.domain_store.list_overview_daily(
        days=days,
    )


async def overview_models(
    days: int = 7,
    gateway_key_id: str | None = None,
    _: Any = Depends(get_current_admin),
) -> OverviewModelAnalytics:
    return await app_state.domain_store.get_model_analytics(
        days=days,
        gateway_key_id=gateway_key_id,
    )


async def overview_dashboard(
    days: int = 7,
    log_limit: int = 50,
    log_offset: int = 0,
    _: Any = Depends(get_current_admin),
) -> OverviewDashboardData:
    summary, daily, models, logs = await asyncio.gather(
        app_state.domain_store.get_overview_summary(
            days=days,
        ),
        app_state.domain_store.list_overview_daily(
            days=days,
        ),
        app_state.domain_store.get_model_analytics(
            days=days,
        ),
        app_state.domain_store.list_request_logs(
            limit=log_limit,
            days=days,
            offset=log_offset,
        ),
    )
    runtime = await app_state.domain_store.get_runtime_settings()
    total_requests = summary.request_count.value
    total_tokens = summary.total_tokens.value
    window_minutes = _overview_window_minutes(days, daily, str(runtime["time_zone"]))
    performance = OverviewPerformanceMetrics(
        avg_requests_per_minute=(
            round(total_requests / window_minutes, 2) if window_minutes > 0 else 0.0
        ),
        avg_tokens_per_minute=(
            round(total_tokens / window_minutes, 2) if window_minutes > 0 else 0.0
        ),
    )
    return OverviewDashboardData(
        summary=summary,
        performance=performance,
        daily=daily,
        models=models,
        logs=logs,
    )


async def request_logs(
    limit: int = 100,
    offset: int = 0,
    gateway_key_id: str | None = None,
    _: Any = Depends(get_current_admin),
) -> list[RequestLogItem]:
    return await app_state.domain_store.list_request_logs(
        limit=limit,
        offset=offset,
        gateway_key_id=gateway_key_id,
    )


async def request_log_page(
    limit: int = 100,
    offset: int = 0,
    gateway_key_id: str | None = None,
    model_prefix: str | None = None,
    status_filter: RequestLogStatusFilter | None = Query(default=None, alias="status"),
    protocol: ProtocolKind | None = None,
    channel: str | None = None,
    keyword: str | None = None,
    sort: RequestLogSortMode = RequestLogSortMode.LATEST,
    _: Any = Depends(get_current_admin),
) -> RequestLogPage:
    return await app_state.domain_store.list_request_log_page(
        limit=limit,
        offset=offset,
        gateway_key_id=gateway_key_id,
        model_prefix=model_prefix,
        status_filter=status_filter,
        protocol=protocol,
        channel=channel,
        keyword=keyword,
        sort=sort,
    )


async def overview_logs(
    days: int = 7,
    limit: int = 50,
    offset: int = 0,
    _: Any = Depends(get_current_admin),
) -> list[RequestLogItem]:
    return await app_state.domain_store.list_request_logs(
        limit=limit,
        days=days,
        offset=offset,
    )


async def clear_request_logs(_: Any = Depends(get_current_admin)) -> Response:
    await app_state.domain_store.clear_request_logs()
    return Response(status_code=204)


async def request_log_detail(
    log_id: int, _: Any = Depends(get_current_admin)
) -> RequestLogDetail:
    try:
        return await app_state.domain_store.get_request_log(log_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail=f"Request log not found: {log_id}"
        ) from exc


async def router_preview(
    payload: RoutePreviewRequest, _: Any = Depends(get_current_admin)
) -> dict[str, Any]:
    channels = await app_state.store.list()
    runtime = await app_state.domain_store.get_runtime_settings()
    _apply_router_runtime_settings(runtime)
    if not payload.model:
        return app_state.router.preview(
            channels,
            payload.protocol,
            None,
            strategy=RoutingStrategy.ROUND_ROBIN,
            route_targets=None,
            use_model_matching=True,
        ).model_dump(mode="json")
    plan = await _resolve_routing_plan(payload.protocol, payload.model)
    return app_state.router.preview(
        channels,
        payload.protocol,
        plan.resolved_group_name or payload.model,
        strategy=plan.strategy,
        route_targets=plan.route_targets,
        use_model_matching=plan.use_model_matching,
        requested_group_name=plan.requested_group_name,
        resolved_group_name=plan.resolved_group_name,
        cursor_key=plan.cursor_key,
    ).model_dump(mode="json")


async def list_model_groups(_: Any = Depends(get_current_admin)) -> list[ModelGroup]:
    return await app_state.domain_store.list_groups()


async def get_model_group(
    group_id: str, _: Any = Depends(get_current_admin)
) -> ModelGroup:
    try:
        return await app_state.domain_store.get_group(group_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail=f"Model group not found: {group_id}"
        ) from exc


async def list_model_group_stats(
    _: Any = Depends(get_current_admin),
) -> list[ModelGroupStats]:
    return await app_state.domain_store.list_group_stats()


async def list_model_prices(
    _: Any = Depends(get_current_admin),
) -> ModelPriceListResponse:
    return await app_state.domain_store.list_model_prices()


async def update_model_price(
    model_key: str, payload: ModelPriceUpdate, _: Any = Depends(get_current_admin)
) -> ModelPriceItem:
    try:
        return await app_state.domain_store.upsert_model_price(
            payload.model_copy(update={"model_key": model_key})
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def sync_model_prices(
    _: Any = Depends(get_current_admin),
) -> ModelPriceListResponse:
    await _sync_group_prices(app_state, overwrite_existing=True)
    return await app_state.domain_store.list_model_prices()


async def list_cronjobs(
    _: Any = Depends(get_current_admin),
) -> list[CronjobItem]:
    return await app_state.cronjob_runner.list_cronjobs()


async def update_cronjob(
    task_id: str,
    payload: CronjobUpdate,
    _: Any = Depends(get_current_admin),
) -> CronjobItem:
    try:
        return await app_state.cronjob_runner.update_cronjob(
            task_id,
            enabled=payload.enabled,
            schedule_type=(
                payload.schedule_type.value
                if payload.schedule_type is not None
                else None
            ),
            interval_hours=payload.interval_hours,
            run_at_time=payload.run_at_time,
            weekdays=payload.weekdays,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail=f"Cron job not found: {task_id}"
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def run_cronjob(
    task_id: str,
    _: Any = Depends(get_current_admin),
) -> CronjobRunResult:
    try:
        task = await app_state.cronjob_runner.run_cronjob_now(task_id)
    except CronjobAlreadyRunningError as exc:
        raise HTTPException(
            status_code=409, detail=f"Cron job is already running: {task_id}"
        ) from exc
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail=f"Cron job not found: {task_id}"
        ) from exc
    return CronjobRunResult(cronjob=task)


async def model_group_candidates(
    payload: ModelGroupCandidatesRequest, _: Any = Depends(get_current_admin)
) -> ModelGroupCandidatesResponse:
    try:
        return await app_state.domain_store.list_group_candidates(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def create_model_group(
    payload: ModelGroupCreate, _: Any = Depends(get_current_admin)
) -> ModelGroup:
    try:
        return await app_state.domain_store.create_group(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def update_model_group(
    group_id: str, payload: ModelGroupUpdate, _: Any = Depends(get_current_admin)
) -> ModelGroup:
    try:
        return await app_state.domain_store.update_group(group_id, payload)
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail=f"Model group not found: {group_id}"
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def delete_model_group(
    group_id: str, _: Any = Depends(get_current_admin)
) -> Response:
    try:
        await app_state.domain_store.delete_group(group_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail=f"Model group not found: {group_id}"
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(status_code=204)


async def list_settings(_: Any = Depends(get_current_admin)) -> list[SettingItem]:
    return await app_state.domain_store.list_settings()


async def update_settings(
    payload: SettingsUpdate, _: Any = Depends(get_current_admin)
) -> list[SettingItem]:
    normalized_items = []
    current_time_zone = None
    next_time_zone = None
    next_time_zone_value = None
    if any(item.key == SETTING_TIME_ZONE for item in payload.items):
        runtime = await app_state.domain_store.get_runtime_settings()
        current_time_zone = str(runtime["time_zone"])
    for item in payload.items:
        if item.key == SETTING_SITE_NAME:
            normalized_items.append(
                SettingItem(key=item.key, value=item.value.strip() or "Lens")
            )
            continue
        if item.key == SETTING_SITE_LOGO_URL:
            normalized_items.append(SettingItem(key=item.key, value=item.value.strip()))
            continue
        if item.key == SETTING_TIME_ZONE:
            try:
                time_zone = resolve_time_zone(item.value)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            next_time_zone = time_zone.key
            next_time_zone_value = time_zone
            normalized_items.append(SettingItem(key=item.key, value=time_zone.key))
            continue
        if item.key in INTEGER_SETTING_KEYS:
            value = item.value.strip()
            try:
                int(value)
            except ValueError as exc:
                raise HTTPException(
                    status_code=400, detail=f"Invalid integer setting: {item.key}"
                ) from exc
            normalized_items.append(SettingItem(key=item.key, value=value))
            continue
        if item.key in FLOAT_SETTING_KEYS:
            value = item.value.strip()
            try:
                float(value)
            except ValueError as exc:
                raise HTTPException(
                    status_code=400, detail=f"Invalid numeric setting: {item.key}"
                ) from exc
            normalized_items.append(SettingItem(key=item.key, value=value))
            continue
        normalized_items.append(SettingItem(key=item.key, value=item.value.strip()))
    stored_items = await app_state.domain_store.upsert_settings(normalized_items)
    if next_time_zone is not None and next_time_zone != current_time_zone:
        await app_state.domain_store.persist_request_log_stats(force=True)
        if next_time_zone_value is not None:
            await app_state.cronjob_runner.reschedule_cronjobs(next_time_zone_value)
    return stored_items


async def list_gateway_api_keys(
    _: Any = Depends(get_current_admin),
) -> list[GatewayApiKey]:
    return await app_state.domain_store.list_gateway_api_keys()


async def create_gateway_api_key(
    payload: GatewayApiKeyCreate, _: Any = Depends(get_current_admin)
) -> GatewayApiKey:
    try:
        return await app_state.domain_store.create_gateway_api_key(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def update_gateway_api_key(
    key_id: str, payload: GatewayApiKeyUpdate, _: Any = Depends(get_current_admin)
) -> GatewayApiKey:
    try:
        return await app_state.domain_store.update_gateway_api_key(key_id, payload)
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail=f"Gateway API key not found: {key_id}"
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


async def delete_gateway_api_key(
    key_id: str, _: Any = Depends(get_current_admin)
) -> Response:
    try:
        await app_state.domain_store.delete_gateway_api_key(key_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail=f"Gateway API key not found: {key_id}"
        ) from exc
    return Response(status_code=204)


async def export_settings_bundle(
    include_logs: bool = False,
    include_gateway_api_keys: bool = False,
    _: Any = Depends(get_current_admin),
) -> JSONResponse:
    dump = await app_state.backup_store.export_dump(
        lens_version=_read_system_version(),
        include_request_logs=include_logs,
        include_gateway_api_keys=include_gateway_api_keys,
    )
    runtime = await app_state.domain_store.get_runtime_settings()
    timestamp = datetime.now(resolve_time_zone(str(runtime["time_zone"]))).strftime(
        "%Y%m%d%H%M%S"
    )
    return JSONResponse(
        content=dump.model_dump(mode="json"),
        headers={
            "content-disposition": f'attachment; filename="lens-backup-{timestamp}.json"',
        },
    )


async def import_settings_bundle(
    file: UploadFile = File(...), _: Any = Depends(get_current_admin)
) -> ConfigImportResult:
    try:
        payload = await file.read()
    finally:
        await file.close()

    try:
        dump = ConfigBackupDump.model_validate_json(payload)
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid backup file") from exc

    try:
        result = await app_state.backup_store.import_dump(dump)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    app_state.domain_store.invalidate_settings_cache()
    return result


async def proxy_openai_chat(
    request: Request, gateway_key: GatewayApiKey = Depends(get_current_gateway_key)
):
    body = await request.json()
    return await _proxy_protocol(
        ProtocolKind.OPENAI_CHAT,
        body,
        gateway_key,
        request.headers.get("user-agent"),
    )


async def proxy_openai_responses(
    request: Request, gateway_key: GatewayApiKey = Depends(get_current_gateway_key)
):
    body = await request.json()
    return await _proxy_protocol(
        ProtocolKind.OPENAI_RESPONSES,
        body,
        gateway_key,
        request.headers.get("user-agent"),
    )


async def proxy_anthropic_messages(
    request: Request, gateway_key: GatewayApiKey = Depends(get_current_gateway_key)
):
    body = await request.json()
    return await _proxy_protocol(
        ProtocolKind.ANTHROPIC,
        body,
        gateway_key,
        request.headers.get("user-agent"),
        _forward_anthropic_headers(request.headers),
    )


async def proxy_openai_embeddings(
    request: Request, gateway_key: GatewayApiKey = Depends(get_current_gateway_key)
):
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(
            status_code=400,
            detail="Embeddings request body must be a JSON object",
        )
    body.pop("stream", None)
    return await _proxy_protocol(
        ProtocolKind.OPENAI_EMBEDDING,
        body,
        gateway_key,
        request.headers.get("user-agent"),
    )


_OPENAI_LIST_PROTOCOLS: frozenset[ProtocolKind] = frozenset(
    {
        ProtocolKind.OPENAI_CHAT,
        ProtocolKind.OPENAI_RESPONSES,
        ProtocolKind.OPENAI_EMBEDDING,
    }
)
_ALL_MODEL_LIST_PROTOCOLS: frozenset[ProtocolKind] = frozenset(ProtocolKind)


def _filtered_group_names(
    groups: list[ModelGroup],
    gateway_key: GatewayApiKey,
    protocols: frozenset[ProtocolKind] | set[ProtocolKind],
) -> list[str]:
    return sorted(
        {
            group.name.strip()
            for group in groups
            if group.name.strip()
            and group.protocol in protocols
            and _gateway_key_allows_model(gateway_key, group.name)
        }
    )


def _build_openai_models_payload(
    groups: list[ModelGroup],
    gateway_key: GatewayApiKey,
    protocols: frozenset[ProtocolKind] | set[ProtocolKind] = _OPENAI_LIST_PROTOCOLS,
) -> dict[str, Any]:
    names = _filtered_group_names(groups, gateway_key, protocols)
    return {
        "object": "list",
        "data": [
            {
                "id": name,
                "object": "model",
                "created": 0,
                "owned_by": "lens",
            }
            for name in names
        ],
    }


def _build_anthropic_models_payload(
    groups: list[ModelGroup], gateway_key: GatewayApiKey
) -> dict[str, Any]:
    names = _filtered_group_names(
        groups, gateway_key, frozenset({ProtocolKind.ANTHROPIC})
    )
    return {
        "data": [
            {
                "id": name,
                "type": "model",
                "display_name": name,
                "created_at": "1970-01-01T00:00:00Z",
            }
            for name in names
        ],
        "first_id": names[0] if names else None,
        "last_id": names[-1] if names else None,
        "has_more": False,
    }


def _build_gemini_models_payload(
    groups: list[ModelGroup], gateway_key: GatewayApiKey
) -> dict[str, Any]:
    names = _filtered_group_names(groups, gateway_key, frozenset({ProtocolKind.GEMINI}))
    return {
        "models": [
            {
                "name": f"models/{name}",
                "baseModelId": name,
                "version": "001",
                "displayName": name,
                "supportedGenerationMethods": [
                    "generateContent",
                    "streamGenerateContent",
                ],
            }
            for name in names
        ]
    }


async def list_gateway_models(
    request: Request,
    gateway_key: GatewayApiKey = Depends(get_current_gateway_key),
) -> dict[str, Any]:
    groups = await app_state.domain_store.list_groups()
    runtime = await app_state.domain_store.get_runtime_settings()
    if runtime["model_list_compat_mode_enabled"]:
        return _build_openai_models_payload(
            groups, gateway_key, _ALL_MODEL_LIST_PROTOCOLS
        )
    if request.headers.get("anthropic-version"):
        return _build_anthropic_models_payload(groups, gateway_key)
    return _build_openai_models_payload(groups, gateway_key)


async def list_gemini_models(
    gateway_key: GatewayApiKey = Depends(get_current_gateway_key),
) -> dict[str, Any]:
    groups = await app_state.domain_store.list_groups()
    return _build_gemini_models_payload(groups, gateway_key)


async def proxy_gemini_generate_content(
    model_name: str,
    request: Request,
    gateway_key: GatewayApiKey = Depends(get_current_gateway_key),
):
    body = await request.json()
    body = {**body, "model": model_name, "stream": False}
    return await _proxy_protocol(
        ProtocolKind.GEMINI,
        body,
        gateway_key,
        request.headers.get("user-agent"),
    )


async def proxy_gemini_stream_generate_content(
    model_name: str,
    request: Request,
    gateway_key: GatewayApiKey = Depends(get_current_gateway_key),
):
    body = await request.json()
    body = {**body, "model": model_name, "stream": True}
    return await _proxy_protocol(
        ProtocolKind.GEMINI,
        body,
        gateway_key,
        request.headers.get("user-agent"),
    )


@dataclass
class _RequestLogger:
    request_log_id: int
    protocol: ProtocolKind
    gateway_key: GatewayApiKey
    started_at: float
    body: dict[str, Any]
    request_content: str | None
    attempts: list[AttemptLog]

    async def update(
        self,
        *,
        requested_group_name: str | None,
        resolved_group_name: str | None,
        upstream_model_name: str | None,
        channel: ChannelConfig | None,
        user_agent: str,
        lifecycle_status: RequestLogLifecycleStatus,
        status_code: int | None,
        success: bool,
        is_stream: bool,
        first_token_latency_ms: int = 0,
        request_content: str | None = None,
        response_content: str | None = None,
        error_message: str | None = None,
        result: UpstreamResult | None = None,
    ) -> None:
        kwargs: dict[str, Any] = {}
        if result is not None:
            kwargs.update(
                input_tokens=result.input_tokens,
                cache_read_input_tokens=result.cache_read_input_tokens,
                cache_write_input_tokens=result.cache_write_input_tokens,
                output_tokens=result.output_tokens,
                total_tokens=result.total_tokens,
                input_cost_usd=result.input_cost_usd,
                output_cost_usd=result.output_cost_usd,
                total_cost_usd=result.total_cost_usd,
            )
        await _update_request_log(
            self.request_log_id,
            protocol=self.protocol,
            requested_group_name=requested_group_name,
            resolved_group_name=resolved_group_name,
            upstream_model_name=upstream_model_name,
            channel_id=channel.id if channel else None,
            channel_name=channel.name if channel else None,
            gateway_key=self.gateway_key,
            user_agent=user_agent,
            lifecycle_status=lifecycle_status,
            status_code=status_code,
            success=success,
            is_stream=is_stream,
            first_token_latency_ms=first_token_latency_ms,
            latency_ms=_elapsed_ms(self.started_at),
            request_content=(
                request_content if request_content is not None else self.request_content
            ),
            response_content=response_content,
            attempts=[item.__dict__ for item in self.attempts],
            error_message=error_message,
            **kwargs,
        )


async def _proxy_protocol(
    protocol: ProtocolKind,
    body: dict[str, Any],
    gateway_key: GatewayApiKey,
    inbound_user_agent: str | None = None,
    inbound_headers: Mapping[str, str] | None = None,
) -> Response:
    channels, runtime = await asyncio.gather(
        app_state.store.list(),
        app_state.domain_store.get_runtime_settings(),
    )
    _apply_router_runtime_settings(runtime)
    started_at = perf_counter()
    request_content = _dump_json(body)
    inbound_ua = _normalize_user_agent(inbound_user_agent)
    upstream_user_agent = (
        inbound_ua
        if inbound_ua and not _is_generic_user_agent(inbound_ua)
        else _default_lens_user_agent()
    )
    is_stream_body = bool(body.get("stream"))
    requested_model = body.get("model")
    if not isinstance(requested_model, str) or not requested_model.strip():
        request_log = await app_state.domain_store.create_pending_request_log(
            protocol=protocol.value,
            user_agent=upstream_user_agent,
            requested_group_name=None,
            resolved_group_name=None,
            upstream_model_name=None,
            channel_id=None,
            channel_name=None,
            gateway_key_id=gateway_key.id,
            is_stream=is_stream_body,
            request_content=request_content,
        )
        await _update_request_log(
            request_log.id,
            protocol=protocol,
            requested_group_name=None,
            resolved_group_name=None,
            upstream_model_name=None,
            channel_id=None,
            channel_name=None,
            gateway_key=gateway_key,
            user_agent=upstream_user_agent,
            lifecycle_status=RequestLogLifecycleStatus.FAILED,
            status_code=400,
            success=False,
            is_stream=is_stream_body,
            first_token_latency_ms=0,
            latency_ms=_elapsed_ms(started_at),
            request_content=request_content,
            attempts=[],
            error_message="Request model is required",
        )
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                error={
                    "type": "missing_model",
                    "message": "Request model is required",
                }
            ).model_dump(mode="json"),
        )
    requested_model = requested_model.strip()
    if not _gateway_key_allows_model(gateway_key, requested_model):
        return JSONResponse(
            status_code=403,
            content=ErrorResponse(
                error={
                    "type": "forbidden_model",
                    "message": "Gateway API key is not allowed to use this model",
                }
            ).model_dump(mode="json"),
        )
    plan: RoutingPlan | None = None
    request_log = await app_state.domain_store.create_pending_request_log(
        protocol=protocol.value,
        user_agent=upstream_user_agent,
        requested_group_name=requested_model,
        resolved_group_name=None,
        upstream_model_name=None,
        channel_id=None,
        channel_name=None,
        gateway_key_id=gateway_key.id,
        is_stream=is_stream_body,
        request_content=request_content,
    )
    log_ctx = _RequestLogger(
        request_log_id=request_log.id,
        protocol=protocol,
        gateway_key=gateway_key,
        started_at=started_at,
        body=body,
        request_content=request_content,
        attempts=[],
    )
    try:
        try:
            plan = await _resolve_routing_plan(protocol, requested_model)
            selection = app_state.router.select(
                channels,
                protocol,
                plan.resolved_group_name,
                strategy=plan.strategy,
                route_targets=plan.route_targets,
                use_model_matching=plan.use_model_matching,
                cursor_key=plan.cursor_key,
            )
            await log_ctx.update(
                requested_group_name=plan.requested_group_name,
                resolved_group_name=plan.resolved_group_name,
                upstream_model_name=None,
                channel=None,
                user_agent=upstream_user_agent,
                lifecycle_status=RequestLogLifecycleStatus.CONNECTING,
                status_code=None,
                success=False,
                is_stream=is_stream_body,
            )
        except LookupError as exc:
            await log_ctx.update(
                requested_group_name=(
                    plan.requested_group_name if plan else requested_model
                ),
                resolved_group_name=plan.resolved_group_name if plan else None,
                upstream_model_name=None,
                channel=None,
                user_agent=upstream_user_agent,
                lifecycle_status=RequestLogLifecycleStatus.FAILED,
                status_code=503,
                success=False,
                is_stream=is_stream_body,
                error_message=str(exc),
            )
            return JSONResponse(
                status_code=503,
                content=ErrorResponse(
                    error={"type": "routing_error", "message": str(exc)}
                ).model_dump(mode="json"),
            )

        errors: list[str] = []
        for target in [selection.primary, *selection.fallbacks]:
            if not app_state.router.is_target_available(target):
                continue
            response = await _try_target(
                target=target,
                protocol=protocol,
                body=body,
                runtime=runtime,
                upstream_user_agent=upstream_user_agent,
                inbound_headers=inbound_headers,
                plan=plan,
                log_ctx=log_ctx,
                errors=errors,
            )
            if response is not None:
                return response

        return JSONResponse(
            status_code=502,
            content=ErrorResponse(
                error={
                    "type": "upstream_error",
                    "message": "All upstream channels failed",
                    "details": errors,
                }
            ).model_dump(mode="json"),
        )
    except Exception as exc:
        logger.exception("Proxy request failed unexpectedly")
        await log_ctx.update(
            requested_group_name=plan.requested_group_name if plan else requested_model,
            resolved_group_name=plan.resolved_group_name if plan else None,
            upstream_model_name=None,
            channel=None,
            user_agent=upstream_user_agent,
            lifecycle_status=RequestLogLifecycleStatus.FAILED,
            status_code=500,
            success=False,
            is_stream=is_stream_body,
            error_message=f"Unexpected proxy error: {type(exc).__name__}: {exc}",
        )
        raise


async def _try_target(
    *,
    target: RouteTarget,
    protocol: ProtocolKind,
    body: dict[str, Any],
    runtime: dict[str, Any],
    upstream_user_agent: str,
    inbound_headers: Mapping[str, str] | None,
    plan: RoutingPlan,
    log_ctx: _RequestLogger,
    errors: list[str],
) -> Response | None:
    channel = target.channel
    attempt_started_at = perf_counter()
    effective_user_agent = upstream_user_agent
    for name, value in channel.headers.items():
        if name.lower() == "user-agent":
            effective_user_agent = _normalize_user_agent(value)
            break

    if needs_conversion(protocol, channel.protocol):
        try:
            upstream_body = convert_request(
                protocol, channel.protocol, body, target.model_name
            )
        except ValueError as exc:
            return await _record_target_failure(
                target=target,
                channel=channel,
                runtime=runtime,
                log_ctx=log_ctx,
                plan=plan,
                errors=errors,
                attempt_started_at=attempt_started_at,
                effective_user_agent=effective_user_agent,
                upstream_body=body,
                exc=UpstreamRequestError(
                    status_code=400,
                    detail=str(exc),
                    router_status_code=None,
                ),
            )
    else:
        upstream_body = _prepare_upstream_body(protocol, body, target.model_name)
    try:
        upstream_body = _apply_param_override(channel, upstream_body)
    except UpstreamRequestError as exc:
        return await _record_target_failure(
            target=target,
            channel=channel,
            runtime=runtime,
            log_ctx=log_ctx,
            plan=plan,
            errors=errors,
            attempt_started_at=attempt_started_at,
            effective_user_agent=effective_user_agent,
            upstream_body=upstream_body,
            exc=exc,
        )
    if protocol == ProtocolKind.OPENAI_EMBEDDING:
        upstream_body.pop("stream", None)

    upstream_request_content = _dump_json(upstream_body)
    await log_ctx.update(
        requested_group_name=plan.requested_group_name,
        resolved_group_name=plan.resolved_group_name,
        upstream_model_name=target.model_name,
        channel=channel,
        user_agent=effective_user_agent,
        lifecycle_status=RequestLogLifecycleStatus.CONNECTING,
        status_code=None,
        success=False,
        is_stream=bool(upstream_body.get("stream")),
        request_content=upstream_request_content,
    )
    try:
        result = await _call_channel(
            channel,
            upstream_body,
            pricing_group_name=plan.resolved_group_name,
            client_protocol=protocol,
            credential_id=target.credential_id,
            user_agent=upstream_user_agent,
            forwarded_headers=inbound_headers,
        )
    except UpstreamRequestError as exc:
        return await _record_target_failure(
            target=target,
            channel=channel,
            runtime=runtime,
            log_ctx=log_ctx,
            plan=plan,
            errors=errors,
            attempt_started_at=attempt_started_at,
            effective_user_agent=effective_user_agent,
            upstream_body=upstream_body,
            exc=exc,
        )
    except HTTPException as exc:
        return await _record_target_failure(
            target=target,
            channel=channel,
            runtime=runtime,
            log_ctx=log_ctx,
            plan=plan,
            errors=errors,
            attempt_started_at=attempt_started_at,
            effective_user_agent=effective_user_agent,
            upstream_body=upstream_body,
            exc=UpstreamRequestError(
                status_code=exc.status_code,
                detail=exc.detail,
                router_status_code=exc.status_code,
            ),
        )

    log_ctx.attempts.append(
        AttemptLog(
            channel_id=channel.id,
            channel_name=channel.name,
            credential_id=target.credential_id,
            credential_name=target.credential_name or "",
            model_name=target.model_name,
            status_code=result.status_code,
            success=True,
            duration_ms=_elapsed_ms(attempt_started_at),
        )
    )
    merged_request_content = result.request_content or upstream_request_content
    if result.is_stream:
        if result.stream_capture is not None:
            result.stream_capture.request_log_id = log_ctx.request_log_id
            result.stream_capture.stream_started_at = log_ctx.started_at
        await log_ctx.update(
            requested_group_name=plan.requested_group_name,
            resolved_group_name=plan.resolved_group_name,
            upstream_model_name=result.upstream_model_name,
            channel=channel,
            user_agent=effective_user_agent,
            lifecycle_status=RequestLogLifecycleStatus.STREAMING,
            status_code=result.status_code,
            success=False,
            is_stream=True,
            request_content=merged_request_content,
        )
        result.response.background = BackgroundTask(
            _record_stream_request_log,
            request_log_id=log_ctx.request_log_id,
            protocol=protocol,
            requested_group_name=plan.requested_group_name,
            resolved_group_name=plan.resolved_group_name,
            channel=channel,
            gateway_key=log_ctx.gateway_key,
            user_agent=effective_user_agent,
            started_at=log_ctx.started_at,
            upstream_body=upstream_body,
            result=result,
            attempts=[item.__dict__ for item in log_ctx.attempts],
        )
        return result.response
    await log_ctx.update(
        requested_group_name=plan.requested_group_name,
        resolved_group_name=plan.resolved_group_name,
        upstream_model_name=result.upstream_model_name,
        channel=channel,
        user_agent=effective_user_agent,
        lifecycle_status=RequestLogLifecycleStatus.SUCCEEDED,
        status_code=result.status_code,
        success=True,
        is_stream=result.is_stream,
        first_token_latency_ms=result.first_token_latency_ms,
        request_content=merged_request_content,
        response_content=result.response_content,
        result=result,
    )
    return result.response


async def _record_target_failure(
    *,
    target: RouteTarget,
    channel: ChannelConfig,
    runtime: dict[str, Any],
    log_ctx: _RequestLogger,
    plan: RoutingPlan,
    errors: list[str],
    attempt_started_at: float,
    effective_user_agent: str,
    upstream_body: dict[str, Any],
    exc: UpstreamRequestError,
) -> None:
    message = _format_channel_error(exc.detail)
    app_state.router.record_failure(
        channel.id,
        message,
        status_code=exc.router_status_code,
        credential_id=target.credential_id,
        channel_keys=channel.keys,
        threshold=int(runtime["circuit_breaker_threshold"]),
        cooldown_seconds=int(runtime["circuit_breaker_cooldown"]),
        max_cooldown_seconds=int(runtime["circuit_breaker_max_cooldown"]),
    )
    errors.append(message)
    log_ctx.attempts.append(
        AttemptLog(
            channel_id=channel.id,
            channel_name=channel.name,
            credential_id=target.credential_id,
            credential_name=target.credential_name or "",
            model_name=target.model_name,
            status_code=exc.status_code,
            success=False,
            duration_ms=_elapsed_ms(attempt_started_at),
            error_message=message,
        )
    )
    await log_ctx.update(
        requested_group_name=plan.requested_group_name,
        resolved_group_name=plan.resolved_group_name,
        upstream_model_name=None,
        channel=channel,
        user_agent=effective_user_agent,
        lifecycle_status=RequestLogLifecycleStatus.FAILED,
        status_code=exc.status_code,
        success=False,
        is_stream=bool(upstream_body.get("stream")),
        request_content=_dump_json(upstream_body),
        error_message=message,
    )
    return None


async def _call_channel(
    channel: ChannelConfig,
    body: dict[str, Any],
    pricing_group_name: str | None = None,
    client_protocol: ProtocolKind | None = None,
    credential_id: str | None = None,
    user_agent: str | None = None,
    forwarded_headers: Mapping[str, str] | None = None,
) -> UpstreamResult:
    upstream = build_upstream_request(
        channel,
        body,
        settings,
        credential_id=credential_id,
        user_agent=user_agent,
        forwarded_headers=forwarded_headers,
    )
    request_content = _dump_json(upstream.json_body)
    runtime = await app_state.domain_store.get_runtime_settings()
    proxy_url = resolve_upstream_proxy_url(channel, runtime["proxy_url"])
    client, close_client = _resolve_http_client(proxy_url)
    is_stream_request = bool(body.get("stream"))

    try:
        stream_started_at = perf_counter()
        response = await _send_upstream(client, upstream, stream=is_stream_request)
        response.raise_for_status()

        is_event_stream = (
            "text/event-stream" in (response.headers.get("content-type") or "").lower()
        )
        if (
            is_event_stream
            and not is_stream_request
            and channel.protocol == ProtocolKind.ANTHROPIC
        ):
            result = await _build_anthropic_sse_to_json_result(
                response, channel, pricing_group_name, request_content
            )
        elif is_event_stream:
            result = _build_stream_result(
                response,
                channel,
                client_protocol,
                body,
                request_content,
                stream_started_at,
            )
        else:
            result = await _build_json_result(
                response,
                channel,
                client_protocol,
                body,
                pricing_group_name,
                request_content,
            )
        app_state.router.record_success(channel.id, credential_id=credential_id)
        return result
    except httpx.HTTPStatusError as exc:
        await exc.response.aread()
        detail = exc.response.text or f"HTTP {exc.response.status_code}"
        raise UpstreamRequestError(
            status_code=exc.response.status_code,
            detail=detail,
            router_status_code=exc.response.status_code,
        ) from exc
    except httpx.HTTPError as exc:
        raise UpstreamRequestError(
            status_code=502,
            detail=_format_transport_error(exc, upstream.url),
            router_status_code=None,
        ) from exc
    finally:
        if close_client:
            await client.aclose()


def _resolve_http_client(proxy_url: str | None) -> tuple[httpx.AsyncClient, bool]:
    if not proxy_url:
        return app_state.http, False
    client = httpx.AsyncClient(
        proxy=proxy_url,
        timeout=app_state.http.timeout,
        limits=httpx.Limits(
            max_connections=settings.max_connections,
            max_keepalive_connections=settings.max_keepalive_connections,
        ),
        trust_env=False,
    )
    return client, True


async def _send_upstream(
    client: httpx.AsyncClient, upstream: Any, *, stream: bool
) -> httpx.Response:
    if stream:
        request = client.build_request(
            upstream.method,
            upstream.url,
            headers=upstream.headers,
            json=upstream.json_body,
        )
        return await client.send(request, stream=True)
    return await client.request(
        upstream.method, upstream.url, headers=upstream.headers, json=upstream.json_body
    )


async def _build_anthropic_sse_to_json_result(
    response: httpx.Response,
    channel: ChannelConfig,
    pricing_group_name: str | None,
    request_content: str | None,
) -> UpstreamResult:
    content = (
        response.content if hasattr(response, "content") else await response.aread()
    )
    raw_content = _decode_content_bytes(content)
    try:
        parsed = _extract_stream_usage(channel.protocol, raw_content)
    except ValueError as exc:
        raise UpstreamRequestError(
            status_code=502,
            detail=f"Invalid upstream usage: {exc}",
            router_status_code=502,
        ) from exc
    try:
        distilled_content = _distill_stream_response_content(
            channel.protocol, raw_content
        )
    except ValueError as exc:
        raise UpstreamRequestError(
            status_code=502,
            detail=f"Invalid upstream response: {exc}",
            router_status_code=502,
        ) from exc
    response_headers = _passthrough_headers(response.headers)
    media_type = response.headers.get("content-type")
    response_content = raw_content

    if distilled_content and distilled_content != raw_content:
        content = distilled_content.encode("utf-8")
        response_content = distilled_content
        media_type = "application/json"
        response_headers.pop("content-type", None)

    cost = await app_state.domain_store.estimate_model_cost(
        pricing_group_name,
        parsed["input_tokens"],
        parsed["output_tokens"],
        parsed["cache_read_input_tokens"],
        parsed["cache_write_input_tokens"],
    )
    return UpstreamResult(
        response=Response(
            content=content,
            status_code=response.status_code,
            media_type=media_type,
            headers=response_headers,
        ),
        status_code=response.status_code,
        is_stream=False,
        upstream_model_name=parsed["resolved_model"],
        input_tokens=parsed["input_tokens"],
        cache_read_input_tokens=parsed["cache_read_input_tokens"],
        cache_write_input_tokens=parsed["cache_write_input_tokens"],
        output_tokens=parsed["output_tokens"],
        total_tokens=parsed["total_tokens"],
        input_cost_usd=cost[0],
        output_cost_usd=cost[1],
        total_cost_usd=cost[2],
        request_content=request_content,
        response_content=response_content,
    )


def _build_stream_result(
    response: httpx.Response,
    channel: ChannelConfig,
    client_protocol: ProtocolKind | None,
    body: dict[str, Any],
    request_content: str | None,
    stream_started_at: float,
) -> UpstreamResult:
    capture = StreamCapture()
    chunk_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    capture.drain_task = asyncio.create_task(
        _pump_stream_response(
            response=response,
            protocol=channel.protocol,
            capture=capture,
            chunk_queue=chunk_queue,
            stream_started_at=stream_started_at,
        )
    )
    raw_iter = _consume_stream_queue(chunk_queue, capture)

    if client_protocol is not None and needs_conversion(
        client_protocol, channel.protocol
    ):
        converted_iter = convert_stream_iterator(
            client_protocol, channel.protocol, raw_iter, body.get("model", "")
        )
        converted_iter = _capture_converted_stream_iterator(converted_iter, capture)
        stream_media = "text/event-stream"
    else:
        converted_iter = raw_iter
        stream_media = response.headers.get("content-type")

    return UpstreamResult(
        response=StreamingResponse(
            converted_iter,
            status_code=response.status_code,
            media_type=stream_media,
            headers=_passthrough_headers(response.headers),
        ),
        is_stream=True,
        status_code=response.status_code,
        upstream_model_name=body.get("model"),
        request_content=request_content,
        stream_capture=capture,
    )


async def _build_json_result(
    response: httpx.Response,
    channel: ChannelConfig,
    client_protocol: ProtocolKind | None,
    body: dict[str, Any],
    pricing_group_name: str | None,
    request_content: str | None,
) -> UpstreamResult:
    content = (
        response.content if hasattr(response, "content") else await response.aread()
    )
    try:
        parsed = _extract_response_usage(channel.protocol, response)
    except ValueError as exc:
        raise UpstreamRequestError(
            status_code=502,
            detail=f"Invalid upstream usage: {exc}",
            router_status_code=502,
        ) from exc
    if client_protocol is not None and needs_conversion(
        client_protocol, channel.protocol
    ):
        content = convert_response(
            client_protocol, channel.protocol, content, body.get("model", "")
        )

    cost = await app_state.domain_store.estimate_model_cost(
        pricing_group_name,
        parsed["input_tokens"],
        parsed["output_tokens"],
        parsed["cache_read_input_tokens"],
        parsed["cache_write_input_tokens"],
    )
    return UpstreamResult(
        response=Response(
            content=content,
            status_code=response.status_code,
            media_type=response.headers.get("content-type"),
            headers=_passthrough_headers(response.headers),
        ),
        status_code=response.status_code,
        is_stream=False,
        upstream_model_name=parsed["resolved_model"],
        input_tokens=parsed["input_tokens"],
        cache_read_input_tokens=parsed["cache_read_input_tokens"],
        cache_write_input_tokens=parsed["cache_write_input_tokens"],
        output_tokens=parsed["output_tokens"],
        total_tokens=parsed["total_tokens"],
        input_cost_usd=cost[0],
        output_cost_usd=cost[1],
        total_cost_usd=cost[2],
        request_content=request_content,
        response_content=_decode_content_bytes(content),
    )


def _model_test_channel(payload: SiteModelTestRequest) -> ChannelConfig:
    return ChannelConfig(
        id="model-test",
        name=payload.credential.name or "model-test",
        protocol=payload.protocol,
        base_url=payload.base_url,
        api_key=payload.credential.api_key,
        headers=payload.headers,
        model_patterns=[],
        keys=[
            {
                "id": payload.credential.id,
                "key": payload.credential.api_key,
                "remark": payload.credential.name,
                "enabled": True,
            }
        ],
        models=[],
        channel_proxy=payload.channel_proxy,
        param_override=payload.param_override,
        match_regex="",
    )


async def _call_model_test_channel(
    *,
    channel: ChannelConfig,
    body: dict[str, Any],
    model_name: str,
    credential_id: str,
) -> SiteModelTestResult:
    upstream = build_upstream_request(
        channel,
        body,
        settings,
        credential_id=credential_id,
        user_agent=_default_lens_user_agent(),
    )
    runtime = await app_state.domain_store.get_runtime_settings()
    proxy_url = resolve_upstream_proxy_url(channel, runtime["proxy_url"])
    client, close_client = _resolve_http_client(proxy_url)

    started_at = perf_counter()
    try:
        response = await client.request(
            upstream.method,
            upstream.url,
            headers=upstream.headers,
            json=upstream.json_body,
        )
        latency_ms = _elapsed_ms(started_at)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            await exc.response.aread()
            detail = exc.response.text or f"HTTP {exc.response.status_code}"
            return SiteModelTestResult(
                success=False,
                status_code=exc.response.status_code,
                latency_ms=latency_ms,
                model_name=model_name,
                credential_id=credential_id,
                error_message=detail,
            )
        raw_payload = response.json()
        output_text = ""
        if channel.protocol == ProtocolKind.OPENAI_CHAT:
            choices = raw_payload.get("choices")
            if isinstance(choices, list):
                for choice in choices:
                    if not isinstance(choice, dict):
                        continue
                    message = choice.get("message")
                    if not isinstance(message, dict):
                        continue
                    text = _stringify_text_content(message.get("content")).strip()
                    if text:
                        output_text = text
                        break
        elif channel.protocol == ProtocolKind.OPENAI_RESPONSES:
            output_text_raw = raw_payload.get("output_text")
            if isinstance(output_text_raw, str) and output_text_raw.strip():
                output_text = output_text_raw.strip()
            else:
                output = raw_payload.get("output")
                if isinstance(output, list):
                    parts: list[str] = []
                    for item in output:
                        if not isinstance(item, dict):
                            continue
                        content = item.get("content")
                        if not isinstance(content, list):
                            continue
                        for part in content:
                            if (
                                isinstance(part, dict)
                                and part.get("type") == "output_text"
                            ):
                                text = part.get("text")
                                if isinstance(text, str) and text.strip():
                                    parts.append(text.strip())
                    output_text = "\n".join(parts)
        elif channel.protocol == ProtocolKind.OPENAI_EMBEDDING:
            data = raw_payload.get("data")
            if isinstance(data, list):
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    vector = item.get("embedding")
                    if isinstance(vector, list):
                        output_text = f"<vector dim={len(vector)}>"
                        break
                    if isinstance(vector, str) and vector:
                        output_text = f"<vector base64 len={len(vector)}>"
                        break
        elif channel.protocol == ProtocolKind.ANTHROPIC:
            content = raw_payload.get("content")
            if isinstance(content, list):
                parts = [
                    str(item.get("text")).strip()
                    for item in content
                    if isinstance(item, dict)
                    and item.get("type") == "text"
                    and item.get("text")
                ]
                output_text = "\n".join(parts)
        elif channel.protocol == ProtocolKind.GEMINI:
            candidates = raw_payload.get("candidates")
            if isinstance(candidates, list):
                for candidate in candidates:
                    if not isinstance(candidate, dict):
                        continue
                    content = candidate.get("content")
                    if not isinstance(content, dict):
                        continue
                    parts_list = content.get("parts")
                    if not isinstance(parts_list, list):
                        continue
                    parts = [
                        str(part.get("text")).strip()
                        for part in parts_list
                        if isinstance(part, dict) and part.get("text")
                    ]
                    if parts:
                        output_text = "\n".join(parts)
                        break
        return SiteModelTestResult(
            success=True,
            status_code=response.status_code,
            latency_ms=latency_ms,
            model_name=model_name,
            credential_id=credential_id,
            output_text=output_text,
        )
    except httpx.HTTPError as exc:
        return SiteModelTestResult(
            success=False,
            status_code=502,
            latency_ms=_elapsed_ms(started_at),
            model_name=model_name,
            credential_id=credential_id,
            error_message=_format_transport_error(exc, upstream.url),
        )
    except ValueError as exc:
        return SiteModelTestResult(
            success=False,
            status_code=502,
            latency_ms=_elapsed_ms(started_at),
            model_name=model_name,
            credential_id=credential_id,
            error_message=f"Invalid upstream response: {exc}",
        )
    finally:
        if close_client:
            await client.aclose()


def _stringify_text_content(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
                continue
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(parts)
    return ""


def _passthrough_headers(headers: httpx.Headers) -> dict[str, str]:
    allowed = {}
    for key in (
        "content-type",
        "cache-control",
        "x-request-id",
        "anthropic-request-id",
        "x-goog-request-id",
    ):
        if key in headers:
            allowed[key] = headers[key]
    return allowed


def _format_channel_error(detail: Any) -> str:
    detail_text = str(detail).strip() if detail is not None else ""
    if not detail_text:
        detail_text = "Unknown error"
    return detail_text


def _format_transport_error(exc: httpx.HTTPError, fallback_url: str) -> str:
    error_type = exc.__class__.__name__
    request = exc.request if hasattr(exc, "request") else None
    target_url = (
        str(request.url) if request and hasattr(request, "url") else fallback_url
    )
    try:
        target_label = str(httpx.URL(target_url).copy_with(query=None))
    except httpx.InvalidURL:
        target_label = target_url
    detail_text = str(exc).strip()
    if detail_text:
        return f"Transport error ({error_type}) while requesting {target_label}: {detail_text}"
    return f"Transport error ({error_type}) while requesting {target_label}"


def _default_lens_user_agent() -> str:
    return f"Lens/{_read_system_version()}"


def _normalize_user_agent(value: str | None) -> str:
    normalized = (value or "").strip()
    if not normalized:
        return ""
    return "".join(char for char in normalized if ord(char) >= 32 and ord(char) != 127)[
        :300
    ].strip()


def _is_generic_user_agent(value: str) -> bool:
    normalized = value.strip().lower()
    if not normalized:
        return True
    return any(token in normalized for token in GENERIC_USER_AGENT_TOKENS)


def _forward_anthropic_headers(headers: Mapping[str, str]) -> dict[str, str]:
    forwarded: dict[str, str] = {}
    for name, value in headers.items():
        normalized_name = name.lower()
        if normalized_name not in ANTHROPIC_FORWARD_HEADERS and not (
            normalized_name.startswith(ANTHROPIC_FORWARD_HEADER_PREFIXES)
        ):
            continue
        normalized_value = value.strip()
        if normalized_value:
            forwarded[normalized_name] = normalized_value
    return forwarded


async def _fetch_upstream_models(channel: ChannelConfig) -> list[str]:
    runtime = await app_state.domain_store.get_runtime_settings()
    proxy_url = resolve_upstream_proxy_url(channel, runtime["proxy_url"])
    client, close_client = _resolve_http_client(proxy_url)

    try:
        response = await client.request(**_model_list_request(channel))
        response.raise_for_status()
        return _parse_model_list(channel.protocol, response.json(), channel.match_regex)
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text or f"HTTP {exc.response.status_code}"
        raise HTTPException(
            status_code=exc.response.status_code, detail=detail
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Transport error: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        if close_client:
            await client.aclose()


def _model_list_request(channel: ChannelConfig) -> dict[str, Any]:
    api_key = resolve_channel_api_key(channel)
    headers = dict(channel.headers)

    if channel.protocol in {
        ProtocolKind.OPENAI_CHAT,
        ProtocolKind.OPENAI_RESPONSES,
        ProtocolKind.OPENAI_EMBEDDING,
    }:
        return {
            "method": "GET",
            "url": resolve_channel_model_list_url(channel),
            "headers": build_upstream_headers(
                {"authorization": f"Bearer {api_key}"},
                headers,
                user_agent=_default_lens_user_agent(),
            ),
        }

    if channel.protocol == ProtocolKind.ANTHROPIC:
        return {
            "method": "GET",
            "url": append_channel_url_path(channel, "v1", "models"),
            "headers": build_upstream_headers(
                {
                    "x-api-key": api_key,
                    "anthropic-version": settings.anthropic_version,
                },
                headers,
                user_agent=_default_lens_user_agent(),
            ),
        }

    if channel.protocol == ProtocolKind.GEMINI:
        return {
            "method": "GET",
            "url": append_channel_url_path(
                channel,
                "v1beta",
                "models",
                query_params={"key": api_key},
            ),
            "headers": build_upstream_headers(
                {},
                headers,
                user_agent=_default_lens_user_agent(),
            ),
        }

    raise ValueError(f"Unsupported protocol={channel.protocol.value}")


def _parse_model_list(
    protocol: ProtocolKind, payload: dict[str, Any], match_regex: str
) -> list[str]:
    names: list[str] = []
    if "data" in payload:
        items = payload["data"]
    elif "models" in payload:
        items = payload["models"]
    else:
        raise ValueError("Model list response missing data/models")
    if not isinstance(items, list):
        raise ValueError("Model list response data/models must be a list")
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Model list item must be an object")
        if protocol == ProtocolKind.GEMINI:
            value = str(item.get("name") or "")
            if value.startswith("models/"):
                value = value[7:]
        else:
            value = str(item.get("id") or item.get("name") or "")
        value = value.strip()
        if not value:
            raise ValueError("Model list item missing model name")
        names.append(value)

    unique_names = list(dict.fromkeys(names))
    if not match_regex.strip():
        return unique_names

    pattern = re.compile(match_regex)
    return [name for name in unique_names if pattern.search(name)]


async def _resolve_routing_plan(
    protocol: ProtocolKind, requested_model: str
) -> RoutingPlan:
    matched_group = await app_state.domain_store.find_group_by_name(
        protocol.value, requested_model
    )
    if matched_group is not None:
        resolved_group = matched_group
        if matched_group.route_group_id.strip():
            try:
                resolved_group = await app_state.domain_store.get_group(
                    matched_group.route_group_id
                )
            except KeyError as exc:
                raise LookupError(
                    f"Route target model group not found: {matched_group.route_group_id}"
                ) from exc
            if resolved_group.route_group_id.strip():
                raise LookupError(
                    f"Route target must be an execution group: {resolved_group.name}"
                )
        channels = await app_state.store.list()
        channel_map = {channel.id: channel for channel in channels}
        route_targets = [
            RouteTarget(
                channel=channel_map[item.channel_id],
                model_name=item.model_name,
                credential_id=item.credential_id,
                credential_name=item.credential_name or None,
            )
            for item in resolved_group.items
            if item.enabled and item.channel_id in channel_map
        ]
        return RoutingPlan(
            requested_group_name=matched_group.name,
            resolved_group_name=resolved_group.name,
            requested_group=matched_group,
            resolved_group=resolved_group,
            strategy=resolved_group.strategy,
            route_targets=route_targets,
            use_model_matching=False,
            cursor_key=f"{protocol.value}:{resolved_group.id}",
        )

    raise LookupError(f"No model group matched {requested_model}")


def _prepare_upstream_body(
    protocol: ProtocolKind, body: dict[str, Any], target_model_name: str | None
) -> dict[str, Any]:
    payload = deepcopy(body)
    if protocol == ProtocolKind.OPENAI_RESPONSES and "input" in payload:
        payload["input"] = _normalize_openai_responses_input(payload.get("input"))
    if not target_model_name:
        return payload
    payload["model"] = target_model_name
    return payload


def _apply_param_override(
    channel: ChannelConfig, body: dict[str, Any]
) -> dict[str, Any]:
    raw_override = channel.param_override.strip()
    if not raw_override:
        return body

    try:
        override = json.loads(raw_override)
    except json.JSONDecodeError as exc:
        raise UpstreamRequestError(
            status_code=400,
            detail=(
                f"Invalid param override JSON for channel {channel.name}: "
                f"{exc.msg} at line {exc.lineno} column {exc.colno}"
            ),
            router_status_code=None,
        ) from exc

    if not isinstance(override, dict):
        raise UpstreamRequestError(
            status_code=400,
            detail=(
                f"Invalid param override for channel {channel.name}: "
                "expected a JSON object"
            ),
            router_status_code=None,
        )
    if "model" in override:
        raise UpstreamRequestError(
            status_code=400,
            detail=(
                f"Invalid param override for channel {channel.name}: "
                "model cannot be overridden"
            ),
            router_status_code=None,
        )

    return _deep_merge_json_objects(body, override)


def _deep_merge_json_objects(
    base: dict[str, Any], override: dict[str, Any]
) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, override_value in override.items():
        base_value = merged.get(key)
        if isinstance(base_value, dict) and isinstance(override_value, dict):
            merged[key] = _deep_merge_json_objects(base_value, override_value)
        else:
            merged[key] = deepcopy(override_value)
    return merged


def _normalize_openai_responses_input(value: Any) -> Any:
    if isinstance(value, str):
        text = value.strip()
        return [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": text}],
            }
        ]

    if isinstance(value, list):
        normalized_items: list[Any] = []
        for item in value:
            if isinstance(item, str):
                text = item.strip()
                normalized_items.append(
                    {
                        "role": "user",
                        "content": [{"type": "input_text", "text": text}],
                    }
                )
                continue

            if isinstance(item, dict) and isinstance(item.get("content"), str):
                normalized = dict(item)
                normalized["content"] = [
                    {"type": "input_text", "text": item["content"]}
                ]
                normalized_items.append(normalized)
                continue

            normalized_items.append(item)
        return normalized_items

    return value


def _elapsed_ms(started_at: float) -> int:
    return max(int((perf_counter() - started_at) * 1000), 0)


async def _record_stream_request_log(
    *,
    request_log_id: int,
    protocol: ProtocolKind,
    requested_group_name: str | None,
    resolved_group_name: str | None,
    channel: ChannelConfig,
    gateway_key: GatewayApiKey,
    user_agent: str,
    started_at: float,
    upstream_body: dict[str, Any],
    result: UpstreamResult,
    attempts: list[dict[str, Any]],
) -> None:
    capture = result.stream_capture
    if capture is not None and capture.drain_task is not None:
        await capture.drain_task
    raw_content = (
        _join_stream_chunks(capture.response_content_chunks)
        if capture is not None
        else result.response_content
    )
    response_protocol = channel.protocol
    response_raw_content = raw_content
    client_response_content = (
        _join_stream_chunks(capture.client_response_content_chunks)
        if capture is not None
        else None
    )
    if (
        capture is not None
        and needs_conversion(protocol, channel.protocol)
        and client_response_content
    ):
        response_protocol = protocol
        response_raw_content = client_response_content
    parse_errors = capture.parse_errors if capture is not None else None
    try:
        parsed = _extract_stream_usage(
            channel.protocol, raw_content, parse_errors=parse_errors
        )
    except ValueError as exc:
        if capture is not None:
            capture.parse_errors.append(str(exc))
        parsed = dict(_EMPTY_USAGE)
    try:
        distilled_content = _distill_stream_response_content(
            response_protocol, response_raw_content
        )
    except ValueError as exc:
        if capture is not None:
            capture.parse_errors.append(str(exc))
        distilled_content = response_raw_content
    capture_issue = _describe_stream_capture_issue(
        channel.protocol, capture, raw_content
    )
    upstream_model_name = parsed["resolved_model"] or result.upstream_model_name
    input_tokens = parsed["input_tokens"]
    cache_read_input_tokens = parsed["cache_read_input_tokens"]
    cache_write_input_tokens = parsed["cache_write_input_tokens"]
    output_tokens = parsed["output_tokens"]
    total_tokens = parsed["total_tokens"]
    input_cost_usd, output_cost_usd, total_cost_usd = (
        await app_state.domain_store.estimate_model_cost(
            resolved_group_name,
            input_tokens,
            output_tokens,
            cache_read_input_tokens,
            cache_write_input_tokens,
        )
    )
    await _update_request_log(
        request_log_id,
        protocol=protocol,
        requested_group_name=requested_group_name,
        resolved_group_name=resolved_group_name,
        upstream_model_name=upstream_model_name,
        channel_id=channel.id,
        channel_name=channel.name,
        gateway_key=gateway_key,
        user_agent=user_agent,
        lifecycle_status=(
            RequestLogLifecycleStatus.FAILED
            if capture_issue is not None
            else RequestLogLifecycleStatus.SUCCEEDED
        ),
        status_code=result.status_code,
        success=capture_issue is None,
        is_stream=True,
        first_token_latency_ms=(
            capture.first_token_latency_ms
            if capture is not None
            else result.first_token_latency_ms
        ),
        latency_ms=_elapsed_ms(started_at),
        input_tokens=input_tokens,
        cache_read_input_tokens=cache_read_input_tokens,
        cache_write_input_tokens=cache_write_input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        input_cost_usd=input_cost_usd,
        output_cost_usd=output_cost_usd,
        total_cost_usd=total_cost_usd,
        request_content=result.request_content or _dump_json(upstream_body),
        response_content=distilled_content,
        attempts=attempts,
        error_message=capture_issue,
    )


async def _update_request_log(
    request_log_id: int,
    *,
    protocol: ProtocolKind,
    requested_group_name: str | None,
    resolved_group_name: str | None,
    upstream_model_name: str | None,
    channel_id: str | None,
    channel_name: str | None,
    gateway_key: GatewayApiKey,
    user_agent: str,
    lifecycle_status: RequestLogLifecycleStatus,
    status_code: int | None,
    success: bool,
    is_stream: bool,
    first_token_latency_ms: int,
    latency_ms: int,
    input_tokens: int = 0,
    cache_read_input_tokens: int = 0,
    cache_write_input_tokens: int = 0,
    output_tokens: int = 0,
    total_tokens: int = 0,
    input_cost_usd: float = 0.0,
    output_cost_usd: float = 0.0,
    total_cost_usd: float = 0.0,
    request_content: str | None = None,
    response_content: str | None = None,
    attempts: list[dict[str, Any]] | None = None,
    error_message: str | None,
) -> None:
    await app_state.domain_store.update_request_log(
        request_log_id,
        protocol=protocol.value,
        requested_group_name=requested_group_name,
        resolved_group_name=resolved_group_name,
        upstream_model_name=upstream_model_name,
        channel_id=channel_id,
        channel_name=channel_name,
        gateway_key_id=gateway_key.id,
        user_agent=user_agent,
        status_code=status_code,
        success=success,
        lifecycle_status=lifecycle_status,
        is_stream=is_stream,
        first_token_latency_ms=first_token_latency_ms,
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        cache_read_input_tokens=cache_read_input_tokens,
        cache_write_input_tokens=cache_write_input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        input_cost_usd=input_cost_usd,
        output_cost_usd=output_cost_usd,
        total_cost_usd=total_cost_usd,
        request_content=request_content,
        response_content=response_content,
        attempts=attempts,
        error_message=error_message,
    )


def _dump_json(value: Any) -> str | None:
    try:
        return json.dumps(value, ensure_ascii=True, separators=(",", ":"))
    except (TypeError, ValueError):
        return None


def _decode_content_bytes(content: bytes | None) -> str | None:
    if not content:
        return None
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("utf-8", errors="replace")


async def _pump_stream_response(
    *,
    response: httpx.Response,
    protocol: ProtocolKind,
    capture: StreamCapture,
    chunk_queue: asyncio.Queue[bytes | None],
    stream_started_at: float,
) -> None:
    try:
        async for chunk in response.aiter_bytes():
            if not chunk:
                continue
            if not capture.saw_first_chunk:
                capture.saw_first_chunk = True
                capture.first_token_latency_ms = _elapsed_ms(stream_started_at)
                if capture.request_log_id is not None:
                    capture.last_persisted_first_token_latency_ms = (
                        capture.first_token_latency_ms
                    )
                    await app_state.domain_store.update_request_log_runtime(
                        capture.request_log_id,
                        first_token_latency_ms=capture.first_token_latency_ms,
                        latency_ms=_elapsed_ms(
                            capture.stream_started_at or stream_started_at
                        ),
                    )
            text = chunk.decode("utf-8", errors="replace")
            if text:
                capture.response_content_chunks.append(text)
            if not capture.client_disconnected:
                chunk_queue.put_nowait(chunk)
        capture.completed = True
    except asyncio.CancelledError:
        capture.errors.append("stream pump cancelled")
    except httpx.HTTPError as exc:
        capture.errors.append(f"stream pump failed: {type(exc).__name__}: {exc}")
    finally:
        if not capture.client_disconnected:
            chunk_queue.put_nowait(None)
        await response.aclose()


async def _consume_stream_queue(
    chunk_queue: asyncio.Queue[bytes | None], capture: StreamCapture
) -> AsyncIterator[bytes]:
    try:
        while True:
            chunk = await chunk_queue.get()
            if chunk is None:
                break
            yield chunk
    except asyncio.CancelledError:
        capture.client_disconnected = True
        raise


async def _capture_converted_stream_iterator(
    raw_iterator: AsyncIterator[bytes], capture: StreamCapture
) -> AsyncIterator[bytes]:
    try:
        async for chunk in raw_iterator:
            text = chunk.decode("utf-8", errors="replace")
            if text:
                capture.client_response_content_chunks.append(text)
            yield chunk
    except ValueError as exc:
        capture.errors.append(str(exc))


def _join_stream_chunks(chunks: list[str]) -> str | None:
    return "".join(chunks) if chunks else None


def _distill_stream_response_content(
    protocol: ProtocolKind, raw_content: str | None
) -> str | None:
    if not raw_content:
        return None

    if protocol == ProtocolKind.OPENAI_RESPONSES:
        payloads = _parse_sse_payloads(raw_content)
        for payload in reversed(payloads):
            if payload.get("type") != "response.completed":
                continue
            response_payload = payload.get("response")
            if isinstance(response_payload, dict):
                compact_payload = _compact_openai_response_payload(
                    _restore_openai_response_output(response_payload, payloads)
                )
                return _dump_json(compact_payload) or raw_content
    if protocol == ProtocolKind.ANTHROPIC:
        restored_message = _restore_anthropic_stream_message(
            _parse_sse_payloads(raw_content)
        )
        if restored_message is not None:
            return _dump_json(restored_message) or raw_content

    return raw_content


def _restore_anthropic_stream_message(
    payloads: list[dict[str, Any]],
) -> dict[str, Any] | None:
    message: dict[str, Any] | None = None
    input_buffers: dict[int, str] = {}

    for payload in payloads:
        payload_type = str(payload.get("type") or "")

        if payload_type == "message_start":
            start_message = payload.get("message")
            if not isinstance(start_message, dict):
                continue
            message = deepcopy(start_message)
            content = message.get("content")
            message["content"] = deepcopy(content) if isinstance(content, list) else []
            continue

        if message is None:
            continue

        if payload_type == "content_block_start":
            index = _coerce_openai_output_index(payload.get("index"))
            block = payload.get("content_block")
            if index is None or not isinstance(block, dict):
                continue
            content = message.setdefault("content", [])
            if not isinstance(content, list):
                content = []
                message["content"] = content
            while len(content) <= index:
                content.append(None)
            content[index] = deepcopy(block)
            continue

        if payload_type == "content_block_delta":
            index = _coerce_openai_output_index(payload.get("index"))
            delta = payload.get("delta")
            if index is None or not isinstance(delta, dict):
                continue
            content = message.get("content")
            if not isinstance(content, list) or index >= len(content):
                continue
            block = content[index]
            if not isinstance(block, dict):
                continue
            delta_type = str(delta.get("type") or "")
            if delta_type == "text_delta":
                block["text"] = f"{block.get('text') or ''}{delta.get('text') or ''}"
            elif delta_type == "input_json_delta":
                input_buffers[index] = (
                    f"{input_buffers.get(index, '')}{delta.get('partial_json') or ''}"
                )
            elif delta_type == "thinking_delta":
                block["thinking"] = (
                    f"{block.get('thinking') or ''}{delta.get('thinking') or ''}"
                )
            elif delta_type == "signature_delta":
                block["signature"] = delta.get("signature") or block.get(
                    "signature", ""
                )
            continue

        if payload_type == "content_block_stop":
            index = _coerce_openai_output_index(payload.get("index"))
            if index is None:
                continue
            _finalize_anthropic_tool_use_input(message, index, input_buffers)
            continue

        if payload_type == "message_delta":
            delta = payload.get("delta")
            if isinstance(delta, dict):
                for key, value in delta.items():
                    message[key] = value
            usage = payload.get("usage")
            if isinstance(usage, dict):
                merged_usage = dict(message.get("usage") or {})
                merged_usage.update(usage)
                message["usage"] = merged_usage

    for index in list(input_buffers):
        _finalize_anthropic_tool_use_input(message, index, input_buffers)

    if message is None:
        return None

    content = message.get("content")
    if isinstance(content, list):
        message["content"] = [item for item in content if item is not None]
    return message


def _finalize_anthropic_tool_use_input(
    message: dict[str, Any] | None,
    index: int,
    input_buffers: dict[int, str],
) -> None:
    if message is None:
        return
    content = message.get("content")
    if not isinstance(content, list) or index >= len(content):
        input_buffers.pop(index, None)
        return
    block = content[index]
    if not isinstance(block, dict) or block.get("type") != "tool_use":
        input_buffers.pop(index, None)
        return

    buffer = input_buffers.pop(index, "")
    if not buffer:
        current_input = block.get("input")
        if isinstance(current_input, dict):
            return
        raise ValueError("Invalid Anthropic tool input")

    try:
        parsed_input = json.loads(buffer)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid Anthropic tool input JSON") from exc
    if not isinstance(parsed_input, dict):
        raise ValueError("Invalid Anthropic tool input")
    block["input"] = parsed_input


def _compact_openai_response_payload(payload: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key in (
        "id",
        "object",
        "model",
        "status",
        "created_at",
        "completed_at",
        "error",
        "incomplete_details",
        "output",
        "usage",
    ):
        value = payload.get(key)
        if value is not None:
            compact[key] = value
    return compact


def _restore_openai_response_output(
    response_payload: dict[str, Any],
    payloads: list[dict[str, Any]],
) -> dict[str, Any]:
    existing_output = response_payload.get("output")
    if isinstance(existing_output, list) and existing_output:
        return response_payload

    rebuilt_output = _rebuild_openai_response_output(payloads)
    if not rebuilt_output:
        return response_payload

    restored_payload = dict(response_payload)
    restored_payload["output"] = rebuilt_output
    return restored_payload


def _rebuild_openai_response_output(
    payloads: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    items_by_index: dict[int, dict[str, Any]] = {}
    for payload in payloads:
        payload_type = str(payload.get("type") or "")
        if payload_type in {"response.output_item.added", "response.output_item.done"}:
            output_index = _coerce_openai_output_index(payload.get("output_index"))
            item = payload.get("item")
            if output_index is None or not isinstance(item, dict):
                continue
            items_by_index[output_index] = _merge_openai_output_item(
                items_by_index.get(output_index), item
            )
            continue

        if payload_type in {
            "response.content_part.added",
            "response.content_part.done",
        }:
            output_index = _coerce_openai_output_index(payload.get("output_index"))
            content_index = _coerce_openai_output_index(payload.get("content_index"))
            part = payload.get("part")
            if (
                output_index is None
                or content_index is None
                or not isinstance(part, dict)
            ):
                continue
            item = _ensure_openai_output_message(
                items_by_index, output_index, payload.get("item_id")
            )
            _upsert_openai_content_part(item, content_index, part)
            continue

        if payload_type == "response.output_text.delta":
            delta = payload.get("delta")
            if not isinstance(delta, str) or not delta:
                continue
            output_index = _coerce_openai_output_index(
                payload.get("output_index"), default=0
            )
            content_index = _coerce_openai_output_index(
                payload.get("content_index"), default=0
            )
            item = _ensure_openai_output_message(
                items_by_index, output_index, payload.get("item_id")
            )
            _append_openai_output_text(item, content_index, delta)
            continue

        if payload_type == "response.output_text.done":
            text = payload.get("text")
            if not isinstance(text, str):
                continue
            output_index = _coerce_openai_output_index(
                payload.get("output_index"), default=0
            )
            content_index = _coerce_openai_output_index(
                payload.get("content_index"), default=0
            )
            item = _ensure_openai_output_message(
                items_by_index, output_index, payload.get("item_id")
            )
            _set_openai_output_text(item, content_index, text)

    return [items_by_index[index] for index in sorted(items_by_index)]


def _merge_openai_output_item(
    existing: dict[str, Any] | None, incoming: dict[str, Any]
) -> dict[str, Any]:
    merged = deepcopy(existing) if existing is not None else {}
    for key, value in incoming.items():
        if key == "content" and isinstance(value, list):
            merged[key] = deepcopy(value)
            continue
        merged[key] = value
    if merged.get("type") == "message" and not isinstance(merged.get("content"), list):
        merged["content"] = []
    return merged


def _ensure_openai_output_message(
    items_by_index: dict[int, dict[str, Any]],
    output_index: int,
    item_id: Any,
) -> dict[str, Any]:
    item = items_by_index.get(output_index)
    if item is None:
        item = {"type": "message", "role": "assistant", "content": []}
        items_by_index[output_index] = item
    if item_id and item.get("id") is None:
        item["id"] = str(item_id)
    if item.get("type") == "message" and not isinstance(item.get("content"), list):
        item["content"] = []
    return item


def _upsert_openai_content_part(
    item: dict[str, Any], content_index: int, part: dict[str, Any]
) -> None:
    content = item.setdefault("content", [])
    if not isinstance(content, list):
        content = []
        item["content"] = content
    while len(content) <= content_index:
        content.append(None)
    content[content_index] = deepcopy(part)


def _append_openai_output_text(
    item: dict[str, Any], content_index: int, delta: str
) -> None:
    content = item.setdefault("content", [])
    if not isinstance(content, list):
        content = []
        item["content"] = content
    while len(content) <= content_index:
        content.append(None)
    part = content[content_index]
    if not isinstance(part, dict):
        part = {"type": "output_text", "text": "", "annotations": []}
        content[content_index] = part
    elif part.get("type") != "output_text":
        return
    part["text"] = f"{part.get('text') or ''}{delta}"
    part.setdefault("annotations", [])


def _set_openai_output_text(
    item: dict[str, Any], content_index: int, text: str
) -> None:
    content = item.setdefault("content", [])
    if not isinstance(content, list):
        content = []
        item["content"] = content
    while len(content) <= content_index:
        content.append(None)
    part = content[content_index]
    if not isinstance(part, dict):
        part = {"type": "output_text", "annotations": []}
        content[content_index] = part
    if part.get("type") != "output_text":
        return
    part["text"] = text
    part.setdefault("annotations", [])


def _coerce_openai_output_index(value: Any, default: int | None = None) -> int | None:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _usage_mapping(value: Any, key: str = "usage") -> Mapping[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"Invalid usage object: {key}")
    return value


def _usage_int(mapping: Mapping[str, Any], key: str) -> int:
    value = mapping.get(key)
    if value is None:
        return 0
    if isinstance(value, bool):
        raise ValueError(f"Invalid usage value: {key}")
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid usage value: {key}") from None
    if parsed < 0:
        raise ValueError(f"Invalid negative usage value: {key}")
    return parsed


def _openai_cached_tokens(usage: Mapping[str, Any], detail_key: str) -> int:
    details = usage.get(detail_key)
    if details is None:
        return 0
    if not isinstance(details, Mapping):
        raise ValueError(f"Invalid usage object: {detail_key}")
    return _usage_int(details, "cached_tokens")


def _anthropic_usage(
    usage: Mapping[str, Any], *, model: str | None
) -> dict[str, int | str | None]:
    base_input_tokens = _usage_int(usage, "input_tokens")
    cache_read_input_tokens = _usage_int(usage, "cache_read_input_tokens")
    cache_write_input_tokens = _usage_int(usage, "cache_creation_input_tokens")
    input_tokens = (
        base_input_tokens + cache_read_input_tokens + cache_write_input_tokens
    )
    output_tokens = _usage_int(usage, "output_tokens")
    return {
        "resolved_model": model,
        "input_tokens": input_tokens,
        "cache_read_input_tokens": cache_read_input_tokens,
        "cache_write_input_tokens": cache_write_input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }


def _gemini_usage(payload: Mapping[str, Any]) -> dict[str, int | str | None]:
    usage = _usage_mapping(payload.get("usageMetadata"), "usageMetadata")
    input_tokens = _usage_int(usage, "promptTokenCount")
    cache_read_input_tokens = _usage_int(usage, "cachedContentTokenCount")
    output_tokens = _usage_int(usage, "candidatesTokenCount")
    total_tokens = _usage_int(usage, "totalTokenCount") or (
        input_tokens + output_tokens
    )
    return {
        "resolved_model": payload.get("modelVersion") or payload.get("model"),
        "input_tokens": input_tokens,
        "cache_read_input_tokens": min(cache_read_input_tokens, input_tokens),
        "cache_write_input_tokens": 0,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def _openai_chat_usage(payload: Mapping[str, Any]) -> dict[str, int | str | None]:
    usage = _usage_mapping(payload.get("usage"))
    cache_read_input_tokens = _openai_cached_tokens(usage, "prompt_tokens_details")
    input_tokens = _usage_int(usage, "prompt_tokens")
    return {
        "resolved_model": payload.get("model"),
        "input_tokens": input_tokens,
        "cache_read_input_tokens": min(cache_read_input_tokens, input_tokens),
        "cache_write_input_tokens": 0,
        "output_tokens": _usage_int(usage, "completion_tokens"),
        "total_tokens": _usage_int(usage, "total_tokens"),
    }


def _openai_responses_usage(
    payload: Mapping[str, Any], *, model: str | None
) -> dict[str, int | str | None]:
    usage = _usage_mapping(payload.get("usage"))
    cache_read_input_tokens = _openai_cached_tokens(usage, "input_tokens_details")
    input_tokens = _usage_int(usage, "input_tokens")
    return {
        "resolved_model": model,
        "input_tokens": input_tokens,
        "cache_read_input_tokens": min(cache_read_input_tokens, input_tokens),
        "cache_write_input_tokens": 0,
        "output_tokens": _usage_int(usage, "output_tokens"),
        "total_tokens": _usage_int(usage, "total_tokens"),
    }


def _openai_embedding_usage(payload: Mapping[str, Any]) -> dict[str, int | str | None]:
    usage = _usage_mapping(payload.get("usage"))
    return {
        "resolved_model": payload.get("model"),
        "input_tokens": _usage_int(usage, "prompt_tokens"),
        "cache_read_input_tokens": 0,
        "cache_write_input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": _usage_int(usage, "total_tokens"),
    }


_EMPTY_USAGE: dict[str, int | str | None] = {
    "resolved_model": None,
    "input_tokens": 0,
    "cache_read_input_tokens": 0,
    "cache_write_input_tokens": 0,
    "output_tokens": 0,
    "total_tokens": 0,
}


def _extract_stream_usage(
    protocol: ProtocolKind,
    raw_content: str | None,
    parse_errors: list[str] | None = None,
) -> dict[str, int | str | None]:
    if protocol == ProtocolKind.OPENAI_EMBEDDING or not raw_content:
        return dict(_EMPTY_USAGE)

    if protocol == ProtocolKind.GEMINI:
        payloads = _parse_sse_payloads(
            raw_content, errors=parse_errors
        ) or _parse_ndjson_payloads(raw_content, errors=parse_errors)
        return _extract_usage_from_payload(protocol, payloads[-1] if payloads else {})

    payloads = _parse_sse_payloads(raw_content, errors=parse_errors)
    merged: dict[str, int | str | None] = dict(_EMPTY_USAGE)
    int_keys = (
        "input_tokens",
        "cache_read_input_tokens",
        "cache_write_input_tokens",
        "output_tokens",
        "total_tokens",
    )
    for payload in payloads:
        parsed = _extract_usage_from_payload(protocol, payload)
        if parsed["resolved_model"]:
            merged["resolved_model"] = parsed["resolved_model"]
        for key in int_keys:
            value = parsed[key]
            assert isinstance(value, int)
            if value:
                merged[key] = max(merged[key], value)
    if not merged["total_tokens"]:
        merged["total_tokens"] = merged["input_tokens"] + merged["output_tokens"]
    return merged


def _parse_sse_payloads(
    raw_content: str, *, errors: list[str] | None = None
) -> list[dict[str, Any]]:
    normalized = _normalize_event_stream_newlines(raw_content)
    payloads: list[dict[str, Any]] = []
    for block in normalized.split("\n\n"):
        data_lines = [
            line[5:].strip() for line in block.splitlines() if line.startswith("data:")
        ]
        if not data_lines:
            continue
        joined = "\n".join(line for line in data_lines if line and line != "[DONE]")
        if not joined:
            continue
        try:
            payload = json.loads(joined)
        except json.JSONDecodeError as exc:
            if errors is not None:
                errors.append(f"invalid SSE JSON: {exc.msg}")
            continue
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


def _parse_ndjson_payloads(
    raw_content: str, *, errors: list[str] | None = None
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for line in _normalize_event_stream_newlines(raw_content).splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            if errors is not None:
                errors.append(f"invalid NDJSON: {exc.msg}")
            continue
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


def _normalize_event_stream_newlines(raw_content: str) -> str:
    return raw_content.replace("\r\n", "\n").replace("\r", "\n")


def _describe_stream_capture_issue(
    protocol: ProtocolKind,
    capture: StreamCapture | None,
    raw_content: str | None,
) -> str | None:
    issues: list[str] = []
    if capture is not None:
        issues.extend(error for error in capture.errors if error)
        issues.extend(error for error in capture.parse_errors if error)

    if not raw_content:
        issues.append("no stream content captured")
    elif protocol == ProtocolKind.OPENAI_RESPONSES:
        payloads = _parse_sse_payloads(raw_content)
        has_completed = any(
            payload.get("type") == "response.completed" for payload in payloads
        )
        if not has_completed:
            issues.append("stream ended before response.completed")

    if capture is not None and not capture.completed:
        issues.append("stream did not drain to completion")

    if not issues:
        return None

    return "; ".join(dict.fromkeys(issues))


def _extract_usage_from_payload(
    protocol: ProtocolKind, payload: dict[str, Any]
) -> dict[str, int | str | None]:
    if protocol == ProtocolKind.OPENAI_CHAT:
        return _openai_chat_usage(payload)
    if protocol == ProtocolKind.OPENAI_RESPONSES:
        if payload.get("type") == "response.completed":
            response_payload = _usage_mapping(payload.get("response"))
            return _openai_responses_usage(
                response_payload,
                model=response_payload.get("model") or payload.get("model"),
            )
        return _openai_responses_usage(payload, model=payload.get("model"))
    if protocol == ProtocolKind.OPENAI_EMBEDDING:
        return _openai_embedding_usage(payload)
    if protocol == ProtocolKind.ANTHROPIC:
        if payload.get("type") == "message_start":
            message = _usage_mapping(payload.get("message"))
            return _anthropic_usage(
                _usage_mapping(message.get("usage")), model=message.get("model")
            )
        if payload.get("type") == "message_delta":
            return _anthropic_usage(_usage_mapping(payload.get("usage")), model=None)
        return _anthropic_usage(
            _usage_mapping(payload.get("usage")), model=payload.get("model")
        )
    return _gemini_usage(payload)


def _extract_response_usage(
    protocol: ProtocolKind, response: httpx.Response
) -> dict[str, int | str | None]:
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("Upstream response JSON must be an object")
    if protocol == ProtocolKind.OPENAI_CHAT:
        return _openai_chat_usage(payload)
    if protocol == ProtocolKind.OPENAI_RESPONSES:
        return _openai_responses_usage(payload, model=payload.get("model"))
    if protocol == ProtocolKind.OPENAI_EMBEDDING:
        return _openai_embedding_usage(payload)
    if protocol == ProtocolKind.ANTHROPIC:
        return _anthropic_usage(
            _usage_mapping(payload.get("usage")), model=payload.get("model")
        )
    return _gemini_usage(payload)


async def _sync_group_prices(state: AppState, overwrite_existing: bool = False) -> None:
    group_names = await state.domain_store.list_group_names(include_routed=True)
    if not group_names:
        await state.domain_store.replace_model_prices([])
        return

    response = await state.http.get("https://models.dev/api.json")
    response.raise_for_status()
    price_index = build_models_dev_price_index(response.json())
    payloads = build_group_price_payloads(group_names, price_index)
    await state.domain_store.sync_model_prices(
        payloads, overwrite_existing=overwrite_existing, allowed_keys=group_names
    )
    await state.domain_store.set_model_price_sync_time(datetime.now(UTC).isoformat())


app = create_app(service_module=__import__(__name__, fromlist=["*"]))

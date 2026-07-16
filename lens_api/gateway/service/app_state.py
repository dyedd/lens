from __future__ import annotations

import logging
from datetime import UTC, datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

import httpx
from packaging import version

from ...core.config import settings
from ...core.db import create_engine, create_session_factory
from ...core.time_zone import resolve_time_zone
from ...models import SettingItem
from ...persistence.repositories import AdminRepository
from ...persistence.backup_store import BackupStore
from ...persistence.channel_store import ChannelStore
from ...persistence.cronjob_store import CronjobSpec, CronjobStore
from ...persistence.repositories import (
    GatewayApiKeyRepository,
    GroupRepository,
    ModelPriceRepository,
    RequestLogStore,
    SettingsRepository,
)
from ...persistence.shared import (
    SETTING_LATEST_VERSION,
    SETTING_LATEST_VERSION_URL,
    SETTING_VERSION_CHECK_AT,
)
from ..cronjob_runner import CronjobRunner
from ..router import GatewayRouter

TASK_REQUEST_LOG_PRUNE = "request_log_prune"
TASK_MODEL_PRICE_SYNC = "model_price_sync"
TASK_REQUEST_LOG_STATS_PERSIST = "request_log_stats_persist"
TASK_VERSION_CHECK = "version_check"
TASK_CHANNEL_MODEL_SYNC = "channel_model_sync"

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


@lru_cache(maxsize=1)
def _read_system_version() -> str:
    from lens_api import __version__

    return __version__


class AppState:
    def __init__(self) -> None:
        self.http = self._create_http_client()
        self._proxy_http_clients: dict[str, httpx.AsyncClient] = {}
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
    def _create_http_client(proxy_url: str | None = None) -> httpx.AsyncClient:
        limits = httpx.Limits(
            max_connections=settings.max_connections,
            max_keepalive_connections=settings.max_keepalive_connections,
        )
        if proxy_url:
            return httpx.AsyncClient(
                proxy=proxy_url,
                timeout=None,
                limits=limits,
                trust_env=False,
            )
        return httpx.AsyncClient(timeout=None, limits=limits, trust_env=False)

    def get_http_client(self, proxy_url: str | None) -> httpx.AsyncClient:
        normalized_proxy_url = (proxy_url or "").strip()
        if not normalized_proxy_url:
            return self.http

        client = self._proxy_http_clients.get(normalized_proxy_url)
        if client is None or client.is_closed:
            client = self._create_http_client(normalized_proxy_url)
            self._proxy_http_clients[normalized_proxy_url] = client
        return client

    async def close_http_clients(self) -> None:
        clients = (self.http, *self._proxy_http_clients.values())
        self._proxy_http_clients.clear()
        for client in clients:
            if not client.is_closed:
                await client.aclose()

    async def _runtime_time_zone(self) -> ZoneInfo:
        runtime = await self.settings_repo.get_runtime_settings()
        return resolve_time_zone(str(runtime["time_zone"]))

    async def _sync_model_prices(self) -> None:
        from .model_price_tasks import _sync_group_prices

        await _sync_group_prices(self, overwrite_existing=True)

    async def _sync_channel_models(self) -> None:
        from .model_sync import sync_channel_models

        await sync_channel_models(self, dry_run=False)

    async def _check_version_update(self) -> None:
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
                        SettingItem(key=SETTING_LATEST_VERSION, value=latest_version),
                        SettingItem(key=SETTING_LATEST_VERSION_URL, value=release_url),
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


app_state = AppState()

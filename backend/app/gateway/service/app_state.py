from __future__ import annotations

import logging
from zoneinfo import ZoneInfo

import httpx

from ...core.config import settings
from ...core.db import create_engine, create_session_factory
from ...core.time_zone import load_time_zone
from ...models.plugins import PluginView
from ...persistence.backup_store import BackupStore
from ...persistence.channel_store import ChannelStore
from ...persistence.cronjob_store import CronjobStore
from ...persistence.repositories import (
    AdminRepository,
    GatewayApiKeyRepository,
    ModelGroupRepository,
    ModelPriceRepository,
    ModelSyncRunRepository,
    RequestLogRepository,
    SettingsRepository,
    SiteCredentialRateRepository,
)
from ...plugins import PluginRegistry
from ...plugins.builtin import BUILTIN_PLUGINS
from ..cronjob_runner import CronjobRunner
from ..router import GatewayRouter

logger = logging.getLogger(__name__)


class AppState:
    def __init__(self) -> None:
        self.http = self._create_http_client()
        self._proxy_http_clients: dict[str, httpx.AsyncClient] = {}
        self.engine = create_engine(settings.database_url)
        self.session_factory = create_session_factory(self.engine)
        self.admin_repo = AdminRepository(self.session_factory)
        self.settings_repo = SettingsRepository(self.session_factory)
        self.gateway_api_key_repo = GatewayApiKeyRepository(self.session_factory)
        self.group_repo = ModelGroupRepository(self.session_factory)
        self.model_price_repo = ModelPriceRepository(self.session_factory)
        self.model_sync_run_repo = ModelSyncRunRepository(self.session_factory)
        self.site_credential_rate_repo = SiteCredentialRateRepository(
            self.session_factory
        )
        self.request_log_store = RequestLogRepository(
            self.session_factory,
            settings_repo=self.settings_repo,
            gateway_key_repo=self.gateway_api_key_repo,
        )

        self.cronjob_store = CronjobStore(self.session_factory)
        self.channel_store = ChannelStore(self.session_factory)
        self.backup_store = BackupStore(self.session_factory)
        self.router = GatewayRouter()
        self.plugin_registry = PluginRegistry(
            BUILTIN_PLUGINS,
            state=self,
            logger=logger,
        )
        self.cronjob_runner = CronjobRunner(
            store=self.cronjob_store,
            specs=self.plugin_registry.cronjob_specs(),
            handlers=self.plugin_registry.cronjob_handlers(),
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
        proxy_cache_key = (proxy_url or "").strip()
        if not proxy_cache_key:
            return self.http

        client = self._proxy_http_clients.get(proxy_cache_key)
        if client is None or client.is_closed:
            client = self._create_http_client(proxy_cache_key)
            self._proxy_http_clients[proxy_cache_key] = client
        return client

    async def close_http_clients(self) -> None:
        clients = (self.http, *self._proxy_http_clients.values())
        self._proxy_http_clients.clear()
        for client in clients:
            if not client.is_closed:
                await client.aclose()

    async def load_plugins(self) -> None:
        """读取插件启停状态，并让计划任务跟随生效插件。"""
        await self.plugin_registry.load()
        self._apply_plugin_contributions()

    async def set_plugin_enabled(self, plugin_id: str, *, enabled: bool) -> PluginView:
        """启用或停用插件，并立即刷新它贡献的计划任务。"""
        view = await self.plugin_registry.set_enabled(plugin_id, enabled=enabled)
        self._apply_plugin_contributions()
        await self.cronjob_runner.ensure_cronjobs()
        return view

    def _apply_plugin_contributions(self) -> None:
        self.cronjob_runner.reconfigure(
            specs=self.plugin_registry.cronjob_specs(),
            handlers=self.plugin_registry.cronjob_handlers(),
        )

    async def _runtime_time_zone(self) -> ZoneInfo:
        runtime = await self.settings_repo.get_runtime_settings()
        return load_time_zone(str(runtime["time_zone"]))


app_state = AppState()

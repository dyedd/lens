from __future__ import annotations

from .shared import (
    Any,
    AsyncSession,
    SettingItem,
    async_sessionmaker,
    asyncio,
)
from .model_prices import DomainModelPricesMixin
from .groups import DomainGroupsMixin
from .gateway_keys import DomainGatewayKeysMixin
from .settings import DomainSettingsMixin
from .request_log_writes import DomainRequestLogWritesMixin
from .request_log_reads import DomainRequestLogReadsMixin
from .request_log_filters import DomainRequestLogFiltersMixin
from .request_log_channel_resolution import DomainRequestLogChannelResolutionMixin
from .overview import DomainOverviewMixin


class DomainStore(
    DomainModelPricesMixin,
    DomainGroupsMixin,
    DomainGatewayKeysMixin,
    DomainSettingsMixin,
    DomainRequestLogWritesMixin,
    DomainRequestLogReadsMixin,
    DomainRequestLogFiltersMixin,
    DomainRequestLogChannelResolutionMixin,
    DomainOverviewMixin,
):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._settings_cache: list[SettingItem] | None = None
        self._settings_cache_at = 0.0
        self._settings_cache_ttl_seconds = 2.0
        self._settings_cache_lock = asyncio.Lock()
        self._runtime_settings_cache: dict[str, Any] | None = None
        self._runtime_settings_cache_at = 0.0

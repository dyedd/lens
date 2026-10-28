from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
)

from .config import (
    load_cronjobs,
    load_gateway_api_keys,
    replace_cronjobs,
    replace_gateway_api_keys,
    replace_settings,
)
from .export_import import BackupExportImportMixin
from .groups import load_groups, replace_groups
from .logs import load_request_logs, replace_request_logs
from .prices_stats import (
    load_model_prices,
    load_stats,
    replace_model_prices,
    replace_stats,
)
from .sites import load_sites, replace_sites


class BackupStore(BackupExportImportMixin):
    load_sites = load_sites
    load_groups = load_groups
    load_model_prices = load_model_prices
    load_stats = load_stats
    load_gateway_api_keys = load_gateway_api_keys
    load_cronjobs = load_cronjobs
    load_request_logs = load_request_logs
    replace_sites = replace_sites
    replace_groups = replace_groups
    replace_model_prices = replace_model_prices
    replace_stats = replace_stats
    replace_settings = replace_settings
    replace_cronjobs = replace_cronjobs
    replace_gateway_api_keys = replace_gateway_api_keys
    replace_request_logs = replace_request_logs

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

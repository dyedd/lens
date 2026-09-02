from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.time_zone import load_time_zone

from .commands import RequestLogCommands
from .hydration import RequestLogHydrator
from .maintenance import RequestLogMaintenance
from .overview import RequestLogOverview
from .ports import GatewayKeyPort, SettingsPort
from .queries import RequestLogQueries
from .statistics import RequestLogStatistics


def runtime_time_zone(runtime: dict[str, Any]):
    return load_time_zone(str(runtime["time_zone"]))


class RequestLogRepository:
    """Compose the request-log collaborators behind one explicit interface."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings_repo: SettingsPort,
        gateway_key_repo: GatewayKeyPort,
    ) -> None:
        hydrator = RequestLogHydrator(gateway_key_repo)
        statistics = RequestLogStatistics(
            session_factory, settings_repo, runtime_time_zone
        )
        self.commands = RequestLogCommands(session_factory, gateway_key_repo)
        self.queries = RequestLogQueries(
            session_factory,
            settings_repo,
            gateway_key_repo,
            hydrator,
            runtime_time_zone,
        )
        self.maintenance = RequestLogMaintenance(
            session_factory, settings_repo, statistics, runtime_time_zone
        )
        self.overview = RequestLogOverview(
            session_factory, settings_repo, statistics, runtime_time_zone
        )
        self.statistics = statistics
        self.hydrator = hydrator
        self.gateway_key_repo = gateway_key_repo

    async def create_pending_request_log(self, **kwargs: Any):
        return await self.commands.create_pending_request_log(**kwargs)

    async def create_request_log(self, **kwargs: Any):
        return await self.commands.create_request_log(**kwargs)

    async def update_request_log(self, log_id: int, **kwargs: Any):
        return await self.commands.update_request_log(log_id, **kwargs)

    async def update_request_log_runtime(self, log_id: int, **kwargs: Any):
        return await self.commands.update_request_log_runtime(log_id, **kwargs)

    async def list_model_health(self, **kwargs: Any):
        return await self.queries.list_model_health(**kwargs)

    async def list_request_log_page(self, **kwargs: Any):
        return await self.queries.list_request_log_page(**kwargs)

    async def get_request_log(self, log_id: int):
        return await self.queries.get_request_log(log_id)

    async def get_overview_summary(self, days: int = 7):
        return await self.overview.get_overview_summary(days)

    async def list_overview_daily(self, days: int = 0):
        return await self.overview.list_overview_daily(days)

    async def get_model_analytics(self, **kwargs: Any):
        return await self.overview.get_model_analytics(**kwargs)

    async def clear_request_logs(self) -> None:
        await self.maintenance.clear_request_logs()

    async def prune_request_logs(self) -> None:
        await self.maintenance.prune_request_logs()

    async def fail_running_request_logs(self) -> None:
        await self.maintenance.fail_running_request_logs()

    async def persist_request_log_stats(self, *, force: bool = False) -> None:
        await self.statistics.persist_request_log_stats(force=force)

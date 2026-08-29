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

    def __getattr__(self, name: str) -> Any:
        for collaborator in (
            self.commands,
            self.queries,
            self.maintenance,
            self.overview,
            self.statistics,
        ):
            value = getattr(collaborator, name, None)
            if value is not None:
                return value
        raise AttributeError(
            f"{type(self).__name__!r} has no collaborator providing {name!r}"
        )

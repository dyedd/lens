from __future__ import annotations

from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.time_zone import load_time_zone

from .overview import RequestLogOverview
from .query import RequestLogHydrator, RequestLogQueries
from .statistics import RequestLogStatistics
from .types import GatewayKeyPort, SettingsPort
from .write import RequestLogCommands, RequestLogMaintenance


def runtime_time_zone(runtime: dict[str, Any]) -> ZoneInfo:
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

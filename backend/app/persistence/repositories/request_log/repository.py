from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .attribution import RequestLogAttribution
from .overview import RequestLogOverview
from .query import RequestLogHydrator, RequestLogQueries
from .statistics import RequestLogStatistics
from .types import GatewayKeyPort, SettingsPort
from .write import RequestLogCommands, RequestLogMaintenance


class RequestLogRepository:
    """Compose the request-log collaborators behind one explicit interface."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings_repo: SettingsPort,
        gateway_key_repo: GatewayKeyPort,
    ) -> None:
        hydrator = RequestLogHydrator(gateway_key_repo)
        statistics = RequestLogStatistics(session_factory, settings_repo)
        self.commands = RequestLogCommands(session_factory, gateway_key_repo)
        self.queries = RequestLogQueries(
            session_factory,
            settings_repo,
            gateway_key_repo,
            hydrator,
        )
        self.maintenance = RequestLogMaintenance(
            session_factory, settings_repo, statistics
        )
        self.overview = RequestLogOverview(session_factory, settings_repo, statistics)
        self.statistics = statistics
        self.attribution = RequestLogAttribution(self.overview)

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...core.time_zone import resolve_time_zone
from ..entities import RequestLogEntity
from .overview_mixin import OverviewMixin
from .request_log_channel_resolution_mixin import (
    RequestLogChannelResolutionMixin,
)
from .request_log_filters_mixin import RequestLogFilterMixin
from .request_log_reads_mixin import RequestLogReadMixin
from .request_log_writes_mixin import RequestLogWriteMixin


class RequestLogStore(
    RequestLogReadMixin,
    RequestLogWriteMixin,
    RequestLogFilterMixin,
    RequestLogChannelResolutionMixin,
    OverviewMixin,
):
    # The five bases share private helpers, so they are composed into one repo.

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings_repo: Any,
        gateway_key_repo: Any,
    ) -> None:
        self._session_factory = session_factory
        self._settings_repo = settings_repo
        self._gateway_key_repo = gateway_key_repo

    def _runtime_time_zone(self, runtime: dict[str, Any]):
        return resolve_time_zone(str(runtime["time_zone"]))

    @staticmethod
    def _normalize_gateway_key_id(gateway_key_id: str | None) -> str | None:
        normalized = (gateway_key_id or "").strip()
        return normalized or None

    @classmethod
    def _apply_gateway_key_filter(
        cls, stmt: Any, *, gateway_key_id: str | None = None
    ) -> Any:
        normalized = cls._normalize_gateway_key_id(gateway_key_id)
        if normalized is None:
            return stmt
        if normalized == "n/a":
            return stmt.where(RequestLogEntity.gateway_key_id.is_(None))
        return stmt.where(RequestLogEntity.gateway_key_id == normalized)

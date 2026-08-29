from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession


class GatewayKeyPort(Protocol):
    async def adjust_spend(
        self, session: AsyncSession, gateway_key_id: str | None, delta: float
    ) -> None: ...

    async def remarks_by_id(
        self, session: AsyncSession, key_ids: list[str | None]
    ) -> dict[str, str]: ...


class SettingsPort(Protocol):
    async def get_runtime_settings(self) -> dict[str, Any]: ...


RuntimeTimeZone = Callable[[dict[str, Any]], ZoneInfo]


class StatisticsPort(Protocol):
    async def persist_request_log_stats(self, *, force: bool = False) -> None: ...

    def request_log_prune_cutoff(
        self, *, keep_days: int, time_zone: ZoneInfo
    ) -> Any: ...

    def daily_stats_by_local_bucket(
        self, rows: list[Any], time_zone: ZoneInfo
    ) -> dict[str, dict[str, float]]: ...

    def model_rows_by_local_bucket(
        self, rows: list[Any], format_text: str, time_zone: ZoneInfo
    ) -> list[tuple[str, str, int, int, float]]: ...


class HydratorPort(Protocol):
    async def hydrate_request_logs(
        self,
        session: AsyncSession,
        entities: list[Any],
        *,
        gateway_has_multiple_keys: bool | None = None,
    ) -> list[Any]: ...

    async def gateway_has_multiple_keys(self, session: AsyncSession) -> bool: ...

    async def request_log_channel_credentials(
        self, session: AsyncSession, channel_ids: list[str | None]
    ) -> tuple[dict[str, int], dict[tuple[str, str], tuple[str, int]]]: ...

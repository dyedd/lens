from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from itertools import batched
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.protocols import RequestLogLifecycleStatus
from app.persistence.entities import RequestLogEntity, SettingEntity
from app.persistence.settings_keys import SETTING_STATS_TIME_ZONE
from app.persistence.stats_entities import (
    OverviewModelDailyStatsEntity,
    RequestLogDailyStatsEntity,
)

from .query import REQUEST_LOG_STATS_COLUMNS
from .types import REQUEST_LOG_TERMINAL_STATUSES, RuntimeTimeZone, SettingsPort


class RequestLogStatistics:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings_repo: SettingsPort,
        runtime_time_zone: RuntimeTimeZone,
    ) -> None:
        self.session_factory = session_factory
        self.settings_repo = settings_repo
        self.runtime_time_zone = runtime_time_zone

    async def persist_request_log_stats(self, *, force: bool = False) -> None:
        """Archive terminal logs without recounting previously archived rows."""
        runtime = await self.settings_repo.get_runtime_settings()
        time_zone = self.runtime_time_zone(runtime)
        before = None
        if not force:
            before = (
                datetime.now(time_zone)
                .replace(hour=0, minute=0, second=0, microsecond=0)
                .astimezone(UTC)
                .replace(tzinfo=None)
            )
        async with self.session_factory.begin() as session:
            await self.archive_request_logs(session, time_zone=time_zone, before=before)

    async def archive_request_logs(
        self,
        session: AsyncSession,
        *,
        time_zone: ZoneInfo,
        before: datetime | None = None,
    ) -> None:
        """Archive one locked snapshot inside the caller's transaction."""
        stored_time_zone = await self._lock_archive_time_zone(session, time_zone)
        model = func.coalesce(
            RequestLogEntity.resolved_group_name, RequestLogEntity.requested_group_name
        ).label("model")
        rows_stmt = (
            select(RequestLogEntity.id, *REQUEST_LOG_STATS_COLUMNS, model)
            .where(RequestLogEntity.lifecycle_status.in_(REQUEST_LOG_TERMINAL_STATUSES))
            .order_by(RequestLogEntity.created_at.asc())
            .with_for_update()
        )
        if stored_time_zone.value != time_zone.key:
            retained_rows = (
                (
                    await session.execute(
                        rows_stmt.where(RequestLogEntity.stats_archived == 1)
                    )
                )
                .mappings()
                .all()
            )
            # Remove only contributions we can rebuild. Deleted detail cannot be rebucketed.
            await self._merge_archive_rows(
                session, retained_rows, ZoneInfo(stored_time_zone.value), direction=-1
            )
            await self._set_archive_flag(session, retained_rows, is_archived=False)
            stored_time_zone.value = time_zone.key
            before = None
        stmt = rows_stmt.where(RequestLogEntity.stats_archived == 0)
        if before is not None:
            stmt = stmt.where(RequestLogEntity.created_at < before)
        rows = (await session.execute(stmt)).mappings().all()
        await self._merge_archive_rows(session, rows, time_zone)
        await self._set_archive_flag(session, rows, is_archived=True)

    @staticmethod
    async def _lock_archive_time_zone(
        session: AsyncSession, time_zone: ZoneInfo
    ) -> SettingEntity:
        dialect = session.get_bind().dialect.name
        insert = sqlite_insert if dialect == "sqlite" else postgresql_insert
        await session.execute(
            insert(SettingEntity)
            .values(key=SETTING_STATS_TIME_ZONE, value=time_zone.key)
            .on_conflict_do_nothing(index_elements=[SettingEntity.key])
        )
        # A write locks both PostgreSQL's row and SQLite's writer until commit.
        await session.execute(
            update(SettingEntity)
            .where(SettingEntity.key == SETTING_STATS_TIME_ZONE)
            .values(value=SettingEntity.value)
        )
        return (
            await session.scalars(
                select(SettingEntity).where(
                    SettingEntity.key == SETTING_STATS_TIME_ZONE
                )
            )
        ).one()

    @staticmethod
    async def _set_archive_flag(
        session: AsyncSession, rows: Sequence[Mapping[str, Any]], *, is_archived: bool
    ) -> None:
        for ids in batched((row["id"] for row in rows), 400, strict=False):
            await session.execute(
                update(RequestLogEntity)
                .where(RequestLogEntity.id.in_(ids))
                .values(stats_archived=int(is_archived))
            )

    async def _merge_archive_rows(
        self,
        session: AsyncSession,
        rows: Sequence[Mapping[str, Any]],
        time_zone: ZoneInfo,
        *,
        direction: int = 1,
    ) -> None:
        daily_rows = [
            tuple(row[column.key] for column in REQUEST_LOG_STATS_COLUMNS)
            for row in rows
        ]
        model_rows = [
            (
                row["created_at"],
                row["model"],
                row["total_tokens"],
                row["total_cost_usd"],
            )
            for row in rows
            if row["lifecycle_status"] == RequestLogLifecycleStatus.SUCCEEDED.value
            and row["model"] is not None
        ]
        daily_buckets = self.daily_stats_by_local_bucket(daily_rows, time_zone)
        model_buckets = self.model_rows_by_local_bucket(model_rows, "%Y%m%d", time_zone)
        # Two binds per model key stay below the SQLite 999-parameter limit.
        daily_entities: dict[str, RequestLogDailyStatsEntity] = {}
        for dates in batched(daily_buckets, 400, strict=False):
            entities = await session.scalars(
                select(RequestLogDailyStatsEntity).where(
                    RequestLogDailyStatsEntity.date.in_(dates)
                )
            )
            daily_entities.update((entity.date, entity) for entity in entities)
        model_entities: dict[tuple[str, str], OverviewModelDailyStatsEntity] = {}
        for keys in batched(
            ((row[0], row[1]) for row in model_buckets), 400, strict=False
        ):
            entities = await session.scalars(
                select(OverviewModelDailyStatsEntity).where(
                    tuple_(
                        OverviewModelDailyStatsEntity.date,
                        OverviewModelDailyStatsEntity.model,
                    ).in_(keys)
                )
            )
            model_entities.update(
                ((entity.date, entity.model), entity) for entity in entities
            )
        for date_value, values in sorted(daily_buckets.items()):
            entity = daily_entities.get(date_value)
            if entity is None:
                if direction < 0:
                    continue
                entity = RequestLogDailyStatsEntity(
                    date=date_value,
                    request_count=0,
                    successful_requests=0,
                    failed_requests=0,
                    wait_time_ms=0,
                    input_tokens=0,
                    cache_read_input_tokens=0,
                    cache_write_input_tokens=0,
                    output_tokens=0,
                    total_tokens=0,
                    input_cost_usd=0.0,
                    output_cost_usd=0.0,
                    total_cost_usd=0.0,
                )
                session.add(entity)
            entity.request_count += direction * int(values["request_count"])
            entity.successful_requests += direction * int(values["successful_requests"])
            entity.failed_requests += direction * int(values["failed_requests"])
            entity.wait_time_ms += direction * int(values["wait_time_ms"])
            entity.input_tokens += direction * int(values["input_tokens"])
            entity.cache_read_input_tokens += direction * int(
                values["cache_read_input_tokens"]
            )
            entity.cache_write_input_tokens += direction * int(
                values["cache_write_input_tokens"]
            )
            entity.output_tokens += direction * int(values["output_tokens"])
            entity.total_tokens += direction * int(values["total_tokens"])
            entity.input_cost_usd += direction * float(values["input_cost_usd"])
            entity.output_cost_usd += direction * float(values["output_cost_usd"])
            entity.total_cost_usd += direction * float(values["total_cost_usd"])
            if entity.request_count == 0:
                await session.delete(entity)
        for date_value, model, requests, total_tokens, total_cost in model_buckets:
            key = {"date": date_value, "model": model}
            entity = model_entities.get((date_value, model))
            if entity is None:
                if direction < 0:
                    continue
                entity = OverviewModelDailyStatsEntity(
                    **key, requests=0, total_tokens=0, total_cost_usd=0.0
                )
                session.add(entity)
            entity.requests += direction * int(requests)
            entity.total_tokens += direction * int(total_tokens)
            entity.total_cost_usd += direction * float(total_cost)
            if entity.requests == 0:
                await session.delete(entity)

    @staticmethod
    def to_utc_datetime(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def request_log_prune_cutoff(*, keep_days: int, time_zone: ZoneInfo) -> datetime:
        local_now = datetime.now(time_zone)
        local_cutoff = local_now.replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(days=max(keep_days, 1) - 1)
        return local_cutoff.astimezone(UTC).replace(tzinfo=None)

    @classmethod
    def daily_stats_by_local_bucket(
        cls, rows: list[Any], time_zone: ZoneInfo
    ) -> dict[str, dict[str, float]]:
        buckets: dict[str, dict[str, float]] = {}
        for row in rows:
            (
                created_at,
                lifecycle_status,
                latency_ms,
                input_tokens,
                cache_read_input_tokens,
                cache_write_input_tokens,
                output_tokens,
                total_tokens,
                input_cost_usd,
                output_cost_usd,
                total_cost_usd,
            ) = row
            utc_created_at = cls.to_utc_datetime(created_at)
            if utc_created_at is None:
                continue
            date_value = utc_created_at.astimezone(time_zone).strftime("%Y%m%d")
            current = buckets.setdefault(
                date_value,
                {
                    "request_count": 0.0,
                    "successful_requests": 0.0,
                    "failed_requests": 0.0,
                    "wait_time_ms": 0.0,
                    "input_tokens": 0.0,
                    "cache_read_input_tokens": 0.0,
                    "cache_write_input_tokens": 0.0,
                    "output_tokens": 0.0,
                    "total_tokens": 0.0,
                    "input_cost_usd": 0.0,
                    "output_cost_usd": 0.0,
                    "total_cost_usd": 0.0,
                },
            )
            success_value = float(
                lifecycle_status == RequestLogLifecycleStatus.SUCCEEDED.value
            )
            failed_value = (
                1.0
                if lifecycle_status == RequestLogLifecycleStatus.FAILED.value
                else 0.0
            )
            current["request_count"] += 1.0
            current["successful_requests"] += success_value
            current["failed_requests"] += failed_value
            current["wait_time_ms"] += float(latency_ms)
            current["input_tokens"] += float(input_tokens)
            current["cache_read_input_tokens"] += float(cache_read_input_tokens)
            current["cache_write_input_tokens"] += float(cache_write_input_tokens)
            current["output_tokens"] += float(output_tokens)
            current["total_tokens"] += float(total_tokens)
            current["input_cost_usd"] += float(input_cost_usd)
            current["output_cost_usd"] += float(output_cost_usd)
            current["total_cost_usd"] += float(total_cost_usd)
        return buckets

    @classmethod
    def model_rows_by_local_bucket(
        cls, rows: list[Any], format_text: str, time_zone: ZoneInfo
    ) -> list[tuple[str, str, int, int, float]]:
        buckets: dict[tuple[str, str], list[float]] = {}
        for created_at, model, total_tokens, total_cost in rows:
            if not model or created_at is None:
                continue
            utc_created_at = cls.to_utc_datetime(created_at)
            if utc_created_at is None:
                continue
            bucket = utc_created_at.astimezone(time_zone).strftime(format_text)
            key = (bucket, str(model))
            current = buckets.setdefault(key, [0.0, 0.0, 0.0])
            current[0] += 1
            current[1] += float(total_tokens)
            current[2] += float(total_cost)
        return [
            (date_value, model, int(values[0]), int(values[1]), float(values[2]))
            for (date_value, model), values in sorted(buckets.items())
        ]

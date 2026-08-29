from __future__ import annotations

from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.overview import (
    OverviewSummary,
    OverviewSummaryMetric,
)
from app.persistence.entities import RequestLogEntity
from app.persistence.stats_entities import (
    ImportedStatsDailyEntity,
    ImportedStatsTotalEntity,
    RequestLogDailyStatsEntity,
)

from .filters import (
    apply_gateway_key_filter,
    apply_request_log_window,
    resolve_imported_date_window,
)
from .overview_daily import OverviewDailyMixin
from .overview_model_analytics import OverviewModelAnalyticsMixin
from .ports import RuntimeTimeZone, SettingsPort
from .statistics import RequestLogStatistics


class RequestLogOverview(
    OverviewDailyMixin,
    OverviewModelAnalyticsMixin,
):
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings_repo: SettingsPort,
        statistics: RequestLogStatistics,
        runtime_time_zone: RuntimeTimeZone,
    ) -> None:
        self.session_factory = session_factory
        self.settings_repo = settings_repo
        self.statistics: RequestLogStatistics = statistics
        self.runtime_time_zone = runtime_time_zone

    async def get_overview_summary(self, days: int = 7) -> OverviewSummary:
        """Return aggregate request metrics and period-over-period deltas."""
        time_zone = self.runtime_time_zone(
            await self.settings_repo.get_runtime_settings()
        )
        async with self.session_factory() as session:
            if days != 0:
                comparison_offset = 1 if days == -1 else days
                recent = await self.merged_period_totals(
                    session, days=days, time_zone=time_zone
                )
                previous = await self.merged_period_totals(
                    session,
                    days=days,
                    offset_days=comparison_offset,
                    time_zone=time_zone,
                )
            else:
                recent = await self.merged_period_totals(
                    session, days=0, time_zone=time_zone
                )
                previous = self.zero_totals()
        request_count = int(recent["request_count"])
        wait_time_ms = int(recent["wait_time_ms"])
        input_tokens = int(recent["input_tokens"])
        cache_read_input_tokens = int(recent["cache_read_input_tokens"])
        cache_write_input_tokens = int(recent["cache_write_input_tokens"])
        output_tokens = int(recent["output_tokens"])
        total_cost_usd = float(recent["total_cost_usd"])
        input_cost_usd = float(recent["input_cost_usd"])
        output_cost_usd = float(recent["output_cost_usd"])
        return OverviewSummary(
            request_count=OverviewSummaryMetric(
                value=request_count,
                delta=self.delta_percent(request_count, previous["request_count"]),
            ),
            wait_time_ms=OverviewSummaryMetric(
                value=wait_time_ms,
                delta=self.delta_percent(wait_time_ms, previous["wait_time_ms"]),
            ),
            total_tokens=OverviewSummaryMetric(
                value=input_tokens + output_tokens,
                delta=self.delta_percent(
                    input_tokens + output_tokens,
                    previous["input_tokens"] + previous["output_tokens"],
                ),
            ),
            total_cost_usd=OverviewSummaryMetric(
                value=total_cost_usd,
                delta=self.delta_percent(total_cost_usd, previous["total_cost_usd"]),
            ),
            input_tokens=OverviewSummaryMetric(
                value=input_tokens,
                delta=self.delta_percent(input_tokens, previous["input_tokens"]),
            ),
            cache_read_input_tokens=OverviewSummaryMetric(
                value=cache_read_input_tokens,
                delta=self.delta_percent(
                    cache_read_input_tokens, previous["cache_read_input_tokens"]
                ),
            ),
            cache_write_input_tokens=OverviewSummaryMetric(
                value=cache_write_input_tokens,
                delta=self.delta_percent(
                    cache_write_input_tokens, previous["cache_write_input_tokens"]
                ),
            ),
            input_cost_usd=OverviewSummaryMetric(
                value=input_cost_usd,
                delta=self.delta_percent(input_cost_usd, previous["input_cost_usd"]),
            ),
            output_tokens=OverviewSummaryMetric(
                value=output_tokens,
                delta=self.delta_percent(output_tokens, previous["output_tokens"]),
            ),
            output_cost_usd=OverviewSummaryMetric(
                value=output_cost_usd,
                delta=self.delta_percent(output_cost_usd, previous["output_cost_usd"]),
            ),
        )

    async def imported_period_totals(
        self,
        session: AsyncSession,
        *,
        days: int,
        time_zone: ZoneInfo,
        offset_days: int = 0,
    ) -> dict[str, float | set[str]]:
        if days == 0:
            imported_total = await session.get(ImportedStatsTotalEntity, 1)
            covered_dates = {
                row[0]
                for row in (
                    await session.execute(select(ImportedStatsDailyEntity.date))
                ).all()
            }
            if imported_total is None:
                return {
                    "request_count": 0.0,
                    "wait_time_ms": 0.0,
                    "input_tokens": 0.0,
                    "cache_read_input_tokens": 0.0,
                    "cache_write_input_tokens": 0.0,
                    "output_tokens": 0.0,
                    "input_cost_usd": 0.0,
                    "output_cost_usd": 0.0,
                    "total_cost_usd": 0.0,
                    "covered_dates": covered_dates,
                }
            return {
                "request_count": float(
                    imported_total.request_success + imported_total.request_failed
                ),
                "wait_time_ms": float(imported_total.wait_time),
                "input_tokens": float(imported_total.input_token),
                "cache_read_input_tokens": 0.0,
                "cache_write_input_tokens": 0.0,
                "output_tokens": float(imported_total.output_token),
                "input_cost_usd": float(imported_total.input_cost),
                "output_cost_usd": float(imported_total.output_cost),
                "total_cost_usd": float(
                    imported_total.input_cost + imported_total.output_cost
                ),
                "covered_dates": covered_dates,
            }
        start_at, end_at = resolve_imported_date_window(
            days, offset_days=offset_days, time_zone=time_zone
        )
        rows = (
            (
                await session.execute(
                    select(ImportedStatsDailyEntity)
                    .where(ImportedStatsDailyEntity.date >= start_at)
                    .where(ImportedStatsDailyEntity.date < end_at)
                )
            )
            .scalars()
            .all()
        )
        covered_dates = {item.date for item in rows}
        return {
            "request_count": float(
                sum(item.request_success + item.request_failed for item in rows)
            ),
            "wait_time_ms": float(sum(item.wait_time for item in rows)),
            "input_tokens": float(sum(item.input_token for item in rows)),
            "cache_read_input_tokens": 0.0,
            "cache_write_input_tokens": 0.0,
            "output_tokens": float(sum(item.output_token for item in rows)),
            "input_cost_usd": float(sum(item.input_cost for item in rows)),
            "output_cost_usd": float(sum(item.output_cost for item in rows)),
            "total_cost_usd": float(
                sum(item.input_cost + item.output_cost for item in rows)
            ),
            "covered_dates": covered_dates,
        }

    async def request_log_period_totals(
        self,
        session: AsyncSession,
        *,
        days: int,
        offset_days: int = 0,
        exclude_dates: set[str] | None = None,
        gateway_key_id: str | None = None,
        include_archived: bool = False,
        time_zone: ZoneInfo,
    ) -> dict[str, float]:
        stmt = select(
            RequestLogEntity.created_at,
            RequestLogEntity.lifecycle_status,
            RequestLogEntity.latency_ms,
            RequestLogEntity.input_tokens,
            RequestLogEntity.cache_read_input_tokens,
            RequestLogEntity.cache_write_input_tokens,
            RequestLogEntity.output_tokens,
            RequestLogEntity.total_tokens,
            RequestLogEntity.input_cost_usd,
            RequestLogEntity.output_cost_usd,
            RequestLogEntity.total_cost_usd,
        ).select_from(RequestLogEntity)
        if not include_archived:
            stmt = stmt.where(RequestLogEntity.stats_archived == 0)
        stmt = apply_request_log_window(
            stmt, days=days, offset_days=offset_days, time_zone=time_zone
        )
        stmt = apply_gateway_key_filter(stmt, gateway_key_id=gateway_key_id)
        rows = (await session.execute(stmt)).all()
        totals = self.zero_totals()
        totals["successful_requests"] = 0.0
        daily_buckets = self.statistics.daily_stats_by_local_bucket(rows, time_zone)
        for date_value, values in daily_buckets.items():
            if exclude_dates and date_value in exclude_dates:
                continue
            totals["request_count"] += float(values["request_count"])
            totals["wait_time_ms"] += float(values["wait_time_ms"])
            totals["input_tokens"] += float(values["input_tokens"])
            totals["cache_read_input_tokens"] += float(
                values["cache_read_input_tokens"]
            )
            totals["cache_write_input_tokens"] += float(
                values["cache_write_input_tokens"]
            )
            totals["output_tokens"] += float(values["output_tokens"])
            totals["input_cost_usd"] += float(values["input_cost_usd"])
            totals["output_cost_usd"] += float(values["output_cost_usd"])
            totals["total_cost_usd"] += float(values["total_cost_usd"])
            totals["successful_requests"] += float(values["successful_requests"])
        return totals

    @staticmethod
    def zero_totals() -> dict[str, float]:
        return {
            "request_count": 0.0,
            "wait_time_ms": 0.0,
            "input_tokens": 0.0,
            "cache_read_input_tokens": 0.0,
            "cache_write_input_tokens": 0.0,
            "output_tokens": 0.0,
            "input_cost_usd": 0.0,
            "output_cost_usd": 0.0,
            "total_cost_usd": 0.0,
        }

    @staticmethod
    def delta_percent(current: float, previous: float) -> float:
        if previous <= 0:
            return 0.0
        return round((current - previous) / previous * 100, 2)

    async def request_log_totals_excluding_imported_days(
        self, session: AsyncSession, *, time_zone: ZoneInfo
    ) -> dict[str, float]:
        imported_dates = {
            row[0]
            for row in (
                await session.execute(select(ImportedStatsDailyEntity.date))
            ).all()
        }
        archived_totals = await self.archived_period_totals(
            session, days=0, exclude_dates=imported_dates, time_zone=time_zone
        )
        live_totals = await self.request_log_period_totals(
            session, days=0, exclude_dates=imported_dates, time_zone=time_zone
        )
        return {
            "request_count": archived_totals["request_count"]
            + live_totals["request_count"],
            "wait_time_ms": archived_totals["wait_time_ms"]
            + live_totals["wait_time_ms"],
            "input_tokens": archived_totals["input_tokens"]
            + live_totals["input_tokens"],
            "cache_read_input_tokens": archived_totals["cache_read_input_tokens"]
            + live_totals["cache_read_input_tokens"],
            "cache_write_input_tokens": archived_totals["cache_write_input_tokens"]
            + live_totals["cache_write_input_tokens"],
            "output_tokens": archived_totals["output_tokens"]
            + live_totals["output_tokens"],
            "input_cost_usd": archived_totals["input_cost_usd"]
            + live_totals["input_cost_usd"],
            "output_cost_usd": archived_totals["output_cost_usd"]
            + live_totals["output_cost_usd"],
            "total_cost_usd": archived_totals["total_cost_usd"]
            + live_totals["total_cost_usd"],
            "successful_requests": archived_totals["successful_requests"]
            + live_totals["successful_requests"],
        }

    async def archived_period_totals(
        self,
        session: AsyncSession,
        *,
        days: int,
        time_zone: ZoneInfo,
        offset_days: int = 0,
        exclude_dates: set[str] | None = None,
    ) -> dict[str, float]:
        stmt = select(
            func.sum(RequestLogDailyStatsEntity.request_count),
            func.sum(RequestLogDailyStatsEntity.wait_time_ms),
            func.sum(RequestLogDailyStatsEntity.input_tokens),
            func.sum(RequestLogDailyStatsEntity.cache_read_input_tokens),
            func.sum(RequestLogDailyStatsEntity.cache_write_input_tokens),
            func.sum(RequestLogDailyStatsEntity.output_tokens),
            func.sum(RequestLogDailyStatsEntity.input_cost_usd),
            func.sum(RequestLogDailyStatsEntity.output_cost_usd),
            func.sum(RequestLogDailyStatsEntity.total_cost_usd),
            func.sum(RequestLogDailyStatsEntity.successful_requests),
        ).select_from(RequestLogDailyStatsEntity)
        start_at, end_at = resolve_imported_date_window(
            days, offset_days=offset_days, time_zone=time_zone
        )
        if start_at is not None:
            stmt = stmt.where(RequestLogDailyStatsEntity.date >= start_at)
        if end_at is not None:
            stmt = stmt.where(RequestLogDailyStatsEntity.date < end_at)
        if exclude_dates:
            stmt = stmt.where(
                RequestLogDailyStatsEntity.date.not_in(sorted(exclude_dates))
            )
        row = (await session.execute(stmt)).one()
        return {
            "request_count": float(row[0] or 0),
            "wait_time_ms": float(row[1] or 0),
            "input_tokens": float(row[2] or 0),
            "cache_read_input_tokens": float(row[3] or 0),
            "cache_write_input_tokens": float(row[4] or 0),
            "output_tokens": float(row[5] or 0),
            "input_cost_usd": float(row[6] or 0),
            "output_cost_usd": float(row[7] or 0),
            "total_cost_usd": float(row[8] or 0),
            "successful_requests": float(row[9] or 0),
        }

    async def merged_period_totals(
        self,
        session: AsyncSession,
        *,
        days: int,
        time_zone: ZoneInfo,
        offset_days: int = 0,
    ) -> dict[str, float]:
        imported_totals = await self.imported_period_totals(
            session, days=days, offset_days=offset_days, time_zone=time_zone
        )
        archived_totals = await self.archived_period_totals(
            session,
            days=days,
            offset_days=offset_days,
            exclude_dates=imported_totals["covered_dates"],
            time_zone=time_zone,
        )
        request_log_totals = await self.request_log_period_totals(
            session,
            days=days,
            offset_days=offset_days,
            exclude_dates=imported_totals["covered_dates"],
            time_zone=time_zone,
        )
        return {
            "request_count": imported_totals["request_count"]
            + archived_totals["request_count"]
            + request_log_totals["request_count"],
            "wait_time_ms": imported_totals["wait_time_ms"]
            + archived_totals["wait_time_ms"]
            + request_log_totals["wait_time_ms"],
            "input_tokens": imported_totals["input_tokens"]
            + archived_totals["input_tokens"]
            + request_log_totals["input_tokens"],
            "cache_read_input_tokens": imported_totals["cache_read_input_tokens"]
            + archived_totals["cache_read_input_tokens"]
            + request_log_totals["cache_read_input_tokens"],
            "cache_write_input_tokens": imported_totals["cache_write_input_tokens"]
            + archived_totals["cache_write_input_tokens"]
            + request_log_totals["cache_write_input_tokens"],
            "output_tokens": imported_totals["output_tokens"]
            + archived_totals["output_tokens"]
            + request_log_totals["output_tokens"],
            "input_cost_usd": imported_totals["input_cost_usd"]
            + archived_totals["input_cost_usd"]
            + request_log_totals["input_cost_usd"],
            "output_cost_usd": imported_totals["output_cost_usd"]
            + archived_totals["output_cost_usd"]
            + request_log_totals["output_cost_usd"],
            "total_cost_usd": imported_totals["total_cost_usd"]
            + archived_totals["total_cost_usd"]
            + request_log_totals["total_cost_usd"],
        }

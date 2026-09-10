from __future__ import annotations

from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.overview import (
    OverviewDailyPoint,
    OverviewModelAnalytics,
    OverviewModelMetricPoint,
    OverviewModelTrendPoint,
    OverviewSummary,
    OverviewSummaryMetric,
)
from app.models.protocols import RequestLogLifecycleStatus
from app.persistence.entities import RequestLogEntity
from app.persistence.stats_entities import (
    ImportedStatsDailyEntity,
    ImportedStatsTotalEntity,
    OverviewModelDailyStatsEntity,
    RequestLogDailyStatsEntity,
)

from .query import (
    apply_gateway_key_filter,
    apply_request_log_window,
    prepare_gateway_key_id,
    resolve_imported_date_window,
)
from .types import RuntimeTimeZone, SettingsPort
from .write import RequestLogStatistics


class OverviewDailyMixin:
    """Build merged daily overview series across imported, archived, and live data."""

    session_factory: AsyncSession
    runtime_time_zone: any
    settings_repo: any
    statistics: any

    async def list_overview_daily(self, days: int = 0) -> list[OverviewDailyPoint]:
        """Return merged daily overview metrics for the requested period."""
        time_zone = self.runtime_time_zone(
            await self.settings_repo.get_runtime_settings()
        )
        async with self.session_factory() as session:
            return await self.merged_daily_points(
                session, days=days, time_zone=time_zone
            )

    async def merged_daily_points(
        self,
        session: AsyncSession,
        *,
        days: int,
        time_zone: ZoneInfo,
        offset_days: int = 0,
    ) -> list[OverviewDailyPoint]:
        imported_points = await self.imported_daily_points(
            session, days=days, offset_days=offset_days, time_zone=time_zone
        )
        imported_dates = {item.date for item in imported_points}
        archived_points = await self.archived_daily_points(
            session,
            days=days,
            offset_days=offset_days,
            exclude_dates=imported_dates,
            time_zone=time_zone,
        )
        request_log_points = await self.request_log_daily_points(
            session,
            days=days,
            offset_days=offset_days,
            exclude_dates=imported_dates,
            time_zone=time_zone,
        )
        merged = {item.date: item for item in imported_points}
        for item in archived_points:
            merged[item.date] = item
        for item in request_log_points:
            current = merged.get(item.date)
            if current is None:
                merged[item.date] = item
                continue
            merged[item.date] = OverviewDailyPoint(
                date=item.date,
                request_count=current.request_count + item.request_count,
                input_tokens=current.input_tokens + item.input_tokens,
                output_tokens=current.output_tokens + item.output_tokens,
                total_tokens=current.total_tokens + item.total_tokens,
                total_cost_usd=current.total_cost_usd + item.total_cost_usd,
                wait_time_ms=current.wait_time_ms + item.wait_time_ms,
                successful_requests=current.successful_requests
                + item.successful_requests,
                failed_requests=current.failed_requests + item.failed_requests,
            )
        return [merged[date] for date in sorted(merged)]

    async def imported_daily_points(
        self,
        session: AsyncSession,
        *,
        days: int,
        time_zone: ZoneInfo,
        offset_days: int = 0,
    ) -> list[OverviewDailyPoint]:
        stmt = select(ImportedStatsDailyEntity).order_by(
            ImportedStatsDailyEntity.date.asc()
        )
        start_at, end_at = resolve_imported_date_window(
            days, offset_days=offset_days, time_zone=time_zone
        )
        if start_at is not None and end_at is not None:
            stmt = stmt.where(ImportedStatsDailyEntity.date >= start_at).where(
                ImportedStatsDailyEntity.date < end_at
            )
        rows = (await session.execute(stmt)).scalars().all()
        return [
            OverviewDailyPoint(
                date=item.date,
                request_count=int(item.request_success + item.request_failed),
                input_tokens=int(item.input_token),
                output_tokens=int(item.output_token),
                total_tokens=int(item.input_token + item.output_token),
                total_cost_usd=float(item.input_cost + item.output_cost),
                wait_time_ms=int(item.wait_time),
                successful_requests=int(item.request_success),
                failed_requests=int(item.request_failed),
            )
            for item in rows
        ]

    async def archived_daily_points(
        self,
        session: AsyncSession,
        *,
        days: int,
        time_zone: ZoneInfo,
        offset_days: int = 0,
        exclude_dates: set[str] | None = None,
    ) -> list[OverviewDailyPoint]:
        stmt = select(RequestLogDailyStatsEntity).order_by(
            RequestLogDailyStatsEntity.date.asc()
        )
        start_at, end_at = resolve_imported_date_window(
            days, offset_days=offset_days, time_zone=time_zone
        )
        if start_at is not None and end_at is not None:
            stmt = stmt.where(RequestLogDailyStatsEntity.date >= start_at).where(
                RequestLogDailyStatsEntity.date < end_at
            )
        if exclude_dates:
            stmt = stmt.where(
                RequestLogDailyStatsEntity.date.not_in(sorted(exclude_dates))
            )
        rows = (await session.execute(stmt)).scalars().all()
        return [
            OverviewDailyPoint(
                date=item.date,
                request_count=int(item.request_count),
                input_tokens=int(item.input_tokens),
                output_tokens=int(item.output_tokens),
                total_tokens=int(item.total_tokens),
                total_cost_usd=float(item.total_cost_usd),
                wait_time_ms=int(item.wait_time_ms),
                successful_requests=int(item.successful_requests),
                failed_requests=int(item.failed_requests),
            )
            for item in rows
        ]

    async def request_log_daily_points(
        self,
        session: AsyncSession,
        *,
        days: int,
        time_zone: ZoneInfo,
        offset_days: int = 0,
        exclude_dates: set[str] | None = None,
        gateway_key_id: str | None = None,
        include_archived: bool = False,
    ) -> list[OverviewDailyPoint]:
        stmt = (
            select(
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
            )
            .select_from(RequestLogEntity)
            .order_by(RequestLogEntity.created_at.asc())
        )
        if not include_archived:
            stmt = stmt.where(RequestLogEntity.stats_archived == 0)
        stmt = apply_request_log_window(
            stmt, days=days, offset_days=offset_days, time_zone=time_zone
        )
        stmt = apply_gateway_key_filter(stmt, gateway_key_id=gateway_key_id)
        rows = (await session.execute(stmt)).all()
        points: list[OverviewDailyPoint] = []
        daily_buckets = self.statistics.daily_stats_by_local_bucket(rows, time_zone)
        for date_value, values in sorted(daily_buckets.items()):
            if exclude_dates and date_value in exclude_dates:
                continue
            total_value = int(values["request_count"])
            success_value = int(values["successful_requests"])
            points.append(
                OverviewDailyPoint(
                    date=date_value,
                    request_count=total_value,
                    input_tokens=int(values["input_tokens"]),
                    output_tokens=int(values["output_tokens"]),
                    total_tokens=int(values["total_tokens"]),
                    total_cost_usd=float(values["total_cost_usd"]),
                    wait_time_ms=int(values["wait_time_ms"]),
                    successful_requests=success_value,
                    failed_requests=int(values["failed_requests"]),
                )
            )
        return points


class OverviewModelAnalyticsMixin:
    """Compute per-model overview distribution and trend analytics."""

    session_factory: AsyncSession
    runtime_time_zone: any
    settings_repo: any
    statistics: any

    async def get_model_analytics(
        self, days: int = 7, gateway_key_id: str | None = None, metric: str = "cost"
    ) -> OverviewModelAnalytics:
        """Return model distribution and trend analytics for a metric."""
        model_metric = metric if metric in {"cost", "requests", "tokens"} else "cost"
        gateway_key_id_value = prepare_gateway_key_id(gateway_key_id)
        time_zone = self.runtime_time_zone(
            await self.settings_repo.get_runtime_settings()
        )
        async with self.session_factory() as session:
            if gateway_key_id_value is not None:
                archived_model_rows = []
                if days == -1:
                    live_model_rows = await self.request_log_model_rows(
                        session,
                        days=days,
                        offset_days=0,
                        gateway_key_id=gateway_key_id_value,
                        include_archived=True,
                        time_zone=time_zone,
                        bucket_format="%Y%m%d%H",
                    )
                else:
                    live_model_rows = await self.request_log_model_rows(
                        session,
                        days=days,
                        offset_days=0,
                        gateway_key_id=gateway_key_id_value,
                        include_archived=True,
                        time_zone=time_zone,
                        bucket_format="%Y%m%d",
                    )
            elif days == -1:
                archived_model_rows = []
                live_model_rows = await self.request_log_model_rows(
                    session,
                    days=days,
                    offset_days=0,
                    gateway_key_id=None,
                    include_archived=False,
                    time_zone=time_zone,
                    bucket_format="%Y%m%d%H",
                )
            else:
                window_start, window_end = resolve_imported_date_window(
                    days, time_zone=time_zone
                )
                archived_model_rows = await self.overview_model_daily_rows(
                    session, start_at=window_start, end_at=window_end
                )
                live_model_rows = await self.request_log_model_rows(
                    session,
                    days=days,
                    offset_days=0,
                    gateway_key_id=None,
                    include_archived=False,
                    time_zone=time_zone,
                    bucket_format="%Y%m%d",
                )
        merged_rows: dict[tuple[str, str], dict[str, float | str]] = {}
        for date_value, model, requests, total_tokens, total_cost in [
            *archived_model_rows,
            *live_model_rows,
        ]:
            if not model:
                continue
            key = (str(date_value), str(model))
            current = merged_rows.get(key)
            if current is None:
                merged_rows[key] = {
                    "date": str(date_value),
                    "model": str(model),
                    "requests": float(requests),
                    "total_tokens": float(total_tokens),
                    "total_cost_usd": float(total_cost),
                }
                continue
            current["requests"] = float(current["requests"]) + float(requests)
            current["total_tokens"] = float(current["total_tokens"]) + float(
                total_tokens
            )
            current["total_cost_usd"] = float(current["total_cost_usd"]) + float(
                total_cost
            )
        trend_rows = sorted(
            merged_rows.values(),
            key=lambda item: (str(item["date"]), str(item["model"])),
        )
        model_rows: dict[str, dict[str, float | str]] = {}
        for item in merged_rows.values():
            model_key = str(item["model"])
            current = model_rows.get(model_key)
            if current is None:
                model_rows[model_key] = {
                    "model": model_key,
                    "requests": float(item["requests"]),
                    "total_tokens": float(item["total_tokens"]),
                    "total_cost_usd": float(item["total_cost_usd"]),
                }
                continue
            current["requests"] = float(current["requests"]) + float(item["requests"])
            current["total_tokens"] = float(current["total_tokens"]) + float(
                item["total_tokens"]
            )
            current["total_cost_usd"] = float(current["total_cost_usd"]) + float(
                item["total_cost_usd"]
            )

        def metric_value(item: dict[str, float | str]) -> float:
            if model_metric == "requests":
                return float(item["requests"])
            if model_metric == "tokens":
                return float(item["total_tokens"])
            return float(item["total_cost_usd"])

        def secondary_metric_value(item: dict[str, float | str]) -> float:
            if model_metric == "cost":
                return float(item["requests"])
            return float(item["total_cost_usd"])

        aggregated_models = list(model_rows.values())
        distribution_rows = sorted(
            aggregated_models,
            key=lambda item: (
                -metric_value(item),
                -secondary_metric_value(item),
                str(item["model"]),
            ),
        )
        distribution = [
            OverviewModelMetricPoint(
                model=str(item["model"]),
                requests=int(item["requests"]),
                total_tokens=int(item["total_tokens"]),
                total_cost_usd=float(item["total_cost_usd"]),
            )
            for item in distribution_rows[:12]
        ]
        trend = [
            OverviewModelTrendPoint(
                date=str(item["date"]),
                model=str(item["model"]),
                value=metric_value(item),
            )
            for item in trend_rows
        ]
        available_models = sorted(
            {item.model for item in distribution} | {item.model for item in trend}
        )
        return OverviewModelAnalytics(
            distribution=distribution, trend=trend, available_models=available_models
        )

    async def overview_model_daily_rows(
        self, session: AsyncSession, *, start_at: str | None, end_at: str | None
    ) -> list[tuple[str, str, int, int, float]]:
        stmt = select(
            OverviewModelDailyStatsEntity.date,
            OverviewModelDailyStatsEntity.model,
            OverviewModelDailyStatsEntity.requests,
            OverviewModelDailyStatsEntity.total_tokens,
            OverviewModelDailyStatsEntity.total_cost_usd,
        )
        if start_at is not None:
            stmt = stmt.where(OverviewModelDailyStatsEntity.date >= start_at)
        if end_at is not None:
            stmt = stmt.where(OverviewModelDailyStatsEntity.date < end_at)
        rows = (
            await session.execute(
                stmt.order_by(OverviewModelDailyStatsEntity.date.asc())
            )
        ).all()
        return [
            (
                str(date_value),
                str(model),
                int(requests),
                int(total_tokens),
                float(total_cost),
            )
            for date_value, model, requests, total_tokens, total_cost in rows
        ]

    async def request_log_model_rows(
        self,
        session: AsyncSession,
        *,
        days: int,
        time_zone: ZoneInfo,
        bucket_format: str,
        offset_days: int = 0,
        gateway_key_id: str | None = None,
        include_archived: bool = False,
    ) -> list[tuple[str, str, int, int, float]]:
        model_expr = func.coalesce(
            RequestLogEntity.resolved_group_name, RequestLogEntity.requested_group_name
        )
        stmt = (
            select(
                RequestLogEntity.created_at,
                model_expr,
                RequestLogEntity.total_tokens,
                RequestLogEntity.total_cost_usd,
            )
            .where(
                RequestLogEntity.lifecycle_status
                == RequestLogLifecycleStatus.SUCCEEDED.value
            )
            .where(model_expr.is_not(None))
            .order_by(RequestLogEntity.created_at.asc())
        )
        if not include_archived:
            stmt = stmt.where(RequestLogEntity.stats_archived == 0)
        stmt = apply_request_log_window(
            stmt, days=days, offset_days=offset_days, time_zone=time_zone
        )
        stmt = apply_gateway_key_filter(stmt, gateway_key_id=gateway_key_id)
        rows = (await session.execute(stmt)).all()
        return self.statistics.model_rows_by_local_bucket(
            rows, bucket_format, time_zone
        )


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

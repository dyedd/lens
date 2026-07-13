from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ..shared import (
    ImportedStatsDailyEntity,
    OverviewDailyPoint,
    RequestLogDailyStatsEntity,
    RequestLogEntity,
    ZoneInfo,
    select,
)


class _OverviewDailyMixin:
    async def list_overview_daily(self, days: int = 0) -> list[OverviewDailyPoint]:
        """Return merged daily overview metrics for the requested period."""
        time_zone = self._runtime_time_zone(
            await self._settings_repo.get_runtime_settings()
        )
        async with self._session_factory() as session:
            return await self._merged_daily_points(
                session, days=days, time_zone=time_zone
            )

    async def _merged_daily_points(
        self,
        session: AsyncSession,
        *,
        days: int,
        time_zone: ZoneInfo,
        offset_days: int = 0,
    ) -> list[OverviewDailyPoint]:
        imported_points = await self._imported_daily_points(
            session, days=days, offset_days=offset_days, time_zone=time_zone
        )
        imported_dates = {item.date for item in imported_points}
        archived_points = await self._archived_daily_points(
            session,
            days=days,
            offset_days=offset_days,
            exclude_dates=imported_dates,
            time_zone=time_zone,
        )
        request_log_points = await self._request_log_daily_points(
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

    async def _imported_daily_points(
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
        start_at, end_at = self._resolve_imported_date_window(
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

    async def _archived_daily_points(
        self,
        session: AsyncSession,
        *,
        days: int,
        offset_days: int = 0,
        exclude_dates: set[str] | None = None,
        time_zone: ZoneInfo,
    ) -> list[OverviewDailyPoint]:
        stmt = select(RequestLogDailyStatsEntity).order_by(
            RequestLogDailyStatsEntity.date.asc()
        )
        start_at, end_at = self._resolve_imported_date_window(
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

    async def _request_log_daily_points(
        self,
        session: AsyncSession,
        *,
        days: int,
        offset_days: int = 0,
        exclude_dates: set[str] | None = None,
        gateway_key_id: str | None = None,
        include_archived: bool = False,
        time_zone: ZoneInfo,
    ) -> list[OverviewDailyPoint]:
        stmt = (
            select(
                RequestLogEntity.created_at,
                RequestLogEntity.success,
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
        stmt = self._apply_request_log_window(
            stmt, days=days, offset_days=offset_days, time_zone=time_zone
        )
        stmt = self._apply_gateway_key_filter(stmt, gateway_key_id=gateway_key_id)
        rows = (await session.execute(stmt)).all()
        points: list[OverviewDailyPoint] = []
        daily_buckets = self._daily_stats_by_local_bucket(rows, time_zone)
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
                    failed_requests=max(total_value - success_value, 0),
                )
            )
        return points

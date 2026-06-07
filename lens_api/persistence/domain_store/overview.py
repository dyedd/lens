from __future__ import annotations

from .shared import (
    Any,
    AsyncSession,
    GatewayApiKeyEntity,
    ImportedStatsDailyEntity,
    ImportedStatsTotalEntity,
    ModelGroupEntity,
    ModelPriceEntity,
    OverviewDailyPoint,
    OverviewMetrics,
    OverviewModelAnalytics,
    OverviewModelDailyStatsEntity,
    OverviewModelMetricPoint,
    OverviewModelTrendPoint,
    OverviewSummary,
    OverviewSummaryMetric,
    RequestLogDailyStatsEntity,
    RequestLogEntity,
    RequestLogLifecycleStatus,
    UTC,
    ZoneInfo,
    datetime,
    func,
    normalize_model_key,
    select,
    timedelta,
)


class DomainOverviewMixin:
    async def get_overview_metrics(self) -> OverviewMetrics:
        time_zone = self._runtime_time_zone(await self.get_runtime_settings())
        async with self._session_factory() as session:
            imported_total = await session.get(ImportedStatsTotalEntity, 1)
            if imported_total is not None:
                extra_totals = await self._request_log_totals_excluding_imported_days(
                    session, time_zone=time_zone
                )
                total_value = int(
                    imported_total.request_success
                    + imported_total.request_failed
                    + extra_totals["request_count"]
                )
                success_value = int(
                    imported_total.request_success + extra_totals["successful_requests"]
                )
            else:
                archived_totals = await self._archived_period_totals(
                    session, days=0, time_zone=time_zone
                )
                live_totals = await self._request_log_period_totals(
                    session, days=0, time_zone=time_zone
                )
                total_value = int(
                    archived_totals["request_count"] + live_totals["request_count"]
                )
                success_value = int(
                    archived_totals["successful_requests"]
                    + live_totals["successful_requests"]
                )

            total_groups = int(
                await session.scalar(select(func.count()).select_from(ModelGroupEntity))
            )
            total_gateway_keys = int(
                await session.scalar(
                    select(func.count()).select_from(GatewayApiKeyEntity)
                )
            )
            enabled_gateway_keys = int(
                await session.scalar(
                    select(func.count())
                    .select_from(GatewayApiKeyEntity)
                    .where(GatewayApiKeyEntity.enabled == 1)
                )
            )

        return OverviewMetrics(
            total_requests=total_value,
            successful_requests=success_value,
            failed_requests=max(total_value - success_value, 0),
            enabled_gateway_keys=enabled_gateway_keys,
            total_gateway_keys=total_gateway_keys,
            enabled_groups=total_groups,
            total_groups=total_groups,
            enabled_channels=0,
            total_channels=0,
        )

    async def get_overview_summary(self, days: int = 7) -> OverviewSummary:
        time_zone = self._runtime_time_zone(await self.get_runtime_settings())
        async with self._session_factory() as session:
            if days != 0:
                comparison_offset = 1 if days == -1 else days
                recent = await self._merged_period_totals(
                    session, days=days, time_zone=time_zone
                )
                previous = await self._merged_period_totals(
                    session,
                    days=days,
                    offset_days=comparison_offset,
                    time_zone=time_zone,
                )
            else:
                recent = await self._merged_period_totals(
                    session, days=0, time_zone=time_zone
                )
                previous = self._zero_totals()

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
                delta=self._delta_percent(request_count, previous["request_count"]),
            ),
            wait_time_ms=OverviewSummaryMetric(
                value=wait_time_ms,
                delta=self._delta_percent(wait_time_ms, previous["wait_time_ms"]),
            ),
            total_tokens=OverviewSummaryMetric(
                value=input_tokens + output_tokens,
                delta=self._delta_percent(
                    input_tokens + output_tokens,
                    previous["input_tokens"] + previous["output_tokens"],
                ),
            ),
            total_cost_usd=OverviewSummaryMetric(
                value=total_cost_usd,
                delta=self._delta_percent(total_cost_usd, previous["total_cost_usd"]),
            ),
            input_tokens=OverviewSummaryMetric(
                value=input_tokens,
                delta=self._delta_percent(input_tokens, previous["input_tokens"]),
            ),
            cache_read_input_tokens=OverviewSummaryMetric(
                value=cache_read_input_tokens,
                delta=self._delta_percent(
                    cache_read_input_tokens, previous["cache_read_input_tokens"]
                ),
            ),
            cache_write_input_tokens=OverviewSummaryMetric(
                value=cache_write_input_tokens,
                delta=self._delta_percent(
                    cache_write_input_tokens, previous["cache_write_input_tokens"]
                ),
            ),
            input_cost_usd=OverviewSummaryMetric(
                value=input_cost_usd,
                delta=self._delta_percent(input_cost_usd, previous["input_cost_usd"]),
            ),
            output_tokens=OverviewSummaryMetric(
                value=output_tokens,
                delta=self._delta_percent(output_tokens, previous["output_tokens"]),
            ),
            output_cost_usd=OverviewSummaryMetric(
                value=output_cost_usd,
                delta=self._delta_percent(output_cost_usd, previous["output_cost_usd"]),
            ),
        )

    async def list_overview_daily(self, days: int = 0) -> list[OverviewDailyPoint]:
        time_zone = self._runtime_time_zone(await self.get_runtime_settings())
        async with self._session_factory() as session:
            return await self._merged_daily_points(
                session, days=days, time_zone=time_zone
            )

    async def get_model_analytics(
        self, days: int = 7, gateway_key_id: str | None = None
    ) -> OverviewModelAnalytics:
        normalized_gateway_key_id = self._normalize_gateway_key_id(gateway_key_id)
        time_zone = self._runtime_time_zone(await self.get_runtime_settings())
        async with self._session_factory() as session:
            if normalized_gateway_key_id is not None:
                archived_model_rows = []
                if days == -1:
                    live_model_rows = await self._request_log_model_hourly_rows(
                        session,
                        days=days,
                        gateway_key_id=normalized_gateway_key_id,
                        include_archived=True,
                        time_zone=time_zone,
                    )
                else:
                    live_model_rows = await self._request_log_model_daily_rows(
                        session,
                        days=days,
                        gateway_key_id=normalized_gateway_key_id,
                        include_archived=True,
                        time_zone=time_zone,
                    )
            elif days == -1:
                archived_model_rows = []
                live_model_rows = await self._request_log_model_hourly_rows(
                    session, days=days, time_zone=time_zone
                )
            else:
                window_start, window_end = self._resolve_imported_date_window(
                    days, time_zone=time_zone
                )
                archived_model_rows = await self._overview_model_daily_rows(
                    session,
                    start_at=window_start,
                    end_at=window_end,
                )
                live_model_rows = await self._request_log_model_daily_rows(
                    session, days=days, time_zone=time_zone
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

        aggregated_models = list(model_rows.values())
        distribution_rows = sorted(
            aggregated_models,
            key=lambda item: (-float(item["total_cost_usd"]), -float(item["requests"])),
        )
        ranking_rows = sorted(
            aggregated_models,
            key=lambda item: (-float(item["requests"]), -float(item["total_cost_usd"])),
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

        ranking = [
            OverviewModelMetricPoint(
                model=str(item["model"]),
                requests=int(item["requests"]),
                total_tokens=int(item["total_tokens"]),
                total_cost_usd=float(item["total_cost_usd"]),
            )
            for item in ranking_rows[:10]
        ]

        trend = [
            OverviewModelTrendPoint(
                date=str(item["date"]),
                model=str(item["model"]),
                value=float(item["total_cost_usd"]),
            )
            for item in trend_rows
        ]

        available_models = sorted(
            {item.model for item in distribution}
            | {item.model for item in ranking}
            | {item.model for item in trend}
        )
        return OverviewModelAnalytics(
            distribution=distribution,
            request_ranking=ranking,
            trend=trend,
            available_models=available_models,
        )

    async def estimate_model_cost(
        self,
        model_name: str | None,
        input_tokens: int,
        output_tokens: int,
        cache_read_input_tokens: int = 0,
        cache_write_input_tokens: int = 0,
    ) -> tuple[float, float, float]:
        if not model_name:
            return 0.0, 0.0, 0.0

        async with self._session_factory() as session:
            entity = await session.get(
                ModelPriceEntity, normalize_model_key(model_name)
            )
            if entity is None:
                return 0.0, 0.0, 0.0

        total_input_tokens = max(input_tokens, 0)
        cache_read_tokens = max(cache_read_input_tokens, 0)
        cache_write_tokens = max(cache_write_input_tokens, 0)
        regular_input_tokens = max(
            total_input_tokens - cache_read_tokens - cache_write_tokens, 0
        )

        input_cost = (regular_input_tokens / 1_000_000) * float(
            entity.input_price_per_million
        )
        input_cost += (cache_read_tokens / 1_000_000) * float(
            entity.cache_read_price_per_million
        )
        input_cost += (cache_write_tokens / 1_000_000) * float(
            entity.cache_write_price_per_million
        )
        output_cost = (max(output_tokens, 0) / 1_000_000) * float(
            entity.output_price_per_million
        )
        total_cost = input_cost + output_cost
        return round(input_cost, 8), round(output_cost, 8), round(total_cost, 8)

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
                    total_tokens=int(values["total_tokens"]),
                    total_cost_usd=float(values["total_cost_usd"]),
                    wait_time_ms=int(values["wait_time_ms"]),
                    successful_requests=success_value,
                    failed_requests=max(total_value - success_value, 0),
                )
            )
        return points

    async def _request_log_totals_excluding_imported_days(
        self, session: AsyncSession, *, time_zone: ZoneInfo
    ) -> dict[str, float]:
        imported_dates = {
            row[0]
            for row in (
                await session.execute(select(ImportedStatsDailyEntity.date))
            ).all()
        }
        archived_totals = await self._archived_period_totals(
            session, days=0, exclude_dates=imported_dates, time_zone=time_zone
        )
        live_totals = await self._request_log_period_totals(
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

    async def _archived_period_totals(
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
        start_at, end_at = self._resolve_imported_date_window(
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

    async def _overview_model_daily_rows(
        self,
        session: AsyncSession,
        *,
        start_at: str | None,
        end_at: str | None,
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

    async def _request_log_model_daily_rows(
        self,
        session: AsyncSession,
        *,
        days: int,
        offset_days: int = 0,
        gateway_key_id: str | None = None,
        include_archived: bool = False,
        time_zone: ZoneInfo,
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
            .where(RequestLogEntity.success == 1)
            .where(
                RequestLogEntity.lifecycle_status
                == RequestLogLifecycleStatus.SUCCEEDED.value
            )
            .where(model_expr.is_not(None))
            .order_by(RequestLogEntity.created_at.asc())
        )
        if not include_archived:
            stmt = stmt.where(RequestLogEntity.stats_archived == 0)
        stmt = self._apply_request_log_window(
            stmt, days=days, offset_days=offset_days, time_zone=time_zone
        )
        stmt = self._apply_gateway_key_filter(stmt, gateway_key_id=gateway_key_id)
        rows = (await session.execute(stmt)).all()
        return self._model_rows_by_local_bucket(rows, "%Y%m%d", time_zone)

    async def _request_log_model_hourly_rows(
        self,
        session: AsyncSession,
        *,
        days: int,
        offset_days: int = 0,
        gateway_key_id: str | None = None,
        include_archived: bool = False,
        time_zone: ZoneInfo,
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
            .where(RequestLogEntity.success == 1)
            .where(
                RequestLogEntity.lifecycle_status
                == RequestLogLifecycleStatus.SUCCEEDED.value
            )
            .where(model_expr.is_not(None))
            .order_by(RequestLogEntity.created_at.asc())
        )
        if not include_archived:
            stmt = stmt.where(RequestLogEntity.stats_archived == 0)
        stmt = self._apply_request_log_window(
            stmt, days=days, offset_days=offset_days, time_zone=time_zone
        )
        stmt = self._apply_gateway_key_filter(stmt, gateway_key_id=gateway_key_id)
        rows = (await session.execute(stmt)).all()
        return self._model_rows_by_local_bucket(rows, "%Y%m%d%H", time_zone)

    async def _merged_period_totals(
        self,
        session: AsyncSession,
        *,
        days: int,
        time_zone: ZoneInfo,
        offset_days: int = 0,
    ) -> dict[str, float]:
        imported_totals = await self._imported_period_totals(
            session, days=days, offset_days=offset_days, time_zone=time_zone
        )
        archived_totals = await self._archived_period_totals(
            session,
            days=days,
            offset_days=offset_days,
            exclude_dates=imported_totals["covered_dates"],
            time_zone=time_zone,
        )
        request_log_totals = await self._request_log_period_totals(
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

    async def _imported_period_totals(
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

        start_at, end_at = self._resolve_imported_date_window(
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

    async def _request_log_period_totals(
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
        ).select_from(RequestLogEntity)
        if not include_archived:
            stmt = stmt.where(RequestLogEntity.stats_archived == 0)
        stmt = self._apply_request_log_window(
            stmt, days=days, offset_days=offset_days, time_zone=time_zone
        )
        stmt = self._apply_gateway_key_filter(stmt, gateway_key_id=gateway_key_id)
        rows = (await session.execute(stmt)).all()
        totals = self._zero_totals()
        totals["successful_requests"] = 0.0
        daily_buckets = self._daily_stats_by_local_bucket(rows, time_zone)
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
    def _zero_totals() -> dict[str, float]:
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
    def _to_utc_datetime(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _request_log_prune_cutoff(*, keep_days: int, time_zone: ZoneInfo) -> datetime:
        local_now = datetime.now(time_zone)
        local_cutoff = local_now.replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(days=max(keep_days, 1) - 1)
        return local_cutoff.astimezone(UTC).replace(tzinfo=None)

    @classmethod
    def _daily_stats_by_local_bucket(
        cls, rows: list[Any], time_zone: ZoneInfo
    ) -> dict[str, dict[str, float]]:
        buckets: dict[str, dict[str, float]] = {}
        for row in rows:
            (
                created_at,
                success,
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
            utc_created_at = cls._to_utc_datetime(created_at)
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
            success_value = 1.0 if int(success) else 0.0
            current["request_count"] += 1.0
            current["successful_requests"] += success_value
            current["failed_requests"] += 0.0 if success_value else 1.0
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
    def _model_rows_by_local_bucket(
        cls, rows: list[Any], format_text: str, time_zone: ZoneInfo
    ) -> list[tuple[str, str, int, int, float]]:
        buckets: dict[tuple[str, str], list[float]] = {}
        for created_at, model, total_tokens, total_cost in rows:
            if not model or created_at is None:
                continue
            utc_created_at = cls._to_utc_datetime(created_at)
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

    @staticmethod
    def _delta_percent(current: float, previous: float) -> float:
        if previous <= 0:
            return 0.0
        return round(((current - previous) / previous) * 100, 2)

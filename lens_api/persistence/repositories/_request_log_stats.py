from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..shared import (
    OverviewModelDailyStatsEntity,
    REQUEST_LOG_TERMINAL_STATUSES,
    RequestLogDailyStatsEntity,
    RequestLogEntity,
    SETTING_STATS_TIME_ZONE,
    SettingEntity,
    UTC,
    datetime,
    delete,
    func,
    select,
    update,
)


class _RequestLogStatsMixin:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def persist_request_log_stats(self, *, force: bool = False) -> None:
        """Archive terminal request logs into daily statistics."""
        runtime = await self._settings_repo.get_runtime_settings()
        now = datetime.now(UTC).replace(tzinfo=None)
        time_zone = self._runtime_time_zone(runtime)
        local_now = now.replace(tzinfo=UTC).astimezone(time_zone)
        today_key = local_now.strftime("%Y%m%d")
        today_start_utc = (
            local_now.replace(hour=0, minute=0, second=0, microsecond=0)
            .astimezone(UTC)
            .replace(tzinfo=None)
        )

        async with self._session_factory() as session:
            stored_time_zone = await session.get(SettingEntity, SETTING_STATS_TIME_ZONE)
            if stored_time_zone is None:
                session.add(
                    SettingEntity(key=SETTING_STATS_TIME_ZONE, value=time_zone.key)
                )
            elif stored_time_zone.value != time_zone.key:
                await session.execute(delete(RequestLogDailyStatsEntity))
                await session.execute(delete(OverviewModelDailyStatsEntity))
                await session.execute(update(RequestLogEntity).values(stats_archived=0))
                stored_time_zone.value = time_zone.key
                force = True

            if not force:
                # Keep today's archived rows live so the current-day bucket can move
                # with the configured application time zone.
                await session.execute(
                    delete(RequestLogDailyStatsEntity).where(
                        RequestLogDailyStatsEntity.date == today_key
                    )
                )
                await session.execute(
                    delete(OverviewModelDailyStatsEntity).where(
                        OverviewModelDailyStatsEntity.date == today_key
                    )
                )
                await session.execute(
                    update(RequestLogEntity)
                    .where(RequestLogEntity.stats_archived == 1)
                    .where(RequestLogEntity.created_at >= today_start_utc)
                    .values(stats_archived=0)
                )

            unarchived_stmt = (
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
                .where(RequestLogEntity.stats_archived == 0)
                .where(
                    RequestLogEntity.lifecycle_status.in_(REQUEST_LOG_TERMINAL_STATUSES)
                )
                .order_by(RequestLogEntity.created_at.asc())
            )
            if not force:
                unarchived_stmt = unarchived_stmt.where(
                    RequestLogEntity.created_at < today_start_utc
                )
            daily_rows = (await session.execute(unarchived_stmt)).all()

            model_expr = func.coalesce(
                RequestLogEntity.resolved_group_name,
                RequestLogEntity.requested_group_name,
            )
            model_stmt = (
                select(
                    RequestLogEntity.created_at,
                    model_expr,
                    RequestLogEntity.total_tokens,
                    RequestLogEntity.total_cost_usd,
                )
                .where(RequestLogEntity.stats_archived == 0)
                .where(
                    RequestLogEntity.lifecycle_status.in_(REQUEST_LOG_TERMINAL_STATUSES)
                )
                .where(RequestLogEntity.success == 1)
                .where(model_expr.is_not(None))
                .order_by(RequestLogEntity.created_at.asc())
            )
            if not force:
                model_stmt = model_stmt.where(
                    RequestLogEntity.created_at < today_start_utc
                )
            model_rows = (await session.execute(model_stmt)).all()

            daily_buckets = self._daily_stats_by_local_bucket(daily_rows, time_zone)
            model_buckets = self._model_rows_by_local_bucket(
                model_rows, "%Y%m%d", time_zone
            )

            for date_value, values in sorted(daily_buckets.items()):
                entity = await session.get(RequestLogDailyStatsEntity, date_value)
                if entity is None:
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
                entity.request_count += int(values["request_count"])
                entity.successful_requests += int(values["successful_requests"])
                entity.failed_requests += int(values["failed_requests"])
                entity.wait_time_ms += int(values["wait_time_ms"])
                entity.input_tokens += int(values["input_tokens"])
                entity.cache_read_input_tokens += int(values["cache_read_input_tokens"])
                entity.cache_write_input_tokens += int(
                    values["cache_write_input_tokens"]
                )
                entity.output_tokens += int(values["output_tokens"])
                entity.total_tokens += int(values["total_tokens"])
                entity.input_cost_usd += float(values["input_cost_usd"])
                entity.output_cost_usd += float(values["output_cost_usd"])
                entity.total_cost_usd += float(values["total_cost_usd"])

            for date_value, model, requests, total_tokens, total_cost in model_buckets:
                key = {"date": date_value, "model": model}
                entity = await session.get(OverviewModelDailyStatsEntity, key)
                if entity is None:
                    entity = OverviewModelDailyStatsEntity(
                        **key, requests=0, total_tokens=0, total_cost_usd=0.0
                    )
                    session.add(entity)
                entity.requests += int(requests)
                entity.total_tokens += int(total_tokens)
                entity.total_cost_usd += float(total_cost)

            if daily_rows or model_rows:
                archive_stmt = (
                    update(RequestLogEntity)
                    .where(RequestLogEntity.stats_archived == 0)
                    .where(
                        RequestLogEntity.lifecycle_status.in_(
                            REQUEST_LOG_TERMINAL_STATUSES
                        )
                    )
                )
                if not force:
                    archive_stmt = archive_stmt.where(
                        RequestLogEntity.created_at < today_start_utc
                    )
                await session.execute(archive_stmt.values(stats_archived=1))

            await session.commit()

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.runtime_channel_ids import protocol_config_id_from_runtime_channel_id
from app.models.protocols import RequestLogLifecycleStatus
from app.models.request_logs import RequestLogItem
from app.persistence.entities import RequestLogEntity, SettingEntity
from app.persistence.settings_keys import SETTING_STATS_TIME_ZONE
from app.persistence.stats_entities import (
    OverviewModelDailyStatsEntity,
    RequestLogDailyStatsEntity,
)

from .query import to_request_log
from .types import (
    REQUEST_LOG_RUNNING_STATUSES,
    REQUEST_LOG_TERMINAL_STATUSES,
    GatewayKeyPort,
    RuntimeTimeZone,
    SettingsPort,
    StatisticsPort,
)


def protocol_config_id_for_channel(channel_id: str | None) -> str | None:
    """Attribute a runtime channel ID to its protocol configuration."""
    if not channel_id:
        return None
    return protocol_config_id_from_runtime_channel_id(channel_id)


def gateway_key_spend_contribution(
    gateway_key_id: str | None,
    lifecycle_status: RequestLogLifecycleStatus | str,
    total_cost_usd: float,
) -> float:
    if not gateway_key_id:
        return 0.0
    lifecycle_value = (
        lifecycle_status.value
        if isinstance(lifecycle_status, RequestLogLifecycleStatus)
        else str(lifecycle_status)
    )
    if lifecycle_value not in REQUEST_LOG_TERMINAL_STATUSES:
        return 0.0
    return max(float(total_cost_usd), 0.0)


class RequestLogCommands:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        gateway_key_repo: GatewayKeyPort,
    ) -> None:
        self.session_factory = session_factory
        self.gateway_key_repo = gateway_key_repo

    async def create_pending_request_log(
        self,
        *,
        protocol: str,
        user_agent: str,
        requested_group_name: str | None,
        resolved_group_name: str | None,
        upstream_model_name: str | None,
        channel_id: str | None,
        channel_name: str | None,
        gateway_key_id: str | None,
        is_stream: bool,
        request_content: str | None = None,
    ) -> RequestLogItem:
        """Create a request log in the connecting lifecycle state."""
        return await self.create_request_log(
            protocol=protocol,
            user_agent=user_agent,
            requested_group_name=requested_group_name,
            resolved_group_name=resolved_group_name,
            upstream_model_name=upstream_model_name,
            channel_id=channel_id,
            channel_name=channel_name,
            gateway_key_id=gateway_key_id,
            status_code=None,
            success=False,
            lifecycle_status=RequestLogLifecycleStatus.CONNECTING,
            is_stream=is_stream,
            first_token_latency_ms=0,
            latency_ms=0,
            input_tokens=0,
            cache_read_input_tokens=0,
            cache_write_input_tokens=0,
            output_tokens=0,
            total_tokens=0,
            input_cost_usd=0.0,
            output_cost_usd=0.0,
            total_cost_usd=0.0,
            rate_multiplier=None,
            billing_mode="tokens",
            billing_units=0,
            request_content=request_content,
            response_content=None,
            attempts=[],
            error_message=None,
        )

    async def create_request_log(
        self,
        *,
        protocol: str,
        user_agent: str,
        requested_group_name: str | None,
        resolved_group_name: str | None,
        upstream_model_name: str | None,
        channel_id: str | None,
        channel_name: str | None,
        gateway_key_id: str | None,
        status_code: int | None,
        success: bool,
        lifecycle_status: RequestLogLifecycleStatus,
        is_stream: bool,
        first_token_latency_ms: int,
        latency_ms: int,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        input_cost_usd: float,
        output_cost_usd: float,
        total_cost_usd: float,
        rate_multiplier: float | None = None,
        billing_mode: str = "tokens",
        billing_units: int = 0,
        cache_read_input_tokens: int = 0,
        cache_write_input_tokens: int = 0,
        request_content: str | None = None,
        response_content: str | None = None,
        attempts: list[dict[str, Any]] | None = None,
        error_message: str | None = None,
    ) -> RequestLogItem:
        """Create and return a persisted request log."""
        item: RequestLogItem
        lifecycle_value = lifecycle_status.value
        async with self.session_factory() as session:
            entity = RequestLogEntity(
                protocol=protocol,
                user_agent=user_agent.strip()[:300],
                requested_group_name=requested_group_name,
                resolved_group_name=resolved_group_name,
                upstream_model_name=upstream_model_name,
                channel_id=channel_id,
                protocol_config_id=protocol_config_id_for_channel(channel_id),
                channel_name=channel_name,
                gateway_key_id=gateway_key_id,
                status_code=status_code,
                success=1 if success else 0,
                lifecycle_status=lifecycle_value,
                is_stream=1 if is_stream else 0,
                first_token_latency_ms=max(first_token_latency_ms, 0),
                latency_ms=latency_ms,
                input_tokens=max(input_tokens, 0),
                cache_read_input_tokens=max(cache_read_input_tokens, 0),
                cache_write_input_tokens=max(cache_write_input_tokens, 0),
                output_tokens=max(output_tokens, 0),
                total_tokens=max(total_tokens, 0),
                input_cost_usd=max(input_cost_usd, 0.0),
                output_cost_usd=max(output_cost_usd, 0.0),
                total_cost_usd=max(total_cost_usd, 0.0),
                rate_multiplier=max(float(rate_multiplier), 0.0)
                if rate_multiplier is not None
                else None,
                billing_mode=billing_mode,
                billing_units=max(billing_units, 0),
                request_content=request_content,
                response_content=response_content,
                attempts_json=json.dumps(attempts or [], ensure_ascii=True),
                error_message=error_message,
                stats_archived=0
                if lifecycle_value in REQUEST_LOG_TERMINAL_STATUSES
                else 1,
            )
            session.add(entity)
            await self.gateway_key_repo.adjust_spend(
                session,
                gateway_key_id,
                gateway_key_spend_contribution(
                    gateway_key_id, lifecycle_value, total_cost_usd
                ),
            )
            await session.commit()
            await session.refresh(entity)
            item = to_request_log(entity)
        return item

    async def update_request_log(
        self,
        log_id: int,
        *,
        protocol: str,
        user_agent: str,
        requested_group_name: str | None,
        resolved_group_name: str | None,
        upstream_model_name: str | None,
        channel_id: str | None,
        channel_name: str | None,
        gateway_key_id: str | None,
        status_code: int | None,
        success: bool,
        lifecycle_status: RequestLogLifecycleStatus,
        is_stream: bool,
        first_token_latency_ms: int,
        latency_ms: int,
        input_tokens: int = 0,
        cache_read_input_tokens: int = 0,
        cache_write_input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
        input_cost_usd: float = 0.0,
        output_cost_usd: float = 0.0,
        total_cost_usd: float = 0.0,
        rate_multiplier: float | None = None,
        billing_mode: str = "tokens",
        billing_units: int = 0,
        request_content: str | None = None,
        response_content: str | None = None,
        attempts: list[dict[str, Any]] | None = None,
        error_message: str | None = None,
    ) -> RequestLogItem | None:
        """Update and return an existing request log when present."""
        lifecycle_value = lifecycle_status.value
        async with self.session_factory() as session:
            entity = await session.get(RequestLogEntity, log_id)
            if entity is None:
                return None
            previous_gateway_key_id = entity.gateway_key_id
            previous_spend = gateway_key_spend_contribution(
                previous_gateway_key_id, entity.lifecycle_status, entity.total_cost_usd
            )
            entity.protocol = protocol
            entity.user_agent = user_agent.strip()[:300]
            entity.requested_group_name = requested_group_name
            entity.resolved_group_name = resolved_group_name
            entity.upstream_model_name = upstream_model_name
            entity.channel_id = channel_id
            entity.protocol_config_id = protocol_config_id_for_channel(channel_id)
            entity.channel_name = channel_name
            entity.gateway_key_id = gateway_key_id
            entity.status_code = status_code
            entity.success = 1 if success else 0
            entity.lifecycle_status = lifecycle_value
            entity.is_stream = 1 if is_stream else 0
            entity.first_token_latency_ms = max(first_token_latency_ms, 0)
            entity.latency_ms = max(latency_ms, 0)
            entity.input_tokens = max(input_tokens, 0)
            entity.cache_read_input_tokens = max(cache_read_input_tokens, 0)
            entity.cache_write_input_tokens = max(cache_write_input_tokens, 0)
            entity.output_tokens = max(output_tokens, 0)
            entity.total_tokens = max(total_tokens, 0)
            entity.input_cost_usd = max(input_cost_usd, 0.0)
            entity.output_cost_usd = max(output_cost_usd, 0.0)
            entity.total_cost_usd = max(total_cost_usd, 0.0)
            entity.rate_multiplier = (
                max(float(rate_multiplier), 0.0)
                if rate_multiplier is not None
                else None
            )
            entity.billing_mode = billing_mode
            entity.billing_units = max(billing_units, 0)
            entity.request_content = request_content
            entity.response_content = response_content
            entity.attempts_json = json.dumps(attempts or [], ensure_ascii=True)
            entity.error_message = error_message
            entity.stats_archived = (
                0 if lifecycle_value in REQUEST_LOG_TERMINAL_STATUSES else 1
            )
            next_spend = gateway_key_spend_contribution(
                gateway_key_id, lifecycle_value, total_cost_usd
            )
            if previous_gateway_key_id == gateway_key_id:
                await self.gateway_key_repo.adjust_spend(
                    session, gateway_key_id, next_spend - previous_spend
                )
            else:
                await self.gateway_key_repo.adjust_spend(
                    session, previous_gateway_key_id, -previous_spend
                )
                await self.gateway_key_repo.adjust_spend(
                    session, gateway_key_id, next_spend
                )
            await session.commit()
            await session.refresh(entity)
            return to_request_log(entity)

    async def update_request_log_runtime(
        self,
        log_id: int,
        *,
        first_token_latency_ms: int | None = None,
        latency_ms: int | None = None,
    ) -> None:
        """Update runtime latency fields for an existing request log."""
        async with self.session_factory() as session:
            entity = await session.get(RequestLogEntity, log_id)
            if entity is None:
                return
            if first_token_latency_ms is not None:
                entity.first_token_latency_ms = max(first_token_latency_ms, 0)
            if latency_ms is not None:
                entity.latency_ms = max(latency_ms, 0)
            await session.commit()


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
        """Archive terminal request logs into daily statistics."""
        runtime = await self.settings_repo.get_runtime_settings()
        now = datetime.now(UTC).replace(tzinfo=None)
        time_zone = self.runtime_time_zone(runtime)
        local_now = now.replace(tzinfo=UTC).astimezone(time_zone)
        today_key = local_now.strftime("%Y%m%d")
        today_start_utc = (
            local_now.replace(hour=0, minute=0, second=0, microsecond=0)
            .astimezone(UTC)
            .replace(tzinfo=None)
        )
        async with self.session_factory() as session:
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
                    RequestLogEntity.lifecycle_status
                    == RequestLogLifecycleStatus.SUCCEEDED.value
                )
                .where(model_expr.is_not(None))
                .order_by(RequestLogEntity.created_at.asc())
            )
            if not force:
                model_stmt = model_stmt.where(
                    RequestLogEntity.created_at < today_start_utc
                )
            model_rows = (await session.execute(model_stmt)).all()
            daily_buckets = self.daily_stats_by_local_bucket(daily_rows, time_zone)
            model_buckets = self.model_rows_by_local_bucket(
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


class RequestLogMaintenance:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings_repo: SettingsPort,
        statistics: StatisticsPort,
        runtime_time_zone: RuntimeTimeZone,
    ) -> None:
        self.session_factory = session_factory
        self.settings_repo = settings_repo
        self.statistics = statistics
        self.runtime_time_zone = runtime_time_zone

    async def clear_request_logs(self) -> None:
        """Archive statistics and delete all request logs."""
        await self.statistics.persist_request_log_stats(force=True)
        async with self.session_factory() as session:
            await session.execute(delete(RequestLogEntity))
            await session.commit()

    async def prune_request_logs(self) -> None:
        """Archive statistics and delete request logs beyond retention."""
        runtime = await self.settings_repo.get_runtime_settings()
        if not runtime["relay_log_keep_enabled"]:
            return
        await self.statistics.persist_request_log_stats(force=True)
        keep_days = int(runtime["relay_log_keep_period"])
        cutoff = self.statistics.request_log_prune_cutoff(
            keep_days=keep_days, time_zone=self.runtime_time_zone(runtime)
        )
        async with self.session_factory() as session:
            await session.execute(
                delete(RequestLogEntity).where(RequestLogEntity.created_at < cutoff)
            )
            await session.commit()

    async def fail_running_request_logs(self) -> None:
        """Mark request logs left running by an interruption as failed."""
        async with self.session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(RequestLogEntity).where(
                            RequestLogEntity.lifecycle_status.in_(
                                REQUEST_LOG_RUNNING_STATUSES
                            )
                        )
                    )
                )
                .scalars()
                .all()
            )
            for entity in rows:
                entity.lifecycle_status = RequestLogLifecycleStatus.FAILED.value
                entity.success = 0
                entity.status_code = None
                if not (entity.error_message or "").strip():
                    entity.error_message = (
                        "Request interrupted while the service was not running"
                    )
                entity.stats_archived = 0
            await session.commit()

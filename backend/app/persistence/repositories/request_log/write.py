from __future__ import annotations

import json

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.runtime_channel_ids import protocol_config_id_from_runtime_channel_id
from app.models.protocols import RequestLogLifecycleStatus
from app.models.request_logs import RequestLogInput, RequestLogItem
from app.persistence.entities import RequestLogEntity

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

    async def create_request_log(self, payload: RequestLogInput) -> RequestLogItem:
        """Create a log and record its initial spend in the same transaction."""
        async with self.session_factory() as session:
            entity = RequestLogEntity()
            _apply_request_log_fields(entity, payload)
            session.add(entity)
            await self.gateway_key_repo.adjust_spend(
                session,
                payload.gateway_key_id,
                gateway_key_spend_contribution(
                    payload.gateway_key_id,
                    payload.lifecycle_status,
                    payload.total_cost_usd,
                ),
            )
            await session.commit()
            await session.refresh(entity)
            return to_request_log(entity)

    async def update_request_log(
        self, log_id: int, payload: RequestLogInput
    ) -> RequestLogItem | None:
        """Replace a log and adjust only the change in its spend."""
        async with self.session_factory() as session:
            entity = await session.get(RequestLogEntity, log_id)
            if entity is None:
                return None
            previous_gateway_key_id = entity.gateway_key_id
            previous_spend = gateway_key_spend_contribution(
                previous_gateway_key_id, entity.lifecycle_status, entity.total_cost_usd
            )
            _apply_request_log_fields(entity, payload)
            entity.latency_ms = max(payload.latency_ms, 0)
            next_spend = gateway_key_spend_contribution(
                payload.gateway_key_id, payload.lifecycle_status, payload.total_cost_usd
            )
            if previous_gateway_key_id == payload.gateway_key_id:
                await self.gateway_key_repo.adjust_spend(
                    session, payload.gateway_key_id, next_spend - previous_spend
                )
            else:
                await self.gateway_key_repo.adjust_spend(
                    session, previous_gateway_key_id, -previous_spend
                )
                await self.gateway_key_repo.adjust_spend(
                    session, payload.gateway_key_id, next_spend
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


def _apply_request_log_fields(
    entity: RequestLogEntity, payload: RequestLogInput
) -> None:
    entity.protocol = payload.protocol
    entity.user_agent = payload.user_agent.strip()[:300]
    entity.requested_group_name = payload.requested_group_name
    entity.resolved_group_name = payload.resolved_group_name
    entity.upstream_model_name = payload.upstream_model_name
    entity.channel_id = payload.channel_id
    entity.protocol_config_id = protocol_config_id_for_channel(payload.channel_id)
    entity.channel_name = payload.channel_name
    entity.gateway_key_id = payload.gateway_key_id
    entity.status_code = payload.status_code
    entity.success = 1 if payload.success else 0
    entity.lifecycle_status = payload.lifecycle_status.value
    entity.is_stream = 1 if payload.is_stream else 0
    entity.first_token_latency_ms = max(payload.first_token_latency_ms, 0)
    entity.latency_ms = payload.latency_ms
    entity.input_tokens = max(payload.input_tokens, 0)
    entity.image_input_tokens = max(payload.image_input_tokens, 0)
    entity.cache_read_input_tokens = max(payload.cache_read_input_tokens, 0)
    entity.cache_write_input_tokens = max(payload.cache_write_input_tokens, 0)
    entity.output_tokens = max(payload.output_tokens, 0)
    entity.total_tokens = max(payload.total_tokens, 0)
    entity.input_cost_usd = max(payload.input_cost_usd, 0.0)
    entity.output_cost_usd = max(payload.output_cost_usd, 0.0)
    entity.total_cost_usd = max(payload.total_cost_usd, 0.0)
    entity.rate_multiplier = (
        max(float(payload.rate_multiplier), 0.0)
        if payload.rate_multiplier is not None
        else None
    )
    entity.billing_mode = payload.billing_mode
    entity.billing_units = max(payload.billing_units, 0)
    entity.request_content = payload.request_content
    entity.response_content = payload.response_content
    entity.attempts_json = json.dumps(payload.attempts or [], ensure_ascii=True)
    entity.error_message = payload.error_message
    entity.stats_archived = (
        0 if payload.lifecycle_status.value in REQUEST_LOG_TERMINAL_STATUSES else 1
    )

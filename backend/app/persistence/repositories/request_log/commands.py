from __future__ import annotations

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.protocols import RequestLogLifecycleStatus
from app.models.request_logs import RequestLogItem
from app.persistence.entities import RequestLogEntity
from app.persistence.request_log_constants import REQUEST_LOG_TERMINAL_STATUSES

from .dto_mapping import to_request_log
from .ports import GatewayKeyPort


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

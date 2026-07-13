from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..shared import (
    Any,
    REQUEST_LOG_TERMINAL_STATUSES,
    RequestLogEntity,
    RequestLogItem,
    RequestLogLifecycleStatus,
    json,
)


class _RequestLogUpdateMixin:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

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
        request_content: str | None = None,
        response_content: str | None = None,
        attempts: list[dict[str, Any]] | None = None,
        error_message: str | None = None,
    ) -> RequestLogItem | None:
        """Update and return an existing request log when present."""
        lifecycle_value = lifecycle_status.value
        async with self._session_factory() as session:
            entity = await session.get(RequestLogEntity, log_id)
            if entity is None:
                return None
            previous_gateway_key_id = entity.gateway_key_id
            previous_spend = self._gateway_key_spend_contribution(
                previous_gateway_key_id,
                entity.lifecycle_status,
                entity.total_cost_usd,
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
            entity.request_content = request_content
            entity.response_content = response_content
            entity.attempts_json = json.dumps(attempts or [], ensure_ascii=True)
            entity.error_message = error_message
            entity.stats_archived = (
                0 if lifecycle_value in REQUEST_LOG_TERMINAL_STATUSES else 1
            )
            next_spend = self._gateway_key_spend_contribution(
                gateway_key_id,
                lifecycle_value,
                total_cost_usd,
            )
            if previous_gateway_key_id == gateway_key_id:
                await self._gateway_key_repo._adjust_gateway_key_spend(
                    session,
                    gateway_key_id,
                    next_spend - previous_spend,
                )
            else:
                await self._gateway_key_repo._adjust_gateway_key_spend(
                    session,
                    previous_gateway_key_id,
                    -previous_spend,
                )
                await self._gateway_key_repo._adjust_gateway_key_spend(
                    session,
                    gateway_key_id,
                    next_spend,
                )
            await session.commit()
            await session.refresh(entity)
            return self._to_request_log(entity)

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


class _RequestLogCreateMixin:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

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
        async with self._session_factory() as session:
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
                request_content=request_content,
                response_content=response_content,
                attempts_json=json.dumps(attempts or [], ensure_ascii=True),
                error_message=error_message,
                stats_archived=(
                    0 if lifecycle_value in REQUEST_LOG_TERMINAL_STATUSES else 1
                ),
            )
            session.add(entity)
            await self._gateway_key_repo._adjust_gateway_key_spend(
                session,
                gateway_key_id,
                self._gateway_key_spend_contribution(
                    gateway_key_id,
                    lifecycle_value,
                    total_cost_usd,
                ),
            )
            await session.commit()
            await session.refresh(entity)
            item = self._to_request_log(entity)
        return item

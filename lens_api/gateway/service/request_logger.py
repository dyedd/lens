from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...models import (
    ChannelConfig,
    GatewayApiKey,
    ProtocolKind,
    RequestLogLifecycleStatus,
)
from .runtime_types import (
    AttemptLog,
    UpstreamResult,
    _attempt_logs_to_dicts,
)
from .app_state import app_state
from .routing_plan import _elapsed_ms


@dataclass(slots=True)
class _RequestLogger:
    request_log_id: int
    protocol: ProtocolKind
    gateway_key: GatewayApiKey
    started_at: float
    body: dict[str, Any]
    request_content: str | None
    attempts: list[AttemptLog]

    async def update(
        self,
        *,
        requested_group_name: str | None,
        resolved_group_name: str | None,
        upstream_model_name: str | None,
        channel: ChannelConfig | None,
        user_agent: str,
        lifecycle_status: RequestLogLifecycleStatus,
        status_code: int | None,
        success: bool,
        is_stream: bool,
        first_token_latency_ms: int = 0,
        request_content: str | None = None,
        response_content: str | None = None,
        error_message: str | None = None,
        result: UpstreamResult | None = None,
    ) -> None:
        kwargs: dict[str, Any] = {}
        if result is not None:
            kwargs.update(
                input_tokens=result.input_tokens,
                cache_read_input_tokens=result.cache_read_input_tokens,
                cache_write_input_tokens=result.cache_write_input_tokens,
                output_tokens=result.output_tokens,
                total_tokens=result.total_tokens,
                input_cost_usd=result.input_cost_usd,
                output_cost_usd=result.output_cost_usd,
                total_cost_usd=result.total_cost_usd,
            )
        await _update_request_log(
            self.request_log_id,
            protocol=self.protocol,
            requested_group_name=requested_group_name,
            resolved_group_name=resolved_group_name,
            upstream_model_name=upstream_model_name,
            channel_id=channel.id if channel else None,
            channel_name=channel.name if channel else None,
            gateway_key=self.gateway_key,
            user_agent=user_agent,
            lifecycle_status=lifecycle_status,
            status_code=status_code,
            success=success,
            is_stream=is_stream,
            first_token_latency_ms=first_token_latency_ms,
            latency_ms=_elapsed_ms(self.started_at),
            request_content=(
                request_content if request_content is not None else self.request_content
            ),
            response_content=response_content,
            attempts=_attempt_logs_to_dicts(self.attempts),
            error_message=error_message,
            **kwargs,
        )


async def _update_request_log(
    request_log_id: int,
    *,
    protocol: ProtocolKind,
    requested_group_name: str | None,
    resolved_group_name: str | None,
    upstream_model_name: str | None,
    channel_id: str | None,
    channel_name: str | None,
    gateway_key: GatewayApiKey,
    user_agent: str,
    lifecycle_status: RequestLogLifecycleStatus,
    status_code: int | None,
    success: bool,
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
    error_message: str | None,
) -> None:
    await app_state.request_log_store.update_request_log(
        request_log_id,
        protocol=protocol.value,
        requested_group_name=requested_group_name,
        resolved_group_name=resolved_group_name,
        upstream_model_name=upstream_model_name,
        channel_id=channel_id,
        channel_name=channel_name,
        gateway_key_id=gateway_key.id,
        user_agent=user_agent,
        status_code=status_code,
        success=success,
        lifecycle_status=lifecycle_status,
        is_stream=is_stream,
        first_token_latency_ms=first_token_latency_ms,
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        cache_read_input_tokens=cache_read_input_tokens,
        cache_write_input_tokens=cache_write_input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        input_cost_usd=input_cost_usd,
        output_cost_usd=output_cost_usd,
        total_cost_usd=total_cost_usd,
        request_content=request_content,
        response_content=response_content,
        attempts=attempts,
        error_message=error_message,
    )

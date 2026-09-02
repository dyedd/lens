from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...models.channels import ChannelConfig
from ...models.gateway_keys import GatewayApiKey
from ...models.protocols import ProtocolKind, RequestLogLifecycleStatus
from .app_state import app_state
from .routing_plan import _elapsed_ms
from .runtime_types import (
    AttemptLog,
    UpstreamResult,
    _attempt_logs_to_dicts,
)


@dataclass(slots=True)
class _RequestLogger:
    """Sole writer of one request-log row across its lifecycle.

    Holds the request-scoped context (route names, user agent, last target) so
    lifecycle methods can derive most columns instead of every caller passing
    the full row each transition. Each write is a full-row update; buffering
    writes in memory is a separate, profile-gated decision.
    """

    request_log_id: int
    protocol: ProtocolKind
    gateway_key: GatewayApiKey
    started_at: float
    body: dict[str, Any]
    request_content: str | None
    attempts: list[AttemptLog]
    user_agent: str
    requested_group_name: str | None = None
    resolved_group_name: str | None = None
    rate_multiplier: float | None = None
    last_channel: ChannelConfig | None = None

    def plan_route(
        self, *, requested_group_name: str | None, resolved_group_name: str | None
    ) -> None:
        """Record the route decision reported by later lifecycle writes."""
        self.requested_group_name = requested_group_name
        self.resolved_group_name = resolved_group_name

    async def connecting(
        self,
        *,
        is_stream: bool,
        upstream_model_name: str | None = None,
        channel: ChannelConfig | None = None,
        user_agent: str | None = None,
        rate_multiplier: float | None = None,
        request_content: str | None = None,
    ) -> None:
        if user_agent is not None:
            self.user_agent = user_agent
        if rate_multiplier is not None:
            self.rate_multiplier = rate_multiplier
        await self._write(
            upstream_model_name=upstream_model_name,
            channel=channel,
            lifecycle_status=RequestLogLifecycleStatus.CONNECTING,
            status_code=None,
            success=False,
            is_stream=is_stream,
            rate_multiplier=rate_multiplier,
            request_content=request_content,
        )

    async def failed(
        self,
        *,
        status_code: int,
        error_message: str,
        is_stream: bool,
        channel: ChannelConfig | None = None,
        user_agent: str | None = None,
        rate_multiplier: float | None = None,
        upstream_model_name: str | None = None,
        request_content: str | None = None,
        first_token_latency_ms: int = 0,
    ) -> None:
        if user_agent is not None:
            self.user_agent = user_agent
        await self._write(
            upstream_model_name=upstream_model_name,
            channel=channel,
            lifecycle_status=RequestLogLifecycleStatus.FAILED,
            status_code=status_code,
            success=False,
            is_stream=is_stream,
            rate_multiplier=rate_multiplier,
            first_token_latency_ms=first_token_latency_ms,
            request_content=request_content,
            error_message=error_message,
        )

    async def streaming(
        self,
        *,
        upstream_model_name: str | None,
        status_code: int,
        first_token_latency_ms: int,
        request_content: str | None,
        channel: ChannelConfig,
        user_agent: str,
        rate_multiplier: float | None,
    ) -> None:
        if user_agent is not None:
            self.user_agent = user_agent
        if rate_multiplier is not None:
            self.rate_multiplier = rate_multiplier
        await self._write(
            upstream_model_name=upstream_model_name,
            channel=channel,
            lifecycle_status=RequestLogLifecycleStatus.STREAMING,
            status_code=status_code,
            success=False,
            is_stream=True,
            rate_multiplier=rate_multiplier,
            first_token_latency_ms=first_token_latency_ms,
            request_content=request_content,
        )

    async def succeeded(
        self,
        *,
        upstream_model_name: str | None,
        status_code: int,
        first_token_latency_ms: int,
        request_content: str | None,
        response_content: str | None,
        result: UpstreamResult,
        channel: ChannelConfig,
        user_agent: str,
        rate_multiplier: float | None,
    ) -> None:
        if user_agent is not None:
            self.user_agent = user_agent
        if rate_multiplier is not None:
            self.rate_multiplier = rate_multiplier
        await self._write(
            upstream_model_name=upstream_model_name,
            channel=channel,
            lifecycle_status=RequestLogLifecycleStatus.SUCCEEDED,
            status_code=status_code,
            success=True,
            is_stream=False,
            rate_multiplier=rate_multiplier,
            first_token_latency_ms=first_token_latency_ms,
            request_content=request_content,
            response_content=response_content,
            result=result,
        )

    async def _write(
        self,
        *,
        upstream_model_name: str | None,
        channel: ChannelConfig | None,
        lifecycle_status: RequestLogLifecycleStatus,
        status_code: int | None,
        success: bool,
        is_stream: bool,
        rate_multiplier: float | None,
        first_token_latency_ms: int = 0,
        request_content: str | None = None,
        response_content: str | None = None,
        error_message: str | None = None,
        result: UpstreamResult | None = None,
    ) -> None:
        if channel is not None:
            self.last_channel = channel
        else:
            channel = self.last_channel
        kwargs: dict[str, Any] = {"rate_multiplier": rate_multiplier}
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
                billing_mode=result.billing_mode,
                billing_units=result.billing_units,
            )
        await _update_request_log(
            self.request_log_id,
            protocol=self.protocol,
            requested_group_name=self.requested_group_name,
            resolved_group_name=self.resolved_group_name,
            upstream_model_name=upstream_model_name,
            channel_id=channel.id if channel else None,
            channel_name=channel.name if channel else None,
            gateway_key=self.gateway_key,
            user_agent=self.user_agent,
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
    rate_multiplier: float | None = None,
    input_tokens: int = 0,
    cache_read_input_tokens: int = 0,
    cache_write_input_tokens: int = 0,
    output_tokens: int = 0,
    total_tokens: int = 0,
    input_cost_usd: float = 0.0,
    output_cost_usd: float = 0.0,
    total_cost_usd: float = 0.0,
    billing_mode: str = "tokens",
    billing_units: int = 0,
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
        rate_multiplier=rate_multiplier,
        billing_mode=billing_mode,
        billing_units=billing_units,
        request_content=request_content,
        response_content=response_content,
        attempts=attempts,
        error_message=error_message,
    )

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...models.channels import ChannelConfig
from ...models.gateway_keys import GatewayApiKey
from ...models.protocols import ProtocolKind, RequestLogLifecycleStatus
from ...models.request_logs import RequestLogInput
from .app_state import app_state
from .routing_plan import elapsed_ms
from .runtime_types import (
    AttemptLog,
    UpstreamResult,
    attempt_logs_to_dicts,
)


@dataclass(slots=True)
class RequestLogger:
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

    async def record_connecting(
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

    async def record_failure(
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

    async def record_streaming(
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

    async def record_success(
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
        payload = RequestLogInput(
            protocol=self.protocol.value,
            requested_group_name=self.requested_group_name,
            resolved_group_name=self.resolved_group_name,
            upstream_model_name=upstream_model_name,
            channel_id=channel.id if channel else None,
            channel_name=channel.name if channel else None,
            gateway_key_id=self.gateway_key.id,
            user_agent=self.user_agent,
            lifecycle_status=lifecycle_status,
            status_code=status_code,
            success=success,
            is_stream=is_stream,
            first_token_latency_ms=first_token_latency_ms,
            latency_ms=elapsed_ms(self.started_at),
            request_content=(
                request_content if request_content is not None else self.request_content
            ),
            response_content=response_content,
            attempts=attempt_logs_to_dicts(self.attempts),
            error_message=error_message,
            rate_multiplier=rate_multiplier,
        )
        if result is not None:
            payload.input_tokens = result.input_tokens
            payload.image_input_tokens = result.image_input_tokens
            payload.cache_read_input_tokens = result.cache_read_input_tokens
            payload.cache_write_input_tokens = result.cache_write_input_tokens
            payload.output_tokens = result.output_tokens
            payload.total_tokens = result.total_tokens
            payload.input_cost_usd = result.input_cost_usd
            payload.output_cost_usd = result.output_cost_usd
            payload.total_cost_usd = result.total_cost_usd
            payload.billing_mode = result.billing_mode
            payload.billing_units = result.billing_units
        await app_state.request_log_store.commands.update_request_log(
            self.request_log_id, payload
        )

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping
from time import perf_counter
from typing import Any

import httpx
from fastapi import Response
from fastapi.responses import StreamingResponse

from ...core.config import settings
from ...models import ChannelConfig, ProtocolKind, RequestLogLifecycleStatus
from ..converters import convert_response, convert_stream_iterator, needs_conversion
from ..router import RouteTarget
from ..upstream_request import build_upstream_request, resolve_upstream_proxy_url
from .runtime_types import (
    AttemptLog,
    RoutingPlan,
    StreamCapture,
    UpstreamRequestError,
    UpstreamResult,
    _RequestDeadline,
)
from .app_state import app_state
from .errors import _protocol_error_response
from .upstream_support import (
    _format_channel_error,
    _format_http_response_error,
    _format_transport_error,
    _passthrough_headers,
    _resolve_http_client,
)
from .payload_serialization import (
    _decode_content_bytes,
    _decode_log_content_bytes,
    _dump_log_json,
    _json_body_bytes,
)
from .request_logger import _RequestLogger
from .stream_logging import (
    _cancel_stream_capture,
    _capture_converted_stream_iterator,
    _safe_estimate_cost,
    _stream_upstream_iterator,
)
from .stream_restore import _distill_stream_response_content
from .response_usage import _extract_response_usage
from .usage import _extract_stream_usage
from .routing_plan import (
    _deadline_scope,
    _elapsed_ms,
    _extract_request_reasoning_effort,
    _is_request_too_large_error,
    _request_body_too_large_message,
)


async def _record_target_failure(
    *,
    target: RouteTarget,
    channel: ChannelConfig,
    runtime: dict[str, Any],
    log_ctx: _RequestLogger,
    plan: RoutingPlan,
    errors: list[str],
    failure_status_codes: list[int | None],
    attempt_started_at: float,
    effective_user_agent: str,
    upstream_body: dict[str, Any],
    request_content: str | None = None,
    exc: UpstreamRequestError,
) -> Response | None:
    message = _format_channel_error(exc.detail)
    log_body_enabled = bool(runtime["relay_log_body_enabled"])
    if not exc.skip_route_failure and not _is_request_too_large_error(
        exc.status_code, message
    ):
        app_state.router.record_failure(
            channel.id,
            message,
            status_code=exc.router_status_code,
            credential_id=target.credential_id,
            channel_keys=channel.keys,
            threshold=int(runtime["circuit_breaker_threshold"]),
            cooldown_seconds=int(runtime["circuit_breaker_cooldown"]),
            max_cooldown_seconds=int(runtime["circuit_breaker_max_cooldown"]),
        )
    errors.append(message)
    failure_status_codes.append(exc.status_code)
    log_ctx.attempts.append(
        AttemptLog(
            channel_id=channel.id,
            channel_name=channel.name,
            credential_id=target.credential_id,
            credential_name=target.credential_name or "",
            model_name=target.model_name,
            status_code=exc.status_code,
            success=False,
            duration_ms=_elapsed_ms(attempt_started_at),
            error_message=message,
            reasoning_effort=_extract_request_reasoning_effort(
                log_ctx.body, upstream_body
            ),
        )
    )
    await log_ctx.update(
        requested_group_name=plan.requested_group_name,
        resolved_group_name=plan.resolved_group_name,
        upstream_model_name=None,
        channel=channel,
        user_agent=effective_user_agent,
        lifecycle_status=RequestLogLifecycleStatus.FAILED,
        status_code=exc.status_code,
        success=False,
        is_stream=bool(upstream_body.get("stream")),
        request_content=(
            exc.request_content
            if exc.request_content is not None
            else (
                request_content
                if request_content is not None
                else (_dump_log_json(upstream_body) if log_body_enabled else None)
            )
        ),
        error_message=message,
    )
    if exc.stop_fallback:
        return _protocol_error_response(
            protocol=log_ctx.protocol,
            status_code=exc.status_code,
            error_type=exc.error_type,
            message=message,
        )
    return None

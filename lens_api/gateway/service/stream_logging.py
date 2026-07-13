from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from ...core.config import settings
from ...models import (
    ChannelConfig,
    GatewayApiKey,
    ProtocolKind,
    RequestLogLifecycleStatus,
)
from ..converters import needs_conversion
from .runtime_types import StreamCapture, UpstreamResult, _RequestDeadline
from .app_state import app_state, logger
from .upstream_support import _format_channel_error
from .routing_plan import _elapsed_ms
from .stream_restore import _distill_stream_response_content
from .usage import (
    _EMPTY_USAGE,
    _describe_stream_capture_issue,
    _extract_stream_usage,
    _extract_usage_from_payload,
    _normalize_event_stream_newlines,
    _parse_sse_payloads,
)
from .payload_serialization import _stringify_text_content
from .request_logger import _update_request_log
from .stream_types import parse_chat_stream_payload, parse_anthropic_stream_payload


from .stream_detection import _cancel_stream_capture, _mark_stream_first_chunk


async def _safe_estimate_cost(
    model_name: str | None,
    input_tokens: int,
    output_tokens: int,
    cache_read_input_tokens: int = 0,
    cache_write_input_tokens: int = 0,
) -> tuple[float, float, float]:
    try:
        return await app_state.model_price_repo.estimate_model_cost(
            model_name,
            input_tokens,
            output_tokens,
            cache_read_input_tokens,
            cache_write_input_tokens,
        )
    except Exception:
        logger.exception("Failed to estimate model cost")
        return (0.0, 0.0, 0.0)


async def _record_stream_request_log(
    *,
    request_log_id: int,
    protocol: ProtocolKind,
    requested_group_name: str | None,
    resolved_group_name: str | None,
    channel: ChannelConfig,
    gateway_key: GatewayApiKey,
    user_agent: str,
    started_at: float,
    result: UpstreamResult,
    attempts: list[dict[str, Any]],
) -> None:
    capture = result.stream_capture
    if capture is not None and capture.first_token_update_task is not None:
        await capture.first_token_update_task
    raw_content = (
        _join_stream_chunks(capture.response_content_chunks)
        if capture is not None and capture.capture_body
        else result.response_content
    )
    if capture is not None:
        capture.response_content_chunks.clear()
    response_protocol = channel.protocol
    response_raw_content = raw_content
    client_response_content = (
        _join_stream_chunks(capture.client_response_content_chunks)
        if capture is not None and capture.capture_body
        else None
    )
    if capture is not None:
        capture.client_response_content_chunks.clear()
    if (
        capture is not None
        and needs_conversion(protocol, channel.protocol)
        and client_response_content
    ):
        response_protocol = protocol
        response_raw_content = client_response_content
    parse_errors = capture.parse_errors if capture is not None else None
    if raw_content:
        try:
            parsed = _extract_stream_usage(
                channel.protocol, raw_content, parse_errors=parse_errors
            )
        except ValueError as exc:
            if capture is not None:
                capture.parse_errors.append(str(exc))
            parsed = _stream_capture_usage(capture)
    else:
        parsed = _stream_capture_usage(capture)
    try:
        distilled_content = _distill_stream_response_content(
            response_protocol, response_raw_content
        )
    except ValueError as exc:
        if capture is not None:
            capture.parse_errors.append(str(exc))
        distilled_content = response_raw_content
    capture_issue = _describe_stream_capture_issue(
        channel.protocol, capture, raw_content
    )
    upstream_model_name = parsed["resolved_model"] or result.upstream_model_name
    input_tokens = parsed["input_tokens"]
    cache_read_input_tokens = parsed["cache_read_input_tokens"]
    cache_write_input_tokens = parsed["cache_write_input_tokens"]
    output_tokens = parsed["output_tokens"]
    total_tokens = parsed["total_tokens"]
    first_token_latency_ms = (
        capture.first_token_latency_ms
        if capture is not None
        else result.first_token_latency_ms
    )
    latency_ms = _elapsed_ms(started_at)
    status_code = _stream_log_status_code(result, capture, capture_issue)
    attempt_logs = [dict(item) for item in attempts]
    if attempt_logs and attempt_logs[-1].get("success"):
        attempt_logs[-1]["duration_ms"] = (
            latency_ms if capture_issue is not None else first_token_latency_ms
        )
        if capture_issue is not None:
            attempt_logs[-1]["success"] = False
            attempt_logs[-1]["error_message"] = capture_issue
            if status_code != result.status_code:
                attempt_logs[-1]["status_code"] = status_code
    await _record_stream_route_health(
        channel=channel,
        capture=capture,
        capture_issue=capture_issue,
        attempts=attempt_logs,
    )
    (
        input_cost_usd,
        output_cost_usd,
        total_cost_usd,
    ) = await _safe_estimate_cost(
        resolved_group_name,
        input_tokens,
        output_tokens,
        cache_read_input_tokens,
        cache_write_input_tokens,
    )
    await _update_request_log(
        request_log_id,
        protocol=protocol,
        requested_group_name=requested_group_name,
        resolved_group_name=resolved_group_name,
        upstream_model_name=upstream_model_name,
        channel_id=channel.id,
        channel_name=channel.name,
        gateway_key=gateway_key,
        user_agent=user_agent,
        lifecycle_status=(
            RequestLogLifecycleStatus.FAILED
            if capture_issue is not None
            else RequestLogLifecycleStatus.SUCCEEDED
        ),
        status_code=status_code,
        success=capture_issue is None,
        is_stream=True,
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
        request_content=result.request_content,
        response_content=distilled_content,
        attempts=attempt_logs,
        error_message=capture_issue,
    )


async def _record_stream_route_health(
    *,
    channel: ChannelConfig,
    capture: StreamCapture | None,
    capture_issue: str | None,
    attempts: list[dict[str, Any]],
) -> None:
    credential_id = _last_attempt_credential_id(attempts)
    if capture_issue is None:
        app_state.router.record_success(channel.id, credential_id=credential_id)
        return
    if _is_client_stream_disconnect(capture):
        return

    try:
        runtime = await app_state.settings_repo.get_runtime_settings()
        app_state.router.record_failure(
            channel.id,
            _format_channel_error(capture_issue),
            status_code=capture.error_status_code if capture is not None else None,
            credential_id=credential_id,
            channel_keys=channel.keys,
            threshold=int(runtime["circuit_breaker_threshold"]),
            cooldown_seconds=int(runtime["circuit_breaker_cooldown"]),
            max_cooldown_seconds=int(runtime["circuit_breaker_max_cooldown"]),
        )
    except Exception:
        logger.warning("Failed to update stream route health", exc_info=True)


def _last_attempt_credential_id(attempts: list[dict[str, Any]]) -> str | None:
    if not attempts:
        return None
    credential_id = attempts[-1].get("credential_id")
    return credential_id if isinstance(credential_id, str) and credential_id else None


def _is_client_stream_disconnect(capture: StreamCapture | None) -> bool:
    if capture is None or not capture.is_client_disconnected:
        return False
    upstream_errors = [
        error for error in capture.errors if error and error != "client disconnected"
    ]
    return not upstream_errors and not capture.parse_errors


def _stream_log_status_code(
    result: UpstreamResult, capture: StreamCapture | None, capture_issue: str | None
) -> int:
    if capture_issue is None:
        return result.status_code
    if capture is not None and capture.error_status_code is not None:
        return capture.error_status_code
    return result.status_code


from .stream_transport import (
    _capture_converted_stream_iterator,
    _stream_upstream_iterator,
)
from .stream_events import (
    _capture_stream_event_chunk,
    _flush_stream_event_buffer,
    _join_stream_chunks,
    _stream_capture_usage,
)

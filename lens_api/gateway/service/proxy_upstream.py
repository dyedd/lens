from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping
from time import perf_counter
from typing import Any

import httpx
from fastapi import Response
from fastapi.responses import StreamingResponse

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


async def _build_anthropic_sse_to_json_result(
    response: httpx.Response,
    channel: ChannelConfig,
    pricing_group_name: str | None,
    request_content: str | None,
    log_body_enabled: bool,
) -> UpstreamResult:
    content = (
        response.content if hasattr(response, "content") else await response.aread()
    )
    raw_content = _decode_content_bytes(content)
    try:
        parsed = _extract_stream_usage(channel.protocol, raw_content)
    except ValueError as exc:
        raise UpstreamRequestError(
            status_code=502,
            detail=f"Invalid upstream usage: {exc}",
            router_status_code=502,
        ) from exc
    try:
        distilled_content = _distill_stream_response_content(
            channel.protocol, raw_content
        )
    except ValueError as exc:
        raise UpstreamRequestError(
            status_code=502,
            detail=f"Invalid upstream response: {exc}",
            router_status_code=502,
        ) from exc
    response_headers = _passthrough_headers(response.headers)
    media_type = response.headers.get("content-type")
    response_content = raw_content

    if distilled_content and distilled_content != raw_content:
        content = distilled_content.encode("utf-8")
        response_content = distilled_content
        media_type = "application/json"
        response_headers.pop("content-type", None)

    cost = await _safe_estimate_cost(
        pricing_group_name,
        parsed["input_tokens"],
        parsed["output_tokens"],
        parsed["cache_read_input_tokens"],
        parsed["cache_write_input_tokens"],
    )
    return UpstreamResult(
        response=Response(
            content=content,
            status_code=response.status_code,
            media_type=media_type,
            headers=response_headers,
        ),
        status_code=response.status_code,
        is_stream=False,
        upstream_model_name=parsed["resolved_model"],
        input_tokens=parsed["input_tokens"],
        cache_read_input_tokens=parsed["cache_read_input_tokens"],
        cache_write_input_tokens=parsed["cache_write_input_tokens"],
        output_tokens=parsed["output_tokens"],
        total_tokens=parsed["total_tokens"],
        input_cost_usd=cost[0],
        output_cost_usd=cost[1],
        total_cost_usd=cost[2],
        request_content=request_content,
        response_content=response_content if log_body_enabled else None,
    )


async def _build_stream_result(
    response: httpx.Response,
    channel: ChannelConfig,
    client_protocol: ProtocolKind | None,
    body: dict[str, Any],
    request_content: str | None,
    stream_started_at: float,
    log_body_enabled: bool,
    *,
    deadline: _RequestDeadline,
) -> UpstreamResult:
    chat_expected_choices = body.get("n", 1)
    if (
        isinstance(chat_expected_choices, bool)
        or not isinstance(chat_expected_choices, int)
        or chat_expected_choices < 1
    ):
        chat_expected_choices = 1
    capture = StreamCapture(
        capture_body=log_body_enabled,
        chat_expected_choices=chat_expected_choices,
        deadline=deadline,
    )
    raw_iter = _stream_upstream_iterator(
        response,
        channel.protocol,
        capture,
        stream_started_at,
    )

    if client_protocol is not None and needs_conversion(
        client_protocol, channel.protocol
    ):
        converted_iter = convert_stream_iterator(
            client_protocol, channel.protocol, raw_iter, body.get("model", "")
        )
        converted_iter = _capture_converted_stream_iterator(converted_iter, capture)
        stream_media = "text/event-stream"
    else:
        converted_iter = raw_iter
        stream_media = response.headers.get("content-type")

    converted_iter = _stream_client_iterator(converted_iter, capture)

    return UpstreamResult(
        response=StreamingResponse(
            converted_iter,
            status_code=response.status_code,
            media_type=stream_media,
            headers=_passthrough_headers(response.headers),
        ),
        is_stream=True,
        status_code=response.status_code,
        first_token_latency_ms=capture.first_token_latency_ms,
        upstream_model_name=body.get("model"),
        request_content=request_content,
        stream_capture=capture,
    )


async def _stream_client_iterator(
    stream: AsyncIterator[bytes],
    capture: StreamCapture,
) -> AsyncIterator[bytes]:
    is_finished = False
    try:
        async for chunk in stream:
            yield chunk
        is_finished = True
    except asyncio.CancelledError:
        await _cancel_stream_capture(capture, "client disconnected")
        raise
    finally:
        if not is_finished and not capture.is_client_disconnected:
            await _cancel_stream_capture(capture, "client disconnected")


async def _build_json_result(
    response: httpx.Response,
    channel: ChannelConfig,
    client_protocol: ProtocolKind | None,
    body: dict[str, Any],
    pricing_group_name: str | None,
    request_content: str | None,
    log_body_enabled: bool,
) -> UpstreamResult:
    content = (
        response.content if hasattr(response, "content") else await response.aread()
    )
    try:
        parsed = _extract_response_usage(
            channel.protocol, response, fallback_model=body.get("model")
        )
    except ValueError as exc:
        raise UpstreamRequestError(
            status_code=502,
            detail=f"Invalid upstream usage: {exc}",
            router_status_code=502,
        ) from exc
    if client_protocol is not None and needs_conversion(
        client_protocol, channel.protocol
    ):
        content = convert_response(
            client_protocol, channel.protocol, content, body.get("model", "")
        )

    cost = await _safe_estimate_cost(
        pricing_group_name,
        parsed["input_tokens"],
        parsed["output_tokens"],
        parsed["cache_read_input_tokens"],
        parsed["cache_write_input_tokens"],
    )
    return UpstreamResult(
        response=Response(
            content=content,
            status_code=response.status_code,
            media_type=response.headers.get("content-type"),
            headers=_passthrough_headers(response.headers),
        ),
        status_code=response.status_code,
        is_stream=False,
        upstream_model_name=parsed["resolved_model"],
        input_tokens=parsed["input_tokens"],
        cache_read_input_tokens=parsed["cache_read_input_tokens"],
        cache_write_input_tokens=parsed["cache_write_input_tokens"],
        output_tokens=parsed["output_tokens"],
        total_tokens=parsed["total_tokens"],
        input_cost_usd=cost[0],
        output_cost_usd=cost[1],
        total_cost_usd=cost[2],
        request_content=request_content,
        response_content=(
            _decode_log_content_bytes(content) if log_body_enabled else None
        ),
    )


from .target_failure import _record_target_failure
from .upstream_execution import _call_channel, _prepare_channel_request

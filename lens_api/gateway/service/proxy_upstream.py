from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping
from time import perf_counter
from typing import Any

import httpx
from fastapi import Response

from ...models import ChannelConfig, ProtocolKind
from ..converters import convert_response, convert_stream_iterator, needs_conversion
from ..upstream_request import build_upstream_request, resolve_upstream_proxy_url
from .runtime_types import (
    StreamCapture,
    UpstreamRequestError,
    UpstreamResult,
    _RequestDeadline,
    _record_stream_error,
)
from .app_state import app_state
from .upstream_support import (
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
from .stream_logging import (
    _cancel_stream_capture,
    _capture_converted_stream_iterator,
    _safe_estimate_cost,
    _stream_upstream_iterator,
)
from .stream_transport import _FinalizingStreamingResponse
from .stream_restore import _distill_stream_response_content
from .response_usage import _extract_response_usage
from .usage import _extract_stream_usage
from .routing_plan import (
    _deadline_scope,
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
    gemini_expected_candidates = 1
    generation_config = body.get("generationConfig")
    if isinstance(generation_config, dict):
        candidate_count = generation_config.get("candidateCount")
        if (
            isinstance(candidate_count, int)
            and not isinstance(candidate_count, bool)
            and candidate_count > 0
        ):
            gemini_expected_candidates = candidate_count
    capture = StreamCapture(
        capture_body=log_body_enabled,
        chat_expected_choices=chat_expected_choices,
        gemini_expected_candidates=gemini_expected_candidates,
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
        response=_FinalizingStreamingResponse(
            converted_iter,
            stream_capture=capture,
            upstream_response=response,
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
        capture.is_client_stream_completed = True
    except asyncio.CancelledError:
        await _cancel_stream_capture(capture)
        raise
    except Exception as exc:
        if not capture.errors:
            _record_stream_error(
                capture,
                f"stream failed: {type(exc).__name__}: {exc}",
                status_code=502,
            )
        raise
    finally:
        if not is_finished and not capture.errors:
            await _cancel_stream_capture(capture)


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


def _prepare_channel_request(
    channel: ChannelConfig,
    body: dict[str, Any],
    *,
    credential_id: str | None,
    user_agent: str | None,
    forwarded_headers: Mapping[str, str] | None,
    upstream_headers_config: Mapping[str, Any] | None,
    log_body_enabled: bool,
    max_request_body_bytes: int,
    path_suffix: str | None = None,
    multipart_files: list[tuple[str, tuple[str, bytes, str]]] | None = None,
) -> tuple[Any, bytes, str | None]:
    upstream = build_upstream_request(
        channel,
        body,
        credential_id=credential_id,
        user_agent=user_agent,
        forwarded_headers=forwarded_headers,
        upstream_headers_config=upstream_headers_config,
        path_suffix=path_suffix,
    )
    if multipart_files is not None:
        multipart_request = httpx.Request(
            "POST",
            upstream.url,
            data=upstream.json_body,
            files=multipart_files,
        )
        body_bytes = multipart_request.read()
        upstream.headers["content-type"] = multipart_request.headers["content-type"]
    else:
        body_bytes = _json_body_bytes(upstream.json_body)
    request_content = _dump_log_json(upstream.json_body) if log_body_enabled else None
    too_large_message = _request_body_too_large_message(
        len(body_bytes), max_request_body_bytes
    )
    if too_large_message is not None:
        raise UpstreamRequestError(
            status_code=413,
            detail=too_large_message,
            router_status_code=None,
            error_type="request_too_large",
            skip_route_failure=True,
            stop_fallback=True,
            request_content=request_content,
        )
    return upstream, body_bytes, request_content


async def _call_channel(
    channel: ChannelConfig,
    body: dict[str, Any],
    upstream: Any,
    body_bytes: bytes,
    request_content: str | None,
    deadline: _RequestDeadline,
    *,
    credential_id: str | None,
    pricing_group_name: str | None = None,
    client_protocol: ProtocolKind | None = None,
    log_body_enabled: bool = False,
    global_proxy_url: str | None = None,
) -> UpstreamResult:
    proxy_url = resolve_upstream_proxy_url(channel, global_proxy_url)
    client = _resolve_http_client(proxy_url)
    is_stream_request = bool(body.get("stream"))

    try:
        stream_started_at = perf_counter()
        async with _deadline_scope(deadline):
            response = await _send_upstream(
                client, upstream, stream=is_stream_request, body_bytes=body_bytes
            )
        response.raise_for_status()

        is_event_stream = (
            "text/event-stream" in (response.headers.get("content-type") or "").lower()
        )
        if (
            is_event_stream
            and not is_stream_request
            and channel.protocol == ProtocolKind.ANTHROPIC
        ):
            result = await _build_anthropic_sse_to_json_result(
                response,
                channel,
                pricing_group_name,
                request_content,
                log_body_enabled,
            )
        elif is_event_stream:
            result = await _build_stream_result(
                response,
                channel,
                client_protocol,
                body,
                request_content,
                stream_started_at,
                log_body_enabled,
                deadline=deadline,
            )
        else:
            result = await _build_json_result(
                response,
                channel,
                client_protocol,
                body,
                pricing_group_name,
                request_content,
                log_body_enabled,
            )
        if not result.is_stream:
            app_state.router.record_success(channel.id, credential_id=credential_id)
        return result
    except httpx.HTTPStatusError as exc:
        await exc.response.aread()
        detail = _format_http_response_error(exc.response)
        raise UpstreamRequestError(
            status_code=exc.response.status_code,
            detail=detail,
            router_status_code=exc.response.status_code,
        ) from exc
    except httpx.HTTPError as exc:
        raise UpstreamRequestError(
            status_code=502,
            detail=_format_transport_error(exc, upstream.url),
            router_status_code=None,
        ) from exc
    except TimeoutError as exc:
        raise UpstreamRequestError(
            status_code=504,
            detail=deadline.timeout_message(),
            router_status_code=None,
            error_type="gateway_timeout",
        ) from exc


async def _send_upstream(
    client: httpx.AsyncClient, upstream: Any, *, stream: bool, body_bytes: bytes
) -> httpx.Response:
    if stream:
        request = client.build_request(
            upstream.method,
            upstream.url,
            headers=upstream.headers,
            content=body_bytes,
        )
        return await client.send(request, stream=True)
    return await client.request(
        upstream.method,
        upstream.url,
        headers=upstream.headers,
        content=body_bytes,
    )

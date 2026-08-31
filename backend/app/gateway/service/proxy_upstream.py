from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from time import perf_counter
from typing import Any

import httpx
from fastapi import Response

from ...models.channels import ChannelConfig
from ...models.protocols import ProtocolKind
from ..converters import (
    convert_response,
    convert_stream_iterator,
    repair_chat_tool_call_stream,
)
from ..router.cooldown import (
    ErrorCategory,
    classify_error,
)
from ..upstream_request import build_upstream_request, resolve_upstream_proxy_url
from .app_state import app_state
from .payload_serialization import (
    _decode_content_bytes,
    _decode_log_content_bytes,
    _dump_log_json,
    _json_body_bytes,
)
from .response_usage import _extract_response_usage
from .routing_plan import (
    _elapsed_ms,
    _gateway_timeout_scope,
    _request_body_too_large_message,
)
from .runtime_types import (
    StreamCapture,
    UpstreamRequestError,
    UpstreamResult,
    _GatewayTimeoutError,
    _record_stream_error,
    _RequestDeadline,
)
from .stream_logging import _safe_estimate_cost
from .stream_restore import _distill_stream_response_content
from .stream_transport import (
    _capture_converted_stream_iterator,
    _FinalizingStreamingResponse,
    _stream_upstream_iterator,
)
from .upstream_support import (
    _format_http_response_error,
    _format_transport_error,
    _passthrough_headers,
    _resolve_http_client,
    _summarize_html_error_detail,
)
from .usage import _extract_stream_usage

_NDJSON_MEDIA_TYPES = {"application/x-ndjson", "application/ndjson"}


def _image_count(body: dict[str, Any], payload: Any) -> int:
    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, list):
        return len(data)
    value = body.get("n", 1)
    try:
        count = int(value)
    except (TypeError, ValueError):
        return 1
    return count if count > 0 else 1


def _response_media_type(response: httpx.Response) -> str:
    content_type = response.headers.get("content-type") or ""
    return content_type.lower().partition(";")[0].strip()


def _looks_like_sse_body(content: bytes) -> bool:
    """Detect an SSE body from upstreams that mislabel their content-type."""
    return content[:64].lstrip().startswith((b"event:", b"data:"))


def _response_with_buffered_body(
    response: httpx.Response, content: bytes, media_type: str
) -> httpx.Response:
    headers = httpx.Headers(response.headers)
    headers["content-type"] = media_type
    return httpx.Response(
        response.status_code,
        content=content,
        headers=headers,
        request=response.request,
    )


def _describe_upstream_body(response: httpx.Response, content: bytes) -> str:
    content_type = response.headers.get("content-type") or "unknown"
    label = (
        f"HTTP {response.status_code} "
        f"(content-type={content_type}, {len(content)} bytes)"
    )
    preview = (_decode_content_bytes(content) or "").strip()
    if not preview:
        return label
    summary = _summarize_html_error_detail(preview, content_type=content_type)
    return f"{label}: {summary[:200]}"


def _parse_retry_after_seconds(value: str | None) -> float | None:
    if not value:
        return None
    trimmed_value = value.strip()
    try:
        seconds = float(trimmed_value)
    except ValueError:
        try:
            retry_at = parsedate_to_datetime(trimmed_value)
        except (TypeError, ValueError, OverflowError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=UTC)
        return max((retry_at - datetime.now(UTC)).total_seconds(), 0.0)
    return seconds if seconds >= 0 else None


def _is_request_level_client_error(status_code: int) -> bool:
    """4xx errors that signal a request-body problem; failover cannot fix them."""
    return status_code in (400, 422)


async def _build_anthropic_sse_to_json_result(
    response: httpx.Response,
    channel: ChannelConfig,
    pricing_group_name: str | None,
    rate_multiplier: float | None,
    request_content: str | None,
    log_body_enabled: bool,
) -> UpstreamResult:
    content = await response.aread()
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
        rate_multiplier=rate_multiplier,
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
        input_cost_usd=cost.input_cost_usd,
        output_cost_usd=cost.output_cost_usd,
        total_cost_usd=cost.total_cost_usd,
        billing_mode=cost.billing_mode,
        billing_units=cost.billing_units,
        request_content=request_content,
        response_content=response_content if log_body_enabled else None,
    )


async def _build_stream_result(
    response: httpx.Response,
    channel: ChannelConfig,
    client_protocol: ProtocolKind | None,
    body: dict[str, Any],
    include_stream_usage: bool,
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
        event_format=(
            "ndjson" if _response_media_type(response) in _NDJSON_MEDIA_TYPES else None
        ),
    )
    raw_iter = _stream_upstream_iterator(
        response,
        channel.protocol,
        capture,
        stream_started_at,
    )
    if (
        client_protocol == ProtocolKind.OPENAI_CHAT
        and channel.protocol == ProtocolKind.OPENAI_CHAT
    ):
        raw_iter = repair_chat_tool_call_stream(
            raw_iter,
            event_format="ndjson" if capture.event_format == "ndjson" else "sse",
        )

    if client_protocol is not None and client_protocol != channel.protocol:
        converted_iter = convert_stream_iterator(
            client_protocol,
            channel.protocol,
            raw_iter,
            body.get("model", ""),
            include_usage=include_stream_usage,
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
    try:
        async for chunk in stream:
            yield chunk
    except Exception as exc:
        if not capture.errors:
            _record_stream_error(
                capture,
                f"stream failed: {type(exc).__name__}: {exc}",
                status_code=502,
            )
        raise
    else:
        capture.is_client_stream_completed = True


async def _build_json_result(
    response: httpx.Response,
    content: bytes,
    channel: ChannelConfig,
    client_protocol: ProtocolKind | None,
    body: dict[str, Any],
    pricing_group_name: str | None,
    rate_multiplier: float | None,
    request_content: str | None,
    log_body_enabled: bool,
) -> UpstreamResult:
    try:
        payload: Any = json.loads(content)
    except ValueError as exc:
        raise UpstreamRequestError(
            status_code=502,
            detail=(
                "Invalid upstream response body: "
                f"{_describe_upstream_body(response, content)}"
            ),
            router_status_code=502,
        ) from exc
    try:
        parsed = _extract_response_usage(
            channel.protocol, payload, fallback_model=body.get("model")
        )
    except ValueError as exc:
        raise UpstreamRequestError(
            status_code=502,
            detail=f"Invalid upstream usage: {exc}",
            router_status_code=502,
        ) from exc
    if client_protocol is not None and client_protocol != channel.protocol:
        try:
            content = convert_response(
                client_protocol, channel.protocol, content, body.get("model", "")
            )
        except ValueError as exc:
            raise UpstreamRequestError(
                status_code=502,
                detail=f"Invalid upstream response: {exc}",
                router_status_code=502,
            ) from exc

    cost = await _safe_estimate_cost(
        pricing_group_name,
        parsed["input_tokens"],
        parsed["output_tokens"],
        parsed["cache_read_input_tokens"],
        parsed["cache_write_input_tokens"],
        image_count=(
            _image_count(body, payload)
            if channel.protocol == ProtocolKind.OPENAI_IMAGE
            else 0
        ),
        rate_multiplier=rate_multiplier,
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
        input_cost_usd=cost.input_cost_usd,
        output_cost_usd=cost.output_cost_usd,
        total_cost_usd=cost.total_cost_usd,
        billing_mode=cost.billing_mode,
        billing_units=cost.billing_units,
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
    model_group_headers: Mapping[str, str] | None,
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
        model_group_headers=model_group_headers,
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
    include_stream_usage: bool,
    pricing_group_name: str | None = None,
    rate_multiplier: float | None = None,
    client_protocol: ProtocolKind | None = None,
    log_body_enabled: bool = False,
    global_proxy_url: str | None = None,
) -> UpstreamResult:
    proxy_url = resolve_upstream_proxy_url(channel, global_proxy_url)
    client = _resolve_http_client(proxy_url)
    is_stream_request = bool(body.get("stream"))
    response: httpx.Response | None = None

    try:
        stream_started_at = perf_counter()
        async with _gateway_timeout_scope(
            deadline.first_token_remaining_seconds(),
            timeout_message=deadline.timeout_message(kind="first_token"),
        ):
            response = await _send_upstream(
                client,
                upstream,
                stream=is_stream_request,
                body_bytes=body_bytes,
            )
        response.raise_for_status()

        media_type = _response_media_type(response)
        is_event_stream = media_type == "text/event-stream"
        is_ndjson_stream = is_stream_request and media_type in _NDJSON_MEDIA_TYPES
        if is_stream_request and not is_event_stream and not is_ndjson_stream:
            # Proxies often default Content-Type to text/html; classify the body.
            async with _gateway_timeout_scope(
                deadline.first_token_remaining_seconds(),
                timeout_message=deadline.timeout_message(kind="first_token"),
            ):
                content = await response.aread()
            if _looks_like_sse_body(content):
                buffered = _response_with_buffered_body(
                    response, content, "text/event-stream"
                )
                await response.aclose()
                response = buffered
                is_event_stream = True
            else:
                result = await _build_json_result(
                    response,
                    content,
                    channel,
                    client_protocol,
                    body,
                    pricing_group_name,
                    rate_multiplier,
                    request_content,
                    log_body_enabled,
                )
                result.first_token_latency_ms = _elapsed_ms(stream_started_at)
                return result

        wants_anthropic_json = (
            not is_stream_request and channel.protocol == ProtocolKind.ANTHROPIC
        )
        if wants_anthropic_json and not is_event_stream:
            # Some upstreams answer a non-stream request with SSE but label it JSON.
            is_event_stream = _looks_like_sse_body(await response.aread())
        if wants_anthropic_json and is_event_stream:
            result = await _build_anthropic_sse_to_json_result(
                response,
                channel,
                pricing_group_name,
                rate_multiplier,
                request_content,
                log_body_enabled,
            )
            result.first_token_latency_ms = _elapsed_ms(stream_started_at)
        elif is_event_stream or is_ndjson_stream:
            result = await _build_stream_result(
                response,
                channel,
                client_protocol,
                body,
                include_stream_usage,
                request_content,
                stream_started_at,
                log_body_enabled,
                deadline=deadline,
            )
            response = None  # _FinalizingStreamingResponse owns the upstream response
        else:
            if is_stream_request:
                async with _gateway_timeout_scope(
                    deadline.first_token_remaining_seconds(),
                    timeout_message=deadline.timeout_message(kind="first_token"),
                ):
                    content = await response.aread()
            else:
                content = await response.aread()
            result = await _build_json_result(
                response,
                content,
                channel,
                client_protocol,
                body,
                pricing_group_name,
                rate_multiplier,
                request_content,
                log_body_enabled,
            )
            result.first_token_latency_ms = _elapsed_ms(stream_started_at)
        return result
    except httpx.HTTPStatusError as exc:
        response = exc.response
        if not response.is_stream_consumed:
            try:
                await response.aread()
            except httpx.HTTPError:
                pass
        status_code = response.status_code
        if response.is_stream_consumed:
            detail = _format_http_response_error(response)
        else:
            detail = f"HTTP {status_code}"
        retry_after_seconds = (
            _parse_retry_after_seconds(response.headers.get("retry-after"))
            if status_code in (429, 503)
            else None
        )
        stop_fallback = _is_request_level_client_error(status_code)
        classification = classify_error(
            status_code,
            detail,
            app_state.router.cooldown_detection_rules,
            response.headers,
        )
        raise UpstreamRequestError(
            status_code=status_code,
            detail=detail,
            router_status_code=status_code,
            router_error_category=classification.category if classification else None,
            router_error_scope=classification.scope if classification else "model",
            router_cooldown_seconds=(
                retry_after_seconds
                if retry_after_seconds is not None
                else classification.cooldown_seconds
                if classification
                else None
            ),
            stop_fallback=stop_fallback,
        ) from exc
    except httpx.HTTPError as exc:
        raise UpstreamRequestError(
            status_code=502,
            detail=_format_transport_error(exc, upstream.url),
            router_status_code=None,
            router_error_category=ErrorCategory.NETWORK,
        ) from exc
    except _GatewayTimeoutError as exc:
        raise UpstreamRequestError(
            status_code=504,
            detail=str(exc),
            router_status_code=None,
            router_error_category=ErrorCategory.TIMEOUT,
            error_type="gateway_timeout",
        ) from exc
    finally:
        if response is not None:
            await response.aclose()


async def _send_upstream(
    client: httpx.AsyncClient,
    upstream: Any,
    *,
    stream: bool,
    body_bytes: bytes,
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


def _client_stream_includes_usage(
    protocol: ProtocolKind, body: Mapping[str, Any]
) -> bool:
    if protocol != ProtocolKind.OPENAI_CHAT:
        return False
    stream_options = body.get("stream_options")
    return (
        isinstance(stream_options, Mapping)
        and stream_options.get("include_usage") is True
    )

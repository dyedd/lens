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

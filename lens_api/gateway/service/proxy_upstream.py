from __future__ import annotations

from .runtime_context import (
    AttemptLog,
    Any,
    AsyncIterator,
    ChannelConfig,
    Mapping,
    ProtocolKind,
    RequestLogLifecycleStatus,
    Response,
    RouteTarget,
    RoutingPlan,
    StreamCapture,
    StreamingResponse,
    UpstreamRequestError,
    UpstreamResult,
    _RequestDeadline,
    app_state,
    asyncio,
    build_upstream_request,
    convert_response,
    convert_stream_iterator,
    httpx,
    needs_conversion,
    perf_counter,
    resolve_upstream_proxy_url,
    settings,
)
from .errors import _protocol_error_response
from .upstream_http import (
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
from .usage import _extract_response_usage, _extract_stream_usage
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
    client_to_close: httpx.AsyncClient | None = None,
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
        client_to_close=client_to_close,
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
    finished = False
    try:
        async for chunk in stream:
            yield chunk
        finished = True
    except asyncio.CancelledError:
        await _cancel_stream_capture(capture, "client disconnected")
        raise
    finally:
        if not finished and not capture.client_disconnected:
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


def _prepare_channel_request(
    channel: ChannelConfig,
    body: dict[str, Any],
    *,
    credential_id: str | None,
    user_agent: str | None,
    forwarded_headers: Mapping[str, str] | None,
    upstream_headers_config: Mapping[str, Any] | None,
    log_body_enabled: bool,
    path_suffix: str | None = None,
    multipart_files: list[tuple[str, tuple[str, bytes, str]]] | None = None,
) -> tuple[Any, bytes, str | None]:
    upstream = build_upstream_request(
        channel,
        body,
        settings,
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
        len(body_bytes), settings.max_request_body_bytes
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
    client, close_client = _resolve_http_client(proxy_url)
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
                client_to_close=client if close_client else None,
            )
            if close_client:
                close_client = False
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
            detail=deadline.message(),
            router_status_code=None,
            error_type="gateway_timeout",
        ) from exc
    finally:
        if close_client:
            await client.aclose()


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

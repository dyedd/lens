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
from .state import app_state, logger
from .upstream_http import _format_channel_error
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


def _stream_payload_has_output(protocol: ProtocolKind, payload: dict[str, Any]) -> bool:
    if protocol == ProtocolKind.OPENAI_CHAT:
        return _chat_stream_payload_has_output(payload)
    if protocol == ProtocolKind.OPENAI_RESPONSES:
        return _responses_stream_payload_has_output(payload)
    if protocol == ProtocolKind.ANTHROPIC:
        return _anthropic_stream_payload_has_output(payload)
    if protocol == ProtocolKind.GEMINI:
        return _gemini_stream_payload_has_output(payload)
    return bool(payload)


def _chat_stream_payload_has_output(payload: dict[str, Any]) -> bool:
    choices = parse_chat_stream_payload(payload)
    if not choices:
        return False

    for choice in choices:
        delta = choice.delta
        if _has_non_empty_stream_value(_stringify_text_content(delta.content)):
            return True
        if _has_non_empty_stream_value(delta.reasoning_content):
            return True
        if _has_non_empty_stream_value(delta.reasoning):
            return True
        if delta.function_call and _chat_function_delta_has_output(delta.function_call):
            return True
        if delta.tool_calls and any(
            _chat_tool_call_delta_has_output(item) for item in delta.tool_calls
        ):
            return True
    return False


def _record_chat_stream_finish_reasons(
    capture: StreamCapture, payload: dict[str, Any]
) -> None:
    choices = payload.get("choices")
    if not isinstance(choices, list):
        return
    for choice in choices:
        if not isinstance(choice, dict) or choice.get("finish_reason") is None:
            continue
        index = choice.get("index", 0)
        if isinstance(index, bool) or not isinstance(index, int):
            index = 0
        capture.chat_finished_choices.add(index)


def _chat_function_delta_has_output(value: dict[str, Any]) -> bool:
    return _has_non_empty_stream_value(
        value.get("name")
    ) or _has_non_empty_stream_value(value.get("arguments"))


def _chat_tool_call_delta_has_output(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if _has_non_empty_stream_value(value.get("id")):
        return True
    if _has_non_empty_stream_value(value.get("type")):
        return True
    return _chat_function_delta_has_output(value.get("function"))


def _responses_stream_payload_has_output(payload: dict[str, Any]) -> bool:
    payload_type = str(payload.get("type") or "")
    if payload_type.endswith(".delta"):
        return any(
            _has_non_empty_stream_value(payload.get(key))
            for key in ("delta", "text", "partial_json")
        )
    item = payload.get("item")
    if payload_type == "response.output_item.added" and isinstance(item, dict):
        return item.get("type") == "function_call" and (
            _has_non_empty_stream_value(item.get("name"))
            or _has_non_empty_stream_value(item.get("call_id"))
        )
    return False


def _anthropic_stream_payload_has_output(payload: dict[str, Any]) -> bool:
    block = parse_anthropic_stream_payload(payload)
    if not block:
        return False

    if block.type == "content_block_delta":
        if not block.delta:
            return False
        return any(
            _has_non_empty_stream_value(block.delta.get(key))
            for key in ("text", "thinking", "partial_json")
        )
    if block.type == "content_block_start":
        content_block = block.content_block
        return (
            content_block
            and content_block.get("type") == "tool_use"
            and (
                _has_non_empty_stream_value(content_block.get("name"))
                or _has_non_empty_stream_value(content_block.get("id"))
            )
        )
    return False


def _gemini_stream_payload_has_output(payload: dict[str, Any]) -> bool:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        return False
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content")
        if not isinstance(content, dict):
            continue
        parts = content.get("parts")
        if not isinstance(parts, list):
            continue
        for part in parts:
            if not isinstance(part, dict):
                continue
            if _has_non_empty_stream_value(part.get("text")):
                return True
            if isinstance(part.get("functionCall"), dict):
                return True
    return False


def _has_non_empty_stream_value(value: Any) -> bool:
    if isinstance(value, str):
        return value != ""
    if isinstance(value, dict):
        return any(_has_non_empty_stream_value(item) for item in value.values())
    if isinstance(value, list):
        return any(_has_non_empty_stream_value(item) for item in value)
    return value is not None


def _mark_stream_first_chunk(capture: StreamCapture, stream_started_at: float) -> None:
    if capture.saw_first_chunk:
        return
    capture.saw_first_chunk = True
    capture.first_token_latency_ms = _elapsed_ms(stream_started_at)
    request_log_id = capture.request_log_id
    if request_log_id is None:
        return
    capture.first_token_update_task = asyncio.create_task(
        _persist_stream_first_token_latency(
            request_log_id=request_log_id,
            first_token_latency_ms=capture.first_token_latency_ms,
            latency_ms=_elapsed_ms(capture.stream_started_at or stream_started_at),
        )
    )


async def _persist_stream_first_token_latency(
    *,
    request_log_id: int,
    first_token_latency_ms: int,
    latency_ms: int,
) -> None:
    try:
        await app_state.request_log_store.update_request_log_runtime(
            request_log_id,
            first_token_latency_ms=first_token_latency_ms,
            latency_ms=latency_ms,
        )
    except Exception:
        logger.warning("Failed to update stream first token latency", exc_info=True)


async def _cancel_stream_capture(
    capture: StreamCapture, reason: str | None = None
) -> None:
    if capture.completed:
        return
    capture.client_disconnected = True
    if reason and reason not in capture.errors:
        capture.errors.append(reason)


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
    if capture is None or not capture.client_disconnected:
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


async def _stream_upstream_iterator(
    response: httpx.Response,
    protocol: ProtocolKind,
    capture: StreamCapture,
    stream_started_at: float,
) -> AsyncIterator[bytes]:
    deadline = capture.deadline
    assert deadline is not None
    try:
        iterator = response.aiter_bytes().__aiter__()
        while True:
            try:
                chunk = await _next_stream_chunk(iterator, deadline)
            except StopAsyncIteration:
                break
            if not chunk:
                continue
            text = chunk.decode("utf-8", errors="replace")
            if text:
                _capture_stream_event_chunk(protocol, capture, text, stream_started_at)
                if capture.capture_body:
                    capture.response_content_chunks.append(text)
            yield chunk
        _flush_stream_event_buffer(protocol, capture, stream_started_at)
        capture.completed = True
    except asyncio.CancelledError:
        capture.error_status_code = 499
        await _cancel_stream_capture(capture, "client disconnected")
        raise
    except TimeoutError:
        capture.error_status_code = 504
        capture.errors.append(deadline.message())
    except httpx.HTTPError as exc:
        capture.error_status_code = 502
        capture.errors.append(f"stream failed: {type(exc).__name__}: {exc}")
    finally:
        await response.aclose()
        if capture.client_to_close is not None:
            await capture.client_to_close.aclose()


async def _next_stream_chunk(
    iterator: AsyncIterator[bytes], deadline: _RequestDeadline
) -> bytes:
    remaining = deadline.remaining_seconds()
    if remaining is None:
        return await iterator.__anext__()
    if remaining <= 0:
        raise TimeoutError(deadline.message())
    async with asyncio.timeout(remaining):
        return await iterator.__anext__()


async def _capture_converted_stream_iterator(
    raw_iterator: AsyncIterator[bytes], capture: StreamCapture
) -> AsyncIterator[bytes]:
    try:
        async for chunk in raw_iterator:
            text = chunk.decode("utf-8", errors="replace")
            if text and capture.capture_body:
                capture.client_response_content_chunks.append(text)
            yield chunk
    except asyncio.CancelledError:
        await _cancel_stream_capture(capture, "client disconnected")
        raise
    except ValueError as exc:
        await _cancel_stream_capture(capture, str(exc))


def _capture_stream_event_chunk(
    protocol: ProtocolKind,
    capture: StreamCapture,
    text: str,
    stream_started_at: float,
) -> None:
    if protocol in (ProtocolKind.OPENAI_EMBEDDING, ProtocolKind.RERANK):
        return
    capture.event_buffer += text
    stream_format = _stream_event_format(protocol, capture)
    if stream_format == "ndjson":
        _drain_ndjson_event_buffer(protocol, capture, stream_started_at, final=False)
    else:
        _drain_sse_event_buffer(protocol, capture, stream_started_at, final=False)


def _flush_stream_event_buffer(
    protocol: ProtocolKind, capture: StreamCapture, stream_started_at: float
) -> None:
    if not capture.event_buffer:
        return
    stream_format = _stream_event_format(protocol, capture)
    if stream_format == "ndjson":
        _drain_ndjson_event_buffer(protocol, capture, stream_started_at, final=True)
    else:
        _drain_sse_event_buffer(protocol, capture, stream_started_at, final=True)


def _stream_event_format(protocol: ProtocolKind, capture: StreamCapture) -> str:
    if protocol != ProtocolKind.GEMINI:
        return "sse"
    if capture.event_format is not None:
        return capture.event_format
    normalized = _normalize_event_stream_newlines(capture.event_buffer).lstrip()
    capture.event_format = "ndjson" if normalized.startswith(("{", "[")) else "sse"
    return capture.event_format


def _drain_sse_event_buffer(
    protocol: ProtocolKind,
    capture: StreamCapture,
    stream_started_at: float,
    *,
    final: bool,
) -> None:
    normalized = _normalize_event_stream_newlines(capture.event_buffer)
    blocks = normalized.split("\n\n")
    if final:
        capture.event_buffer = ""
    else:
        capture.event_buffer = blocks.pop()
    for block in blocks:
        payloads = _parse_sse_payloads(f"{block}\n\n", errors=capture.parse_errors)
        for payload in payloads:
            _record_stream_event_payload(protocol, capture, payload, stream_started_at)


def _drain_ndjson_event_buffer(
    protocol: ProtocolKind,
    capture: StreamCapture,
    stream_started_at: float,
    *,
    final: bool,
) -> None:
    normalized = _normalize_event_stream_newlines(capture.event_buffer)
    lines = normalized.split("\n")
    if final:
        capture.event_buffer = ""
    else:
        capture.event_buffer = lines.pop()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            capture.parse_errors.append(f"invalid NDJSON: {exc.msg}")
            continue
        if isinstance(payload, dict):
            _record_stream_event_payload(protocol, capture, payload, stream_started_at)


def _record_stream_event_payload(
    protocol: ProtocolKind,
    capture: StreamCapture,
    payload: dict[str, Any],
    stream_started_at: float,
) -> None:
    if not capture.saw_first_chunk and _stream_payload_has_output(protocol, payload):
        _mark_stream_first_chunk(capture, stream_started_at)
    if protocol == ProtocolKind.OPENAI_CHAT:
        _record_chat_stream_finish_reasons(capture, payload)
    try:
        parsed = _extract_usage_from_payload(protocol, payload)
    except ValueError as exc:
        capture.parse_errors.append(str(exc))
        return
    if parsed["resolved_model"]:
        capture.resolved_model = str(parsed["resolved_model"])
    for key in (
        "input_tokens",
        "cache_read_input_tokens",
        "cache_write_input_tokens",
        "output_tokens",
        "total_tokens",
    ):
        value = parsed[key]
        assert isinstance(value, int)
        if value:
            setattr(capture, key, max(getattr(capture, key), value))


def _stream_capture_usage(capture: StreamCapture | None) -> dict[str, int | str | None]:
    if capture is None:
        return dict(_EMPTY_USAGE)
    total_tokens = max(
        capture.total_tokens, capture.input_tokens + capture.output_tokens
    )
    return {
        "resolved_model": capture.resolved_model,
        "input_tokens": capture.input_tokens,
        "cache_read_input_tokens": capture.cache_read_input_tokens,
        "cache_write_input_tokens": capture.cache_write_input_tokens,
        "output_tokens": capture.output_tokens,
        "total_tokens": total_tokens,
    }


def _join_stream_chunks(chunks: list[str]) -> str | None:
    return "".join(chunks) if chunks else None

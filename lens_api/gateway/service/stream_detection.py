from __future__ import annotations

import asyncio
from typing import Any

from ...models import ProtocolKind
from .app_state import app_state, logger
from .payload_serialization import _stringify_text_content
from .routing_plan import _elapsed_ms
from .runtime_types import StreamCapture
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
    if capture.has_seen_first_chunk:
        return
    capture.has_seen_first_chunk = True
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
    if capture.is_completed:
        return
    capture.is_client_disconnected = True
    if reason and reason not in capture.errors:
        capture.errors.append(reason)

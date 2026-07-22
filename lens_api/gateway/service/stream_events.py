from __future__ import annotations

import json
from typing import Any

from ...models import ProtocolKind
from .runtime_types import StreamCapture, _record_stream_parse_error
from .routing_plan import _elapsed_ms
from .usage import (
    _EMPTY_USAGE,
    _extract_usage_from_payload,
    _normalize_event_stream_newlines,
    _parse_sse_payloads,
)
from .payload_serialization import _stringify_text_content
from .stream_types import parse_chat_stream_payload, parse_anthropic_stream_payload
from .stream_detection import (
    _mark_stream_first_chunk,
    _record_stream_completion,
    _stream_payload_has_output,
)

_STREAM_EVENT_BUFFER_LIMIT_CHARS = 1_000_000


def _capture_stream_event_chunk(
    protocol: ProtocolKind,
    capture: StreamCapture,
    text: str,
    stream_started_at: float,
) -> None:
    if protocol in (ProtocolKind.OPENAI_EMBEDDING, ProtocolKind.RERANK):
        return
    text = _normalize_stream_event_chunk(capture, text)
    stream_format = _stream_event_format(protocol, capture, text)
    delimiter = "\n" if stream_format == "ndjson" else "\n\n"
    if capture.is_discarding_oversized_event:
        text = _resume_after_oversized_event(capture, text, delimiter)
        if not text:
            return
    capture.event_buffer += text
    if stream_format == "ndjson":
        _drain_ndjson_event_buffer(protocol, capture, stream_started_at, is_final=False)
    else:
        _drain_sse_event_buffer(protocol, capture, stream_started_at, is_final=False)
    if _is_oversized_event(capture.event_buffer):
        capture.is_discarding_oversized_event = True
        tail_length = len(delimiter) - 1
        capture.event_buffer = (
            capture.event_buffer[-tail_length:] if tail_length else ""
        )


def _flush_stream_event_buffer(
    protocol: ProtocolKind, capture: StreamCapture, stream_started_at: float
) -> None:
    if capture.event_pending_carriage_return:
        capture.event_buffer += "\n"
        capture.event_pending_carriage_return = False
    if capture.is_discarding_oversized_event:
        capture.event_buffer = ""
        capture.is_discarding_oversized_event = False
        return
    if not capture.event_buffer:
        return
    stream_format = _stream_event_format(protocol, capture, "")
    if stream_format == "ndjson":
        _drain_ndjson_event_buffer(protocol, capture, stream_started_at, is_final=True)
    else:
        _drain_sse_event_buffer(protocol, capture, stream_started_at, is_final=True)


def _stream_event_format(
    protocol: ProtocolKind, capture: StreamCapture, pending_text: str
) -> str:
    if capture.event_format is not None:
        return capture.event_format
    if protocol != ProtocolKind.GEMINI:
        return "sse"
    normalized = f"{capture.event_buffer}{pending_text}".lstrip()
    if not normalized:
        return "sse"
    capture.event_format = "ndjson" if normalized.startswith(("{", "[")) else "sse"
    return capture.event_format


def _normalize_stream_event_chunk(capture: StreamCapture, text: str) -> str:
    if capture.event_pending_carriage_return:
        text = f"\r{text}"
        capture.event_pending_carriage_return = False
    if text.endswith("\r"):
        text = text[:-1]
        capture.event_pending_carriage_return = True
    return _normalize_event_stream_newlines(text)


def _resume_after_oversized_event(
    capture: StreamCapture, text: str, delimiter: str
) -> str:
    pending = f"{capture.event_buffer}{text}"
    boundary_index = pending.find(delimiter)
    if boundary_index < 0:
        tail_length = len(delimiter) - 1
        capture.event_buffer = pending[-tail_length:] if tail_length else ""
        return ""
    capture.event_buffer = ""
    capture.is_discarding_oversized_event = False
    return pending[boundary_index + len(delimiter) :]


def _is_oversized_event(value: str) -> bool:
    return len(value) > _STREAM_EVENT_BUFFER_LIMIT_CHARS


def _drain_sse_event_buffer(
    protocol: ProtocolKind,
    capture: StreamCapture,
    stream_started_at: float,
    *,
    is_final: bool,
) -> None:
    normalized = _normalize_event_stream_newlines(capture.event_buffer)
    blocks = normalized.split("\n\n")
    if is_final:
        capture.event_buffer = ""
    else:
        capture.event_buffer = blocks.pop()
    for block in blocks:
        parse_errors: list[str] = []
        payloads = _parse_sse_payloads(f"{block}\n\n", errors=parse_errors)
        for error in parse_errors:
            _record_stream_parse_error(capture, error)
        for payload in payloads:
            _record_stream_event_payload(protocol, capture, payload, stream_started_at)


def _drain_ndjson_event_buffer(
    protocol: ProtocolKind,
    capture: StreamCapture,
    stream_started_at: float,
    *,
    is_final: bool,
) -> None:
    normalized = _normalize_event_stream_newlines(capture.event_buffer)
    lines = normalized.split("\n")
    if is_final:
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
            _record_stream_parse_error(capture, f"invalid NDJSON: {exc.msg}")
            continue
        if isinstance(payload, dict):
            _record_stream_event_payload(protocol, capture, payload, stream_started_at)


def _record_stream_event_payload(
    protocol: ProtocolKind,
    capture: StreamCapture,
    payload: dict[str, Any],
    stream_started_at: float,
) -> None:
    if not capture.has_seen_first_chunk and _stream_payload_has_output(
        protocol, payload
    ):
        _mark_stream_first_chunk(capture, stream_started_at)
    _record_stream_completion(protocol, capture, payload)
    try:
        parsed = _extract_usage_from_payload(protocol, payload)
    except ValueError as exc:
        _record_stream_parse_error(capture, str(exc))
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

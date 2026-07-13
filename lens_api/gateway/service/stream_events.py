from __future__ import annotations

import json
from typing import Any

from ...models import ProtocolKind
from .runtime_types import StreamCapture
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
    _record_chat_stream_finish_reasons,
    _stream_payload_has_output,
)


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
        _drain_ndjson_event_buffer(protocol, capture, stream_started_at, is_final=False)
    else:
        _drain_sse_event_buffer(protocol, capture, stream_started_at, is_final=False)


def _flush_stream_event_buffer(
    protocol: ProtocolKind, capture: StreamCapture, stream_started_at: float
) -> None:
    if not capture.event_buffer:
        return
    stream_format = _stream_event_format(protocol, capture)
    if stream_format == "ndjson":
        _drain_ndjson_event_buffer(protocol, capture, stream_started_at, is_final=True)
    else:
        _drain_sse_event_buffer(protocol, capture, stream_started_at, is_final=True)


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
    is_final: bool,
) -> None:
    normalized = _normalize_event_stream_newlines(capture.event_buffer)
    blocks = normalized.split("\n\n")
    if is_final:
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
    if not capture.has_seen_first_chunk and _stream_payload_has_output(
        protocol, payload
    ):
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

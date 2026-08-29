from __future__ import annotations

import json
from typing import Any

from ...models.protocols import ProtocolKind
from .runtime_types import (
    StreamCapture,
    _record_stream_error,
    _record_stream_parse_error,
)
from .stream_detection import (
    _mark_stream_first_chunk,
    _record_stream_completion,
    _stream_payload_has_output,
)
from .stream_parsing import (
    _parse_sse_payloads,
    _to_lf_line_endings,
)
from .usage import _EMPTY_USAGE, _extract_usage_from_payload

_STREAM_EVENT_BUFFER_LIMIT_CHARS = 1_000_000


def _capture_stream_event_chunk(
    protocol: ProtocolKind,
    capture: StreamCapture,
    text: str,
    stream_started_at: float,
) -> int | None:
    if protocol in (ProtocolKind.OPENAI_EMBEDDING, ProtocolKind.RERANK):
        return None
    raw_text = text
    had_pending_carriage_return = capture.event_pending_carriage_return
    text = _to_lf_stream_chunk(capture, text)
    stream_format = _stream_event_format(protocol, capture, text)
    delimiter = "\n" if stream_format == "ndjson" else "\n\n"
    skipped_prefix_length = 0
    if capture.is_discarding_oversized_event:
        resumed_text = _resume_after_oversized_event(capture, text, delimiter)
        if not resumed_text:
            return None
        skipped_prefix_length = len(text) - len(resumed_text)
        text = resumed_text
    pending_length = len(capture.event_buffer)
    capture.event_buffer += text
    if stream_format == "ndjson":
        terminal_boundary = _drain_ndjson_event_buffer(
            protocol, capture, stream_started_at, is_final=False
        )
    else:
        terminal_boundary = _drain_sse_event_buffer(
            protocol, capture, stream_started_at, is_final=False
        )
    if terminal_boundary is not None:
        lf_prefix_length = skipped_prefix_length + max(
            terminal_boundary - pending_length, 0
        )
        return _raw_prefix_length_for_lf_text(
            raw_text,
            lf_prefix_length,
            had_pending_carriage_return=had_pending_carriage_return,
        )
    if _is_oversized_event(capture.event_buffer):
        capture.is_discarding_oversized_event = True
        tail_length = len(delimiter) - 1
        capture.event_buffer = (
            capture.event_buffer[-tail_length:] if tail_length else ""
        )
    return None


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
    probe_text = f"{capture.event_buffer}{pending_text}".lstrip()
    if not probe_text:
        return "sse"
    capture.event_format = "ndjson" if probe_text.startswith(("{", "[")) else "sse"
    return capture.event_format


def _to_lf_stream_chunk(capture: StreamCapture, text: str) -> str:
    if capture.event_pending_carriage_return:
        text = f"\r{text}"
        capture.event_pending_carriage_return = False
    if text.endswith("\r"):
        text = text[:-1]
        capture.event_pending_carriage_return = True
    return _to_lf_line_endings(text)


def _raw_prefix_length_for_lf_text(
    raw_text: str,
    lf_prefix_length: int,
    *,
    had_pending_carriage_return: bool,
) -> int:
    if lf_prefix_length <= 0:
        return 0
    source = f"\r{raw_text}" if had_pending_carriage_return else raw_text
    source_offset = 1 if had_pending_carriage_return else 0
    lf_length = 0
    source_index = 0
    while source_index < len(source):
        if source[source_index] == "\r" and source_index + 1 < len(source):
            if source[source_index + 1] == "\n":
                source_index += 2
            else:
                source_index += 1
        else:
            source_index += 1
        lf_length += 1
        if lf_length >= lf_prefix_length:
            return max(source_index - source_offset, 0)
    return len(raw_text)


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
) -> int | None:
    lf_content = _to_lf_line_endings(capture.event_buffer)
    blocks = lf_content.split("\n\n")
    if is_final:
        capture.event_buffer = ""
    else:
        capture.event_buffer = blocks.pop()
    processed_length = 0
    for block in blocks:
        block_length = len(block) + 2
        if protocol == ProtocolKind.OPENAI_CHAT and _is_chat_done_event(block):
            capture.protocol_completed = True
            capture.event_buffer = ""
            return processed_length + block_length
        parse_errors: list[str] = []
        payloads = _parse_sse_payloads(f"{block}\n\n", errors=parse_errors)
        for error in parse_errors:
            _record_stream_parse_error(capture, error)
        for payload in payloads:
            if _record_stream_event_payload(
                protocol, capture, payload, stream_started_at
            ):
                capture.event_buffer = ""
                return processed_length + block_length
        processed_length += block_length
    return None


def _drain_ndjson_event_buffer(
    protocol: ProtocolKind,
    capture: StreamCapture,
    stream_started_at: float,
    *,
    is_final: bool,
) -> int | None:
    lf_content = _to_lf_line_endings(capture.event_buffer)
    lines = lf_content.split("\n")
    if is_final:
        capture.event_buffer = ""
    else:
        capture.event_buffer = lines.pop()
    processed_length = 0
    for raw_line in lines:
        line_length = len(raw_line) + 1
        line = raw_line.strip()
        if not line:
            processed_length += line_length
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            _record_stream_parse_error(capture, f"invalid NDJSON: {exc.msg}")
            processed_length += line_length
            continue
        if isinstance(payload, dict) and _record_stream_event_payload(
            protocol, capture, payload, stream_started_at
        ):
            capture.event_buffer = ""
            return processed_length + line_length
        processed_length += line_length
    return None


def _is_chat_done_event(block: str) -> bool:
    data_lines = [
        line[5:].strip() for line in block.splitlines() if line.startswith("data:")
    ]
    return data_lines == ["[DONE]"]


def _record_stream_event_payload(
    protocol: ProtocolKind,
    capture: StreamCapture,
    payload: dict[str, Any],
    stream_started_at: float,
) -> bool:
    if not capture.has_seen_first_chunk and _stream_payload_has_output(
        protocol, payload
    ):
        _mark_stream_first_chunk(capture, stream_started_at)
    error_message = _stream_payload_error_message(protocol, payload)
    if error_message is not None:
        _record_stream_error(capture, error_message, status_code=502)
    is_terminal = error_message is not None or _record_stream_completion(
        protocol, capture, payload
    )
    try:
        parsed = _extract_usage_from_payload(protocol, payload)
    except ValueError as exc:
        _record_stream_parse_error(capture, str(exc))
        return is_terminal
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
    return is_terminal


def _stream_payload_error_message(
    protocol: ProtocolKind, payload: dict[str, Any]
) -> str | None:
    event_type = payload.get("type")
    error: Any
    if protocol == ProtocolKind.OPENAI_RESPONSES:
        if event_type == "response.failed":
            response = payload.get("response")
            error = response.get("error") if isinstance(response, dict) else None
        elif event_type == "error":
            error = payload.get("error")
        else:
            return None
    elif protocol == ProtocolKind.ANTHROPIC:
        if event_type != "error":
            return None
        error = payload.get("error")
    elif protocol in (ProtocolKind.OPENAI_CHAT, ProtocolKind.GEMINI):
        if "error" not in payload:
            return None
        error = payload.get("error")
    else:
        return None

    message = error.get("message") if isinstance(error, dict) else error
    if not isinstance(message, str) or not message.strip():
        message = payload.get("message")
    if not isinstance(message, str) or not message.strip():
        message = str(event_type or "error")
    return f"{protocol.value} stream failed: {message.strip()}"


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

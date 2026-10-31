from __future__ import annotations

import asyncio
import codecs
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ...router.cooldown import ErrorCategory

if TYPE_CHECKING:
    from ..runtime_types import RequestDeadline


_STREAM_CONTENT_CAPTURE_LIMIT_BYTES = 1_000_000
_STREAM_ERROR_SAMPLE_LIMIT = 20


def _new_incremental_utf8_decoder() -> codecs.IncrementalDecoder:
    """Hold partial multi-byte sequences across chunk boundaries."""
    return codecs.getincrementaldecoder("utf-8")(errors="replace")


def append_error_sample(errors: list[str] | None, message: str) -> None:
    """Append a unique stream error while keeping the sample bounded."""
    if errors is None or not message or message in errors:
        return
    if len(errors) < _STREAM_ERROR_SAMPLE_LIMIT:
        errors.append(message)


@dataclass(slots=True)
class StreamCapture:
    capture_body: bool
    deadline: RequestDeadline
    has_seen_first_chunk: bool = False
    chat_expected_choices: int = 1
    chat_finished_choices: set[int] = field(default_factory=set)
    first_token_latency_ms: int = 0
    response_content_chunks: list[str] = field(default_factory=list)
    response_content_bytes: int = 0
    is_response_content_truncated: bool = False
    client_response_content_chunks: list[str] = field(default_factory=list)
    client_response_content_bytes: int = 0
    is_client_response_content_truncated: bool = False
    event_buffer: str = ""
    event_format: str | None = None
    event_pending_carriage_return: bool = False
    is_discarding_oversized_event: bool = False
    is_client_stream_completed: bool = False
    protocol_completed: bool = False
    is_client_disconnected: bool = False
    first_token_update_task: asyncio.Task[None] | None = None
    parse_errors: list[str] = field(default_factory=list)
    input_tokens: int = 0
    image_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_write_input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    resolved_model: str | None = None
    errors: list[str] = field(default_factory=list)
    request_log_id: int | None = None
    stream_started_at: float = 0.0
    route_started_revision: int = -1
    route_cursor_key: str = ""
    route_was_probe: bool = False
    error_status_code: int | None = None
    error_category: ErrorCategory | None = None
    error_cooldown_seconds: float | None = None
    error_retry_action: str | None = None
    skip_route_failure: bool = False
    content_decoder: codecs.IncrementalDecoder = field(
        default_factory=_new_incremental_utf8_decoder
    )
    client_content_decoder: codecs.IncrementalDecoder = field(
        default_factory=_new_incremental_utf8_decoder
    )


def capture_stream_content(
    capture: StreamCapture, text: str, *, client_response: bool = False
) -> None:
    if not capture.capture_body or not text:
        return

    if client_response:
        chunks = capture.client_response_content_chunks
        captured_bytes = capture.client_response_content_bytes
        is_truncated = capture.is_client_response_content_truncated
    else:
        chunks = capture.response_content_chunks
        captured_bytes = capture.response_content_bytes
        is_truncated = capture.is_response_content_truncated
    if is_truncated:
        return

    remaining_bytes = _STREAM_CONTENT_CAPTURE_LIMIT_BYTES - captured_bytes
    encoded = text.encode("utf-8")
    captured_text = text
    if len(encoded) > remaining_bytes:
        captured_text = encoded[:remaining_bytes].decode("utf-8", errors="ignore")
        encoded = captured_text.encode("utf-8")
        is_truncated = True
    if captured_text:
        chunks.append(captured_text)
        captured_bytes += len(encoded)

    if client_response:
        capture.client_response_content_bytes = captured_bytes
        capture.is_client_response_content_truncated = is_truncated
    else:
        capture.response_content_bytes = captured_bytes
        capture.is_response_content_truncated = is_truncated


def record_stream_error(
    capture: StreamCapture,
    message: str,
    *,
    status_code: int | None = None,
    category: ErrorCategory | None = None,
    cooldown_seconds: float | None = None,
    skip_route_failure: bool = False,
) -> None:
    if status_code is not None:
        capture.error_status_code = status_code
    if category is not None and capture.error_category is None:
        capture.error_category = category
        capture.error_retry_action = (
            "retry_key"
            if category in (ErrorCategory.AUTH, ErrorCategory.RATE_LIMIT)
            else "retry_channel"
        )
    if cooldown_seconds is not None and capture.error_cooldown_seconds is None:
        capture.error_cooldown_seconds = cooldown_seconds
    if skip_route_failure:
        capture.skip_route_failure = True
    append_error_sample(capture.errors, message)


def record_stream_parse_error(capture: StreamCapture, message: str) -> None:
    append_error_sample(capture.parse_errors, message)

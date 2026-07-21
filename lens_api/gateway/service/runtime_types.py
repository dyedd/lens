from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Literal

from fastapi import HTTPException, Response

from ...models import ModelGroup, RoutingStrategy
from ..router import RouteTarget

_STREAM_CONTENT_CAPTURE_LIMIT_BYTES = 1_000_000
_STREAM_ERROR_SAMPLE_LIMIT = 20

_TimeoutKind = Literal["first_token", "stream_idle"]


@dataclass(slots=True)
class RoutingPlan:
    requested_group_name: str | None
    resolved_group_name: str | None
    requested_group: ModelGroup | None
    resolved_group: ModelGroup | None
    strategy: RoutingStrategy
    route_targets: list[RouteTarget] | None
    use_model_matching: bool
    cursor_key: str | None = None


@dataclass(slots=True)
class UpstreamResult:
    response: Response
    status_code: int
    is_stream: bool = False
    first_token_latency_ms: int = 0
    upstream_model_name: str | None = None
    input_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_write_input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    input_cost_usd: float = 0.0
    output_cost_usd: float = 0.0
    total_cost_usd: float = 0.0
    request_content: str | None = None
    response_content: str | None = None
    stream_capture: StreamCapture | None = None


@dataclass(slots=True)
class AttemptLog:
    channel_id: str
    channel_name: str
    credential_id: str | None
    credential_name: str
    model_name: str | None
    status_code: int | None
    success: bool
    duration_ms: int
    error_message: str | None = None
    reasoning_effort: str | None = None


@dataclass(frozen=True, slots=True)
class _RequestDeadline:
    started_at: float
    first_token_timeout_seconds: float
    stream_idle_timeout_seconds: float

    def first_token_remaining_seconds(self) -> float | None:
        """Remaining first-token budget from started_at; None means unlimited."""
        if self.first_token_timeout_seconds <= 0:
            return None
        return max(
            self.first_token_timeout_seconds - (perf_counter() - self.started_at),
            0.0,
        )

    def is_first_token_expired(self) -> bool:
        remaining = self.first_token_remaining_seconds()
        return remaining is not None and remaining <= 0

    def stream_chunk_wait_seconds(self, *, has_seen_first_chunk: bool) -> float | None:
        if not has_seen_first_chunk:
            return self.first_token_remaining_seconds()
        return (
            self.stream_idle_timeout_seconds
            if self.stream_idle_timeout_seconds > 0
            else None
        )

    def timeout_message(self, *, kind: _TimeoutKind) -> str:
        if kind == "first_token":
            timeout_seconds = self.first_token_timeout_seconds
            label = self._format_timeout_label(timeout_seconds)
            return f"Gateway first-token timed out after {label}s"
        timeout_seconds = self.stream_idle_timeout_seconds
        label = self._format_timeout_label(timeout_seconds)
        return f"Gateway stream idle timed out after {label}s"

    @staticmethod
    def _format_timeout_label(timeout_seconds: float) -> str:
        if timeout_seconds.is_integer():
            return str(int(timeout_seconds))
        return f"{timeout_seconds:.3f}".rstrip("0").rstrip(".")


class _GatewayTimeoutError(TimeoutError):
    """Raised only when a Lens-managed gateway timeout expires."""


class UpstreamRequestError(HTTPException):
    def __init__(
        self,
        status_code: int,
        detail: Any,
        *,
        router_status_code: int | None,
        error_type: str = "upstream_error",
        skip_route_failure: bool = False,
        stop_fallback: bool = False,
        request_content: str | None = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.router_status_code = router_status_code
        self.error_type = error_type
        self.skip_route_failure = skip_route_failure
        self.stop_fallback = stop_fallback
        self.request_content = request_content


def _attempt_logs_to_dicts(attempts: list[AttemptLog]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for attempt in attempts:
        item = {
            "channel_id": attempt.channel_id,
            "channel_name": attempt.channel_name,
            "credential_id": attempt.credential_id,
            "credential_name": attempt.credential_name,
            "model_name": attempt.model_name,
            "status_code": attempt.status_code,
            "success": attempt.success,
            "duration_ms": attempt.duration_ms,
            "error_message": attempt.error_message,
        }
        if attempt.reasoning_effort is not None:
            item["reasoning_effort"] = attempt.reasoning_effort
        items.append(item)
    return items


@dataclass(slots=True)
class StreamCapture:
    capture_body: bool
    deadline: _RequestDeadline
    has_seen_first_chunk: bool = False
    chat_expected_choices: int = 1
    chat_finished_choices: set[int] = field(default_factory=set)
    gemini_expected_candidates: int = 1
    gemini_finished_candidates: set[int] = field(default_factory=set)
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
    is_completed: bool = False
    is_client_stream_completed: bool = False
    protocol_completed: bool = False
    is_client_disconnected: bool = False
    first_token_update_task: asyncio.Task[None] | None = None
    parse_errors: list[str] = field(default_factory=list)
    input_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_write_input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    resolved_model: str | None = None
    errors: list[str] = field(default_factory=list)
    request_log_id: int | None = None
    stream_started_at: float = 0.0
    error_status_code: int | None = None


def _capture_stream_content(
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


def _record_stream_error(
    capture: StreamCapture, message: str, *, status_code: int | None = None
) -> None:
    if status_code is not None:
        capture.error_status_code = status_code
    if not message or message in capture.errors:
        return
    if len(capture.errors) < _STREAM_ERROR_SAMPLE_LIMIT:
        capture.errors.append(message)


def _record_stream_parse_error(capture: StreamCapture, message: str) -> None:
    if not message or message in capture.parse_errors:
        return
    if len(capture.parse_errors) < _STREAM_ERROR_SAMPLE_LIMIT:
        capture.parse_errors.append(message)

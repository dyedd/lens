from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

from fastapi import HTTPException, Response

from ...models import ModelGroup, RoutingStrategy
from ..router import RouteTarget


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
    timeout_seconds: float

    def remaining_seconds(self) -> float | None:
        if self.timeout_seconds <= 0:
            return None
        return max(self.timeout_seconds - (perf_counter() - self.started_at), 0.0)

    def is_expired(self) -> bool:
        remaining = self.remaining_seconds()
        return remaining is not None and remaining <= 0

    def timeout_message(self) -> str:
        timeout_seconds = float(max(self.timeout_seconds, 0))
        if timeout_seconds.is_integer():
            timeout_label = str(int(timeout_seconds))
        else:
            timeout_label = f"{timeout_seconds:.3f}".rstrip("0").rstrip(".")
        return f"Gateway request timed out after {timeout_label}s"


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
    has_seen_first_chunk: bool = False
    chat_expected_choices: int = 1
    chat_finished_choices: set[int] = field(default_factory=set)
    first_token_latency_ms: int = 0
    response_content_chunks: list[str] = field(default_factory=list)
    client_response_content_chunks: list[str] = field(default_factory=list)
    event_buffer: str = ""
    event_format: str | None = None
    is_completed: bool = False
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
    deadline: _RequestDeadline | None = None
    error_status_code: int | None = None

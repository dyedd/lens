"""Unified protocol intermediate representation for responses.

A spoke parses an upstream response body into :class:`UnifiedResponse`, and
another spoke builds the client protocol's response body from it. Usage keeps
the same fields as the normalized usage that
``gateway/service/streaming/usage.py`` already derives from upstream payloads.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .unified import Citation, ContentPart, Refusal


class FinishReason(str, Enum):
    """Protocol-neutral stop reason."""

    END_TURN = "end_turn"
    MAX_TOKENS = "max_tokens"
    TOOL_USE = "tool_use"
    CONTENT_FILTER = "content_filter"
    STOP_SEQUENCE = "stop_sequence"
    OTHER = "other"


class ResponseStatus(str, Enum):
    """Terminal status of a response the client asked to observe."""

    COMPLETED = "completed"
    INCOMPLETE = "incomplete"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    reasoning_tokens: int = 0
    audio_input_tokens: int = 0
    audio_output_tokens: int = 0
    accepted_prediction_tokens: int = 0
    rejected_prediction_tokens: int = 0
    # Provider-executed searches billed alongside tokens.
    web_search_requests: int = 0


@dataclass(slots=True)
class UnifiedResponse:
    id: str = ""
    model: str = ""
    parts: list[ContentPart] = field(default_factory=list)
    finish: FinishReason = FinishReason.END_TURN
    usage: Usage = field(default_factory=Usage)
    status: ResponseStatus = ResponseStatus.COMPLETED
    # Machine-readable reason when ``status`` is ``incomplete``
    # (``max_output_tokens``, ``content_filter``).
    incomplete_reason: str = ""


__all__ = [
    "Citation",
    "FinishReason",
    "Refusal",
    "ResponseStatus",
    "UnifiedResponse",
    "Usage",
]

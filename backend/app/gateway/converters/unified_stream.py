"""Unified protocol intermediate representation for response streams.

Streams are represented as a flat sequence of semantic events: one start
event, per-block start/delta/stop events, and one terminal finish event
carrying usage. Parsers translate upstream wire chunks into these events and
serializers translate them into the client protocol's wire chunks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .unified_response import FinishReason, Usage


class BlockKind(str, Enum):
    TEXT = "text"
    REASONING = "reasoning"
    TOOL_CALL = "tool_call"


@dataclass(slots=True)
class StreamStart:
    id: str = ""
    model: str = ""


@dataclass(slots=True)
class BlockStart:
    index: int
    kind: BlockKind
    call_id: str = ""
    name: str = ""


@dataclass(slots=True)
class TextDelta:
    index: int
    text: str


@dataclass(slots=True)
class ReasoningDelta:
    index: int
    text: str


@dataclass(slots=True)
class SignatureDelta:
    """Provider-opaque reasoning state for a reasoning block."""

    index: int
    opaque: str


@dataclass(slots=True)
class ToolCallArgsDelta:
    index: int
    arguments: str


@dataclass(slots=True)
class BlockStop:
    index: int


@dataclass(slots=True)
class StreamFinish:
    reason: FinishReason = FinishReason.END_TURN
    usage: Usage = field(default_factory=Usage)


@dataclass(slots=True)
class StreamError:
    message: str


StreamEvent = (
    StreamStart
    | BlockStart
    | TextDelta
    | ReasoningDelta
    | SignatureDelta
    | ToolCallArgsDelta
    | BlockStop
    | StreamFinish
    | StreamError
)

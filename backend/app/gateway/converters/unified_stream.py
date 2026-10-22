"""Unified protocol intermediate representation for response streams.

Streams are represented as a flat sequence of semantic events: one start
event, per-block start/delta/stop events, and one terminal finish event
carrying usage. Parsers translate upstream wire chunks into these events and
serializers translate them into the client protocol's wire chunks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .unified_response import Citation, FinishReason, ResponseStatus, Usage


class BlockKind(str, Enum):
    TEXT = "text"
    REASONING = "reasoning"
    TOOL_CALL = "tool_call"
    # A provider-executed tool (web search, code interpreter, MCP, ...).
    SERVER_TOOL = "server_tool"
    REFUSAL = "refusal"


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
    # Wire item id for blocks that carry one (Responses ``output_item.added``).
    item_id: str = ""
    # Server-tool lifecycle marker (``in_progress``, ``searching``, ...).
    status: str = ""


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
class RefusalDelta:
    index: int
    text: str


@dataclass(slots=True)
class CitationDelta:
    """A source annotation attached to a text block as it streams."""

    index: int
    citation: Citation


@dataclass(slots=True)
class ServerToolStatusDelta:
    """A lifecycle change for a provider-executed tool block."""

    index: int
    status: str


@dataclass(slots=True)
class BlockStop:
    index: int


@dataclass(slots=True)
class StreamFinish:
    reason: FinishReason = FinishReason.END_TURN
    usage: Usage = field(default_factory=Usage)
    status: ResponseStatus = ResponseStatus.COMPLETED
    incomplete_reason: str = ""


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
    | RefusalDelta
    | CitationDelta
    | ServerToolStatusDelta
    | BlockStop
    | StreamFinish
    | StreamError
)

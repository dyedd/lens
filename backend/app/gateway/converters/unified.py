"""Unified protocol intermediate representation for chat-style requests.

Every spoke parses a wire request into these types and builds a wire request
from them, so any client protocol can reach any upstream protocol without a
per-pair converter. Provider-specific state (Anthropic thinking signatures,
Responses reasoning items, Gemini thought signatures) is carried in
``opaque`` fields together with its ``origin`` protocol, and replayed only
when the target protocol matches that origin.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ...models.protocols import ProtocolKind


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ToolChoiceMode(str, Enum):
    AUTO = "auto"
    REQUIRED = "required"
    NONE = "none"
    FUNCTION = "function"


@dataclass(slots=True)
class TextPart:
    text: str
    cache_breakpoint: bool = False


@dataclass(slots=True)
class ImagePart:
    """Inline image data or a URL reference; exactly one source is set."""

    media_type: str = ""
    data: str = ""
    url: str = ""
    detail: str = ""


@dataclass(slots=True)
class FilePart:
    """Inline file data, a URL reference, or an upstream file id."""

    media_type: str = ""
    data: str = ""
    url: str = ""
    file_id: str = ""
    filename: str = ""


@dataclass(slots=True)
class ReasoningPart:
    """Model reasoning text, provider-opaque state, or both.

    ``opaque`` holds the source protocol's own replay state: the Anthropic
    thinking signature, or the tokenized Responses reasoning item. ``origin``
    is the protocol that produced it; builders replay it only when their own
    protocol matches, and otherwise fall back to ``text``.
    """

    text: str = ""
    opaque: str = ""
    origin: ProtocolKind = ProtocolKind.OPENAI_CHAT


@dataclass(slots=True)
class ToolCallPart:
    call_id: str
    name: str
    arguments: str = ""
    origin: ProtocolKind | None = None
    opaque: str = ""


@dataclass(slots=True)
class ToolResultPart:
    call_id: str
    content: str = ""
    is_error: bool = False


ContentPart = (
    TextPart | ImagePart | FilePart | ReasoningPart | ToolCallPart | ToolResultPart
)


@dataclass(slots=True)
class Message:
    role: MessageRole
    parts: list[ContentPart] = field(default_factory=list)
    # True when the source protocol sent this message as a bare string rather
    # than a content array; builders emit the same shape to match the wire
    # contract the client already speaks.
    plain_text_content: bool = False


@dataclass(slots=True)
class ToolDefinition:
    name: str
    description: str = ""
    parameters: dict[str, Any] | None = None
    strict: bool | None = None


@dataclass(slots=True)
class ToolChoice:
    mode: ToolChoiceMode = ToolChoiceMode.AUTO
    name: str = ""
    allow_parallel: bool | None = None
    allowed_names: tuple[str, ...] = ()


@dataclass(slots=True)
class ReasoningIntent:
    """Requested reasoning behaviour, in protocol-neutral terms."""

    enabled: bool | None = None
    effort: str | None = None
    budget_tokens: int | None = None
    summarized: bool = False


@dataclass(slots=True)
class ResponseFormat:
    kind: str = ""
    schema: dict[str, Any] | None = None
    name: str = ""
    strict: bool | None = None


@dataclass(slots=True)
class GenerationConfig:
    max_output_tokens: int | None = None
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    stop: tuple[str, ...] = ()
    seed: int | None = None
    presence_penalty: float | None = None
    frequency_penalty: float | None = None


@dataclass(slots=True)
class UnifiedRequest:
    """A chat request in protocol-neutral form.

    ``passthrough`` carries request fields the source protocol and the target
    protocol share verbatim (``stream_options``, ``metadata``, prompt-cache
    hints); builders copy them in and let explicitly mapped fields win.
    ``replay_reasoning`` asks builders to send prior-turn reasoning text back
    upstream (DeepSeek and Kimi require it alongside tool calls);
    ``include_usage`` asks for usage reporting on upstream streams that make
    it optional.
    """

    model: str = ""
    stream: bool = False
    replay_reasoning: bool = False
    include_usage: bool = False
    passthrough: dict[str, Any] = field(default_factory=dict)
    # Protocol the client spoke. Some target protocols treat clients
    # differently (an Anthropic client's history cannot reference a Responses
    # response id, so Responses upstreams need ``store: false``).
    origin: ProtocolKind = ProtocolKind.OPENAI_CHAT
    system: list[ContentPart] = field(default_factory=list)
    messages: list[Message] = field(default_factory=list)
    tools: list[ToolDefinition] = field(default_factory=list)
    tool_choice: ToolChoice | None = None
    reasoning: ReasoningIntent | None = None
    response_format: ResponseFormat | None = None
    generation: GenerationConfig = field(default_factory=GenerationConfig)
    user_id: str = ""

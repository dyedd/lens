"""Unified protocol intermediate representation for chat-style requests.

Every spoke parses a wire request into these types and builds a wire request
from them, so any client protocol can reach any upstream protocol without a
per-pair converter. Provider-specific state (Anthropic thinking signatures,
Responses reasoning items, Gemini thought signatures) is carried in
``opaque`` fields together with its ``origin`` protocol, and replayed only
when the target protocol matches that origin.

Fields that only some protocols can express (custom and namespace tools,
server-side tools, multimodal tool results, prompt-cache breakpoints) keep a
protocol-neutral shape here so a spoke can either render them natively or
degrade them through :mod:`capabilities` instead of failing the whole request.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from ...models.protocols import ProtocolKind


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class ToolChoiceMode(str, Enum):
    AUTO = "auto"
    REQUIRED = "required"
    NONE = "none"
    FUNCTION = "function"


class ToolKind(str, Enum):
    """How the model is expected to produce a call for a declared tool.

    ``FUNCTION`` takes a JSON object validated against ``parameters``.
    ``CUSTOM`` takes free-form text (a grammar or an unconstrained string),
    which only the Responses protocol models natively; other targets render it
    as a single-string function argument.
    """

    FUNCTION = "function"
    CUSTOM = "custom"


class ServerToolKind(str, Enum):
    """Tools executed by the provider rather than by the client."""

    WEB_SEARCH = "web_search"
    FILE_SEARCH = "file_search"
    CODE_INTERPRETER = "code_interpreter"
    IMAGE_GENERATION = "image_generation"
    COMPUTER_USE = "computer_use"
    MCP = "mcp"
    TOOL_SEARCH = "tool_search"
    LOCAL_SHELL = "local_shell"
    SHELL = "shell"
    OTHER = "other"


class ReasoningKind(str, Enum):
    """What a reasoning part's opaque state stands for."""

    NONE = "none"
    # Anthropic ``thinking.signature``.
    SIGNATURE = "signature"
    # Anthropic ``redacted_thinking.data``.
    REDACTED = "redacted"
    # Responses ``reasoning.encrypted_content``.
    ENCRYPTED = "encrypted"
    # Gemini ``thoughtSignature``.
    THOUGHT_SIGNATURE = "thought_signature"


@dataclass(slots=True)
class Citation:
    """A source annotation attached to generated text."""

    url: str = ""
    title: str = ""
    start_index: int | None = None
    end_index: int | None = None
    raw: dict[str, Any] | None = None


@dataclass(slots=True)
class Refusal:
    """A refusal the model produced instead of text."""

    text: str = ""


@dataclass(slots=True)
class TextPart:
    text: str
    cache_breakpoint: bool = False
    # Raw ``cache_control`` object as the source protocol wrote it, so a Claude
    # target can replay its exact shape (``{"type": "ephemeral", "ttl": "1h"}``)
    # instead of rebuilding it from a boolean.
    cache_control: dict[str, Any] | None = None
    citations: list[Citation] = field(default_factory=list)


@dataclass(slots=True)
class ImagePart:
    """Inline image data or a URL reference; exactly one source is set."""

    media_type: str = ""
    data: str = ""
    url: str = ""
    detail: str = ""
    cache_control: dict[str, Any] | None = None


@dataclass(slots=True)
class FilePart:
    """Inline file data, a URL reference, or an upstream file id."""

    media_type: str = ""
    data: str = ""
    url: str = ""
    file_id: str = ""
    filename: str = ""
    cache_control: dict[str, Any] | None = None


@dataclass(slots=True)
class AudioPart:
    """Inline audio data or a URL reference."""

    media_type: str = ""
    data: str = ""
    url: str = ""
    format: str = ""


@dataclass(slots=True)
class ReasoningPart:
    """Model reasoning text, provider-opaque state, or both.

    ``opaque`` holds the source protocol's own replay state: the Anthropic
    thinking signature, or the tokenized Responses reasoning item. ``origin``
    is the protocol that produced it; builders replay it only when their own
    protocol matches and the model family is compatible, and otherwise fall
    back to ``text``. ``item_id`` and ``summary`` keep the Responses reasoning
    item's identity and summary parts so a reasoning-aware client sees the
    same structure it sent.
    """

    text: str = ""
    opaque: str = ""
    origin: ProtocolKind = ProtocolKind.OPENAI_CHAT
    kind: ReasoningKind = ReasoningKind.NONE
    item_id: str = ""
    summary: tuple[str, ...] = ()
    # Byte-level form for same-protocol replay: the source item exactly as the
    # provider wrote it. Only the protocol named by ``origin`` may re-emit it.
    sealed: dict[str, Any] | None = None


@dataclass(slots=True)
class ToolCallPart:
    call_id: str
    name: str
    arguments: str = ""
    origin: ProtocolKind | None = None
    opaque: str = ""
    kind: ToolKind = ToolKind.FUNCTION
    # Declaring namespace for namespaced tools; flat protocols concatenate it
    # into the wire name and restore it on the way back.
    namespace: str = ""
    cache_control: dict[str, Any] | None = None


@dataclass(slots=True)
class ToolResultPart:
    """A tool's output.

    ``content`` is the flattened text form used by every protocol. ``parts``
    carries the structured form (text plus images or files) that Anthropic and
    Responses accept but flat protocols cannot, so a builder can either emit
    it natively or degrade it through ``capabilities``.
    """

    call_id: str
    content: str = ""
    is_error: bool = False
    parts: list[ContentPart] = field(default_factory=list)
    cache_control: dict[str, Any] | None = None


@dataclass(slots=True)
class ServerToolPart:
    """A provider-executed tool call and, when the provider returned it, its result.

    Responses models this as a single ``web_search_call`` item; Anthropic models
    it as a ``server_tool_use`` block paired with a ``*_tool_result`` block. Both
    collapse into this part, and ``raw`` keeps the source item so a builder can
    replay it byte for byte when the target protocol is the one that produced it.
    """

    kind: ServerToolKind = ServerToolKind.OTHER
    name: str = ""
    call_id: str = ""
    status: str = ""
    arguments: str = ""
    output: list[ContentPart] = field(default_factory=list)
    origin: ProtocolKind = ProtocolKind.OPENAI_CHAT
    raw: dict[str, Any] | None = None


ContentPart = (
    TextPart
    | ImagePart
    | FilePart
    | AudioPart
    | ReasoningPart
    | ToolCallPart
    | ToolResultPart
    | ServerToolPart
    | Refusal
)


@dataclass(slots=True)
class Message:
    role: MessageRole
    parts: list[ContentPart] = field(default_factory=list)
    # True when the source protocol sent this message as a bare string rather
    # than a content array; builders emit the same shape to match the wire
    # contract the client already speaks.
    plain_text_content: bool = False
    # A breakpoint the source put on the message itself; Anthropic only accepts
    # it on content blocks, so builders sink it onto the last part.
    cache_control: dict[str, Any] | None = None


@dataclass(slots=True)
class ToolDefinition:
    name: str
    description: str = ""
    parameters: dict[str, Any] | None = None
    strict: bool | None = None
    kind: ToolKind = ToolKind.FUNCTION
    # Free-form input grammar for custom tools (``{"type": "grammar", ...}``).
    format: dict[str, Any] | None = None
    namespace: str = ""
    cache_control: dict[str, Any] | None = None


@dataclass(slots=True)
class ServerToolDefinition:
    """A provider-executed tool the client asked for."""

    kind: ServerToolKind = ServerToolKind.OTHER
    name: str = ""
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ToolChoice:
    mode: ToolChoiceMode = ToolChoiceMode.AUTO
    name: str = ""
    allow_parallel: bool | None = None
    allowed_names: tuple[str, ...] = ()
    namespace: str = ""
    kind: ToolKind = ToolKind.FUNCTION


@dataclass(slots=True)
class ReasoningIntent:
    """Requested reasoning behaviour, in protocol-neutral terms."""

    enabled: bool | None = None
    effort: str | None = None
    budget_tokens: int | None = None
    summarized: bool = False
    # Responses ``reasoning.summary`` value (``auto``, ``concise``, ``detailed``).
    summary: str | None = None


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
    logit_bias: dict[str, float] | None = None
    # Multi-choice decoding; only Chat and Gemini can express more than one.
    n: int | None = None
    logprobs: bool | None = None
    top_logprobs: int | None = None
    verbosity: str | None = None
    modalities: tuple[str, ...] = ()


@dataclass(slots=True)
class Continuation:
    """Server-side conversation state the client asked to reuse.

    Only the protocol that issued the identifier can honour it, so builders for
    other targets must drop it (and the caller must resend full history).
    """

    previous_response_id: str = ""
    conversation_id: str = ""
    store: bool | None = None
    prompt_cache_key: str = ""
    prompt_cache_retention: str = ""
    safety_identifier: str = ""
    service_tier: str = ""


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
    server_tools: list[ServerToolDefinition] = field(default_factory=list)
    tool_choice: ToolChoice | None = None
    reasoning: ReasoningIntent | None = None
    response_format: ResponseFormat | None = None
    generation: GenerationConfig = field(default_factory=GenerationConfig)
    continuation: Continuation = field(default_factory=Continuation)
    user_id: str = ""

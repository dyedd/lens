"""Anthropic Messages spoke: wire payloads <-> unified request.

Building covers the upstream direction (any chat-style client reaching an
Anthropic channel); parsing covers the same wire shapes coming back from an
Anthropic upstream. Reasoning state uses the existing Lens envelope
(``responses_common``) so Responses-origin thinking survives a round trip and
Anthropic-origin thinking is never rewritten.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Mapping
from typing import Any

from ...models.protocols import ProtocolKind
from . import cache, capabilities, repair
from .sse import (
    anthropic_block_delta,
    anthropic_block_start,
    anthropic_block_stop,
    format_sse_event,
    parse_sse_json_stream,
)
from .unified import (
    AudioPart,
    Citation,
    ContentPart,
    FilePart,
    ImagePart,
    Message,
    MessageRole,
    ReasoningIntent,
    ReasoningKind,
    ReasoningPart,
    Refusal,
    ServerToolDefinition,
    ServerToolKind,
    ServerToolPart,
    TextPart,
    ToolCallPart,
    ToolChoice,
    ToolChoiceMode,
    ToolDefinition,
    ToolKind,
    ToolResultPart,
    UnifiedRequest,
)
from .unified_response import FinishReason, UnifiedResponse, Usage
from .unified_stream import (
    BlockKind,
    BlockStart,
    BlockStop,
    CitationDelta,
    ReasoningDelta,
    RefusalDelta,
    ServerToolStatusDelta,
    SignatureDelta,
    StreamFinish,
    StreamStart,
    TextDelta,
    ToolCallArgsDelta,
)
from .validation import required_string

_ORIGIN = ProtocolKind.ANTHROPIC
DEFAULT_MAX_TOKENS = 4096
_REASONING_BUDGET_TOKENS = {
    "minimal": 1024,
    "low": 2048,
    "medium": 4096,
    "high": 8192,
    "xhigh": 16384,
    "max": 32768,
    "auto": 4096,
}


def build_anthropic_request(request: UnifiedRequest) -> dict[str, Any]:
    """Build an Anthropic Messages request body from the unified request."""
    # Breakpoints must be normalised and trimmed before anything is rendered,
    # because rendering copies each part's ``cache_control`` into the block.
    for message in request.messages:
        cache.sink_message_breakpoint(message)
    cache.apply_cache_budget(request)

    messages: list[dict[str, Any]] = []
    pending_results: list[dict[str, Any]] = []
    drops = capabilities.ContentDrops()
    for message in repair.repair_history(list(request.messages)):
        if message.role == MessageRole.TOOL:
            for part in message.parts:
                if isinstance(part, ToolResultPart):
                    pending_results.append(_tool_result_to_anthropic(part))
            continue
        if pending_results:
            messages.append({"role": "user", "content": pending_results})
            pending_results = []
        if message.role == MessageRole.SYSTEM:
            # Anthropic only accepts system content at the top level, so a
            # mid-conversation system turn keeps its place as a reminder.
            text = "\n".join(
                part.text for part in message.parts if isinstance(part, TextPart)
            )
            if text:
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": capabilities.as_reminder(text),
                            }
                        ],
                    }
                )
            continue
        rendered = _message_to_anthropic(message, request=request, drops=drops)
        if message.role is MessageRole.USER:
            content = rendered["content"]
            drops.keep(
                len(content) if isinstance(content, list) else int(bool(content))
            )
            drops.end_turn()
        messages.append(rendered)
    if pending_results:
        messages.append({"role": "user", "content": pending_results})
    drops.raise_if_empty()

    body: dict[str, Any] = dict(request.passthrough)
    body["model"] = request.model
    body["max_tokens"] = (
        request.generation.max_output_tokens
        if request.generation.max_output_tokens is not None
        else DEFAULT_MAX_TOKENS
    )
    messages = _merge_alternating(messages)
    body["messages"] = messages or [{"role": "user", "content": ""}]

    if request.system:
        system = _parts_to_anthropic_content(request.system, role=MessageRole.USER)
        if isinstance(system, str):
            if system:
                body["system"] = system
        elif system:
            body["system"] = system

    generation = request.generation
    if generation.temperature is not None:
        body["temperature"] = generation.temperature
    if generation.top_p is not None:
        body["top_p"] = generation.top_p
    if generation.top_k is not None:
        body["top_k"] = generation.top_k
    if generation.stop:
        body["stop_sequences"] = list(generation.stop)
    tools = [_tool_to_anthropic(tool) for tool in request.tools]
    tools.extend(
        _server_tool_to_anthropic_definition(tool) for tool in request.server_tools
    )
    if tools:
        body["tools"] = tools
    if request.tool_choice is not None and request.tools:
        body["tool_choice"] = _tool_choice_to_anthropic(request.tool_choice)
    if request.reasoning is not None:
        _apply_reasoning_intent(body, request.reasoning)
    if (
        request.response_format is not None
        and request.response_format.kind == "json_schema"
    ):
        body["output_config"] = {
            "format": {
                "type": "json_schema",
                "schema": request.response_format.schema or {},
            }
        }
    if request.user_id:
        body.setdefault("metadata", {})["user_id"] = request.user_id
    return body


def parse_anthropic_request(body: Mapping[str, Any]) -> UnifiedRequest:
    """Parse an Anthropic Messages request body into the unified request."""
    request = UnifiedRequest(model=_text(body.get("model")))
    request.stream = body.get("stream") is True
    request.generation.max_output_tokens = _optional_int(body.get("max_tokens"))
    request.generation.temperature = _optional_float(body.get("temperature"))
    request.generation.top_p = _optional_float(body.get("top_p"))
    request.generation.top_k = _optional_int(body.get("top_k"))
    stop = body.get("stop_sequences")
    if isinstance(stop, list):
        request.generation.stop = tuple(
            value for value in stop if isinstance(value, str)
        )
    request.reasoning = _anthropic_reasoning_intent(body)
    metadata = body.get("metadata")
    if isinstance(metadata, Mapping):
        request.user_id = _text(metadata.get("user_id"))
    request.system = _anthropic_system_parts(body.get("system"))

    messages = body.get("messages")
    if not isinstance(messages, list):
        raise ValueError("Anthropic request messages must be an array")
    for message in messages:
        request.messages.extend(_anthropic_message(message))

    request.tools, request.server_tools = _anthropic_tools(body.get("tools"))
    request.tool_choice = _anthropic_tool_choice(body.get("tool_choice"))
    return request


def _anthropic_system_parts(value: Any) -> list[ContentPart]:
    if value is None:
        return []
    if isinstance(value, str):
        return [TextPart(text=value)] if value else []
    if not isinstance(value, list):
        raise ValueError("Anthropic system must be a string or array")
    parts: list[ContentPart] = []
    for block in value:
        if not isinstance(block, Mapping):
            raise ValueError("Anthropic system must contain objects")
        if block.get("type") != "text":
            raise ValueError("Unsupported Anthropic system block type")
        hint = cache.normalize_cache_control(block.get("cache_control"))
        parts.append(
            TextPart(
                text=required_string(
                    block.get("text"),
                    "Anthropic system text blocks must contain text",
                    allow_empty=True,
                ),
                cache_breakpoint=hint is not None,
                cache_control=hint,
            )
        )
    return parts


def _anthropic_message(value: Any) -> list[Message]:
    if not isinstance(value, Mapping):
        raise ValueError("Anthropic messages must contain objects")
    role = value.get("role")
    if role not in {"user", "assistant"}:
        raise ValueError("Anthropic messages must contain a valid role")
    content = value.get("content")
    if isinstance(content, str):
        return [
            Message(
                role=MessageRole(role),
                parts=[TextPart(text=content)],
                plain_text_content=True,
            )
        ]
    if not isinstance(content, list):
        raise ValueError("Anthropic message content must be a string or array")

    media: list[ContentPart] = []
    texts: list[str] = []
    text_cache: dict[str, Any] | None = None
    thinking: list[ReasoningPart] = []
    tool_calls: list[ContentPart] = []
    tool_results: list[ContentPart] = []
    server_parts: list[ServerToolPart] = []
    for block in content:
        if not isinstance(block, Mapping):
            raise ValueError("Anthropic message content must contain objects")
        block_type = block.get("type")
        if block_type == "text":
            texts.append(
                required_string(
                    block.get("text"),
                    "Anthropic text blocks must contain text",
                    allow_empty=True,
                )
            )
            hint = cache.normalize_cache_control(block.get("cache_control"))
            if hint is not None:
                text_cache = hint
        elif block_type == "thinking":
            thinking.append(
                ReasoningPart(
                    text=required_string(
                        block.get("thinking"),
                        "Anthropic thinking blocks must contain thinking",
                        allow_empty=True,
                    ),
                    opaque=_text(block.get("signature")),
                    origin=_ORIGIN,
                    kind=ReasoningKind.SIGNATURE,
                )
            )
        elif block_type == "redacted_thinking":
            thinking.append(
                ReasoningPart(
                    opaque=required_string(
                        block.get("data"),
                        "Anthropic redacted_thinking must contain data",
                        allow_empty=True,
                    ),
                    origin=_ORIGIN,
                    kind=ReasoningKind.REDACTED,
                )
            )
        elif block_type in {"image", "document"}:
            part = _anthropic_media(block)
            part.cache_control = cache.normalize_cache_control(
                block.get("cache_control")
            )
            media.append(part)
        elif block_type == "tool_use":
            tool_input = block.get("input", {})
            if not isinstance(tool_input, Mapping):
                raise ValueError("Anthropic tool_use input must be an object")
            tool_calls.append(
                ToolCallPart(
                    call_id=required_string(
                        block.get("id"), "Anthropic tool_use must contain id"
                    ),
                    name=required_string(
                        block.get("name"), "Anthropic tool_use must contain name"
                    ),
                    arguments=json.dumps(dict(tool_input), ensure_ascii=False),
                    origin=_ORIGIN,
                )
            )
        elif block_type == "tool_result":
            tool_results.append(_anthropic_tool_result(block))
        elif block_type == "server_tool_use":
            tool_input = block.get("input", {})
            name = required_string(
                block.get("name"), "Anthropic server_tool_use must contain name"
            )
            server_parts.append(
                ServerToolPart(
                    kind=_anthropic_server_tool_kind(name),
                    name=name,
                    call_id=required_string(
                        block.get("id"), "Anthropic server_tool_use must contain id"
                    ),
                    status="in_progress",
                    arguments=json.dumps(tool_input, ensure_ascii=False)
                    if isinstance(tool_input, Mapping)
                    else "",
                    origin=_ORIGIN,
                )
            )
        elif isinstance(block_type, str) and block_type.endswith("_tool_result"):
            _attach_server_result(server_parts, block, block_type)
        else:
            raise ValueError(f"Unsupported Anthropic content block type: {block_type}")

    messages: list[Message] = []
    for result in tool_results:
        messages.append(Message(role=MessageRole.TOOL, parts=[result]))
    parts: list[ContentPart] = []
    if thinking and role == "assistant":
        parts.extend(thinking)
    if texts:
        parts.append(TextPart(text="\n".join(texts), cache_control=text_cache))
    parts.extend(media)
    parts.extend(tool_calls)
    parts.extend(server_parts)
    if parts:
        messages.append(
            Message(
                role=MessageRole(role),
                parts=parts,
                cache_control=cache.normalize_cache_control(value.get("cache_control")),
            )
        )
    return messages


def _attach_server_result(
    parts: list[ServerToolPart], block: Mapping[str, Any], block_type: str
) -> None:
    """Fold a provider tool's result block onto the call it answers."""
    call_id = _text(block.get("tool_use_id"))
    output: list[ContentPart] = []
    content = block.get("content")
    if isinstance(content, str):
        output.append(TextPart(text=content))
    elif isinstance(content, list):
        for item in content:
            if not isinstance(item, Mapping):
                continue
            item_type = item.get("type")
            if item_type in {"web_search_result", "text"}:
                title = _text(item.get("title"))
                url = _text(item.get("url"))
                text = _text(item.get("text")) or _text(item.get("content"))
                if url:
                    output.append(
                        TextPart(
                            text=f"{title or url}\n{url}",
                            citations=[Citation(url=url, title=title)],
                        )
                    )
                elif text:
                    output.append(TextPart(text=text))
            elif item_type == "image":
                output.append(_anthropic_media(item))
    for part in parts:
        if part.call_id and part.call_id == call_id:
            part.output = output
            part.status = "failed" if block.get("is_error") is True else "completed"
            return
    # A result whose call scrolled out of history still has to survive, so it
    # becomes a standalone server-tool part rather than vanishing.
    parts.append(
        ServerToolPart(
            kind=_anthropic_server_tool_kind(block_type.replace("_tool_result", "")),
            call_id=call_id,
            status="completed",
            output=output,
            origin=_ORIGIN,
        )
    )


def _anthropic_media(block: Mapping[str, Any]) -> ContentPart:
    source = block.get("source")
    if not isinstance(source, Mapping):
        raise ValueError("Anthropic media must contain a source object")
    source_type = source.get("type")
    if block.get("type") == "image":
        if source_type == "url":
            return ImagePart(
                url=required_string(
                    source.get("url"), "Anthropic images must contain url"
                )
            )
        if source_type == "base64":
            return ImagePart(
                media_type=required_string(
                    source.get("media_type"),
                    "Anthropic base64 images must contain media_type",
                ),
                data=required_string(
                    source.get("data"), "Anthropic base64 images must contain data"
                ),
            )
        raise ValueError("Unsupported Anthropic image source type")

    filename = block.get("title")
    if not isinstance(filename, str) or not filename:
        filename = "document.pdf"
    if source_type == "url":
        return FilePart(
            url=required_string(
                source.get("url"), "Anthropic URL documents must contain url"
            ),
            filename=filename,
        )
    if source_type == "base64":
        return FilePart(
            media_type=required_string(
                source.get("media_type"),
                "Anthropic base64 documents must contain media_type",
            ),
            data=required_string(
                source.get("data"), "Anthropic base64 documents must contain data"
            ),
            filename=filename,
        )
    if source_type == "text":
        return FilePart(
            media_type="text/plain",
            data=required_string(
                source.get("data"),
                "Anthropic text documents must contain data",
                allow_empty=True,
            ),
            filename=filename,
        )
    if source_type == "file":
        return FilePart(
            file_id=required_string(
                source.get("file_id"), "Anthropic file sources must contain file_id"
            ),
            filename=filename,
        )
    if source_type == "content":
        content = source.get("content")
        if isinstance(content, str):
            return FilePart(media_type="text/plain", data=content, filename=filename)
        if isinstance(content, list):
            texts = [
                required_string(
                    item.get("text"),
                    "Anthropic content documents must contain text",
                    allow_empty=True,
                )
                for item in content
                if isinstance(item, Mapping) and item.get("type") == "text"
            ]
            return FilePart(
                media_type="text/plain",
                data="\n".join(texts),
                filename=filename,
            )
        raise ValueError("Anthropic content documents must contain string or array")
    raise ValueError("Unsupported Anthropic document source type")


def _anthropic_tool_result(block: Mapping[str, Any]) -> ToolResultPart:
    """Parse a tool result, keeping media beside the text.

    Anthropic lets a tool return images and documents inline; flattening them to
    text loses them entirely on the way to a target that accepts them too.
    """
    content = block.get("content")
    texts: list[str] = []
    parts: list[ContentPart] = []
    if isinstance(content, str):
        texts.append(content)
    elif isinstance(content, list):
        for item in content:
            if not isinstance(item, Mapping):
                raise ValueError("Anthropic tool_result content must contain objects")
            block_type = item.get("type")
            if block_type == "text":
                texts.append(
                    required_string(
                        item.get("text"),
                        "Anthropic tool_result text blocks must contain text",
                        allow_empty=True,
                    )
                )
            elif block_type in {"image", "document"}:
                parts.append(_anthropic_media(item))
            else:
                raise ValueError("Unsupported Anthropic tool_result block type")
    elif content is not None:
        raise ValueError("Anthropic tool_result content must be a string or array")
    return ToolResultPart(
        call_id=required_string(
            block.get("tool_use_id"),
            "Anthropic tool_result must contain tool_use_id",
        ),
        content="\n".join(texts),
        is_error=block.get("is_error") is True,
        parts=parts,
    )


def _anthropic_tools(
    value: Any,
) -> tuple[list[ToolDefinition], list[ServerToolDefinition]]:
    """Split Anthropic tools into client-declared and provider-executed ones.

    A dated ``type`` (``web_search_20250305``) marks a tool Anthropic runs
    itself; everything else is a client tool the model calls back through.
    """
    if value is None:
        return [], []
    if not isinstance(value, list):
        raise ValueError("Anthropic tools must be an array")
    tools: list[ToolDefinition] = []
    server_tools: list[ServerToolDefinition] = []
    for tool in value:
        if not isinstance(tool, Mapping):
            raise ValueError("Anthropic tools must contain objects")
        tool_type = tool.get("type")
        if isinstance(tool_type, str) and _is_anthropic_server_tool(tool_type):
            server_tools.append(
                ServerToolDefinition(
                    kind=_anthropic_server_tool_kind(tool_type),
                    name=_text(tool.get("name")) or tool_type,
                    options={
                        key: item
                        for key, item in tool.items()
                        if key not in {"name", "type"}
                    },
                )
            )
            continue
        if tool_type not in {None, "custom"}:
            raise ValueError("Unsupported Anthropic tool type")
        input_schema = tool.get("input_schema")
        if not isinstance(input_schema, Mapping):
            raise ValueError("Anthropic tools must contain input_schema")
        hint = cache.normalize_cache_control(tool.get("cache_control"))
        tools.append(
            ToolDefinition(
                name=required_string(
                    tool.get("name"), "Anthropic tools must contain name"
                ),
                description=_text(tool.get("description")),
                parameters=dict(input_schema),
                cache_control=hint,
            )
        )
    return tools, server_tools


def _is_anthropic_server_tool(tool_type: str) -> bool:
    return "_20" in tool_type and tool_type not in {"custom"}


def _anthropic_server_tool_kind(tool_type: str) -> ServerToolKind:
    lowered = tool_type.lower()
    if "web_search" in lowered:
        return ServerToolKind.WEB_SEARCH
    if "code_execution" in lowered or "code_interpreter" in lowered:
        return ServerToolKind.CODE_INTERPRETER
    if "tool_search" in lowered:
        return ServerToolKind.TOOL_SEARCH
    if "computer" in lowered:
        return ServerToolKind.COMPUTER_USE
    if "bash" in lowered or "shell" in lowered:
        return ServerToolKind.SHELL
    return ServerToolKind.OTHER


def _anthropic_tool_choice(value: Any) -> ToolChoice | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError("Anthropic tool_choice must be an object")
    choice_type = value.get("type", "auto")
    disable_parallel = value.get("disable_parallel_tool_use")
    allow_parallel = (
        not disable_parallel if isinstance(disable_parallel, bool) else None
    )
    if choice_type == "auto":
        return ToolChoice(mode=ToolChoiceMode.AUTO, allow_parallel=allow_parallel)
    if choice_type == "any":
        return ToolChoice(mode=ToolChoiceMode.REQUIRED, allow_parallel=allow_parallel)
    if choice_type == "none":
        return ToolChoice(mode=ToolChoiceMode.NONE)
    if choice_type == "tool":
        return ToolChoice(
            mode=ToolChoiceMode.FUNCTION,
            name=required_string(
                value.get("name"), "Anthropic tool_choice tool must contain name"
            ),
            allow_parallel=allow_parallel,
        )
    raise ValueError("Unsupported Anthropic tool_choice type")


def build_anthropic_response(response: UnifiedResponse) -> dict[str, Any]:
    """Build an Anthropic Messages response body from the unified response."""
    content: list[dict[str, Any]] = []
    for part in response.parts:
        if isinstance(part, ReasoningPart):
            content.append(_reasoning_to_anthropic(part))
        elif isinstance(part, TextPart):
            if part.text:
                block: dict[str, Any] = {"type": "text", "text": part.text}
                if part.citations:
                    block["citations"] = [
                        _citation_to_anthropic(citation) for citation in part.citations
                    ]
                content.append(block)
        elif isinstance(part, Refusal):
            # Anthropic has no refusal block, so the text carries the refusal
            # rather than dropping it from the answer.
            content.append({"type": "text", "text": part.text})
        elif isinstance(part, ToolCallPart):
            content.append(_tool_call_to_anthropic(part))
        elif isinstance(part, ServerToolPart):
            content.extend(_server_tool_to_anthropic(part))
    whether_tools = any(isinstance(part, ToolCallPart) for part in response.parts)
    return {
        "id": response.id or f"msg_{uuid.uuid4().hex[:24]}",
        "type": "message",
        "role": "assistant",
        "model": response.model,
        "content": content,
        "stop_reason": _anthropic_stop_reason(response.finish, has_tools=whether_tools),
        "stop_sequence": None,
        "usage": _anthropic_usage_wire(response.usage),
    }


def _citation_to_anthropic(citation: Citation) -> dict[str, Any]:
    if citation.raw:
        return dict(citation.raw)
    result: dict[str, Any] = {
        "type": "web_search_result_location",
        "url": citation.url,
        "title": citation.title or citation.url,
        "cited_text": "",
    }
    if citation.start_index is not None:
        result["start_char_index"] = citation.start_index
    if citation.end_index is not None:
        result["end_char_index"] = citation.end_index
    return result


def parse_anthropic_response(body: Mapping[str, Any]) -> UnifiedResponse:
    """Parse an Anthropic Messages response body into the unified response."""
    content = body.get("content")
    if not isinstance(content, list):
        raise ValueError("Anthropic response must contain content")
    usage = body.get("usage")
    return UnifiedResponse(
        id=_text(body.get("id")),
        model=_text(body.get("model")),
        parts=_anthropic_content_parts(content),
        finish=_anthropic_finish_reason(body.get("stop_reason")),
        usage=_anthropic_usage(usage if isinstance(usage, Mapping) else {}),
    )


def _message_to_anthropic(
    message: Message,
    *,
    request: UnifiedRequest,
    drops: capabilities.ContentDrops | None = None,
) -> dict[str, Any]:
    content = _parts_to_anthropic_content(
        list(message.parts),
        role=message.role,
        replay_reasoning=request.replay_reasoning,
        drops=drops,
    )
    return {"role": message.role.value, "content": content}


def _parts_to_anthropic_content(
    parts: list[ContentPart],
    *,
    role: MessageRole,
    replay_reasoning: bool = False,
    drops: capabilities.ContentDrops | None = None,
) -> str | list[dict[str, Any]]:
    text_blocks: list[dict[str, Any]] = []
    media_blocks: list[dict[str, Any]] = []
    call_blocks: list[dict[str, Any]] = []
    result_blocks: list[dict[str, Any]] = []
    server_blocks: list[dict[str, Any]] = []
    thinking_blocks: list[dict[str, Any]] = []
    dropped = False
    for part in parts:
        if isinstance(part, TextPart):
            block: dict[str, Any] = {"type": "text", "text": part.text}
            _attach_cache(block, part.cache_control)
            text_blocks.append(block)
        elif isinstance(part, (ImagePart, FilePart)):
            block = (
                _image_to_anthropic(part)
                if isinstance(part, ImagePart)
                else _file_to_anthropic(part)
            )
            _attach_cache(block, part.cache_control)
            media_blocks.append(block)
        elif isinstance(part, AudioPart):
            # Anthropic has no audio block, so the part leaves its turn rather
            # than failing a request that is otherwise sendable.
            dropped = True
            if drops is not None:
                drops.drop("audio")
        elif isinstance(part, ReasoningPart) and role is MessageRole.ASSISTANT:
            if replay_reasoning or part.origin is _ORIGIN:
                thinking_blocks.append(_reasoning_to_anthropic(part))
        elif isinstance(part, ToolCallPart):
            call_blocks.append(_tool_call_to_anthropic(part))
        elif isinstance(part, ToolResultPart):
            result_blocks.append(_tool_result_to_anthropic(part))
        elif isinstance(part, ServerToolPart):
            server_blocks.extend(_server_tool_to_anthropic(part))
        elif isinstance(part, Refusal):
            text_blocks.append({"type": "text", "text": part.text})

    # Anthropic requires thinking first in an assistant turn, and tool results
    # first in a user turn.
    blocks = (
        [*thinking_blocks, *text_blocks, *media_blocks, *server_blocks, *call_blocks]
        if role is MessageRole.ASSISTANT
        else [*result_blocks, *server_blocks, *text_blocks, *media_blocks]
    )
    # Collapse to a bare string only for an untouched all-text turn, so a turn
    # that lost a part keeps the block form its client sent.
    if not dropped and all(
        block.get("type") == "text" and "cache_control" not in block for block in blocks
    ):
        return "\n".join(block["text"] for block in blocks)
    return blocks


def _attach_cache(block: dict[str, Any], cache_control: dict[str, Any] | None) -> None:
    if cache_control is not None:
        block["cache_control"] = cache_control


def _server_tool_to_anthropic(part: ServerToolPart) -> list[dict[str, Any]]:
    """Render a provider tool call and its result as Anthropic server blocks."""
    kind = part.kind.value
    if not part.call_id:
        # A result whose call is gone still has to be readable somewhere.
        text = _server_output_text(part)
        return [{"type": "text", "text": text}] if text else []
    name = part.name or kind
    try:
        tool_input = json.loads(part.arguments) if part.arguments else {}
    except ValueError:
        tool_input = {}
    blocks: list[dict[str, Any]] = [
        {
            "type": "server_tool_use",
            "id": part.call_id,
            "name": name,
            "input": tool_input if isinstance(tool_input, dict) else {},
        }
    ]
    if part.output:
        result_type = f"{name}_tool_result"
        blocks.append(
            {
                "type": result_type,
                "tool_use_id": part.call_id,
                "content": _server_result_content(part),
            }
        )
    return blocks


def _server_result_content(part: ServerToolPart) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = []
    for item in part.output:
        if isinstance(item, TextPart):
            if item.citations:
                for citation in item.citations:
                    content.append(
                        {
                            "type": "web_search_result",
                            "url": citation.url,
                            "title": citation.title or citation.url,
                        }
                    )
                continue
            content.append({"type": "text", "text": item.text})
        elif isinstance(item, ImagePart):
            content.append(_image_to_anthropic(item))
    return content


def _server_output_text(part: ServerToolPart) -> str:
    label = part.name or part.kind.value
    text = " ".join(
        item.text for item in part.output if isinstance(item, TextPart) and item.text
    )
    return f"[{label}] {text}".strip()


def _image_to_anthropic(part: ImagePart) -> dict[str, Any]:
    if part.data:
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": part.media_type or "image/png",
                "data": part.data,
            },
        }
    if part.url:
        return {"type": "image", "source": {"type": "url", "url": part.url}}
    raise ValueError("Unified image part must contain data or a URL")


def _file_to_anthropic(part: FilePart) -> dict[str, Any]:
    if part.data:
        media_type = part.media_type or "application/pdf"
        if media_type.startswith("text/"):
            return {
                "type": "document",
                "source": {"type": "text", "media_type": media_type, "data": part.data},
            }
        return {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": part.data,
            },
        }
    if part.url:
        return {"type": "document", "source": {"type": "url", "url": part.url}}
    if part.file_id:
        return {
            "type": "document",
            "source": {"type": "file", "file_id": part.file_id},
        }
    raise ValueError("Unified file part must contain data, a URL, or a file id")


def _reasoning_to_anthropic(part: ReasoningPart) -> dict[str, Any]:
    if part.kind is ReasoningKind.REDACTED and part.opaque:
        return {"type": "redacted_thinking", "data": part.opaque}
    if part.text:
        block: dict[str, Any] = {"type": "thinking", "thinking": part.text}
        if part.opaque:
            block["signature"] = part.opaque
        return block
    if part.opaque:
        return {"type": "redacted_thinking", "data": part.opaque}
    return {"type": "thinking", "thinking": ""}


def _tool_call_to_anthropic(part: ToolCallPart) -> dict[str, Any]:
    name = capabilities.namespaced_name(part.namespace, part.name)
    if part.kind is ToolKind.CUSTOM:
        # Anthropic has no free-form tool, so the raw input is carried in the
        # single-string argument shape :func:`render_custom_tool` declared.
        return {
            "type": "tool_use",
            "id": part.call_id,
            "name": name,
            "input": {"input": capabilities.unwrap_custom_tool_input(part.arguments)},
        }
    arguments = part.arguments or "{}"
    try:
        parsed_input = json.loads(arguments)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid tool call arguments JSON") from exc
    if not isinstance(parsed_input, Mapping):
        raise ValueError("Tool call arguments must be a JSON object")
    return {
        "type": "tool_use",
        "id": part.call_id,
        "name": name,
        "input": dict(parsed_input),
    }


def _tool_result_to_anthropic(part: ToolResultPart) -> dict[str, Any]:
    block: dict[str, Any] = {"type": "tool_result", "tool_use_id": part.call_id}
    if part.parts:
        content: list[dict[str, Any]] = []
        if part.content:
            content.append({"type": "text", "text": part.content})
        for nested in part.parts:
            if isinstance(nested, ImagePart):
                content.append(_image_to_anthropic(nested))
            elif isinstance(nested, FilePart):
                content.append(_file_to_anthropic(nested))
            elif isinstance(nested, TextPart):
                content.append({"type": "text", "text": nested.text})
        block["content"] = content or part.content
    else:
        block["content"] = part.content
    if part.is_error:
        block["is_error"] = True
    _attach_cache(block, part.cache_control)
    return block


def _tool_to_anthropic(tool: ToolDefinition) -> dict[str, Any]:
    name = capabilities.namespaced_name(tool.namespace, tool.name)
    if tool.kind is ToolKind.CUSTOM:
        description, parameters = capabilities.render_custom_tool(
            tool.description, tool.format
        )
        result: dict[str, Any] = {
            "name": name,
            "description": description,
            "input_schema": parameters,
        }
    else:
        result = {"name": name}
        if tool.description:
            result["description"] = tool.description
        result["input_schema"] = tool.parameters or {
            "type": "object",
            "properties": {},
        }
    _attach_cache(result, tool.cache_control)
    return result


def _server_tool_to_anthropic_definition(tool: ServerToolDefinition) -> dict[str, Any]:
    """Declare a provider-executed tool the way Anthropic expects it."""
    result: dict[str, Any] = {
        "type": _anthropic_server_type(tool.kind),
        "name": tool.name or _anthropic_server_type(tool.kind),
    }
    result.update(tool.options)
    return result


def _anthropic_server_type(kind: ServerToolKind) -> str:
    return {
        ServerToolKind.WEB_SEARCH: "web_search_20250305",
        ServerToolKind.CODE_INTERPRETER: "code_execution_20250522",
        ServerToolKind.COMPUTER_USE: "computer_20250124",
        ServerToolKind.TOOL_SEARCH: "tool_search_tool_regex_20251119",
        ServerToolKind.SHELL: "bash_20250124",
    }.get(kind, "web_search_20250305")


def _tool_choice_to_anthropic(choice: ToolChoice) -> dict[str, Any]:
    if choice.mode == ToolChoiceMode.FUNCTION:
        return {
            "type": "tool",
            "name": capabilities.namespaced_name(choice.namespace, choice.name),
        }
    if choice.mode == ToolChoiceMode.REQUIRED:
        return {"type": "any"}
    if choice.mode == ToolChoiceMode.NONE:
        return {"type": "none"}
    result: dict[str, Any] = {"type": "auto"}
    if choice.allow_parallel is not None:
        result["disable_parallel_tool_use"] = not choice.allow_parallel
    return result


def _apply_reasoning_intent(body: dict[str, Any], intent: ReasoningIntent) -> None:
    if intent.enabled is False or intent.effort == "none":
        body["thinking"] = {"type": "disabled"}
        return
    if intent.effort:
        body.setdefault("output_config", {})["effort"] = intent.effort
        body["thinking"] = {"type": "adaptive"}
        return
    budget = intent.budget_tokens or _REASONING_BUDGET_TOKENS.get(
        intent.effort or "", DEFAULT_MAX_TOKENS
    )
    body["thinking"] = {"type": "enabled", "budget_tokens": max(budget, 1024)}


def _merge_alternating(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for message in messages:
        if merged and merged[-1]["role"] == message["role"]:
            merged[-1]["content"] = _concatenate_anthropic_content(
                merged[-1]["content"], message["content"]
            )
            continue
        merged.append(message)
    if merged and merged[0]["role"] != "user":
        merged.insert(0, {"role": "user", "content": ""})
    return merged


def _concatenate_anthropic_content(first: Any, second: Any) -> list[dict[str, Any]]:
    def blocks(value: Any) -> list[dict[str, Any]]:
        if isinstance(value, str):
            return [{"type": "text", "text": value}] if value else []
        return list(value)

    return [*blocks(first), *blocks(second)]


def _anthropic_content_parts(content: list[Any]) -> list[ContentPart]:
    parts: list[ContentPart] = []
    servers: list[ServerToolPart] = []
    for block in content:
        if not isinstance(block, Mapping):
            raise ValueError("Anthropic content must contain objects")
        block_type = block.get("type")
        if block_type == "text":
            parts.append(
                TextPart(
                    text=required_string(
                        block.get("text"),
                        "Anthropic text blocks must contain text",
                        allow_empty=True,
                    ),
                    citations=_anthropic_citations(block.get("citations")),
                )
            )
        elif block_type == "thinking":
            parts.append(
                ReasoningPart(
                    text=required_string(
                        block.get("thinking"),
                        "Anthropic thinking blocks must contain thinking",
                        allow_empty=True,
                    ),
                    opaque=_text(block.get("signature")),
                    origin=_ORIGIN,
                    kind=ReasoningKind.SIGNATURE,
                )
            )
        elif block_type == "redacted_thinking":
            parts.append(
                ReasoningPart(
                    opaque=required_string(
                        block.get("data"),
                        "Anthropic redacted_thinking must contain data",
                        allow_empty=True,
                    ),
                    origin=_ORIGIN,
                    kind=ReasoningKind.REDACTED,
                )
            )
        elif block_type == "tool_use":
            tool_input = block.get("input", {})
            if not isinstance(tool_input, Mapping):
                raise ValueError("Anthropic tool_use input must be an object")
            parts.append(
                ToolCallPart(
                    call_id=required_string(
                        block.get("id"), "Anthropic tool_use must contain id"
                    ),
                    name=required_string(
                        block.get("name"), "Anthropic tool_use must contain name"
                    ),
                    arguments=json.dumps(dict(tool_input), ensure_ascii=False),
                    origin=_ORIGIN,
                )
            )
        elif block_type == "server_tool_use":
            name = required_string(
                block.get("name"), "Anthropic server_tool_use must contain name"
            )
            tool_input = block.get("input")
            servers.append(
                ServerToolPart(
                    kind=_anthropic_server_tool_kind(name),
                    name=name,
                    call_id=required_string(
                        block.get("id"), "Anthropic server_tool_use must contain id"
                    ),
                    status="in_progress",
                    arguments=json.dumps(tool_input, ensure_ascii=False)
                    if isinstance(tool_input, Mapping)
                    else "",
                    origin=_ORIGIN,
                )
            )
        elif isinstance(block_type, str) and block_type.endswith("_tool_result"):
            _attach_server_result(servers, block, block_type)
    parts.extend(servers)
    return parts


def _anthropic_citations(value: Any) -> list[Citation]:
    if not isinstance(value, list):
        return []
    citations: list[Citation] = []
    for block in value:
        if not isinstance(block, Mapping):
            continue
        url = _text(block.get("url"))
        if not url:
            continue
        citations.append(
            Citation(
                url=url,
                title=_text(block.get("title")),
                start_index=_optional_index(block.get("start_char_index")),
                end_index=_optional_index(block.get("end_char_index")),
                raw=dict(block),
            )
        )
    return citations


def _optional_index(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _anthropic_usage(value: Mapping[str, Any]) -> Usage:
    """Read Anthropic usage, whose input_tokens excludes cached and written tokens."""
    cached = _optional_int(value.get("cache_read_input_tokens")) or 0
    cache_write = _optional_int(value.get("cache_creation_input_tokens")) or 0
    usage = Usage(
        input_tokens=(_optional_int(value.get("input_tokens")) or 0)
        + cached
        + cache_write,
        output_tokens=_optional_int(value.get("output_tokens")) or 0,
        cached_input_tokens=cached,
        cache_creation_input_tokens=cache_write,
    )
    output_details = value.get("output_tokens_details")
    if isinstance(output_details, Mapping):
        usage.reasoning_tokens = (
            _optional_int(output_details.get("thinking_tokens")) or 0
        )
    return usage


def _anthropic_usage_wire(usage: Usage) -> dict[str, Any]:
    """Write Anthropic usage, whose input_tokens excludes cached and written tokens."""
    result: dict[str, Any] = {
        "input_tokens": max(
            usage.input_tokens
            - usage.cached_input_tokens
            - usage.cache_creation_input_tokens,
            0,
        ),
        "output_tokens": usage.output_tokens,
    }
    if usage.cached_input_tokens or usage.cache_creation_input_tokens:
        result["cache_creation_input_tokens"] = usage.cache_creation_input_tokens
        result["cache_read_input_tokens"] = usage.cached_input_tokens
    return result


def _anthropic_finish_reason(value: Any) -> FinishReason:
    return {
        "end_turn": FinishReason.END_TURN,
        "stop_sequence": FinishReason.STOP_SEQUENCE,
        "max_tokens": FinishReason.MAX_TOKENS,
        "tool_use": FinishReason.TOOL_USE,
        "refusal": FinishReason.CONTENT_FILTER,
        "pause_turn": FinishReason.OTHER,
    }.get(value, FinishReason.END_TURN)


def _anthropic_stop_reason(reason: FinishReason, *, has_tools: bool) -> str:
    if reason == FinishReason.TOOL_USE or (
        reason == FinishReason.END_TURN and has_tools
    ):
        return "tool_use"
    return {
        FinishReason.END_TURN: "end_turn",
        FinishReason.MAX_TOKENS: "max_tokens",
        FinishReason.CONTENT_FILTER: "refusal",
        FinishReason.STOP_SEQUENCE: "stop_sequence",
        FinishReason.OTHER: "end_turn",
    }[reason]


def _anthropic_reasoning_intent(body: Mapping[str, Any]) -> ReasoningIntent | None:
    thinking = body.get("thinking")
    output_config = body.get("output_config")
    effort = output_config.get("effort") if isinstance(output_config, Mapping) else None
    intent = ReasoningIntent()
    if isinstance(thinking, Mapping):
        thinking_type = thinking.get("type")
        if thinking_type == "disabled":
            return ReasoningIntent(enabled=False, effort="none")
        if thinking_type == "enabled":
            intent.enabled = True
            intent.budget_tokens = _optional_int(thinking.get("budget_tokens"))
            intent.summarized = True
        elif thinking_type == "adaptive":
            intent.enabled = True
            intent.summarized = thinking.get("display", "summarized") != "omitted"
    if isinstance(effort, str) and effort:
        intent.effort = effort
        intent.enabled = effort != "none"
    if intent.effort is None and intent.enabled is None:
        return None
    return intent


async def parse_anthropic_stream(
    raw_iterator: AsyncIterator[bytes],
) -> AsyncIterator[Any]:
    """Parse an Anthropic SSE stream into unified stream events."""
    state = _AnthropicParseState()
    async for payload in parse_sse_json_stream(raw_iterator):
        for event in state.update(payload):
            yield event
    for event in state.finish_events():
        yield event


class _AnthropicParseState:
    """Tracks Anthropic content blocks and maps them onto unified blocks."""

    def __init__(self) -> None:

        self._block_kind = BlockKind
        self.message_id = ""
        self.model = ""
        self.started = False
        self.block_index: dict[int, int] = {}
        self.block_kind: dict[int, Any] = {}
        self.next_index = 0
        self.stop_reason: Any = None
        self.usage = Usage()

    def update(self, payload: Mapping[str, Any]) -> list[Any]:

        event_type = payload.get("type")
        events: list[Any] = []
        if event_type == "message_start":
            message = payload.get("message")
            if isinstance(message, Mapping):
                self.message_id = _text(message.get("id"))
                self.model = _text(message.get("model"))
                usage = message.get("usage")
                if isinstance(usage, Mapping):
                    self.usage = _merge_usage(self.usage, _anthropic_usage(usage))
            if not self.started:
                self.started = True
                events.append(StreamStart(id=self.message_id, model=self.model))
            return events
        if event_type == "content_block_start":
            index = _event_index(payload, "index")
            block = payload.get("content_block")
            if not isinstance(block, Mapping):
                raise ValueError("Anthropic content_block_start must contain a block")
            block_type = block.get("type")
            unified_index = self._allocate(index, block_type)
            if block_type == "text":
                events.append(
                    BlockStart(index=unified_index, kind=self._block_kind.TEXT)
                )
            elif block_type == "thinking":
                events.append(
                    BlockStart(index=unified_index, kind=self._block_kind.REASONING)
                )
            elif block_type == "redacted_thinking":
                events.append(
                    BlockStart(index=unified_index, kind=self._block_kind.REASONING)
                )
                data = _text(block.get("data"))
                if data:
                    events.append(SignatureDelta(index=unified_index, opaque=data))
            elif block_type == "tool_use":
                events.append(
                    BlockStart(
                        index=unified_index,
                        kind=self._block_kind.TOOL_CALL,
                        call_id=_text(block.get("id")),
                        name=_text(block.get("name")),
                    )
                )
            return events
        if event_type == "content_block_delta":
            index = _event_index(payload, "index")
            delta = payload.get("delta")
            if not isinstance(delta, Mapping):
                raise ValueError("Anthropic content_block_delta must contain a delta")
            unified_index = self.block_index.get(index)
            if unified_index is None:
                raise ValueError("Anthropic delta arrived before content_block_start")
            delta_type = delta.get("type")
            if delta_type == "text_delta":
                events.append(
                    TextDelta(index=unified_index, text=_text(delta.get("text")))
                )
            elif delta_type == "thinking_delta":
                events.append(
                    ReasoningDelta(
                        index=unified_index, text=_text(delta.get("thinking"))
                    )
                )
            elif delta_type == "signature_delta":
                events.append(
                    SignatureDelta(
                        index=unified_index, opaque=_text(delta.get("signature"))
                    )
                )
            elif delta_type == "input_json_delta":
                events.append(
                    ToolCallArgsDelta(
                        index=unified_index, arguments=_text(delta.get("partial_json"))
                    )
                )
            return events
        if event_type == "content_block_stop":
            index = _event_index(payload, "index")
            unified_index = self.block_index.get(index)
            if unified_index is None:
                raise ValueError(
                    "Anthropic block stop arrived before content_block_start"
                )
            return [BlockStop(index=unified_index)]
        if event_type == "error":
            error = payload.get("error")
            message = _text(error.get("message")) if isinstance(error, Mapping) else ""
            detail = _text(error.get("type")) if isinstance(error, Mapping) else ""
            label = f"{detail}: {message}" if detail and message else message or detail
            raise ValueError(f"Anthropic upstream error: {label or 'unknown error'}")
        if event_type == "message_delta":
            delta = payload.get("delta")
            if isinstance(delta, Mapping) and delta.get("stop_reason"):
                self.stop_reason = delta.get("stop_reason")
            usage = payload.get("usage")
            if isinstance(usage, Mapping):
                self.usage = _merge_usage(self.usage, _anthropic_usage(usage))
            return events
        return events

    def _allocate(self, index: int, block_type: Any) -> int:
        unified_index = self.next_index
        self.next_index += 1
        self.block_index[index] = unified_index
        self.block_kind[index] = block_type
        return unified_index

    def finish_events(self) -> list[Any]:
        if not self.started:
            raise ValueError("Anthropic stream ended before message_start")
        return [
            StreamFinish(
                reason=_anthropic_finish_reason(self.stop_reason), usage=self.usage
            )
        ]


def serialize_anthropic_stream(
    events: AsyncIterator[Any],
    original_model: str,
) -> AsyncIterator[bytes]:
    """Serialize unified stream events into an Anthropic SSE stream."""
    return _anthropic_serializer(events, original_model)


async def _anthropic_serializer(
    events: AsyncIterator[Any],
    original_model: str,
) -> AsyncIterator[bytes]:
    from .unified_stream import (
        StreamFinish,
    )

    kind_by_index: dict[int, Any] = {}
    call_by_index: dict[int, tuple[str, str]] = {}
    started = False
    message_id = f"msg_{uuid.uuid4().hex[:24]}"
    model = original_model
    open_blocks: list[int] = []

    def message_start() -> bytes:
        return format_sse_event(
            "message_start",
            {
                "type": "message_start",
                "message": {
                    "id": message_id,
                    "type": "message",
                    "role": "assistant",
                    "model": model,
                    "content": [],
                    "stop_reason": None,
                    "stop_sequence": None,
                    "usage": {"input_tokens": 0, "output_tokens": 0},
                },
            },
        )

    async for event in events:
        if isinstance(event, StreamStart):
            message_id = event.id or message_id
            model = event.model or model
            if not started:
                started = True
                yield message_start()
                yield format_sse_event("ping", {"type": "ping"})
            continue
        if isinstance(event, BlockStart):
            if not started:
                started = True
                yield message_start()
                yield format_sse_event("ping", {"type": "ping"})
            kind_by_index[event.index] = event.kind
            open_blocks.append(event.index)
            if event.kind == BlockKind.TEXT:
                yield anthropic_block_start(event.index, {"type": "text", "text": ""})
            elif event.kind == BlockKind.REASONING:
                yield anthropic_block_start(
                    event.index, {"type": "thinking", "thinking": ""}
                )
            elif event.kind == BlockKind.REFUSAL:
                # Anthropic has no refusal block; the text still reaches the
                # client as ordinary text.
                yield anthropic_block_start(event.index, {"type": "text", "text": ""})
            elif event.kind == BlockKind.SERVER_TOOL:
                call_by_index[event.index] = (event.call_id, event.name)
                yield anthropic_block_start(
                    event.index,
                    {
                        "type": "server_tool_use",
                        "id": event.call_id,
                        "name": event.name,
                        "input": {},
                    },
                )
            else:
                call_by_index[event.index] = (event.call_id, event.name)
                yield anthropic_block_start(
                    event.index,
                    {
                        "type": "tool_use",
                        "id": event.call_id,
                        "name": event.name,
                        "input": {},
                    },
                )
            continue
        if isinstance(event, TextDelta):
            yield anthropic_block_delta(
                event.index, {"type": "text_delta", "text": event.text}
            )
            continue
        if isinstance(event, RefusalDelta):
            if event.index not in open_blocks:
                open_blocks.append(event.index)
                yield anthropic_block_start(event.index, {"type": "text", "text": ""})
            yield anthropic_block_delta(
                event.index, {"type": "text_delta", "text": event.text}
            )
            continue
        if isinstance(event, CitationDelta):
            yield anthropic_block_delta(
                event.index,
                {
                    "type": "citations_delta",
                    "citation": _citation_to_anthropic(event.citation),
                },
            )
            continue
        if isinstance(event, ServerToolStatusDelta):
            # Anthropic reports server-tool progress by closing the block, so a
            # completed status becomes the block stop it would have sent.
            if event.status in {"completed", "failed"} and event.index in open_blocks:
                open_blocks.remove(event.index)
                yield anthropic_block_stop(event.index)
            continue
        if isinstance(event, ReasoningDelta):
            if event.index not in open_blocks and event.text:
                yield anthropic_block_start(
                    event.index, {"type": "thinking", "thinking": ""}
                )
                open_blocks.append(event.index)
            yield anthropic_block_delta(
                event.index, {"type": "thinking_delta", "thinking": event.text}
            )
            continue
        if isinstance(event, SignatureDelta):
            yield anthropic_block_delta(
                event.index, {"type": "signature_delta", "signature": event.opaque}
            )
            continue
        if isinstance(event, ToolCallArgsDelta):
            yield anthropic_block_delta(
                event.index,
                {"type": "input_json_delta", "partial_json": event.arguments},
            )
            continue
        if isinstance(event, BlockStop):
            if event.index in open_blocks:
                open_blocks.remove(event.index)
            yield anthropic_block_stop(event.index)
            continue
        if isinstance(event, StreamFinish):
            if not started:
                started = True
                yield message_start()
                yield format_sse_event("ping", {"type": "ping"})
            for index in sorted(open_blocks):
                yield anthropic_block_stop(index)
            open_blocks.clear()
            has_tools = any(
                kind in {BlockKind.TOOL_CALL, BlockKind.SERVER_TOOL}
                for kind in kind_by_index.values()
            )
            yield format_sse_event(
                "message_delta",
                {
                    "type": "message_delta",
                    "delta": {
                        "stop_reason": _anthropic_stop_reason(
                            event.reason, has_tools=has_tools
                        ),
                        "stop_sequence": None,
                    },
                    "usage": {
                        **_anthropic_usage_wire(event.usage),
                        "output_tokens": event.usage.output_tokens,
                    },
                },
            )
            yield format_sse_event("message_stop", {"type": "message_stop"})
            return
    for index in sorted(open_blocks):
        yield anthropic_block_stop(index)


def _event_index(payload: Mapping[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Anthropic event must contain {key}")
    return value


def _merge_usage(first: Usage, second: Usage) -> Usage:
    return Usage(
        input_tokens=second.input_tokens or first.input_tokens,
        output_tokens=second.output_tokens or first.output_tokens,
        cached_input_tokens=second.cached_input_tokens or first.cached_input_tokens,
        cache_creation_input_tokens=(
            second.cache_creation_input_tokens or first.cache_creation_input_tokens
        ),
        reasoning_tokens=second.reasoning_tokens or first.reasoning_tokens,
    )


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _optional_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    return float(value) if isinstance(value, int | float) else None

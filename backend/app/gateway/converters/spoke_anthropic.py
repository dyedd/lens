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
from .sse import (
    anthropic_block_delta,
    anthropic_block_start,
    anthropic_block_stop,
    format_sse_event,
    parse_sse_json_stream,
)
from .unified import (
    ContentPart,
    FilePart,
    ImagePart,
    Message,
    MessageRole,
    ReasoningIntent,
    ReasoningPart,
    TextPart,
    ToolCallPart,
    ToolChoice,
    ToolChoiceMode,
    ToolDefinition,
    ToolResultPart,
    UnifiedRequest,
)
from .unified_response import FinishReason, UnifiedResponse, Usage
from .unified_stream import (
    BlockKind,
    BlockStart,
    BlockStop,
    ReasoningDelta,
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
    messages: list[dict[str, Any]] = []
    pending_results: list[dict[str, Any]] = []
    for message in request.messages:
        if message.role == MessageRole.TOOL:
            for part in message.parts:
                if isinstance(part, ToolResultPart):
                    pending_results.append(_tool_result_to_anthropic(part))
            continue
        if pending_results:
            messages.append({"role": "user", "content": pending_results})
            pending_results = []
        messages.append(_message_to_anthropic(message, request=request))
    if pending_results:
        messages.append({"role": "user", "content": pending_results})

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
    if request.tools:
        body["tools"] = [_tool_to_anthropic(tool) for tool in request.tools]
    if request.tool_choice is not None:
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

    request.tools = _anthropic_tools(body.get("tools"))
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
        parts.append(
            TextPart(
                text=required_string(
                    block.get("text"),
                    "Anthropic system text blocks must contain text",
                    allow_empty=True,
                ),
                cache_breakpoint=isinstance(block.get("cache_control"), Mapping),
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
    thinking: list[ReasoningPart] = []
    tool_calls: list[ContentPart] = []
    tool_results: list[ContentPart] = []
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
                )
            )
        elif block_type in {"image", "document"}:
            media.append(_anthropic_media(block))
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
            tool_results.append(
                ToolResultPart(
                    call_id=required_string(
                        block.get("tool_use_id"),
                        "Anthropic tool_result must contain tool_use_id",
                    ),
                    content=_anthropic_tool_result_text(block.get("content")),
                    is_error=block.get("is_error") is True,
                )
            )
        else:
            raise ValueError(f"Unsupported Anthropic content block type: {block_type}")

    messages: list[Message] = []
    for result in tool_results:
        messages.append(Message(role=MessageRole.TOOL, parts=[result]))
    parts: list[ContentPart] = []
    if thinking and role == "assistant":
        parts.extend(thinking)
    if texts:
        parts.append(TextPart(text="\n".join(texts)))
    parts.extend(media)
    parts.extend(tool_calls)
    if parts:
        messages.append(Message(role=MessageRole(role), parts=parts))
    return messages


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


def _anthropic_tool_result_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if not isinstance(value, list):
        raise ValueError("Anthropic tool_result content must be a string or array")
    texts: list[str] = []
    for block in value:
        if not isinstance(block, Mapping):
            raise ValueError("Anthropic tool_result content must contain objects")
        if block.get("type") == "text":
            texts.append(
                required_string(
                    block.get("text"),
                    "Anthropic tool_result text blocks must contain text",
                    allow_empty=True,
                )
            )
        else:
            raise ValueError("Unsupported Anthropic tool_result block type")
    return "\n".join(texts)


def _anthropic_tools(value: Any) -> list[ToolDefinition]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("Anthropic tools must be an array")
    result: list[ToolDefinition] = []
    for tool in value:
        if not isinstance(tool, Mapping):
            raise ValueError("Anthropic tools must contain objects")
        if tool.get("type") not in {None, "custom"}:
            raise ValueError("Unsupported Anthropic tool type")
        input_schema = tool.get("input_schema")
        if not isinstance(input_schema, Mapping):
            raise ValueError("Anthropic tools must contain input_schema")
        result.append(
            ToolDefinition(
                name=required_string(
                    tool.get("name"), "Anthropic tools must contain name"
                ),
                description=_text(tool.get("description")),
                parameters=dict(input_schema),
            )
        )
    return result


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
                content.append({"type": "text", "text": part.text})
        elif isinstance(part, ToolCallPart):
            content.append(_tool_call_to_anthropic(part))
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
    message: Message, *, request: UnifiedRequest
) -> dict[str, Any]:
    parts: list[ContentPart] = list(message.parts)
    content = _parts_to_anthropic_content(
        parts, role=message.role, replay_reasoning=request.replay_reasoning
    )
    return {"role": message.role.value, "content": content}


def _parts_to_anthropic_content(
    parts: list[ContentPart],
    *,
    role: MessageRole,
    replay_reasoning: bool = False,
) -> str | list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    text_parts: list[str] = []
    for part in parts:
        if isinstance(part, TextPart):
            text_parts.append(part.text)
        elif isinstance(part, ImagePart):
            blocks.append(_image_to_anthropic(part))
        elif isinstance(part, FilePart):
            blocks.append(_file_to_anthropic(part))
        elif isinstance(part, ReasoningPart) and role == MessageRole.ASSISTANT:
            if replay_reasoning or part.origin == _ORIGIN:
                blocks.append(_reasoning_to_anthropic(part))
        elif isinstance(part, ToolCallPart):
            blocks.append(_tool_call_to_anthropic(part))
        elif isinstance(part, ToolResultPart):
            blocks.append(_tool_result_to_anthropic(part))

    text = "\n".join(value for value in text_parts if value)
    if not blocks:
        return text
    result: list[dict[str, Any]] = []
    if text:
        result.append({"type": "text", "text": text})
    return [*result, *blocks]


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
    if part.origin == _ORIGIN and part.opaque and not part.text:
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
        "name": part.name,
        "input": dict(parsed_input),
    }


def _tool_result_to_anthropic(part: ToolResultPart) -> dict[str, Any]:
    block: dict[str, Any] = {
        "type": "tool_result",
        "tool_use_id": part.call_id,
        "content": part.content,
    }
    if part.is_error:
        block["is_error"] = True
    return block


def _tool_to_anthropic(tool: ToolDefinition) -> dict[str, Any]:
    result: dict[str, Any] = {"name": tool.name}
    if tool.description:
        result["description"] = tool.description
    result["input_schema"] = tool.parameters or {"type": "object", "properties": {}}
    return result


def _tool_choice_to_anthropic(choice: ToolChoice) -> dict[str, Any]:
    if choice.mode == ToolChoiceMode.FUNCTION:
        return {"type": "tool", "name": choice.name}
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
                    )
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
    return parts


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
            if event.kind == _block_kinds().TEXT:
                yield anthropic_block_start(event.index, {"type": "text", "text": ""})
            elif event.kind == _block_kinds().REASONING:
                yield anthropic_block_start(
                    event.index, {"type": "thinking", "thinking": ""}
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
                kind == _block_kinds().TOOL_CALL for kind in kind_by_index.values()
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


def _block_kinds() -> Any:

    return BlockKind


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

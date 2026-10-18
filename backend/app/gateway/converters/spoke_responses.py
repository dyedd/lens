"""OpenAI Responses spoke: wire payloads <-> unified request.

The pairwise converters only ever used Responses as one side of a fixed pair,
so this module implements both directions against the unified protocol:
parsing a Responses client request or upstream response, and building a
Responses request or response body.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from typing import Any

from ...models.protocols import ProtocolKind
from .chat_stream import ChatToolCall, ChatToolCalls, chat_choice_index
from .responses_common import (
    decode_reasoning_item,
    encode_reasoning_item,
    raise_for_failed_response,
    reasoning_summary_text,
    usage_int,
    validate_terminal_response,
)
from .sse import (
    FINISH_REASON_CHAT_TO_RESPONSES,
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
    ResponseFormat,
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
    ReasoningDelta,
    SignatureDelta,
    StreamFinish,
    StreamStart,
    TextDelta,
    ToolCallArgsDelta,
)
from .validation import required_string

_ORIGIN = ProtocolKind.OPENAI_RESPONSES


def parse_responses_request(body: Mapping[str, Any]) -> UnifiedRequest:
    """Parse a Responses API request body into the unified request."""
    request = UnifiedRequest(model=_text(body.get("model")))
    request.stream = body.get("stream") is True
    request.generation.max_output_tokens = _optional_int(body.get("max_output_tokens"))
    request.generation.temperature = _optional_float(body.get("temperature"))
    request.generation.top_p = _optional_float(body.get("top_p"))
    request.generation.top_k = _optional_int(body.get("top_k"))
    stop = body.get("stop")
    if isinstance(stop, str):
        request.generation.stop = (stop,)
    elif isinstance(stop, list):
        request.generation.stop = tuple(item for item in stop if isinstance(item, str))
    request.reasoning = _responses_reasoning_intent(body.get("reasoning"))
    request.response_format = _responses_response_format(body.get("text"))
    request.user_id = _text(body.get("user")) or _text(body.get("safety_identifier"))

    instructions = body.get("instructions")
    if isinstance(instructions, str) and instructions:
        request.system = [TextPart(text=instructions)]
    elif instructions is not None and not isinstance(instructions, str):
        raise ValueError("Responses instructions must be a string")

    request.messages = _responses_input_to_messages(
        body.get("input", []), request.system
    )
    request.tools = _responses_tools(body.get("tools"))
    request.tool_choice = _responses_tool_choice(body.get("tool_choice"))
    parallel = body.get("parallel_tool_calls")
    if request.tool_choice is None and isinstance(parallel, bool):
        request.tool_choice = ToolChoice(
            mode=ToolChoiceMode.AUTO, allow_parallel=parallel
        )
    return request


def build_responses_request(request: UnifiedRequest) -> dict[str, Any]:
    """Build a Responses API request body from the unified request."""
    items: list[dict[str, Any]] = []
    if request.system:
        items.append(
            {
                "role": "system",
                "content": "\n".join(
                    part.text
                    for part in request.system
                    if isinstance(part, TextPart) and part.text
                ),
            }
        )
    for message in request.messages:
        if message.role == MessageRole.TOOL:
            for part in message.parts:
                if isinstance(part, ToolResultPart):
                    items.append(_tool_result_to_responses(part))
            continue
        items.extend(_message_to_responses(message, request=request))

    body: dict[str, Any] = dict(request.passthrough)
    body.pop("stream_options", None)
    body["input"] = items
    body["model"] = request.model
    if request.stream:
        body["stream"] = True
    if request.origin == ProtocolKind.ANTHROPIC:
        # An Anthropic client cannot replay a Responses id, so the upstream
        # must be told not to rely on server-side conversation state.
        body["store"] = False
    body.pop("previous_response_id", None)
    generation = request.generation
    if generation.max_output_tokens is not None:
        body["max_output_tokens"] = generation.max_output_tokens
    if generation.temperature is not None:
        body["temperature"] = generation.temperature
    if generation.top_p is not None:
        body["top_p"] = generation.top_p
    if generation.top_k is not None:
        body["top_k"] = generation.top_k
    if generation.stop:
        body["stop"] = list(generation.stop)
    if request.tools:
        body["tools"] = [_tool_to_responses(tool) for tool in request.tools]
    if request.tool_choice is not None and request.tools:
        body["tool_choice"] = _tool_choice_to_responses(request.tool_choice)
        if request.tool_choice.allow_parallel is not None:
            body["parallel_tool_calls"] = request.tool_choice.allow_parallel
    if request.reasoning is not None and request.reasoning.effort is not None:
        body["reasoning"] = {"effort": request.reasoning.effort}
    if request.response_format is not None and request.response_format.kind:
        body["text"] = {
            "format": _response_format_to_responses(request.response_format)
        }
    has_reasoning = any(
        isinstance(part, ReasoningPart)
        for message in request.messages
        for part in message.parts
    )
    if has_reasoning or (request.reasoning is not None and request.reasoning.enabled):
        body["include"] = ["reasoning.encrypted_content"]
    return body


def parse_responses_response(body: Mapping[str, Any]) -> UnifiedResponse:
    """Parse a Responses API response body into the unified response."""
    output = validate_terminal_response(body)
    usage = body.get("usage")
    return UnifiedResponse(
        id=_text(body.get("id")),
        model=_text(body.get("model")),
        parts=_responses_output_parts(output),
        finish=_responses_finish_reason(body, output),
        usage=_responses_usage(usage if isinstance(usage, Mapping) else {}),
    )


def build_responses_response(response: UnifiedResponse) -> dict[str, Any]:
    """Build a Responses API response body from the unified response."""
    output: list[dict[str, Any]] = []
    text_parts: list[dict[str, Any]] = []
    tool_calls: list[dict[str, Any]] = []
    reasoning_items: list[dict[str, Any]] = []

    for part in response.parts:
        if isinstance(part, TextPart):
            text_parts.append(
                {"type": "output_text", "annotations": [], "text": part.text}
            )
        elif isinstance(part, ReasoningPart):
            reasoning_items.append(_reasoning_to_responses(part))
        elif isinstance(part, ToolCallPart):
            tool_calls.append(
                {
                    "type": "function_call",
                    "id": f"fc_{uuid.uuid4().hex[:24]}",
                    "call_id": part.call_id,
                    "name": part.name,
                    "arguments": part.arguments or "{}",
                    "status": "completed",
                }
            )

    output.extend(reasoning_items)
    if text_parts:
        output.append(
            {
                "type": "message",
                "id": f"msg_{uuid.uuid4().hex[:24]}",
                "status": "completed",
                "role": "assistant",
                "content": text_parts,
            }
        )
    output.extend(tool_calls)

    status = _responses_status(response.finish)
    body: dict[str, Any] = {
        "id": response.id or f"resp_{uuid.uuid4().hex[:24]}",
        "object": "response",
        "created_at": int(time.time()),
        "model": response.model,
        "status": status,
        "output": output,
        "parallel_tool_calls": True,
        "tool_choice": "auto",
        "tools": [],
        "usage": _responses_usage_wire(response.usage),
    }
    if status == "incomplete":
        body["incomplete_details"] = {"reason": _incomplete_reason(response.finish)}
    return body


def _responses_status(reason: FinishReason) -> str:
    if reason == FinishReason.MAX_TOKENS:
        return "incomplete"
    return "completed"


def _incomplete_reason(reason: FinishReason) -> str:
    if reason == FinishReason.CONTENT_FILTER:
        return "content_filter"
    return "max_output_tokens"


def _responses_input_to_messages(
    value: Any,
    system_parts: list[ContentPart],
) -> list[Message]:
    if isinstance(value, str):
        return [
            Message(
                role=MessageRole.USER,
                parts=[TextPart(text=value)],
                plain_text_content=True,
            )
        ]
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("Responses input must be a string or array")

    messages: list[Message] = []
    pending_calls: list[ContentPart] = []

    def flush() -> None:
        if pending_calls:
            messages.append(
                Message(role=MessageRole.ASSISTANT, parts=list(pending_calls))
            )
            pending_calls.clear()

    for item in value:
        if not isinstance(item, Mapping):
            raise ValueError("Responses input must contain objects")
        item_type = item.get("type")
        role = item.get("role")
        if (
            (item_type is None or item_type == "message")
            and isinstance(role, str)
            and role in {"system", "developer"}
        ):
            # System prompts are instructions, not turn history; other
            # protocols receive them beside the messages.
            flush()
            system_parts.extend(_responses_content_parts(item.get("content")))
            continue
        if item_type == "function_call":
            pending_calls.append(
                ToolCallPart(
                    call_id=required_string(
                        item.get("call_id"),
                        "Responses function_call must contain call_id",
                    ),
                    name=required_string(
                        item.get("name"), "Responses function_call must contain name"
                    ),
                    arguments=required_string(
                        item.get("arguments"),
                        "Responses function_call must contain arguments",
                        allow_empty=True,
                    ),
                    origin=_ORIGIN,
                )
            )
            continue
        flush()
        if item_type == "function_call_output":
            messages.append(
                Message(
                    role=MessageRole.TOOL,
                    parts=[
                        ToolResultPart(
                            call_id=required_string(
                                item.get("call_id"),
                                "Responses function_call_output must contain call_id",
                            ),
                            content=_tool_output_text(item.get("output")),
                        )
                    ],
                )
            )
        elif item_type == "reasoning":
            messages.append(
                Message(
                    role=MessageRole.ASSISTANT,
                    parts=[
                        ReasoningPart(
                            text=reasoning_summary_text(item),
                            opaque=encode_reasoning_item(item),
                            origin=_ORIGIN,
                        )
                    ],
                )
            )
        else:
            messages.append(_responses_message_to_unified(item))
    flush()
    return messages


def _responses_message_to_unified(item: Mapping[str, Any]) -> Message:
    item_type = item.get("type")
    if item_type is not None and item_type != "message":
        raise ValueError(f"Unsupported Responses input item type: {item_type}")
    role = item.get("role")
    if not isinstance(role, str) or role not in {"user", "assistant"}:
        raise ValueError("Responses messages must contain a valid role")
    return Message(
        role=MessageRole(role),
        parts=_responses_content_parts(item.get("content")),
    )


def _responses_content_parts(value: Any) -> list[ContentPart]:
    if value is None:
        return []
    if isinstance(value, str):
        return [TextPart(text=value)]
    if not isinstance(value, list):
        raise ValueError("Responses message content must be a string or array")
    parts: list[ContentPart] = []
    for block in value:
        if not isinstance(block, Mapping):
            raise ValueError("Responses message content must contain objects")
        block_type = block.get("type")
        if block_type in {"input_text", "output_text", "text", "summary_text"}:
            parts.append(
                TextPart(
                    text=required_string(
                        block.get("text"),
                        "Responses text parts must contain text",
                        allow_empty=True,
                    )
                )
            )
        elif block_type == "input_image":
            parts.append(_responses_image_to_unified(block))
        elif block_type == "input_file":
            parts.append(_responses_file_to_unified(block))
        elif block_type == "refusal":
            parts.append(
                TextPart(
                    text=required_string(
                        block.get("refusal"),
                        "Responses refusal parts must contain refusal",
                        allow_empty=True,
                    )
                )
            )
        else:
            raise ValueError(f"Unsupported Responses content part type: {block_type}")
    return parts


def _responses_image_to_unified(block: Mapping[str, Any]) -> ImagePart:
    image_url = block.get("image_url")
    detail = _text(block.get("detail"))
    if isinstance(image_url, Mapping):
        detail = _text(image_url.get("detail")) or detail
        image_url = image_url.get("url")
    url = required_string(
        image_url, "Responses input_image parts must contain image_url"
    )
    if url.startswith("data:") and ";base64," in url:
        header, _, data = url.partition(",")
        return ImagePart(
            media_type=header[len("data:") :].split(";")[0], data=data, detail=detail
        )
    return ImagePart(url=url, detail=detail)


def _responses_file_to_unified(block: Mapping[str, Any]) -> FilePart:
    part = FilePart(
        file_id=_text(block.get("file_id")),
        url=_text(block.get("file_url")),
        filename=_text(block.get("filename")),
    )
    data = _text(block.get("file_data"))
    if data.startswith("data:") and ";base64," in data:
        header, _, payload = data.partition(",")
        part.media_type = header[len("data:") :].split(";")[0]
        part.data = payload
    elif data:
        part.data = data
    if not (part.file_id or part.data or part.url):
        raise ValueError("Responses input_file parts must contain a file source")
    return part


def _tool_output_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        texts: list[str] = []
        for block in value:
            if isinstance(block, Mapping) and isinstance(block.get("text"), str):
                texts.append(block["text"])
        return "".join(texts)
    return str(value)


def _responses_tools(value: Any) -> list[ToolDefinition]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("Responses tools must be an array")
    result: list[ToolDefinition] = []
    for tool in value:
        if not isinstance(tool, Mapping):
            raise ValueError("Responses tools must contain objects")
        if tool.get("type") != "function":
            raise ValueError("Unsupported Responses tool type")
        parameters = tool.get("parameters")
        result.append(
            ToolDefinition(
                name=required_string(
                    tool.get("name"), "Responses function tools must contain name"
                ),
                description=_text(tool.get("description")),
                parameters=dict(parameters)
                if isinstance(parameters, Mapping)
                else None,
                strict=tool.get("strict")
                if isinstance(tool.get("strict"), bool)
                else None,
            )
        )
    return result


def _responses_tool_choice(value: Any) -> ToolChoice | None:
    if value is None:
        return None
    if isinstance(value, str):
        if value in {"auto", "none", "required"}:
            return ToolChoice(mode=ToolChoiceMode(value))
        return None
    if not isinstance(value, Mapping):
        raise ValueError("Unsupported Responses tool_choice")
    if value.get("type") == "function":
        return ToolChoice(
            mode=ToolChoiceMode.FUNCTION,
            name=required_string(
                value.get("name"),
                "Responses function tool_choice must contain name",
            ),
        )
    tools = value.get("tools")
    if value.get("type") == "allowed_tools" and isinstance(tools, list):
        names = tuple(
            item["name"]
            for item in tools
            if isinstance(item, Mapping) and isinstance(item.get("name"), str)
        )
        if names:
            return ToolChoice(
                mode=ToolChoiceMode.FUNCTION, name=names[0], allowed_names=names
            )
    return None


def _responses_reasoning_intent(value: Any) -> ReasoningIntent | None:
    if not isinstance(value, Mapping):
        return None
    effort = _text(value.get("effort"))
    if not effort:
        return None
    return ReasoningIntent(
        enabled=effort != "none",
        effort=effort,
        summarized=_text(value.get("summary")) not in {"", "none"},
    )


def _responses_response_format(value: Any) -> ResponseFormat | None:
    if not isinstance(value, Mapping):
        return None
    format_value = value.get("format")
    if not isinstance(format_value, Mapping):
        return None
    format_type = _text(format_value.get("type"))
    if format_type in {"text", "json_object"}:
        return ResponseFormat(kind=format_type)
    if format_type != "json_schema":
        return None
    schema = format_value.get("schema")
    if not isinstance(schema, Mapping):
        raise ValueError("Responses json_schema format must contain schema")
    return ResponseFormat(
        kind="json_schema",
        name=_text(format_value.get("name")),
        schema=dict(schema),
        strict=format_value.get("strict")
        if isinstance(format_value.get("strict"), bool)
        else None,
    )


def _message_to_responses(
    message: Message, *, request: UnifiedRequest
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    content: list[dict[str, Any]] = []
    tool_calls: list[dict[str, Any]] = []
    for part in message.parts:
        if isinstance(part, ReasoningPart):
            if part.origin == _ORIGIN:
                decoded = decode_reasoning_item(part.opaque)
                if decoded is not None:
                    items.append(decoded)
            continue
        if isinstance(part, ToolCallPart):
            tool_calls.append(
                {
                    "type": "function_call",
                    "call_id": part.call_id,
                    "name": part.name,
                    "arguments": part.arguments or "{}",
                }
            )
            continue
        if isinstance(part, TextPart):
            content.append(
                {
                    "type": (
                        "input_text"
                        if message.role != MessageRole.ASSISTANT
                        else "output_text"
                    ),
                    "text": part.text,
                }
            )
        elif isinstance(part, ImagePart):
            content.append(_image_to_responses(part))
        elif isinstance(part, FilePart):
            content.append(_file_to_responses(part))
        elif isinstance(part, ToolResultPart):
            items.append(_tool_result_to_responses(part))

    if content or not tool_calls:
        if (
            message.plain_text_content
            and len(content) == 1
            and content[0].get("type") in {"input_text", "output_text"}
        ):
            items.append({"role": message.role.value, "content": content[0]["text"]})
        else:
            items.append({"role": message.role.value, "content": content})
    items.extend(tool_calls)
    return items


def _image_to_responses(part: ImagePart) -> dict[str, Any]:
    if part.data:
        url = f"data:{part.media_type or 'image/png'};base64,{part.data}"
    elif part.url:
        url = part.url
    else:
        raise ValueError("Unified image part must contain data or a URL")
    result: dict[str, Any] = {"type": "input_image", "image_url": url}
    if part.detail:
        result["detail"] = part.detail
    return result


def _file_to_responses(part: FilePart) -> dict[str, Any]:
    result: dict[str, Any] = {"type": "input_file"}
    if part.file_id:
        result["file_id"] = part.file_id
    elif part.data:
        result["file_data"] = (
            f"data:{part.media_type or 'application/pdf'};base64,{part.data}"
        )
    elif part.url:
        result["file_url"] = part.url
    else:
        raise ValueError("Unified file part must contain data, a URL, or a file id")
    if part.filename:
        result["filename"] = part.filename
    return result


def _tool_result_to_responses(part: ToolResultPart) -> dict[str, Any]:
    return {
        "type": "function_call_output",
        "call_id": part.call_id,
        "output": part.content,
    }


def _tool_to_responses(tool: ToolDefinition) -> dict[str, Any]:
    result: dict[str, Any] = {"type": "function", "name": tool.name}
    if tool.description:
        result["description"] = tool.description
    if tool.parameters is not None:
        result["parameters"] = tool.parameters
    if tool.strict is not None:
        result["strict"] = tool.strict
    return result


def _tool_choice_to_responses(choice: ToolChoice) -> Any:
    if choice.mode == ToolChoiceMode.FUNCTION:
        return {"type": "function", "name": choice.name}
    if choice.mode == ToolChoiceMode.REQUIRED:
        return "required"
    return choice.mode.value


def _response_format_to_responses(response_format: ResponseFormat) -> dict[str, Any]:
    if response_format.kind != "json_schema":
        return {"type": response_format.kind or "text"}
    result: dict[str, Any] = {
        "type": "json_schema",
        "name": response_format.name or "response",
    }
    if response_format.schema is not None:
        result["schema"] = response_format.schema
    if response_format.strict is not None:
        result["strict"] = response_format.strict
    return result


def _reasoning_to_responses(part: ReasoningPart) -> dict[str, Any]:
    decoded = decode_reasoning_item(part.opaque)
    if decoded is not None:
        return decoded
    item: dict[str, Any] = {
        "type": "reasoning",
        "id": f"rs_{uuid.uuid4().hex[:24]}",
        "summary": [],
        "status": "completed",
    }
    if part.text:
        item["summary"] = [
            {"type": "summary_text", "text": text}
            for text in part.text.split("\n\n")
            if text
        ]
    return item


def _responses_output_parts(output: list[Any]) -> list[ContentPart]:
    parts: list[ContentPart] = []
    for item in output:
        if not isinstance(item, Mapping):
            raise ValueError("Responses upstream output must contain objects")
        item_type = item.get("type")
        if item_type == "reasoning":
            parts.append(
                ReasoningPart(
                    text=reasoning_summary_text(item),
                    opaque=encode_reasoning_item(item),
                    origin=_ORIGIN,
                )
            )
        elif item_type == "function_call":
            parts.append(
                ToolCallPart(
                    call_id=required_string(
                        item.get("call_id"),
                        "Responses function_call must contain call_id",
                    ),
                    name=required_string(
                        item.get("name"), "Responses function_call must contain name"
                    ),
                    arguments=required_string(
                        item.get("arguments"),
                        "Responses function_call must contain arguments",
                        allow_empty=True,
                    ),
                    origin=_ORIGIN,
                )
            )
        elif item_type == "message":
            parts.extend(_responses_content_parts(item.get("content")))
    return parts


def _responses_finish_reason(
    body: Mapping[str, Any], output: list[Any]
) -> FinishReason:
    status = body.get("status")
    if status == "incomplete":
        details = body.get("incomplete_details")
        reason = details.get("reason") if isinstance(details, Mapping) else None
        if reason == "content_filter":
            return FinishReason.CONTENT_FILTER
        return FinishReason.MAX_TOKENS
    has_tools = any(
        isinstance(item, Mapping) and item.get("type") == "function_call"
        for item in output
    )
    return FinishReason.TOOL_USE if has_tools else FinishReason.END_TURN


def _responses_usage(value: Mapping[str, Any]) -> Usage:
    input_tokens = usage_int(value, "input_tokens")
    cached = 0
    cache_write = 0
    input_details = value.get("input_tokens_details")
    if isinstance(input_details, Mapping):
        cached = usage_int(input_details, "cached_tokens")
        cache_write = usage_int(input_details, "cache_write_tokens")
    reasoning = 0
    output_details = value.get("output_tokens_details")
    if isinstance(output_details, Mapping):
        reasoning = usage_int(output_details, "reasoning_tokens")
    return Usage(
        # Responses input_tokens is the inclusive total, unlike Anthropic's.
        input_tokens=input_tokens,
        output_tokens=usage_int(value, "output_tokens"),
        cached_input_tokens=cached,
        cache_creation_input_tokens=cache_write,
        reasoning_tokens=reasoning,
    )


def _responses_usage_wire(usage: Usage) -> dict[str, Any]:
    return {
        "input_tokens": usage.input_tokens,
        "input_tokens_details": {
            "cached_tokens": usage.cached_input_tokens,
            "cache_write_tokens": usage.cache_creation_input_tokens,
        },
        "output_tokens": usage.output_tokens,
        "output_tokens_details": {"reasoning_tokens": usage.reasoning_tokens},
        "total_tokens": usage.input_tokens + usage.output_tokens,
    }


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


async def parse_responses_stream(
    raw_iterator: AsyncIterator[bytes],
) -> AsyncIterator[Any]:
    """Parse a Responses API SSE stream into unified stream events."""
    from .sse import parse_sse_json_stream
    from .unified_stream import (
        BlockStart,
        BlockStop,
        ReasoningDelta,
        SignatureDelta,
        StreamFinish,
        StreamStart,
        TextDelta,
        ToolCallArgsDelta,
    )

    text_blocks: dict[tuple[int, int], int] = {}
    item_blocks: dict[int, int] = {}
    open_blocks: set[int] = set()
    next_index = 0
    started = False
    message_id = ""

    def allocate() -> int:
        nonlocal next_index
        index = next_index
        next_index += 1
        open_blocks.add(index)
        return index

    async for payload in parse_sse_json_stream(raw_iterator):
        response = payload.get("response")
        event_type = payload.get("type")
        if isinstance(response, Mapping) and not started:
            started = True
            message_id = _text(response.get("id"))
            yield StreamStart(id=message_id, model=_text(response.get("model")))
        if event_type == "response.reasoning_summary_text.delta":
            output_index = _event_int(payload, "output_index")
            index = item_blocks.get(output_index)
            if index is None:
                index = allocate()
                item_blocks[output_index] = index
                yield BlockStart(index=index, kind=BlockKind.REASONING)
            yield ReasoningDelta(index=index, text=_text(payload.get("delta")))
        elif event_type in {"response.output_text.delta", "response.refusal.delta"}:
            key = (
                _event_int(payload, "output_index"),
                _event_int(payload, "content_index"),
            )
            index = text_blocks.get(key)
            if index is None:
                index = allocate()
                text_blocks[key] = index
                yield BlockStart(index=index, kind=BlockKind.TEXT)
            yield TextDelta(index=index, text=_text(payload.get("delta")))
        elif event_type == "response.output_item.added":
            item = payload.get("item")
            if isinstance(item, Mapping) and item.get("type") == "function_call":
                index = allocate()
                item_blocks[_event_int(payload, "output_index")] = index
                yield BlockStart(
                    index=index,
                    kind=BlockKind.TOOL_CALL,
                    call_id=_text(item.get("call_id")),
                    name=_text(item.get("name")),
                )
        elif event_type == "response.function_call_arguments.delta":
            index = item_blocks.get(_event_int(payload, "output_index"))
            if index is None:
                raise ValueError("Responses arguments arrived before function_call")
            yield ToolCallArgsDelta(index=index, arguments=_text(payload.get("delta")))
        elif event_type == "response.output_item.done":
            item = payload.get("item")
            if isinstance(item, Mapping) and item.get("type") == "reasoning":
                output_index = _event_int(payload, "output_index")
                index = item_blocks.get(output_index)
                if index is None:
                    index = allocate()
                    item_blocks[output_index] = index
                    yield BlockStart(index=index, kind=BlockKind.REASONING)
                yield SignatureDelta(index=index, opaque=encode_reasoning_item(item))
            index = item_blocks.get(_event_int(payload, "output_index"))
            if index is not None and index in open_blocks:
                open_blocks.discard(index)
                yield BlockStop(index=index)
        elif event_type in {"response.completed", "response.incomplete"}:
            if not isinstance(response, Mapping):
                raise ValueError(f"Invalid {event_type} event")
            output = validate_terminal_response(response)
            usage = response.get("usage")
            yield StreamFinish(
                reason=_responses_finish_reason(response, output),
                usage=_responses_usage(usage if isinstance(usage, Mapping) else {}),
            )
            return
        elif event_type in {"response.failed", "error"}:
            raise_for_failed_response(response if isinstance(response, Mapping) else {})
            raise ValueError("Responses stream failed")
    raise ValueError("Responses stream ended before terminal event")


async def serialize_responses_stream(
    events: AsyncIterator[Any], original_model: str
) -> AsyncIterator[bytes]:
    """Serialize unified stream events into a Responses API SSE stream.

    Reuses the Chat -> Responses stream adapter by re-encoding unified events
    as chat deltas, so both paths share one SSE emitter.
    """
    async for chunk in _serialize_responses_stream(events, original_model):
        yield chunk


async def _serialize_responses_stream(
    events: AsyncIterator[Any], original_model: str
) -> AsyncIterator[bytes]:

    async def chat_payloads() -> AsyncIterator[bytes]:
        tool_identities: dict[int, tuple[str, str]] = {}
        tool_announced: set[int] = set()
        async for event in events:
            if isinstance(event, StreamStart):
                continue
            if isinstance(event, BlockStart):
                if event.kind == BlockKind.TOOL_CALL:
                    tool_identities[event.index] = (event.call_id, event.name)
                continue
            if isinstance(event, TextDelta):
                yield _chat_chunk({"content": event.text})
            elif isinstance(event, ToolCallArgsDelta):
                call_id, name = tool_identities.get(event.index, ("", ""))
                function: dict[str, Any] = {"arguments": event.arguments}
                delta: dict[str, Any] = {"function": function}
                if event.index not in tool_announced:
                    tool_announced.add(event.index)
                    delta["id"] = call_id
                    delta["type"] = "function"
                    function["name"] = name
                yield _chat_chunk({"tool_calls": [{"index": event.index, **delta}]})
            elif isinstance(event, ReasoningDelta):
                yield _chat_chunk({"reasoning_content": event.text})
            elif isinstance(event, SignatureDelta):
                # Chat has no signature channel; the response-side envelope is
                # re-encoded by the terminal event instead.
                continue
            elif isinstance(event, StreamFinish):
                yield _chat_chunk(
                    {},
                    finish_reason=_responses_wire_finish_reason(event.reason),
                    usage={
                        "prompt_tokens": event.usage.input_tokens,
                        "completion_tokens": event.usage.output_tokens,
                        "prompt_tokens_details": {
                            "cached_tokens": event.usage.cached_input_tokens
                        },
                    },
                )
                yield b"data: [DONE]\n\n"
                return
        raise ValueError("Unified stream ended before finish event")

    async for chunk in _chat_stream_to_responses_stream(
        chat_payloads(), original_model
    ):
        yield chunk


def _chat_chunk(
    delta: dict[str, Any],
    *,
    finish_reason: str | None = None,
    usage: dict[str, Any] | None = None,
) -> bytes:
    import json

    payload: dict[str, Any] = {
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}]
    }
    if usage is not None:
        payload["usage"] = usage
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()


def _responses_wire_finish_reason(reason: FinishReason) -> str:
    if reason == FinishReason.MAX_TOKENS:
        return "length"
    if reason == FinishReason.CONTENT_FILTER:
        return "content_filter"
    if reason == FinishReason.TOOL_USE:
        return "tool_calls"
    return "stop"


def _event_int(payload: Mapping[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Responses event must contain {key}")
    return value


# Responses stream emission, moved out of the old pairwise Chat ->
# Responses converter so the hub keeps one emitter per protocol.
async def _chat_stream_to_responses_stream(
    raw_iterator: AsyncIterator[bytes],
    original_model: str,
) -> AsyncIterator[bytes]:
    """Convert a chat SSE stream into a Responses API SSE stream."""
    state = _ResponsesStreamState(
        response_id=f"resp_{uuid.uuid4().hex[:24]}",
        message_id=f"msg_{uuid.uuid4().hex[:24]}",
        created_at=int(time.time()),
        model=original_model,
    )
    for event in state.start_events():
        yield event
    async for payload in parse_sse_json_stream(raw_iterator, require_done=True):
        for event in state.update(payload):
            yield event
    for event in state.finish_events():
        yield event
    yield b"data: [DONE]\n\n"


@dataclass(slots=True)
class _ResponsesStreamState:
    response_id: str
    message_id: str
    created_at: int
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    text_output_index: int | None = None
    text_parts: list[str] = field(default_factory=list)
    tool_calls: ChatToolCalls = field(default_factory=ChatToolCalls)
    next_output_index: int = 0
    finish_reason: str | None = None
    sequence_number: int = 0

    def start_events(self) -> list[bytes]:
        return [
            self.event(
                event_type,
                response=self.response(status="in_progress", output=[], usage=None),
            )
            for event_type in ("response.created", "response.in_progress")
        ]

    def update(self, payload: dict[str, Any]) -> list[bytes]:
        model = payload.get("model")
        if isinstance(model, str) and model:
            self.model = model
        usage = payload.get("usage") or {}
        if usage.get("prompt_tokens"):
            self.input_tokens = usage["prompt_tokens"]
        if usage.get("completion_tokens"):
            self.output_tokens = usage["completion_tokens"]

        events: list[bytes] = []
        for choice in payload.get("choices", []):
            self.finish_reason = choice.get("finish_reason") or self.finish_reason
            delta = choice.get("delta", {})
            events.extend(self._text_events(delta.get("content")))
            for value in delta.get("tool_calls") or []:
                events.extend(
                    self._tool_events(value, choice_index=chat_choice_index(choice))
                )
        return events

    def finish_events(self) -> list[bytes]:
        status, incomplete_details = _response_status(self.finish_reason)
        events: list[bytes] = []
        output_by_index: dict[int, dict[str, Any]] = {}

        text_events, text_output = self._finish_text(status)
        events.extend(text_events)
        if text_output is not None:
            output_index, item = text_output
            output_by_index[output_index] = item

        for tool_call in self.tool_calls:
            tool_events, output_index, item = self._finish_tool(tool_call, status)
            events.extend(tool_events)
            output_by_index[output_index] = item

        response = self.response(
            status=status,
            output=[output_by_index[index] for index in sorted(output_by_index)],
            usage={
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "total_tokens": self.input_tokens + self.output_tokens,
            },
        )
        if incomplete_details is not None:
            response["incomplete_details"] = incomplete_details
        terminal_type = (
            "response.completed" if status == "completed" else "response.incomplete"
        )
        events.append(self.event(terminal_type, response=response))
        return events

    def _text_events(self, delta: Any) -> list[bytes]:
        if not delta:
            return []
        if not isinstance(delta, str):
            raise ValueError("Chat content delta must be a string")
        events: list[bytes] = []
        if self.text_output_index is None:
            self.text_output_index = self.allocate_output_index()
            events.extend(
                [
                    self.event(
                        "response.output_item.added",
                        output_index=self.text_output_index,
                        item={
                            "id": self.message_id,
                            "type": "message",
                            "status": "in_progress",
                            "role": "assistant",
                            "content": [],
                        },
                    ),
                    self.event(
                        "response.content_part.added",
                        output_index=self.text_output_index,
                        content_index=0,
                        part={
                            "type": "output_text",
                            "text": "",
                            "annotations": [],
                        },
                    ),
                ]
            )
        self.text_parts.append(delta)
        events.append(
            self.event(
                "response.output_text.delta",
                output_index=self.text_output_index,
                content_index=0,
                delta=delta,
            )
        )
        return events

    def _tool_events(self, value: Any, *, choice_index: int) -> list[bytes]:
        events: list[bytes] = []
        for tool_call in self.tool_calls.update_many(value, choice_index=choice_index):
            if tool_call.target_index is None:
                tool_call.target_index = self.allocate_output_index()
            if not tool_call.announced and tool_call.call_id and tool_call.name:
                events.append(self._announce_tool(tool_call))
            if tool_call.announced:
                arguments_delta = tool_call.take_argument_delta()
                if arguments_delta:
                    events.append(
                        self._tool_arguments_event(tool_call, arguments_delta)
                    )
        return events

    def _finish_text(
        self, status: str
    ) -> tuple[list[bytes], tuple[int, dict[str, Any]] | None]:
        if self.text_output_index is None:
            return [], None
        text = "".join(self.text_parts)
        part = {"type": "output_text", "text": text, "annotations": []}
        item = {
            "id": self.message_id,
            "type": "message",
            "status": status,
            "role": "assistant",
            "content": [part],
        }
        events = [
            self.event(
                "response.output_text.done",
                item_id=self.message_id,
                output_index=self.text_output_index,
                content_index=0,
                text=text,
            ),
            self.event(
                "response.content_part.done",
                item_id=self.message_id,
                output_index=self.text_output_index,
                content_index=0,
                part=part,
            ),
            self.event(
                "response.output_item.done",
                output_index=self.text_output_index,
                item=item,
            ),
        ]
        return events, (self.text_output_index, item)

    def _finish_tool(
        self, tool_call: ChatToolCall, status: str
    ) -> tuple[list[bytes], int, dict[str, Any]]:
        events: list[bytes] = []
        if not tool_call.announced:
            events.append(self._announce_tool(tool_call))
        arguments_delta = tool_call.take_argument_delta()
        if arguments_delta:
            events.append(self._tool_arguments_event(tool_call, arguments_delta))
        output_index = _tool_output_index(tool_call)
        arguments = tool_call.arguments
        item = _tool_item(self, tool_call, status=status)
        events.extend(
            [
                self.event(
                    "response.function_call_arguments.done",
                    item_id=_tool_item_id(self, tool_call),
                    output_index=output_index,
                    arguments=arguments,
                ),
                self.event(
                    "response.output_item.done",
                    output_index=output_index,
                    item=item,
                ),
            ]
        )
        return events, output_index, item

    def _announce_tool(self, tool_call: ChatToolCall) -> bytes:
        event = self.event(
            "response.output_item.added",
            output_index=_tool_output_index(tool_call),
            item=_tool_item(self, tool_call, status="in_progress"),
        )
        tool_call.announced = True
        return event

    def _tool_arguments_event(self, tool_call: ChatToolCall, delta: str) -> bytes:
        return self.event(
            "response.function_call_arguments.delta",
            item_id=_tool_item_id(self, tool_call),
            output_index=_tool_output_index(tool_call),
            delta=delta,
        )

    def allocate_output_index(self) -> int:
        output_index = self.next_output_index
        self.next_output_index += 1
        return output_index

    def event(self, event_type: str, **payload: Any) -> bytes:
        data = {
            "type": event_type,
            "sequence_number": self.sequence_number,
            **payload,
        }
        self.sequence_number += 1
        return format_sse_event(event_type, data)

    def response(
        self,
        *,
        status: str,
        output: list[dict[str, Any]],
        usage: dict[str, int] | None,
    ) -> dict[str, Any]:
        return {
            "id": self.response_id,
            "object": "response",
            "created_at": self.created_at,
            "model": self.model,
            "status": status,
            "output": output,
            "usage": usage,
        }


def _response_status(finish_reason: Any) -> tuple[str, dict[str, str] | None]:
    status = FINISH_REASON_CHAT_TO_RESPONSES.get(finish_reason, "completed")
    if status == "completed":
        return status, None
    reason = (
        "content_filter" if finish_reason == "content_filter" else "max_output_tokens"
    )
    return status, {"reason": reason}


def _tool_item(
    state: _ResponsesStreamState,
    tool_call: ChatToolCall,
    *,
    status: str,
) -> dict[str, Any]:
    if not tool_call.call_id:
        raise ValueError("Chat tool call stream ended without id")
    if not tool_call.name:
        raise ValueError("Chat tool call stream ended without function.name")
    return {
        "id": _tool_item_id(state, tool_call),
        "type": "function_call",
        "status": status,
        "name": tool_call.name,
        "arguments": tool_call.arguments if status != "in_progress" else "",
        "call_id": tool_call.call_id,
    }


def _tool_item_id(state: _ResponsesStreamState, tool_call: ChatToolCall) -> str:
    return f"fc_{state.response_id.removeprefix('resp_')}_{tool_call.index}"


def _tool_output_index(tool_call: ChatToolCall) -> int:
    if tool_call.target_index is None:
        raise ValueError("Chat tool call stream ended without an output index")
    return tool_call.target_index

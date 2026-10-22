"""OpenAI Responses spoke: wire payloads <-> unified request.

The pairwise converters only ever used Responses as one side of a fixed pair,
so this module implements both directions against the unified protocol:
parsing a Responses client request or upstream response, and building a
Responses request or response body.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from typing import Any

from ...models.protocols import ProtocolKind
from . import cache, repair, signatures
from .chat_stream import ChatToolCall, ChatToolCalls, chat_choice_index
from .responses_common import (
    decode_reasoning_item,
    encode_reasoning_item,
    is_reasoning_envelope,
    lift_additional_tools,
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
    AudioPart,
    Citation,
    ContentPart,
    Continuation,
    FilePart,
    ImagePart,
    Message,
    MessageRole,
    ReasoningIntent,
    ReasoningKind,
    ReasoningPart,
    Refusal,
    ResponseFormat,
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
from .unified_response import (
    FinishReason,
    ResponseStatus,
    UnifiedResponse,
    Usage,
)
from .unified_stream import (
    BlockKind,
    BlockStart,
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

_ORIGIN = ProtocolKind.OPENAI_RESPONSES

# Input items that carry only server-side replay state. Other protocols have no
# equivalent, and dropping them keeps the visible conversation intact.
_SKIPPABLE_INPUT_ITEM_TYPES = frozenset(
    {
        "additional_tools",  # lifted into top-level tools before parsing
        "tool_search_call",
        "tool_search_output",
        "compaction",
        "compaction_trigger",
        "item_reference",
        "configuration_update",
    }
)

# Hosted tool items the model produced; each becomes a server-tool trace.
_SERVER_TOOL_ITEM_KINDS: dict[str, ServerToolKind] = {
    "web_search_call": ServerToolKind.WEB_SEARCH,
    "file_search_call": ServerToolKind.FILE_SEARCH,
    "code_interpreter_call": ServerToolKind.CODE_INTERPRETER,
    "image_generation_call": ServerToolKind.IMAGE_GENERATION,
    "computer_call": ServerToolKind.COMPUTER_USE,
    "computer_call_output": ServerToolKind.COMPUTER_USE,
    "mcp_call": ServerToolKind.MCP,
    "mcp_list_tools": ServerToolKind.MCP,
    "mcp_approval_request": ServerToolKind.MCP,
    "mcp_approval_response": ServerToolKind.MCP,
    "local_shell_call": ServerToolKind.LOCAL_SHELL,
    "shell_call": ServerToolKind.SHELL,
    "shell_call_output": ServerToolKind.SHELL,
}
_SERVER_TOOL_ITEM_TYPES = frozenset(_SERVER_TOOL_ITEM_KINDS)

# Canonical provider-tool names, which other protocols derive wire types from.
_SERVER_TOOL_NAMES: dict[ServerToolKind, str] = {
    ServerToolKind.WEB_SEARCH: "web_search",
    ServerToolKind.FILE_SEARCH: "file_search",
    ServerToolKind.CODE_INTERPRETER: "code_interpreter",
    ServerToolKind.IMAGE_GENERATION: "image_generation",
    ServerToolKind.COMPUTER_USE: "computer",
    ServerToolKind.MCP: "mcp",
    ServerToolKind.LOCAL_SHELL: "local_shell",
    ServerToolKind.SHELL: "bash",
    ServerToolKind.TOOL_SEARCH: "tool_search",
}


def parse_responses_request(body: Mapping[str, Any]) -> UnifiedRequest:
    """Parse a Responses API request body into the unified request."""
    body = lift_additional_tools(body)
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
    request.continuation = _responses_continuation(body)
    store = body.get("store")
    if isinstance(store, bool):
        request.continuation.store = store

    instructions = body.get("instructions")
    if isinstance(instructions, str) and instructions:
        request.system = [TextPart(text=instructions)]
    elif instructions is not None and not isinstance(instructions, str):
        raise ValueError("Responses instructions must be a string")

    request.messages = _responses_input_to_messages(
        body.get("input", []), request.system
    )
    request.tools, request.server_tools = _responses_tools(body.get("tools"))
    request.tool_choice = _responses_tool_choice(body.get("tool_choice"))
    parallel = body.get("parallel_tool_calls")
    if request.tool_choice is None and isinstance(parallel, bool):
        request.tool_choice = ToolChoice(
            mode=ToolChoiceMode.AUTO, allow_parallel=parallel
        )
    return request


def _responses_continuation(body: Mapping[str, Any]) -> Continuation:
    """Collect the server-side conversation handles a Responses client sent."""
    conversation = body.get("conversation")
    conversation_id = ""
    if isinstance(conversation, str):
        conversation_id = conversation
    elif isinstance(conversation, Mapping):
        conversation_id = _text(conversation.get("id"))
    return Continuation(
        previous_response_id=_text(body.get("previous_response_id")),
        conversation_id=conversation_id,
        prompt_cache_key=_text(body.get("prompt_cache_key")),
        safety_identifier=_text(body.get("safety_identifier")),
        service_tier=_text(body.get("service_tier")),
    )


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
    for message in repair.repair_history(list(request.messages)):
        if message.role == MessageRole.TOOL:
            for part in message.parts:
                if isinstance(part, ToolResultPart):
                    items.append(_tool_result_to_responses(part))
            continue
        items.extend(_message_to_responses(message, target_model=request.model))

    body: dict[str, Any] = dict(request.passthrough)
    body.pop("stream_options", None)
    body["input"] = items
    body["model"] = request.model
    if request.stream:
        body["stream"] = True
    continuation = request.continuation
    if request.origin is ProtocolKind.OPENAI_RESPONSES:
        # Only a Responses client can reuse a server-side response id.
        if continuation.previous_response_id:
            body["previous_response_id"] = continuation.previous_response_id
        if continuation.conversation_id:
            body["conversation"] = continuation.conversation_id
        if continuation.store is not None:
            body["store"] = continuation.store
    else:
        # No other client can name a stored response, so the upstream must not
        # be told to keep one on that client's behalf.
        body.pop("previous_response_id", None)
        if request.origin is ProtocolKind.ANTHROPIC:
            body["store"] = False
    for key, value in (
        ("prompt_cache_key", continuation.prompt_cache_key),
        ("prompt_cache_retention", continuation.prompt_cache_retention),
        ("safety_identifier", continuation.safety_identifier),
        ("service_tier", continuation.service_tier),
    ):
        if value:
            body.setdefault(key, value)
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
    for key, value in (
        ("seed", generation.seed),
        ("presence_penalty", generation.presence_penalty),
        ("frequency_penalty", generation.frequency_penalty),
        ("top_logprobs", generation.top_logprobs),
    ):
        if value is not None:
            body[key] = value
    tools = [_tool_to_responses(tool) for tool in request.tools]
    tools.extend(_server_tool_to_responses(tool) for tool in request.server_tools)
    if tools:
        body["tools"] = tools
    if request.tool_choice is not None and tools:
        body["tool_choice"] = _tool_choice_to_responses(request.tool_choice)
        if request.tool_choice.allow_parallel is not None:
            body["parallel_tool_calls"] = request.tool_choice.allow_parallel
    if request.reasoning is not None and (
        request.reasoning.effort is not None or request.reasoning.summary is not None
    ):
        reasoning: dict[str, Any] = {}
        if request.reasoning.effort is not None:
            reasoning["effort"] = request.reasoning.effort
        if request.reasoning.summary is not None:
            reasoning["summary"] = request.reasoning.summary
        body["reasoning"] = reasoning
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
        status=_responses_payload_status(body),
        incomplete_reason=_responses_incomplete_reason(body),
    )


def build_responses_response(response: UnifiedResponse) -> dict[str, Any]:
    """Build a Responses API response body from the unified response."""
    output: list[dict[str, Any]] = []
    text_parts: list[dict[str, Any]] = []
    tool_calls: list[dict[str, Any]] = []
    reasoning_items: list[dict[str, Any]] = []
    server_items: list[dict[str, Any]] = []

    for part in response.parts:
        if isinstance(part, TextPart):
            text_parts.append(
                {
                    "type": "output_text",
                    "annotations": [
                        _citation_to_responses(citation) for citation in part.citations
                    ],
                    "text": part.text,
                }
            )
        elif isinstance(part, ReasoningPart):
            reasoning_items.append(_reasoning_to_responses(part))
        elif isinstance(part, ToolCallPart):
            item: dict[str, Any] = {
                "id": f"ctc_{uuid.uuid4().hex[:24]}"
                if part.kind is ToolKind.CUSTOM
                else f"fc_{uuid.uuid4().hex[:24]}",
                "call_id": part.call_id,
                "name": part.name,
                "status": "completed",
            }
            if part.namespace:
                item["namespace"] = part.namespace
            if part.kind is ToolKind.CUSTOM:
                item["type"] = "custom_tool_call"
                item["input"] = part.arguments
            else:
                item["type"] = "function_call"
                item["arguments"] = part.arguments or "{}"
            tool_calls.append(item)
        elif isinstance(part, ServerToolPart):
            server_items.append(_server_part_to_responses(part))
        elif isinstance(part, Refusal):
            text_parts.append(
                {"type": "refusal", "refusal": part.text, "annotations": []}
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
    output.extend(server_items)

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
            # Leading instructions are prepended; a system item that arrives
            # after the conversation keeps its position so a target without
            # mid-turn system turns can demote it in place.
            flush()
            parts = _responses_content_parts(item.get("content"))
            if messages:
                messages.append(Message(role=MessageRole.SYSTEM, parts=parts))
            else:
                system_parts.extend(parts)
            continue
        if item_type in _SKIPPABLE_INPUT_ITEM_TYPES:
            continue
        if item_type in {"function_call", "custom_tool_call"}:
            pending_calls.append(_responses_call_to_unified(item, item_type))
            continue
        if item_type in _SERVER_TOOL_ITEM_TYPES:
            server = _responses_server_item(item, item_type)
            if server is not None:
                pending_calls.append(server)
            continue
        flush()
        if item_type in {"function_call_output", "custom_tool_call_output"}:
            messages.append(
                Message(
                    role=MessageRole.TOOL,
                    parts=[_responses_tool_output(item)],
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
                            kind=ReasoningKind.ENCRYPTED,
                            item_id=_text(item.get("id")),
                            summary=tuple(_reasoning_summary_parts(item)),
                            sealed=dict(item),
                        )
                    ],
                )
            )
        else:
            messages.append(_responses_message_to_unified(item))
    flush()
    return messages


def _reasoning_summary_parts(item: Mapping[str, Any]) -> list[str]:
    summary = item.get("summary")
    if not isinstance(summary, list):
        return []
    texts: list[str] = []
    for block in summary:
        if isinstance(block, Mapping) and isinstance(block.get("text"), str):
            texts.append(block["text"])
    return texts


def _responses_call_to_unified(item: Mapping[str, Any], item_type: str) -> ToolCallPart:
    if item_type == "custom_tool_call":
        return ToolCallPart(
            call_id=required_string(
                item.get("call_id"), "Responses custom_tool_call must contain call_id"
            ),
            name=required_string(
                item.get("name"), "Responses custom_tool_call must contain name"
            ),
            arguments=_text(item.get("input")),
            origin=_ORIGIN,
            kind=ToolKind.CUSTOM,
            namespace=_text(item.get("namespace")),
        )
    return ToolCallPart(
        call_id=required_string(
            item.get("call_id"), "Responses function_call must contain call_id"
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
        namespace=_text(item.get("namespace")),
    )


def _responses_tool_output(item: Mapping[str, Any]) -> ToolResultPart:
    value = item.get("output")
    texts: list[str] = []
    parts: list[ContentPart] = []
    if isinstance(value, list):
        for block in value:
            if not isinstance(block, Mapping):
                continue
            block_type = block.get("type")
            if block_type in {"input_text", "output_text", "text"}:
                text = block.get("text")
                if isinstance(text, str):
                    texts.append(text)
            elif block_type == "input_image":
                parts.append(_responses_image_to_unified(block))
            elif block_type == "input_file":
                parts.append(_responses_file_to_unified(block))
    return ToolResultPart(
        call_id=required_string(
            item.get("call_id"),
            f"Responses {item.get('type')} must contain call_id",
        ),
        content="\n".join(texts) if texts else _tool_output_text(value),
        parts=parts,
    )


def _responses_server_item(
    item: Mapping[str, Any], item_type: str
) -> ServerToolPart | None:
    """Keep a hosted tool call from history as a server-tool trace."""
    kind = _SERVER_TOOL_ITEM_KINDS.get(item_type)
    if kind is None:
        return None
    status = _text(item.get("status"))
    return ServerToolPart(
        kind=kind,
        # The canonical tool name, not the item type: Anthropic derives its
        # ``<name>_tool_result`` block type from this, and ``web_search_call``
        # would produce a block type that does not exist.
        name=_SERVER_TOOL_NAMES.get(kind, ""),
        call_id=_text(item.get("id")) or _text(item.get("call_id")),
        status=status,
        arguments=json.dumps(item.get("action") or {}, ensure_ascii=False)
        if isinstance(item.get("action"), Mapping)
        else "",
        output=_server_item_output(item),
        origin=_ORIGIN,
        raw=dict(item),
    )


def _server_item_output(item: Mapping[str, Any]) -> list[ContentPart]:
    results: list[ContentPart] = []
    action = item.get("action")
    sources = action.get("sources") if isinstance(action, Mapping) else None
    if isinstance(sources, list):
        for source in sources:
            if not isinstance(source, Mapping):
                continue
            url = _text(source.get("url"))
            if url:
                results.append(
                    TextPart(
                        text=f"{_text(source.get('title')) or url}\n{url}",
                        citations=[Citation(url=url, title=_text(source.get("title")))],
                    )
                )
    return results


def _responses_message_to_unified(item: Mapping[str, Any]) -> Message:
    item_type = item.get("type")
    if item_type is not None and item_type != "message":
        raise ValueError(
            f"Responses input item type '{item_type}' cannot be converted to "
            "another protocol"
        )
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
            hint = cache.normalize_cache_control(block.get("cache_control"))
            parts.append(
                TextPart(
                    text=required_string(
                        block.get("text"),
                        "Responses text parts must contain text",
                        allow_empty=True,
                    ),
                    cache_breakpoint=hint is not None,
                    cache_control=hint,
                    citations=_responses_annotations(block.get("annotations")),
                )
            )
        elif block_type == "input_image":
            part = _responses_image_to_unified(block)
            part.cache_control = cache.normalize_cache_control(
                block.get("cache_control")
            )
            parts.append(part)
        elif block_type == "input_file":
            part = _responses_file_to_unified(block)
            part.cache_control = cache.normalize_cache_control(
                block.get("cache_control")
            )
            parts.append(part)
        elif block_type == "input_audio":
            parts.append(_responses_audio_to_unified(block))
        elif block_type == "refusal":
            parts.append(
                Refusal(
                    text=required_string(
                        block.get("refusal"),
                        "Responses refusal parts must contain refusal",
                        allow_empty=True,
                    )
                )
            )
        else:
            raise ValueError(
                f"Responses content part type '{block_type}' cannot be converted "
                "to another protocol"
            )
    return parts


def _responses_annotations(value: Any) -> list[Citation]:
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
                start_index=_optional_int(block.get("start_index")),
                end_index=_optional_int(block.get("end_index")),
                raw=dict(block),
            )
        )
    return citations


def _responses_audio_to_unified(block: Mapping[str, Any]) -> AudioPart:
    audio = block.get("input_audio")
    if not isinstance(audio, Mapping):
        raise ValueError("Responses input_audio parts must contain an object")
    data = _text(audio.get("data"))
    url = _text(audio.get("url"))
    if not data and not url:
        raise ValueError("Responses input_audio parts must contain data or a url")
    return AudioPart(
        data=data,
        url=url,
        format=_text(audio.get("format")),
        media_type=_text(audio.get("mime_type")),
    )


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


_SERVER_TOOL_TYPES: dict[str, ServerToolKind] = {
    "web_search": ServerToolKind.WEB_SEARCH,
    "web_search_preview": ServerToolKind.WEB_SEARCH,
    "web_search_2025_08_26": ServerToolKind.WEB_SEARCH,
    "file_search": ServerToolKind.FILE_SEARCH,
    "code_interpreter": ServerToolKind.CODE_INTERPRETER,
    "image_generation": ServerToolKind.IMAGE_GENERATION,
    "computer_use_preview": ServerToolKind.COMPUTER_USE,
    "computer_use": ServerToolKind.COMPUTER_USE,
    "mcp": ServerToolKind.MCP,
    "local_shell": ServerToolKind.LOCAL_SHELL,
    "shell": ServerToolKind.SHELL,
    "tool_search": ServerToolKind.TOOL_SEARCH,
}


def _responses_tools(
    value: Any,
) -> tuple[list[ToolDefinition], list[ServerToolDefinition]]:
    """Split Responses tools into client-declared and provider-executed ones.

    ``custom`` and ``namespace`` keep their native shape so they round-trip to a
    Responses upstream and degrade elsewhere; hosted tools become server tools
    rather than being rejected.
    """
    if value is None:
        return [], []
    if not isinstance(value, list):
        raise ValueError("Responses tools must be an array")
    tools: list[ToolDefinition] = []
    server_tools: list[ServerToolDefinition] = []
    for tool in value:
        if not isinstance(tool, Mapping):
            raise ValueError("Responses tools must contain objects")
        tool_type = tool.get("type")
        if isinstance(tool_type, str) and tool_type in _SERVER_TOOL_TYPES:
            server_tools.append(
                ServerToolDefinition(
                    kind=_SERVER_TOOL_TYPES[tool_type],
                    name=tool_type,
                    options={
                        key: item
                        for key, item in tool.items()
                        if key not in {"type", "name"}
                    },
                )
            )
            continue
        if tool_type == "namespace":
            namespace = required_string(
                tool.get("name"), "Responses namespace tools must contain name"
            )
            members, nested_servers = _responses_tools(tool.get("tools"))
            for member in members:
                member.namespace = namespace
            tools.extend(members)
            server_tools.extend(nested_servers)
            continue
        if tool_type == "custom":
            tools.append(
                ToolDefinition(
                    name=required_string(
                        tool.get("name"), "Responses custom tools must contain name"
                    ),
                    description=_text(tool.get("description")),
                    kind=ToolKind.CUSTOM,
                    format=dict(tool["format"])
                    if isinstance(tool.get("format"), Mapping)
                    else None,
                )
            )
            continue
        if tool_type != "function":
            raise ValueError(
                f"Responses tool type '{tool_type}' cannot be converted to "
                "another protocol"
            )
        parameters = tool.get("parameters")
        tools.append(
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
    return tools, server_tools


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
    message: Message, *, target_model: str = ""
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    content: list[dict[str, Any]] = []
    tool_calls: list[dict[str, Any]] = []
    for part in message.parts:
        if isinstance(part, ReasoningPart):
            if part.origin is not _ORIGIN:
                continue
            if part.opaque and not signatures.can_replay(
                origin=part.origin,
                target=_ORIGIN,
                opaque=part.opaque,
                target_model=target_model,
            ):
                # Sealed by another provider family: replay only what is
                # readable, because the blob would be rejected upstream.
                items.append(_plain_reasoning_item(part))
                continue
            if part.sealed is not None:
                items.append(dict(part.sealed))
                continue
            decoded = decode_reasoning_item(part.opaque)
            if decoded is not None:
                items.append(decoded)
            elif part.text:
                items.append(_plain_reasoning_item(part))
            continue
        if isinstance(part, ToolCallPart):
            tool_calls.append(_tool_call_to_responses(part))
            continue
        if isinstance(part, ServerToolPart):
            items.append(_server_part_to_responses(part))
            continue
        if isinstance(part, TextPart):
            # Responses has no ``cache_control``; prompt caching is requested
            # with ``prompt_cache_key`` instead, so a breakpoint is not emitted.
            block: dict[str, Any] = {
                "type": (
                    "input_text"
                    if message.role != MessageRole.ASSISTANT
                    else "output_text"
                ),
                "text": part.text,
            }
            if part.citations:
                block["annotations"] = [
                    _citation_to_responses(citation) for citation in part.citations
                ]
            content.append(block)
        elif isinstance(part, ImagePart):
            content.append(_image_to_responses(part))
        elif isinstance(part, FilePart):
            content.append(_file_to_responses(part))
        elif isinstance(part, AudioPart):
            content.append(_audio_to_responses(part))
        elif isinstance(part, Refusal):
            content.append({"type": "refusal", "refusal": part.text})
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


def _plain_reasoning_item(part: ReasoningPart) -> dict[str, Any]:
    item: dict[str, Any] = {"type": "reasoning", "summary": []}
    if part.item_id:
        item["id"] = part.item_id
    if part.summary:
        item["summary"] = [
            {"type": "summary_text", "text": text} for text in part.summary
        ]
    elif part.text:
        item["summary"] = [{"type": "summary_text", "text": part.text}]
    return item


def _citation_to_responses(citation: Citation) -> dict[str, Any]:
    if citation.raw:
        return dict(citation.raw)
    result: dict[str, Any] = {
        "type": "url_citation",
        "url": citation.url,
        "title": citation.title or citation.url,
    }
    if citation.start_index is not None and citation.end_index is not None:
        result["start_index"] = citation.start_index
        result["end_index"] = citation.end_index
    return result


def _audio_to_responses(part: AudioPart) -> dict[str, Any]:
    audio: dict[str, Any] = {}
    if part.data:
        audio["data"] = part.data
    if part.url:
        audio["url"] = part.url
    if part.format:
        audio["format"] = part.format
    if not audio:
        raise ValueError("Unified audio part must contain data or a URL")
    return {"type": "input_audio", "input_audio": audio}


def _tool_call_to_responses(part: ToolCallPart) -> dict[str, Any]:
    item: dict[str, Any] = {"call_id": part.call_id}
    if part.namespace:
        item["namespace"] = part.namespace
    if part.kind is ToolKind.CUSTOM:
        item["type"] = "custom_tool_call"
        item["name"] = part.name
        item["input"] = part.arguments
        return item
    item["type"] = "function_call"
    item["name"] = part.name
    item["arguments"] = part.arguments or "{}"
    return item


def _server_part_to_responses(part: ServerToolPart) -> dict[str, Any]:
    """Re-emit a hosted tool call in the shape Responses produced it."""
    if part.raw is not None:
        return dict(part.raw)
    item_type = {
        ServerToolKind.WEB_SEARCH: "web_search_call",
        ServerToolKind.FILE_SEARCH: "file_search_call",
        ServerToolKind.CODE_INTERPRETER: "code_interpreter_call",
        ServerToolKind.IMAGE_GENERATION: "image_generation_call",
        ServerToolKind.COMPUTER_USE: "computer_call",
        ServerToolKind.MCP: "mcp_call",
        ServerToolKind.LOCAL_SHELL: "local_shell_call",
        ServerToolKind.SHELL: "shell_call",
    }.get(part.kind, "web_search_call")
    item: dict[str, Any] = {"type": item_type, "id": part.call_id or part.name}
    if part.status:
        item["status"] = part.status
    if part.kind is ServerToolKind.WEB_SEARCH:
        action: dict[str, Any] = {"type": "search"}
        try:
            parsed = json.loads(part.arguments) if part.arguments else {}
        except ValueError:
            parsed = {}
        if isinstance(parsed, Mapping):
            action.update(parsed)
        sources = [
            {"type": "url", "url": citation.url, "title": citation.title}
            for output in part.output
            if isinstance(output, TextPart)
            for citation in output.citations
        ]
        if sources:
            action["sources"] = sources
        item["action"] = action
    return item


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
    """Emit a tool output, keeping media Responses can carry inline."""
    output: Any = part.content
    if part.parts:
        blocks: list[dict[str, Any]] = []
        if part.content:
            blocks.append({"type": "input_text", "text": part.content})
        for nested in part.parts:
            if isinstance(nested, ImagePart):
                blocks.append(_image_to_responses(nested))
            elif isinstance(nested, FilePart):
                blocks.append(_file_to_responses(nested))
            elif isinstance(nested, TextPart):
                blocks.append({"type": "input_text", "text": nested.text})
        output = blocks or part.content
    return {
        "type": "function_call_output",
        "call_id": part.call_id,
        "output": output,
    }


def _tool_to_responses(tool: ToolDefinition) -> dict[str, Any]:
    if tool.kind is ToolKind.CUSTOM:
        result: dict[str, Any] = {"type": "custom", "name": tool.name}
        if tool.description:
            result["description"] = tool.description
        if tool.format is not None:
            result["format"] = tool.format
        return result
    result = {"type": "function", "name": tool.name}
    if tool.description:
        result["description"] = tool.description
    if tool.parameters is not None:
        result["parameters"] = tool.parameters
    if tool.strict is not None:
        result["strict"] = tool.strict
    return result


def _server_tool_to_responses(tool: ServerToolDefinition) -> dict[str, Any]:
    result: dict[str, Any] = {"type": tool.name or tool.kind.value}
    result.update(tool.options)
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
                    kind=ReasoningKind.ENCRYPTED,
                    item_id=_text(item.get("id")),
                    summary=tuple(_reasoning_summary_parts(item)),
                    sealed=dict(item),
                )
            )
        elif item_type in {"function_call", "custom_tool_call"}:
            parts.append(_responses_call_to_unified(item, item_type))
        elif item_type in _SERVER_TOOL_ITEM_TYPES:
            server = _responses_server_item(item, item_type)
            if server is not None:
                parts.append(server)
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
        isinstance(item, Mapping)
        and item.get("type") in {"function_call", "custom_tool_call"}
        for item in output
    )
    return FinishReason.TOOL_USE if has_tools else FinishReason.END_TURN


def _responses_payload_status(body: Mapping[str, Any]) -> ResponseStatus:
    status = body.get("status")
    return {
        "completed": ResponseStatus.COMPLETED,
        "incomplete": ResponseStatus.INCOMPLETE,
        "failed": ResponseStatus.FAILED,
        "cancelled": ResponseStatus.CANCELLED,
    }.get(status, ResponseStatus.COMPLETED)


def _responses_incomplete_reason(body: Mapping[str, Any]) -> str:
    details = body.get("incomplete_details")
    if not isinstance(details, Mapping):
        return ""
    return _text(details.get("reason"))


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
            message = _text(payload.get("message"))
            error = payload.get("error")
            if not message and isinstance(error, Mapping):
                message = _text(error.get("message"))
            raise ValueError(message or "Responses stream failed")
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
            elif isinstance(event, RefusalDelta):
                # The chat-shaped state has no refusal channel, so the refusal
                # text streams as content rather than disappearing.
                yield _chat_chunk({"content": event.text})
            elif isinstance(event, CitationDelta):
                url = event.citation.url
                if url:
                    yield _chat_chunk({"content": f" [{url}]"})
            elif isinstance(event, ServerToolStatusDelta):
                # Lifecycle ticks carry no content the client can act on.
                continue
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
                # Chat has no signature channel, so the envelope travels in its
                # own internal chunk for the Responses state to re-encode.
                yield _chat_chunk({"reasoning_signature": event.opaque})
            elif isinstance(event, StreamFinish):
                # A tool call whose upstream sent no argument delta still needs
                # an identity frame; otherwise the response omits the call.
                for index in sorted(tool_identities):
                    if index in tool_announced:
                        continue
                    call_id, name = tool_identities[index]
                    if not call_id and not name:
                        continue
                    tool_announced.add(index)
                    yield _chat_chunk(
                        {
                            "tool_calls": [
                                {
                                    "index": index,
                                    "id": call_id,
                                    "type": "function",
                                    "function": {"name": name, "arguments": "{}"},
                                }
                            ]
                        }
                    )
                yield _chat_chunk(
                    {},
                    finish_reason=_responses_wire_finish_reason(event.reason),
                    usage={
                        "prompt_tokens": event.usage.input_tokens,
                        "completion_tokens": event.usage.output_tokens,
                        "cache_write_tokens": event.usage.cache_creation_input_tokens,
                        "completion_tokens_details": {
                            "reasoning_tokens": event.usage.reasoning_tokens,
                        },
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
    cached_tokens: int = 0
    cache_write_tokens: int = 0
    reasoning_tokens: int = 0
    reasoning_output_index: int | None = None
    reasoning_parts: list[str] = field(default_factory=list)
    reasoning_signature: str = ""
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
        prompt_details = usage.get("prompt_tokens_details")
        if isinstance(prompt_details, dict):
            self.cached_tokens = int(prompt_details.get("cached_tokens") or 0)
        if usage.get("cache_write_tokens"):
            self.cache_write_tokens = usage["cache_write_tokens"]
        completion_details = usage.get("completion_tokens_details")
        if isinstance(completion_details, dict):
            self.reasoning_tokens = int(completion_details.get("reasoning_tokens") or 0)

        events: list[bytes] = []
        for choice in payload.get("choices", []):
            self.finish_reason = choice.get("finish_reason") or self.finish_reason
            delta = choice.get("delta", {})
            events.extend(self._reasoning_events(delta.get("reasoning_content")))
            events.extend(
                self._reasoning_signature_events(delta.get("reasoning_signature"))
            )
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

        reasoning_events, reasoning_output = self._finish_reasoning()
        events.extend(reasoning_events)
        if reasoning_output is not None:
            output_index, item = reasoning_output
            output_by_index[output_index] = item

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
        usage_payload = response.get("usage")
        if isinstance(usage_payload, dict):
            usage_payload["input_tokens_details"] = {
                "cached_tokens": self.cached_tokens,
                "cache_write_tokens": self.cache_write_tokens,
            }
            usage_payload["output_tokens_details"] = {
                "reasoning_tokens": self.reasoning_tokens,
            }
        terminal_type = (
            "response.completed" if status == "completed" else "response.incomplete"
        )
        events.append(self.event(terminal_type, response=response))
        return events

    def _reasoning_item_id(self) -> str:
        return f"rs_{self.response_id.removeprefix('resp_')}"

    def _ensure_reasoning_started(self) -> list[bytes]:
        if self.reasoning_output_index is not None:
            return []
        self.reasoning_output_index = self.allocate_output_index()
        return [
            self.event(
                "response.output_item.added",
                output_index=self.reasoning_output_index,
                item={
                    "id": self._reasoning_item_id(),
                    "type": "reasoning",
                    "status": "in_progress",
                    "summary": [],
                },
            ),
            self.event(
                "response.reasoning_summary_part.added",
                output_index=self.reasoning_output_index,
                summary_index=0,
                part={"type": "summary_text", "text": ""},
            ),
        ]

    def _reasoning_events(self, delta: Any) -> list[bytes]:
        if not delta:
            return []
        if not isinstance(delta, str):
            raise ValueError("Chat reasoning delta must be a string")
        events = self._ensure_reasoning_started()
        self.reasoning_parts.append(delta)
        events.append(
            self.event(
                "response.reasoning_summary_text.delta",
                output_index=self.reasoning_output_index,
                summary_index=0,
                delta=delta,
            )
        )
        return events

    def _reasoning_signature_events(self, value: Any) -> list[bytes]:
        if not isinstance(value, str) or not value:
            return []
        events = self._ensure_reasoning_started()
        self.reasoning_signature = value
        return events

    def _reasoning_item(self) -> dict[str, Any]:
        if self.reasoning_signature and is_reasoning_envelope(self.reasoning_signature):
            decoded = decode_reasoning_item(self.reasoning_signature)
            if decoded is not None:
                return decoded
        text = "".join(self.reasoning_parts)
        return {
            "id": self._reasoning_item_id(),
            "type": "reasoning",
            "status": "completed",
            "summary": [
                {"type": "summary_text", "text": part}
                for part in text.split("\n\n")
                if part
            ],
        }

    def _finish_reasoning(
        self,
    ) -> tuple[list[bytes], tuple[int, dict[str, Any]] | None]:
        if self.reasoning_output_index is None:
            return [], None
        text = "".join(self.reasoning_parts)
        item = self._reasoning_item()
        events = [
            self.event(
                "response.reasoning_summary_text.done",
                output_index=self.reasoning_output_index,
                summary_index=0,
                text=text,
            ),
            self.event(
                "response.reasoning_summary_part.done",
                output_index=self.reasoning_output_index,
                summary_index=0,
                part={"type": "summary_text", "text": text},
            ),
            self.event(
                "response.output_item.done",
                output_index=self.reasoning_output_index,
                item=item,
            ),
        ]
        return events, (self.reasoning_output_index, item)

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

"""Chat Completions spoke: wire payloads <-> unified request.

Parsing covers the OpenAI Chat Completions request and response shapes
(including ``reasoning_content`` and the streaming tool-call repair already
handled by ``chat_stream``); building covers the same shapes for an upstream
that speaks Chat Completions.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ...models.protocols import ProtocolKind
from .unified import (
    ContentPart,
    FilePart,
    GenerationConfig,
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
from .validation import required_string

_ORIGIN = ProtocolKind.OPENAI_CHAT
_MAX_TOKEN_KEYS = ("max_completion_tokens", "max_tokens")


def parse_chat_request(body: Mapping[str, Any]) -> UnifiedRequest:
    """Parse a Chat Completions request body into the unified request."""
    messages = body.get("messages")
    if not isinstance(messages, list):
        raise ValueError("Chat request messages must be an array")

    request = UnifiedRequest(model=_optional_string(body.get("model")) or "")
    request.stream = _optional_bool(body.get("stream")) or False
    request.replay_reasoning = (
        _optional_bool(body.get("_lens_replay_reasoning")) or False
    )
    request.include_usage = _stream_includes_usage(body.get("stream_options"))
    request.generation = _chat_generation_config(body)
    request.tools = _chat_tools(body.get("tools"))
    request.tool_choice = _chat_tool_choice(body.get("tool_choice"))
    request.response_format = _chat_response_format(body)
    request.reasoning = _chat_reasoning_intent(body)
    request.user_id = _optional_string(body.get("user")) or ""
    request.passthrough = _chat_passthrough(body)

    for message in messages:
        request.messages.extend(_chat_message(message))
    return request


def build_chat_request(request: UnifiedRequest) -> dict[str, Any]:
    """Build a Chat Completions request body from the unified request."""
    messages: list[dict[str, Any]] = []
    if request.system:
        messages.append(
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
        messages.append(_message_to_chat(message, request=request))

    body: dict[str, Any] = dict(request.passthrough)
    body["messages"] = messages
    body["model"] = request.model
    generation = request.generation
    if generation.max_output_tokens is not None:
        body["max_tokens"] = generation.max_output_tokens
    for key, value in (
        ("temperature", generation.temperature),
        ("top_p", generation.top_p),
        ("top_k", generation.top_k),
    ):
        if value is not None:
            body[key] = value
    for key, value in (
        ("seed", generation.seed),
        ("presence_penalty", generation.presence_penalty),
        ("frequency_penalty", generation.frequency_penalty),
    ):
        if value is not None:
            body[key] = value
    if generation.stop:
        body["stop"] = list(generation.stop)
    if request.tools:
        body["tools"] = [_tool_to_chat(tool) for tool in request.tools]
    if request.tool_choice is not None and request.tools:
        body["tool_choice"] = _tool_choice_to_chat(request.tool_choice)
        if request.tool_choice.allow_parallel is not None:
            body["parallel_tool_calls"] = request.tool_choice.allow_parallel
    if request.reasoning is not None and request.reasoning.effort is not None:
        body["reasoning_effort"] = request.reasoning.effort
    if request.response_format is not None and request.response_format.kind:
        body["response_format"] = _response_format_to_chat(request.response_format)
    if request.user_id:
        body["user"] = request.user_id
    if request.stream:
        body["stream"] = True
        if request.include_usage:
            body.setdefault("stream_options", {"include_usage": True})
    else:
        body.pop("stream_options", None)
    return body


def parse_chat_response(body: Mapping[str, Any]) -> UnifiedResponse:
    """Parse a Chat Completions response body into the unified response."""
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("Chat response must contain choices")
    choice = choices[0]
    if not isinstance(choice, Mapping):
        raise ValueError("Chat response choices must contain objects")

    response = UnifiedResponse(
        id=_optional_string(body.get("id")) or "",
        model=_optional_string(body.get("model")) or "",
        finish=_chat_finish_reason(choice.get("finish_reason")),
        usage=_chat_usage(body.get("usage")),
    )
    message = choice.get("message")
    if not isinstance(message, Mapping):
        raise ValueError("Chat response choices must contain a message")
    response.parts = _chat_message_parts(message)
    return response


def build_chat_response(response: UnifiedResponse) -> dict[str, Any]:
    """Build a Chat Completions response body from the unified response."""
    text_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    reasoning: list[str] = []
    for part in response.parts:
        if isinstance(part, TextPart):
            text_parts.append(part.text)
        elif isinstance(part, ReasoningPart):
            reasoning.append(part.text)
        elif isinstance(part, ToolCallPart):
            tool_calls.append(
                {
                    "id": part.call_id,
                    "type": "function",
                    "function": {"name": part.name, "arguments": part.arguments},
                }
            )

    message: dict[str, Any] = {"role": "assistant"}
    content = "".join(text_parts)
    message["content"] = content or (None if tool_calls else "")
    if reasoning:
        message["reasoning_content"] = "".join(reasoning)
    if tool_calls:
        message["tool_calls"] = tool_calls

    body: dict[str, Any] = {
        "id": response.id,
        "object": "chat.completion",
        "model": response.model,
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": _chat_finish_reason_wire(response.finish),
            }
        ],
        "usage": _chat_usage_wire(response.usage),
    }
    return body


def _chat_generation_config(body: Mapping[str, Any]) -> GenerationConfig:
    config = GenerationConfig()
    for key in _MAX_TOKEN_KEYS:
        value = body.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            config.max_output_tokens = value
            break
    config.temperature = _optional_float(body.get("temperature"))
    config.top_p = _optional_float(body.get("top_p"))
    top_k = body.get("top_k")
    config.top_k = (
        top_k if isinstance(top_k, int) and not isinstance(top_k, bool) else None
    )
    config.seed = body.get("seed") if isinstance(body.get("seed"), int) else None
    config.presence_penalty = _optional_float(body.get("presence_penalty"))
    config.frequency_penalty = _optional_float(body.get("frequency_penalty"))
    stop = body.get("stop")
    if isinstance(stop, str):
        config.stop = (stop,)
    elif isinstance(stop, list):
        config.stop = tuple(value for value in stop if isinstance(value, str))
    return config


def _chat_passthrough(body: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in (
        "stream_options",
        "metadata",
        "store",
        "service_tier",
        "safety_identifier",
        "prompt_cache_key",
        "prompt_cache_options",
        "prompt_cache_retention",
        "parallel_tool_calls",
        "verbosity",
    ):
        if key in body:
            result[key] = body[key]
    return result


def _chat_message(message: Any) -> list[Message]:
    if not isinstance(message, Mapping):
        raise ValueError("Chat request messages must contain objects")
    role = message.get("role")
    if not isinstance(role, str):
        raise ValueError("Chat messages must contain a string role")
    if role == "tool":
        return [
            Message(
                role=MessageRole.TOOL,
                parts=[
                    ToolResultPart(
                        call_id=required_string(
                            message.get("tool_call_id"),
                            "Chat tool messages must contain tool_call_id",
                        ),
                        content=_chat_tool_output(message.get("content")),
                    )
                ],
            )
        ]
    if role == "developer":
        role = "system"
    if role not in {"system", "user", "assistant"}:
        raise ValueError(f"Unsupported Chat message role: {role}")

    parts: list[ContentPart] = _chat_content_parts(message.get("content"))
    if role == "assistant":
        reasoning = message.get("reasoning_content")
        if isinstance(reasoning, str) and reasoning:
            parts.insert(0, ReasoningPart(text=reasoning, origin=_ORIGIN))
        raw_tool_calls = message.get("tool_calls")
        if raw_tool_calls is not None:
            if not isinstance(raw_tool_calls, list):
                raise ValueError("Chat assistant tool_calls must be an array")
            parts.extend(_chat_tool_calls(raw_tool_calls))
    message_role = MessageRole.SYSTEM if role == "system" else MessageRole(role)
    return [
        Message(
            role=message_role,
            parts=parts,
            plain_text_content=isinstance(message.get("content"), str),
        )
    ]


def _chat_content_parts(content: Any) -> list[ContentPart]:
    if content is None:
        return []
    if isinstance(content, str):
        return [TextPart(text=content)]
    if not isinstance(content, list):
        raise ValueError("Chat message content must be a string or array")
    parts: list[ContentPart] = []
    for part in content:
        if not isinstance(part, Mapping):
            raise ValueError("Chat message content must contain objects")
        part_type = part.get("type")
        if part_type == "text":
            parts.append(
                TextPart(
                    text=required_string(
                        part.get("text"),
                        "Chat text parts must contain text",
                        allow_empty=True,
                    )
                )
            )
        elif part_type == "image_url":
            parts.append(_chat_image_part(part))
        elif part_type == "file":
            parts.append(_chat_file_part(part))
        else:
            raise ValueError(f"Unsupported Chat content part type: {part_type}")
    return parts


def _chat_image_part(part: Mapping[str, Any]) -> ImagePart:
    image_url = part.get("image_url")
    detail = ""
    if isinstance(image_url, Mapping):
        detail = _optional_string(image_url.get("detail")) or ""
        image_url = image_url.get("url")
    url = required_string(image_url, "Chat image_url parts must contain a URL")
    if detail and detail not in {"auto", "low", "high"}:
        detail = ""
    if url.startswith("data:") and ";base64," in url:
        header, _, data = url.partition(",")
        media_type = header[len("data:") :].split(";")[0]
        return ImagePart(media_type=media_type, data=data, detail=detail)
    return ImagePart(url=url, detail=detail)


def _chat_file_part(part: Mapping[str, Any]) -> FilePart:
    file = part.get("file")
    if not isinstance(file, Mapping):
        raise ValueError("Chat file parts must contain a file object")
    result = FilePart()
    for key, attribute in (
        ("file_id", "file_id"),
        ("file_data", "data"),
        ("file_url", "url"),
        ("filename", "filename"),
    ):
        value = file.get(key)
        if isinstance(value, str) and value:
            setattr(result, attribute, value)
    if not (result.file_id or result.data or result.url):
        raise ValueError("Chat file parts must contain a file source")
    return result


def _chat_tool_output(content: Any) -> str:
    if isinstance(content, str):
        return content
    if content is None:
        return ""
    if not isinstance(content, list):
        raise ValueError("Chat tool message content must be a string or array")
    text_parts: list[str] = []
    for part in content:
        if not isinstance(part, Mapping):
            raise ValueError("Chat tool message content must contain objects")
        if part.get("type") == "text":
            text_parts.append(
                required_string(
                    part.get("text"),
                    "Chat tool text parts must contain text",
                    allow_empty=True,
                )
            )
        else:
            raise ValueError(
                f"Unsupported Chat tool content part type: {part.get('type')}"
            )
    return "".join(text_parts)


def _chat_tool_calls(value: list[Any]) -> list[ToolCallPart]:
    result: list[ToolCallPart] = []
    for tool_call in value:
        if not isinstance(tool_call, Mapping):
            raise ValueError("Chat assistant tool_calls must contain objects")
        if tool_call.get("type") != "function":
            raise ValueError("Unsupported Chat tool call type")
        function = tool_call.get("function")
        if not isinstance(function, Mapping):
            raise ValueError("Chat function tool call must contain a function object")
        result.append(
            ToolCallPart(
                call_id=required_string(
                    tool_call.get("id"), "Chat function tool calls must contain id"
                ),
                name=required_string(
                    function.get("name"),
                    "Chat function tool calls must contain function.name",
                ),
                arguments=required_string(
                    function.get("arguments"),
                    "Chat function tool calls must contain function.arguments",
                    allow_empty=True,
                ),
                origin=_ORIGIN,
            )
        )
    return result


def _chat_tools(value: Any) -> list[ToolDefinition]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("Chat tools must be an array")
    result: list[ToolDefinition] = []
    for tool in value:
        if not isinstance(tool, Mapping):
            raise ValueError("Chat tools must contain objects")
        if tool.get("type") != "function":
            raise ValueError("Unsupported Chat tool type")
        function = tool.get("function")
        if not isinstance(function, Mapping):
            raise ValueError("Chat function tools must contain a function object")
        parameters = function.get("parameters")
        result.append(
            ToolDefinition(
                name=required_string(
                    function.get("name"), "Chat function tools must contain name"
                ),
                description=_optional_string(function.get("description")) or "",
                parameters=dict(parameters)
                if isinstance(parameters, Mapping)
                else None,
                strict=function.get("strict")
                if isinstance(function.get("strict"), bool)
                else None,
            )
        )
    return result


def _chat_tool_choice(value: Any) -> ToolChoice | None:
    if value is None:
        return None
    if isinstance(value, str):
        if value not in {"auto", "none", "required"}:
            raise ValueError("Unsupported Chat tool_choice")
        return ToolChoice(mode=ToolChoiceMode(value))
    if not isinstance(value, Mapping) or value.get("type") != "function":
        raise ValueError("Unsupported Chat tool_choice")
    function = value.get("function")
    if not isinstance(function, Mapping):
        raise ValueError("Chat function tool_choice must contain a function object")
    return ToolChoice(
        mode=ToolChoiceMode.FUNCTION,
        name=required_string(
            function.get("name"), "Chat function tool_choice must contain name"
        ),
    )


def _chat_response_format(body: Mapping[str, Any]) -> ResponseFormat | None:
    response_format = body.get("response_format")
    if not isinstance(response_format, Mapping):
        return None
    format_type = response_format.get("type")
    if format_type in {"json_object", "text"}:
        return ResponseFormat(kind=format_type)
    if format_type != "json_schema":
        return None
    json_schema = response_format.get("json_schema")
    if not isinstance(json_schema, Mapping):
        raise ValueError("Chat json_schema response_format is invalid")
    schema = json_schema.get("schema")
    if not isinstance(schema, Mapping):
        raise ValueError("Chat json_schema response_format must contain schema")
    return ResponseFormat(
        kind="json_schema",
        name=required_string(
            json_schema.get("name"),
            "Chat json_schema response_format must contain name",
        ),
        schema=dict(schema),
        strict=json_schema.get("strict")
        if isinstance(json_schema.get("strict"), bool)
        else None,
    )


def _chat_reasoning_intent(body: Mapping[str, Any]) -> ReasoningIntent | None:
    effort = body.get("reasoning_effort")
    if not isinstance(effort, str) or not effort:
        return None
    if effort == "none":
        return ReasoningIntent(enabled=False, effort=effort)
    return ReasoningIntent(enabled=True, effort=effort)


def _message_to_chat(message: Message, *, request: UnifiedRequest) -> dict[str, Any]:
    if message.role == MessageRole.TOOL:
        results = [part for part in message.parts if isinstance(part, ToolResultPart)]
        first = results[0] if results else ToolResultPart(call_id="")
        return {
            "role": "tool",
            "tool_call_id": first.call_id,
            "content": first.content,
        }

    content_parts: list[ContentPart] = []
    tool_calls: list[dict[str, Any]] = []
    reasoning_text: list[str] = []
    for part in message.parts:
        if isinstance(part, ReasoningPart):
            if part.origin == _ORIGIN or request.replay_reasoning:
                reasoning_text.append(part.text)
        elif isinstance(part, ToolCallPart):
            tool_calls.append(
                {
                    "id": part.call_id,
                    "type": "function",
                    "function": {"name": part.name, "arguments": part.arguments},
                }
            )
        else:
            content_parts.append(part)

    content = _parts_to_chat_content(content_parts)
    result: dict[str, Any] = {"role": message.role.value, "content": content}
    if reasoning_text and any(reasoning_text):
        result["reasoning_content"] = "".join(reasoning_text)
    if tool_calls:
        result["tool_calls"] = tool_calls
    return result


def _parts_to_chat_content(parts: list[ContentPart]) -> Any:
    """Build Chat message content: a bare string, or text plus media parts."""
    text: list[str] = []
    media: list[dict[str, Any]] = []
    for part in parts:
        if isinstance(part, TextPart):
            text.append(part.text)
        elif isinstance(part, ImagePart):
            media.append(_image_to_chat(part))
        elif isinstance(part, FilePart):
            media.append(_file_to_chat(part))
    joined = "\n".join(text)
    if not media:
        return joined
    text_part = {"type": "text", "text": joined}
    return [*([text_part] if joined else []), *media]


def _image_to_chat(part: ImagePart) -> dict[str, Any]:
    if part.url:
        url = part.url
    elif part.data:
        url = f"data:{part.media_type};base64,{part.data}"
    else:
        raise ValueError("Unified image part must contain data or a URL")
    image_url: dict[str, Any] = {"url": url}
    if part.detail:
        image_url["detail"] = part.detail
    return {"type": "image_url", "image_url": image_url}


def _file_to_chat(part: FilePart) -> dict[str, Any]:
    file: dict[str, Any] = {}
    for key, value in (
        ("file_id", part.file_id),
        ("file_data", part.data),
        ("file_url", part.url),
        ("filename", part.filename),
    ):
        if value:
            file[key] = value
    if not any(key in file for key in ("file_id", "file_data", "file_url")):
        raise ValueError("Unified file part must contain data, a URL, or a file id")
    return {"type": "file", "file": file}


def _tool_to_chat(tool: ToolDefinition) -> dict[str, Any]:
    function: dict[str, Any] = {"name": tool.name}
    if tool.description:
        function["description"] = tool.description
    if tool.parameters is not None:
        function["parameters"] = tool.parameters
    if tool.strict is not None:
        function["strict"] = tool.strict
    return {"type": "function", "function": function}


def _tool_choice_to_chat(choice: ToolChoice) -> Any:
    if choice.mode == ToolChoiceMode.FUNCTION:
        return {"type": "function", "function": {"name": choice.name}}
    if choice.mode == ToolChoiceMode.REQUIRED:
        return "required"
    return choice.mode.value


def _response_format_to_chat(response_format: ResponseFormat) -> dict[str, Any]:
    if response_format.kind != "json_schema":
        return {"type": response_format.kind or "text"}
    json_schema: dict[str, Any] = {"name": response_format.name or "response"}
    if response_format.schema is not None:
        json_schema["schema"] = response_format.schema
    if response_format.strict is not None:
        json_schema["strict"] = response_format.strict
    return {"type": "json_schema", "json_schema": json_schema}


def _stream_includes_usage(value: Any) -> bool:
    if not isinstance(value, Mapping):
        return False
    return value.get("include_usage") is True


def _chat_message_parts(message: Mapping[str, Any]) -> list[ContentPart]:
    parts: list[ContentPart] = []
    content = message.get("content")
    if isinstance(content, str) and content:
        parts.append(TextPart(text=content))
    elif isinstance(content, list):
        parts.extend(_chat_content_parts(content))
    reasoning = message.get("reasoning_content") or message.get("reasoning")
    if isinstance(reasoning, str) and reasoning:
        parts.append(ReasoningPart(text=reasoning, origin=_ORIGIN))
    raw_tool_calls = message.get("tool_calls")
    if isinstance(raw_tool_calls, list):
        parts.extend(_chat_tool_calls(raw_tool_calls))
    return parts


def _chat_finish_reason(value: Any) -> FinishReason:
    return {
        "stop": FinishReason.END_TURN,
        "length": FinishReason.MAX_TOKENS,
        "tool_calls": FinishReason.TOOL_USE,
        "function_call": FinishReason.TOOL_USE,
        "content_filter": FinishReason.CONTENT_FILTER,
    }.get(value, FinishReason.END_TURN)


def _chat_finish_reason_wire(reason: FinishReason) -> str:
    return {
        FinishReason.END_TURN: "stop",
        FinishReason.MAX_TOKENS: "length",
        FinishReason.TOOL_USE: "tool_calls",
        FinishReason.CONTENT_FILTER: "content_filter",
        FinishReason.STOP_SEQUENCE: "stop",
        FinishReason.OTHER: "stop",
    }[reason]


def _chat_usage(value: Any) -> Usage:
    if not isinstance(value, Mapping):
        return Usage()
    return _chat_payload_usage(value)


def _chat_usage_wire(usage: Usage) -> dict[str, Any]:
    result: dict[str, Any] = {
        "prompt_tokens": usage.input_tokens,
        "completion_tokens": usage.output_tokens,
        "total_tokens": usage.input_tokens + usage.output_tokens,
    }
    if usage.cached_input_tokens or usage.cache_creation_input_tokens:
        result["prompt_tokens_details"] = {
            "cached_tokens": usage.cached_input_tokens,
            "cache_write_tokens": usage.cache_creation_input_tokens,
        }
    if usage.reasoning_tokens:
        result["completion_tokens_details"] = {
            "reasoning_tokens": usage.reasoning_tokens
        }
    return result


def _usage_int(usage: Mapping[str, Any], key: str) -> int:
    value = usage.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _chat_payload_usage(value: Mapping[str, Any]) -> Usage:
    details = value.get("prompt_tokens_details")
    cached = details.get("cached_tokens") if isinstance(details, Mapping) else 0
    completion_details = value.get("completion_tokens_details")
    reasoning = (
        completion_details.get("reasoning_tokens")
        if isinstance(completion_details, Mapping)
        else 0
    )
    return Usage(
        input_tokens=_usage_int(value, "prompt_tokens"),
        output_tokens=_usage_int(value, "completion_tokens"),
        cached_input_tokens=cached if isinstance(cached, int) else 0,
        reasoning_tokens=reasoning if isinstance(reasoning, int) else 0,
    )


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _optional_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _optional_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None

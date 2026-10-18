"""Gemini generateContent spoke: wire payloads <-> unified request.

Gemini has no pairwise converter today, so this module covers both
directions: parsing a Gemini client request and building a Gemini upstream
request from the unified request. ``thoughtSignature`` state is carried
through the IR as opaque data and replayed only for Gemini-origin calls, with
Google's documented sentinel used when a replayed call has no signature of its
own (Gemini 3 rejects the request otherwise).
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Mapping
from typing import Any

from ...models.protocols import ProtocolKind
from .unified import (
    ContentPart,
    FilePart,
    GenerationConfig,
    ImagePart,
    Message,
    MessageRole,
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
from .unified_stream import BlockKind
from .validation import required_string

_ORIGIN = ProtocolKind.GEMINI
DUMMY_THOUGHT_SIGNATURE = "skip_thought_signature_validator"
_THOUGHT_SIGNATURE_MODELS = ("gemini-3", "gemini-4", "gemini-5")

_GEMINI_FINISH = {
    "STOP": FinishReason.END_TURN,
    "MAX_TOKENS": FinishReason.MAX_TOKENS,
    "SAFETY": FinishReason.CONTENT_FILTER,
    "RECITATION": FinishReason.CONTENT_FILTER,
    "BLOCKLIST": FinishReason.CONTENT_FILTER,
    "PROHIBITED_CONTENT": FinishReason.CONTENT_FILTER,
    "SPII": FinishReason.CONTENT_FILTER,
    "MALFORMED_FUNCTION_CALL": FinishReason.TOOL_USE,
    "IMAGE_SAFETY": FinishReason.CONTENT_FILTER,
    "LANGUAGE": FinishReason.END_TURN,
}

_FINISH_TO_GEMINI = {
    FinishReason.END_TURN: "STOP",
    FinishReason.MAX_TOKENS: "MAX_TOKENS",
    FinishReason.TOOL_USE: "STOP",
    FinishReason.CONTENT_FILTER: "SAFETY",
    FinishReason.STOP_SEQUENCE: "STOP",
    FinishReason.OTHER: "STOP",
}


def parse_gemini_request(body: Mapping[str, Any]) -> UnifiedRequest:
    """Parse a Gemini generateContent request body into the unified request."""
    request = UnifiedRequest(model=_text(body.get("model")))
    request.stream = body.get("stream") is True
    request.generation = _gemini_generation_config(body.get("generationConfig"))

    system_instruction = body.get("systemInstruction")
    if isinstance(system_instruction, Mapping):
        request.system = _gemini_parts_to_unified(
            system_instruction.get("parts"), role=MessageRole.USER
        )
    elif isinstance(system_instruction, str):
        request.system = [TextPart(text=system_instruction)]

    contents = body.get("contents")
    if contents is not None:
        if not isinstance(contents, list):
            raise ValueError("Gemini contents must be an array")
        request.messages = _gemini_contents_to_messages(contents)

    tools = body.get("tools")
    if isinstance(tools, list):
        request.tools = _gemini_tools(tools)
    tool_config = body.get("toolConfig")
    if isinstance(tool_config, Mapping):
        request.tool_choice = _gemini_tool_choice(tool_config)
    return request


def build_gemini_request(request: UnifiedRequest) -> dict[str, Any]:
    """Build a Gemini generateContent request body from the unified request."""
    contents: list[dict[str, Any]] = []
    results_by_name = _tool_result_names(request.messages)
    for message in request.messages:
        contents.append(_message_to_gemini(message, results_by_name=results_by_name))

    body: dict[str, Any] = {"contents": contents or [{"role": "user", "parts": []}]}
    if request.system:
        body["systemInstruction"] = {
            "parts": _unified_parts_to_gemini(request.system, role=MessageRole.USER)
        }
    generation = _generation_to_gemini(request.generation)
    if generation:
        body["generationConfig"] = generation
    if request.tools:
        declarations = [_tool_to_gemini(tool) for tool in request.tools]
        if declarations:
            body["tools"] = [{"functionDeclarations": declarations}]
    if request.tool_choice is not None:
        tool_config = _tool_choice_to_gemini(request.tool_choice)
        if tool_config:
            body["toolConfig"] = tool_config
    if request.response_format is not None:
        _apply_response_format(body, request.response_format)
    return body


def parse_gemini_response(body: Mapping[str, Any]) -> UnifiedResponse:
    """Parse a Gemini generateContent response body into the unified response."""
    candidates = body.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("Gemini response must contain candidates")
    candidate = candidates[0]
    if not isinstance(candidate, Mapping):
        raise ValueError("Gemini candidates must contain objects")
    content = candidate.get("content")
    parts: list[ContentPart] = []
    if isinstance(content, Mapping):
        parts = _gemini_parts_to_unified(
            content.get("parts"), role=MessageRole.ASSISTANT
        )
    usage_metadata = body.get("usageMetadata")
    return UnifiedResponse(
        id=_text(body.get("responseId")) or f"gemini_{uuid.uuid4().hex[:24]}",
        model=_text(body.get("modelVersion")),
        parts=parts,
        finish=_gemini_finish_reason(candidate.get("finishReason")),
        usage=_gemini_usage(
            usage_metadata if isinstance(usage_metadata, Mapping) else {}
        ),
    )


def build_gemini_response(response: UnifiedResponse) -> dict[str, Any]:
    """Build a Gemini generateContent response body from the unified response."""
    parts = _unified_parts_to_gemini(
        response.parts, role=MessageRole.ASSISTANT, model=""
    )
    body: dict[str, Any] = {
        "candidates": [
            {
                "content": {"role": "model", "parts": parts},
                "finishReason": _FINISH_TO_GEMINI[response.finish],
                "index": 0,
            }
        ]
    }
    if response.model:
        body["modelVersion"] = response.model
    if response.id:
        body["responseId"] = response.id
    usage = response.usage
    if usage.input_tokens or usage.output_tokens:
        body["usageMetadata"] = _gemini_usage_wire(usage)
    return body


def _gemini_contents_to_messages(contents: list[Any]) -> list[Message]:
    messages: list[Message] = []
    for content in contents:
        if not isinstance(content, Mapping):
            raise ValueError("Gemini contents must contain objects")
        role = content.get("role", "user")
        if role == "model":
            message_role = MessageRole.ASSISTANT
        elif role in {"user", "system", "tool"}:
            message_role = MessageRole.USER
        else:
            raise ValueError(f"Unsupported Gemini content role: {role}")
        messages.append(
            Message(
                role=message_role,
                parts=_gemini_parts_to_unified(content.get("parts"), role=message_role),
            )
        )
    return messages


def _gemini_parts_to_unified(value: Any, *, role: MessageRole) -> list[ContentPart]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("Gemini parts must be an array")
    parts: list[ContentPart] = []
    for part in value:
        if not isinstance(part, Mapping):
            raise ValueError("Gemini parts must contain objects")
        parts.extend(_gemini_part_to_unified(part, role=role))
    return parts


def _gemini_part_to_unified(
    part: Mapping[str, Any], *, role: MessageRole
) -> list[ContentPart]:
    signature = _text(part.get("thoughtSignature"))
    if "functionCall" in part:
        call = part.get("functionCall")
        if not isinstance(call, Mapping):
            raise ValueError("Gemini functionCall must be an object")
        arguments = call.get("args")
        return [
            ToolCallPart(
                call_id=_text(call.get("id")) or f"call_{uuid.uuid4().hex[:24]}",
                name=required_string(
                    call.get("name"), "Gemini functionCall must contain name"
                ),
                arguments=json.dumps(
                    dict(arguments) if isinstance(arguments, Mapping) else {},
                    ensure_ascii=False,
                ),
                origin=_ORIGIN,
                opaque=signature,
            )
        ]
    if "functionResponse" in part:
        response = part.get("functionResponse")
        if not isinstance(response, Mapping):
            raise ValueError("Gemini functionResponse must be an object")
        payload = response.get("response")
        return [
            ToolResultPart(
                call_id=_text(response.get("id")) or _text(response.get("name")),
                content=json.dumps(
                    payload if isinstance(payload, Mapping) else {}, ensure_ascii=False
                ),
            )
        ]
    if "inlineData" in part or "fileData" in part:
        return [_gemini_media_to_unified(part)]
    text = part.get("text")
    if isinstance(text, str):
        if part.get("thought") is True:
            return [ReasoningPart(text=text, opaque=signature, origin=_ORIGIN)]
        if not text and signature:
            return [ReasoningPart(opaque=signature, origin=_ORIGIN)]
        return [TextPart(text=text)]
    return []


def _gemini_media_to_unified(part: Mapping[str, Any]) -> ContentPart:
    inline = part.get("inlineData")
    if isinstance(inline, Mapping):
        media_type = _text(inline.get("mimeType"))
        data = _text(inline.get("data"))
        if media_type.startswith("image/"):
            return ImagePart(media_type=media_type, data=data)
        return FilePart(media_type=media_type, data=data)
    file_data = part.get("fileData")
    if isinstance(file_data, Mapping):
        media_type = _text(file_data.get("mimeType"))
        url = _text(file_data.get("fileUri"))
        if media_type.startswith("image/"):
            return ImagePart(media_type=media_type, url=url)
        return FilePart(media_type=media_type, url=url)
    raise ValueError("Gemini media parts must contain inlineData or fileData")


def _tool_result_names(messages: list[Message]) -> dict[str, str]:
    names: dict[str, str] = {}
    for message in messages:
        for part in message.parts:
            if isinstance(part, ToolCallPart) and part.call_id:
                names[part.call_id] = part.name
    return names


def _message_to_gemini(
    message: Message, *, results_by_name: Mapping[str, str]
) -> dict[str, Any]:
    role = "model" if message.role == MessageRole.ASSISTANT else "user"
    return {
        "role": role,
        "parts": _unified_parts_to_gemini(
            message.parts, role=message.role, results_by_name=results_by_name
        ),
    }


def _unified_parts_to_gemini(
    parts: list[ContentPart],
    *,
    role: MessageRole,
    model: str = "",
    results_by_name: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Build Gemini parts, keeping calls and results in Gemini's required order."""
    text_parts: list[str] = []
    media: list[dict[str, Any]] = []
    calls: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    pending_signature = ""

    for part in parts:
        if isinstance(part, TextPart):
            text_parts.append(part.text)
        elif isinstance(part, ImagePart):
            media.append(_image_to_gemini(part))
        elif isinstance(part, FilePart):
            media.append(_file_to_gemini(part))
        elif isinstance(part, ReasoningPart):
            if part.origin == _ORIGIN:
                if part.text:
                    block: dict[str, Any] = {"thought": True, "text": part.text}
                    if part.opaque:
                        block["thoughtSignature"] = part.opaque
                    media.append(block)
                elif part.opaque:
                    pending_signature = part.opaque
        elif isinstance(part, ToolCallPart):
            calls.append(
                _tool_call_to_gemini(part, model=model, pending=pending_signature)
            )
            pending_signature = ""
        elif isinstance(part, ToolResultPart):
            results.append(
                _tool_result_to_gemini(part, results_by_name=results_by_name or {})
            )

    built: list[dict[str, Any]] = []
    text = "".join(text_parts)
    if text:
        built.append({"text": text})
    built.extend(media)
    built.extend(calls)
    built.extend(results)
    return built


def _image_to_gemini(part: ImagePart) -> dict[str, Any]:
    if part.data:
        return {
            "inlineData": {
                "mimeType": part.media_type or "image/png",
                "data": part.data,
            }
        }
    if part.url:
        return {
            "fileData": {
                "mimeType": part.media_type or "image/png",
                "fileUri": part.url,
            }
        }
    raise ValueError("Unified image part must contain data or a URL")


def _file_to_gemini(part: FilePart) -> dict[str, Any]:
    if part.data:
        return {
            "inlineData": {
                "mimeType": part.media_type or "application/pdf",
                "data": part.data,
            }
        }
    if part.url:
        return {
            "fileData": {
                "mimeType": part.media_type or "application/pdf",
                "fileUri": part.url,
            }
        }
    raise ValueError("Unified file part must contain data or a URL")


def _tool_call_to_gemini(
    part: ToolCallPart, *, model: str, pending: str
) -> dict[str, Any]:
    arguments = part.arguments or "{}"
    try:
        parsed = json.loads(arguments)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid tool call arguments JSON") from exc
    call: dict[str, Any] = {
        "functionCall": {
            "name": part.name,
            "args": dict(parsed) if isinstance(parsed, Mapping) else {},
        }
    }
    signature = part.opaque
    if not signature and part.origin == _ORIGIN:
        signature = pending
    if not signature and _requires_thought_signature(model):
        signature = DUMMY_THOUGHT_SIGNATURE
    if signature:
        call["thoughtSignature"] = signature
    return call


def _tool_result_to_gemini(
    part: ToolResultPart, *, results_by_name: Mapping[str, str]
) -> dict[str, Any]:
    content = part.content or "{}"
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        parsed = {"result": content}
    response: dict[str, Any] = {
        "name": results_by_name.get(part.call_id) or part.call_id or "function",
        "response": parsed if isinstance(parsed, Mapping) else {"result": parsed},
    }
    if part.call_id:
        response["id"] = part.call_id
    return {"functionResponse": response}


def _generation_to_gemini(config: GenerationConfig) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if config.max_output_tokens is not None:
        result["maxOutputTokens"] = config.max_output_tokens
    if config.temperature is not None:
        result["temperature"] = config.temperature
    if config.top_p is not None:
        result["topP"] = config.top_p
    if config.top_k is not None:
        result["topK"] = config.top_k
    if config.stop:
        result["stopSequences"] = list(config.stop)
    if config.seed is not None:
        result["seed"] = config.seed
    if config.presence_penalty is not None:
        result["presencePenalty"] = config.presence_penalty
    if config.frequency_penalty is not None:
        result["frequencyPenalty"] = config.frequency_penalty
    return result


def _gemini_generation_config(value: Any) -> GenerationConfig:
    config = GenerationConfig()
    if not isinstance(value, Mapping):
        return config
    config.max_output_tokens = _optional_int(value.get("maxOutputTokens"))
    config.temperature = _optional_float(value.get("temperature"))
    config.top_p = _optional_float(value.get("topP"))
    config.top_k = _optional_int(value.get("topK"))
    config.seed = _optional_int(value.get("seed"))
    config.presence_penalty = _optional_float(value.get("presencePenalty"))
    config.frequency_penalty = _optional_float(value.get("frequencyPenalty"))
    stop = value.get("stopSequences")
    if isinstance(stop, list):
        config.stop = tuple(item for item in stop if isinstance(item, str))
    return config


def _apply_response_format(
    body: dict[str, Any], response_format: ResponseFormat
) -> None:
    generation = body.setdefault("generationConfig", {})
    if response_format.kind == "json_schema" and response_format.schema is not None:
        generation["responseMimeType"] = "application/json"
        generation["responseSchema"] = response_format.schema
    elif response_format.kind == "json_object":
        generation["responseMimeType"] = "application/json"


def _tool_to_gemini(tool: ToolDefinition) -> dict[str, Any]:
    declaration: dict[str, Any] = {"name": tool.name}
    if tool.description:
        declaration["description"] = tool.description
    if tool.parameters is not None:
        declaration["parameters"] = tool.parameters
    return declaration


def _gemini_tools(value: list[Any]) -> list[ToolDefinition]:
    result: list[ToolDefinition] = []
    for tool in value:
        if not isinstance(tool, Mapping):
            raise ValueError("Gemini tools must contain objects")
        declarations = tool.get("functionDeclarations")
        if not isinstance(declarations, list):
            continue
        for declaration in declarations:
            if not isinstance(declaration, Mapping):
                raise ValueError("Gemini functionDeclarations must contain objects")
            parameters = declaration.get("parameters") or declaration.get(
                "parametersJsonSchema"
            )
            result.append(
                ToolDefinition(
                    name=required_string(
                        declaration.get("name"),
                        "Gemini functionDeclarations must contain name",
                    ),
                    description=_text(declaration.get("description")),
                    parameters=dict(parameters)
                    if isinstance(parameters, Mapping)
                    else None,
                )
            )
    return result


def _tool_choice_to_gemini(choice: ToolChoice) -> dict[str, Any] | None:
    config: dict[str, Any] = {}
    if choice.mode == ToolChoiceMode.NONE:
        config["mode"] = "NONE"
    elif choice.mode == ToolChoiceMode.REQUIRED:
        config["mode"] = "ANY"
    elif choice.mode == ToolChoiceMode.FUNCTION:
        config["mode"] = "ANY"
        config["allowedFunctionNames"] = [choice.name]
    elif choice.allowed_names:
        config["mode"] = "ANY"
        config["allowedFunctionNames"] = list(choice.allowed_names)
    else:
        return None
    return {"functionCallingConfig": config}


def _gemini_tool_choice(tool_config: Mapping[str, Any]) -> ToolChoice | None:
    config = tool_config.get("functionCallingConfig")
    if not isinstance(config, Mapping):
        return None
    mode = _text(config.get("mode")).upper()
    allowed = config.get("allowedFunctionNames")
    names = (
        tuple(item for item in allowed if isinstance(item, str))
        if isinstance(allowed, list)
        else ()
    )
    if mode == "NONE":
        return ToolChoice(mode=ToolChoiceMode.NONE)
    if mode == "ANY":
        if names:
            return ToolChoice(
                mode=ToolChoiceMode.FUNCTION, name=names[0], allowed_names=names
            )
        return ToolChoice(mode=ToolChoiceMode.REQUIRED)
    return ToolChoice(mode=ToolChoiceMode.AUTO)


def _gemini_finish_reason(value: Any) -> FinishReason:
    return _GEMINI_FINISH.get(_text(value).upper(), FinishReason.END_TURN)


def _gemini_usage(value: Mapping[str, Any]) -> Usage:
    prompt = _optional_int(value.get("promptTokenCount")) or 0
    cached = _optional_int(value.get("cachedContentTokenCount")) or 0
    return Usage(
        # promptTokenCount already includes the cached portion.
        input_tokens=max(prompt - cached, 0),
        output_tokens=_optional_int(value.get("candidatesTokenCount")) or 0,
        cached_input_tokens=cached,
        reasoning_tokens=_optional_int(value.get("thoughtsTokenCount")) or 0,
    )


def _gemini_usage_wire(usage: Usage) -> dict[str, Any]:
    return {
        "promptTokenCount": usage.input_tokens + usage.cached_input_tokens,
        "candidatesTokenCount": usage.output_tokens,
        "cachedContentTokenCount": usage.cached_input_tokens,
        "thoughtsTokenCount": usage.reasoning_tokens,
        "totalTokenCount": (
            usage.input_tokens
            + usage.cached_input_tokens
            + usage.output_tokens
            + usage.reasoning_tokens
        ),
    }


def _requires_thought_signature(model: str) -> bool:
    name = _text(model).casefold()
    return any(family in name for family in _THOUGHT_SIGNATURE_MODELS)


def _block_kinds() -> Any:
    return BlockKind


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


async def parse_gemini_stream(
    raw_iterator: AsyncIterator[bytes],
) -> AsyncIterator[Any]:
    """Parse a Gemini SSE stream into unified stream events."""
    from .sse import parse_sse_json_stream
    from .unified_stream import (
        BlockStart,
        ReasoningDelta,
        SignatureDelta,
        StreamFinish,
        StreamStart,
        TextDelta,
        ToolCallArgsDelta,
    )

    started = False
    text_index = 0
    reasoning_index = 1
    next_index = 2
    saw_text = False
    saw_reasoning = False
    finish = FinishReason.END_TURN
    usage = Usage()
    async for payload in parse_sse_json_stream(raw_iterator):
        candidates = payload.get("candidates")
        if isinstance(candidates, list) and candidates:
            candidate = candidates[0]
            if isinstance(candidate, Mapping):
                if candidate.get("finishReason"):
                    finish = _gemini_finish_reason(candidate.get("finishReason"))
                content = candidate.get("content")
                if isinstance(content, Mapping):
                    for part in _gemini_parts_to_unified(
                        content.get("parts"), role=MessageRole.ASSISTANT
                    ):
                        if isinstance(part, TextPart) and part.text:
                            if not started:
                                started = True
                                yield StreamStart(id=_text(payload.get("responseId")))
                            if not saw_text:
                                saw_text = True
                                yield BlockStart(index=text_index, kind=BlockKind.TEXT)
                            yield TextDelta(index=text_index, text=part.text)
                        elif isinstance(part, ReasoningPart):
                            if not started:
                                started = True
                                yield StreamStart(id=_text(payload.get("responseId")))
                            if part.text:
                                if not saw_reasoning:
                                    saw_reasoning = True
                                    yield BlockStart(
                                        index=reasoning_index, kind=BlockKind.REASONING
                                    )
                                yield ReasoningDelta(
                                    index=reasoning_index, text=part.text
                                )
                            if part.opaque:
                                yield SignatureDelta(
                                    index=reasoning_index, opaque=part.opaque
                                )
                        elif isinstance(part, ToolCallPart):
                            if not started:
                                started = True
                                yield StreamStart(id=_text(payload.get("responseId")))
                            index = next_index
                            next_index += 1
                            yield BlockStart(
                                index=index,
                                kind=BlockKind.TOOL_CALL,
                                call_id=part.call_id,
                                name=part.name,
                            )
                            yield ToolCallArgsDelta(
                                index=index, arguments=part.arguments
                            )
        usage_metadata = payload.get("usageMetadata")
        if isinstance(usage_metadata, Mapping):
            usage = _gemini_usage(usage_metadata)
    if not started:
        raise ValueError("Gemini stream ended before any candidate content")
    yield StreamFinish(reason=finish, usage=usage)


async def serialize_gemini_stream(
    events: AsyncIterator[Any], original_model: str
) -> AsyncIterator[bytes]:
    """Serialize unified stream events into a Gemini SSE stream."""
    from .sse import format_sse_event
    from .unified_stream import (
        BlockStart,
        ReasoningDelta,
        SignatureDelta,
        StreamFinish,
        TextDelta,
        ToolCallArgsDelta,
    )

    kind_by_index: dict[int, BlockKind] = {}
    calls: dict[int, tuple[str, str]] = {}
    buffers: dict[int, dict[str, Any]] = {}
    order: list[dict[str, Any]] = []
    signatures: dict[int, str] = {}
    message_id = f"gemini_{uuid.uuid4().hex[:24]}"

    def emit(parts: list[dict[str, Any]], finish_reason: str | None = None) -> bytes:
        payload: dict[str, Any] = {
            "candidates": [
                {
                    "content": {"role": "model", "parts": parts},
                    "index": 0,
                }
            ],
            "modelVersion": original_model,
            "responseId": message_id,
        }
        if finish_reason:
            payload["candidates"][0]["finishReason"] = finish_reason
        return format_sse_event(None, payload)

    async for event in events:
        if isinstance(event, BlockStart):
            kind_by_index[event.index] = event.kind
            if event.kind == BlockKind.TOOL_CALL:
                calls[event.index] = (event.call_id, event.name)
                order.append({"kind": BlockKind.TOOL_CALL, "index": event.index})
            continue
        if isinstance(event, TextDelta):
            buffers.setdefault(event.index, {"text": ""})
            buffers[event.index]["text"] += event.text
            yield emit([{"text": event.text}])
            continue
        if isinstance(event, ReasoningDelta):
            buffers.setdefault(event.index, {"text": ""})
            buffers[event.index]["text"] += event.text
            yield emit([{"thought": True, "text": event.text}])
            continue
        if isinstance(event, SignatureDelta):
            signatures[event.index] = event.opaque
            continue
        if isinstance(event, ToolCallArgsDelta):
            call_id, name = calls.get(event.index, ("", ""))
            payload = _tool_call_to_gemini(
                ToolCallPart(
                    call_id=call_id,
                    name=name,
                    arguments=event.arguments,
                    origin=_ORIGIN,
                    opaque=signatures.get(event.index, ""),
                ),
                model=original_model,
                pending="",
            )
            yield emit([payload])
            continue
        if isinstance(event, StreamFinish):
            yield emit([], finish_reason=_FINISH_TO_GEMINI[event.reason])
            return

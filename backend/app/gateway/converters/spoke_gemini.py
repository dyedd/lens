"""Gemini generateContent 请求、响应和流式事件与统一协议之间的转换。"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Mapping
from typing import Any

from ...models.protocols import ProtocolKind
from . import capabilities, repair
from .sse import format_sse_event, parse_sse_json_stream
from .unified import (
    AudioPart,
    ContentPart,
    FilePart,
    GenerationConfig,
    ImagePart,
    Message,
    MessageRole,
    ReasoningIntent,
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
from .unified_response import FinishReason, ResponseStatus, UnifiedResponse, Usage
from .unified_stream import (
    BlockKind,
    BlockStart,
    BlockStop,
    ReasoningDelta,
    RefusalDelta,
    SignatureDelta,
    StreamError,
    StreamFinish,
    StreamStart,
    TextDelta,
    ToolCallArgsDelta,
)
from .validation import required_string

_ORIGIN = ProtocolKind.GEMINI
DUMMY_THOUGHT_SIGNATURE = "skip_thought_signature_validator"

_GEMINI_FINISH = {
    "STOP": FinishReason.END_TURN,
    "MAX_TOKENS": FinishReason.MAX_TOKENS,
    "SAFETY": FinishReason.CONTENT_FILTER,
    "RECITATION": FinishReason.CONTENT_FILTER,
    "BLOCKLIST": FinishReason.CONTENT_FILTER,
    "PROHIBITED_CONTENT": FinishReason.CONTENT_FILTER,
    "SPII": FinishReason.CONTENT_FILTER,
    "MALFORMED_FUNCTION_CALL": FinishReason.OTHER,
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
    request = UnifiedRequest(model=_text(body.get("model")), origin=_ORIGIN)
    request.stream = body.get("stream") is True
    generation = body.get("generationConfig")
    request.generation = _gemini_generation_config(generation)
    if isinstance(generation, Mapping):
        thinking = generation.get("thinkingConfig")
        if isinstance(thinking, Mapping):
            budget = _optional_int(thinking.get("thinkingBudget"))
            request.reasoning = ReasoningIntent(
                enabled=budget != 0,
                effort=_text(thinking.get("thinkingLevel")).lower() or None,
                budget_tokens=budget,
                summarized=thinking.get("includeThoughts") is True,
            )
        if generation.get("responseMimeType") == "application/json":
            schema = generation.get("responseJsonSchema") or generation.get(
                "responseSchema"
            )
            request.response_format = ResponseFormat(
                kind="json_schema" if isinstance(schema, Mapping) else "json_object",
                schema=dict(schema) if isinstance(schema, Mapping) else None,
            )
    system = body.get("systemInstruction")
    if isinstance(system, Mapping):
        request.system = _gemini_parts_to_unified(
            system.get("parts"), role=MessageRole.USER
        )
    contents = body.get("contents")
    if not isinstance(contents, list):
        raise ValueError("Gemini contents must be an array")
    request.messages = _gemini_contents_to_messages(contents)
    tools = body.get("tools")
    if isinstance(tools, list):
        request.tools = _gemini_tools(tools)
        for tool in tools:
            for name in (
                "googleSearch",
                "googleSearchRetrieval",
                "codeExecution",
                "urlContext",
                "googleMaps",
                "fileSearch",
            ):
                options = tool.get(name)
                if isinstance(options, Mapping):
                    kind = (
                        ServerToolKind.WEB_SEARCH
                        if name.startswith("googleSearch")
                        else ServerToolKind.CODE_INTERPRETER
                        if name == "codeExecution"
                        else ServerToolKind.OTHER
                    )
                    request.server_tools.append(
                        ServerToolDefinition(
                            kind=kind, name=name, options=dict(options)
                        )
                    )
    config = body.get("toolConfig")
    if isinstance(config, Mapping):
        request.tool_choice = _gemini_tool_choice(config)
    return request


def build_gemini_request(request: UnifiedRequest) -> dict[str, Any]:
    messages = repair.repair_history(list(request.messages))
    names = _tool_result_names(messages)
    contents: list[dict[str, Any]] = []
    for message in messages:
        parts = _unified_parts_to_gemini(
            message.parts, role=message.role, results_by_name=names
        )
        if not parts:
            if message.role == MessageRole.USER and message.parts:
                raise capabilities.UnsupportedContentError(
                    "Content cannot be sent to Gemini"
                )
            continue
        role = "model" if message.role == MessageRole.ASSISTANT else "user"
        if contents and contents[-1]["role"] == role:
            contents[-1]["parts"].extend(parts)
        else:
            contents.append({"role": role, "parts": parts})
    body: dict[str, Any] = {"contents": contents}
    if request.system:
        body["systemInstruction"] = {
            "parts": _unified_parts_to_gemini(request.system, role=MessageRole.USER)
        }
    generation = _generation_to_gemini(request.generation)
    if request.reasoning is not None:
        generation["thinkingConfig"] = gemini_thinking_config(
            request.reasoning, request.model
        )
    if generation:
        body["generationConfig"] = generation
    tools: list[dict[str, Any]] = []
    if request.tools:
        tools.append(
            {"functionDeclarations": [_tool_to_gemini(tool) for tool in request.tools]}
        )
    for tool in request.server_tools:
        name = {
            ServerToolKind.WEB_SEARCH: "googleSearch",
            ServerToolKind.CODE_INTERPRETER: "codeExecution",
        }.get(tool.kind, tool.name)
        if name in {
            "googleSearch",
            "googleSearchRetrieval",
            "codeExecution",
            "urlContext",
            "googleMaps",
            "fileSearch",
        }:
            tools.append({name: dict(tool.options) if tool.name == name else {}})
    if tools:
        body["tools"] = tools
    if request.tool_choice is not None and request.tools:
        body["toolConfig"] = _tool_choice_to_gemini(request.tool_choice)
    if request.response_format is not None:
        _apply_response_format(body, request.response_format)
    return body


def parse_gemini_response(body: Mapping[str, Any]) -> UnifiedResponse:
    candidates = body.get("candidates")
    feedback = body.get("promptFeedback")
    usage = body.get("usageMetadata")
    if not candidates and isinstance(feedback, Mapping) and feedback.get("blockReason"):
        return UnifiedResponse(
            model=_text(body.get("modelVersion")),
            parts=[
                Refusal(
                    text=_text(feedback.get("blockReasonMessage"))
                    or _text(feedback.get("blockReason"))
                )
            ],
            finish=FinishReason.CONTENT_FILTER,
            status=ResponseStatus.INCOMPLETE,
            incomplete_reason="content_filter",
            usage=_gemini_usage(usage if isinstance(usage, Mapping) else {}),
        )
    if (
        not isinstance(candidates, list)
        or not candidates
        or not isinstance(candidates[0], Mapping)
    ):
        raise ValueError("Gemini response must contain candidates")
    candidate = candidates[0]
    content = candidate.get("content")
    parts = (
        _gemini_parts_to_unified(content.get("parts"), role=MessageRole.ASSISTANT)
        if isinstance(content, Mapping)
        else []
    )
    finish = _gemini_finish_reason(candidate.get("finishReason"))
    if finish == FinishReason.END_TURN and any(
        isinstance(part, ToolCallPart) for part in parts
    ):
        finish = FinishReason.TOOL_USE
    return UnifiedResponse(
        id=_text(body.get("responseId")) or f"gemini_{uuid.uuid4().hex[:24]}",
        model=_text(body.get("modelVersion")),
        parts=parts,
        finish=finish,
        usage=_gemini_usage(usage if isinstance(usage, Mapping) else {}),
        status=ResponseStatus.INCOMPLETE
        if finish in {FinishReason.MAX_TOKENS, FinishReason.CONTENT_FILTER}
        else ResponseStatus.COMPLETED,
        incomplete_reason="max_output_tokens"
        if finish == FinishReason.MAX_TOKENS
        else "content_filter"
        if finish == FinishReason.CONTENT_FILTER
        else "",
    )


def build_gemini_response(response: UnifiedResponse) -> dict[str, Any]:
    parts = _unified_parts_to_gemini(
        response.parts,
        role=MessageRole.ASSISTANT,
        include_reasoning=True,
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
    pending: dict[str, list[str]] = {}
    for content in contents:
        if not isinstance(content, Mapping):
            raise ValueError("Gemini contents must contain objects")
        role = content.get("role", "user")
        if role not in {"model", "user"}:
            raise ValueError(f"Unsupported Gemini content role: {role}")
        message_role = MessageRole.ASSISTANT if role == "model" else MessageRole.USER
        parts: list[ContentPart] = []
        wire_parts = content.get("parts")
        if not isinstance(wire_parts, list):
            raise ValueError("Gemini parts must be an array")
        for wire_part in wire_parts:
            if not isinstance(wire_part, Mapping):
                raise ValueError("Gemini parts must contain objects")
            parsed = _gemini_part_to_unified(wire_part, role=message_role)
            for part in parsed:
                if isinstance(part, ToolCallPart):
                    pending.setdefault(part.name, []).append(part.call_id)
                elif isinstance(part, ToolResultPart):
                    response = wire_part["functionResponse"]
                    calls = pending.get(_text(response.get("name")), [])
                    if not response.get("id") and calls:
                        part.call_id = calls.pop(0)
                    elif part.call_id in calls:
                        calls.remove(part.call_id)
            parts.extend(parsed)
        if message_role == MessageRole.USER:
            for part in parts:
                if isinstance(part, ToolResultPart):
                    messages.append(Message(role=MessageRole.TOOL, parts=[part]))
            parts = [part for part in parts if not isinstance(part, ToolResultPart)]
        if parts:
            messages.append(Message(role=message_role, parts=parts))
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
        if arguments is not None and not isinstance(arguments, Mapping):
            raise ValueError("Gemini functionCall args must be an object")
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
                is_error=isinstance(payload, Mapping) and "error" in payload,
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
        return (
            [ReasoningPart(opaque=signature, origin=_ORIGIN)] if signature else []
        ) + [TextPart(text=text)]
    if signature:
        return [ReasoningPart(opaque=signature, origin=_ORIGIN)]
    for field in ("executableCode", "codeExecutionResult"):
        value = part.get(field)
        if isinstance(value, Mapping):
            text = _text(value.get("code") or value.get("output"))
            return [
                ServerToolPart(
                    kind=ServerToolKind.CODE_INTERPRETER,
                    name="code_execution",
                    origin=_ORIGIN,
                    raw=dict(part),
                    output=[TextPart(text=text)],
                )
            ]
    return []


def _gemini_media_to_unified(part: Mapping[str, Any]) -> ContentPart:
    inline = part.get("inlineData")
    if isinstance(inline, Mapping):
        media_type = _text(inline.get("mimeType"))
        data = _text(inline.get("data"))
        if media_type.startswith("image/"):
            return ImagePart(media_type=media_type, data=data)
        if media_type.startswith("audio/"):
            return AudioPart(media_type=media_type, data=data)
        return FilePart(media_type=media_type, data=data)
    file_data = part.get("fileData")
    if isinstance(file_data, Mapping):
        media_type = _text(file_data.get("mimeType"))
        url = _text(file_data.get("fileUri"))
        if media_type.startswith("image/"):
            return ImagePart(media_type=media_type, url=url)
        if media_type.startswith("audio/"):
            return AudioPart(media_type=media_type, url=url)
        return FilePart(media_type=media_type, url=url)
    raise ValueError("Gemini media parts must contain inlineData or fileData")


def _tool_result_names(messages: list[Message]) -> dict[str, str]:
    names: dict[str, str] = {}
    for message in messages:
        for part in message.parts:
            if isinstance(part, ToolCallPart) and part.call_id:
                names[part.call_id] = part.name
    return names


def _unified_parts_to_gemini(
    parts: list[ContentPart],
    *,
    role: MessageRole,
    results_by_name: Mapping[str, str] | None = None,
    include_reasoning: bool = False,
) -> list[dict[str, Any]]:
    built: list[dict[str, Any]] = []
    pending = ""
    for part in parts:
        if isinstance(part, TextPart | Refusal):
            if part.text:
                block: dict[str, Any] = {
                    "text": capabilities.as_reminder(part.text)
                    if role == MessageRole.SYSTEM
                    else part.text
                }
                if pending:
                    block["thoughtSignature"] = pending
                    pending = ""
                built.append(block)
        elif isinstance(part, ImagePart):
            built.append(_image_to_gemini(part))
        elif isinstance(part, FilePart):
            built.append(_file_to_gemini(part))
        elif isinstance(part, AudioPart):
            built.append(
                _file_to_gemini(
                    FilePart(
                        media_type=part.media_type or f"audio/{part.format or 'wav'}",
                        data=part.data,
                        url=part.url,
                    )
                )
            )
        elif isinstance(part, ReasoningPart):
            if part.text and (part.origin == _ORIGIN or include_reasoning):
                block = {"thought": True, "text": part.text}
                if part.origin == _ORIGIN and part.opaque:
                    block["thoughtSignature"] = part.opaque
                built.append(block)
            elif part.origin == _ORIGIN and part.opaque:
                pending = part.opaque
        elif isinstance(part, ToolCallPart):
            built.append(_tool_call_to_gemini(part, pending=pending))
            pending = ""
        elif isinstance(part, ToolResultPart):
            built.append(
                _tool_result_to_gemini(part, results_by_name=results_by_name or {})
            )
        elif isinstance(part, ServerToolPart):
            if part.origin == _ORIGIN and part.raw:
                built.append(dict(part.raw))
            elif part.output:
                built.extend(_unified_parts_to_gemini(part.output, role=role))
    if pending:
        built.append({"text": "", "thoughtSignature": pending})
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


def _tool_call_to_gemini(part: ToolCallPart, *, pending: str) -> dict[str, Any]:
    if part.kind == ToolKind.CUSTOM:
        arguments: Any = {"input": part.arguments}
    else:
        try:
            arguments = json.loads(part.arguments or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid tool call arguments JSON") from exc
        if not isinstance(arguments, Mapping):
            raise ValueError("Tool call arguments must be a JSON object")
    function: dict[str, Any] = {
        "name": capabilities.namespaced_name(part.namespace, part.name),
        "args": dict(arguments),
    }
    if part.call_id:
        function["id"] = part.call_id
    # 跨协议历史没有 Google 签名，使用官方占位值跳过签名校验。
    signature = (part.opaque or pending) if part.origin == _ORIGIN else ""
    return {
        "functionCall": function,
        "thoughtSignature": signature or DUMMY_THOUGHT_SIGNATURE,
    }


def _tool_result_to_gemini(
    part: ToolResultPart, *, results_by_name: Mapping[str, str]
) -> dict[str, Any]:
    content = part.content or "{}"
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        parsed = {"result": content}
    if part.is_error and (not isinstance(parsed, Mapping) or "error" not in parsed):
        parsed = {"error": parsed}
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
    if config.n is not None:
        result["candidateCount"] = config.n
    if config.modalities:
        result["responseModalities"] = [item.upper() for item in config.modalities]
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
    config.n = _optional_int(value.get("candidateCount"))
    modalities = value.get("responseModalities")
    if isinstance(modalities, list):
        config.modalities = tuple(
            item.lower() for item in modalities if isinstance(item, str)
        )
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
        generation["responseJsonSchema"] = response_format.schema
    elif response_format.kind == "json_object":
        generation["responseMimeType"] = "application/json"


def _tool_to_gemini(tool: ToolDefinition) -> dict[str, Any]:
    declaration: dict[str, Any] = {
        "name": capabilities.namespaced_name(tool.namespace, tool.name)
    }
    description, parameters = tool.description, tool.parameters
    if tool.kind == ToolKind.CUSTOM:
        description, parameters = capabilities.render_custom_tool(
            tool.description, tool.format
        )
    if description:
        declaration["description"] = description
    if parameters is not None:
        declaration["parametersJsonSchema"] = parameters
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
        config["allowedFunctionNames"] = list(choice.allowed_names) or [
            capabilities.namespaced_name(choice.namespace, choice.name)
        ]
    elif choice.allowed_names:
        config["mode"] = "ANY"
        config["allowedFunctionNames"] = list(choice.allowed_names)
    else:
        config["mode"] = "AUTO"
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
    thoughts = _optional_int(value.get("thoughtsTokenCount")) or 0
    return Usage(
        input_tokens=prompt,
        output_tokens=(_optional_int(value.get("candidatesTokenCount")) or 0)
        + thoughts,
        cached_input_tokens=min(
            _optional_int(value.get("cachedContentTokenCount")) or 0, prompt
        ),
        reasoning_tokens=thoughts,
    )


def _gemini_usage_wire(usage: Usage) -> dict[str, Any]:
    return {
        "promptTokenCount": usage.input_tokens,
        "candidatesTokenCount": max(usage.output_tokens - usage.reasoning_tokens, 0),
        "cachedContentTokenCount": usage.cached_input_tokens,
        "thoughtsTokenCount": usage.reasoning_tokens,
        "totalTokenCount": usage.input_tokens + usage.output_tokens,
    }


def gemini_thinking_config(intent: ReasoningIntent, model: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    effort = (intent.effort or "").lower()
    budget = intent.budget_tokens
    if "gemini-2.5" in model.lower():
        if intent.enabled is False or effort == "none":
            budget = 0
        elif budget is None:
            budget = {
                "minimal": 512,
                "low": 1024,
                "medium": 4096,
                "high": 8192,
                "xhigh": 16384,
                "max": 24576,
            }.get(effort, -1)
        if "pro" in model.lower() and budget == 0:
            budget = 128
        result["thinkingBudget"] = budget
    else:
        low = (
            intent.enabled is False
            or effort in {"none", "minimal", "low"}
            or (budget is not None and 0 <= budget <= 4096)
        )
        result["thinkingLevel"] = "LOW" if low else "HIGH"
    if intent.summarized:
        result["includeThoughts"] = True
    return result


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


async def parse_gemini_stream(raw_iterator: AsyncIterator[bytes]) -> AsyncIterator[Any]:
    started = False
    finished = False
    finish = FinishReason.END_TURN
    saw_calls = False
    usage: dict[str, Any] = {}
    next_index = 0
    active: tuple[int, BlockKind] | None = None
    async for payload in parse_sse_json_stream(raw_iterator):
        if "error" in payload:
            error = payload["error"]
            raise ValueError(
                _text(error.get("message"))
                if isinstance(error, Mapping)
                else str(error)
            )
        metadata = payload.get("usageMetadata")
        if isinstance(metadata, Mapping):
            usage.update(metadata)
        candidates = payload.get("candidates")
        feedback = payload.get("promptFeedback")
        blocked = isinstance(feedback, Mapping) and bool(feedback.get("blockReason"))
        if not isinstance(candidates, list) or not candidates:
            if blocked:
                if not started:
                    started = True
                    yield StreamStart(model=_text(payload.get("modelVersion")))
                yield BlockStart(index=next_index, kind=BlockKind.REFUSAL)
                yield RefusalDelta(
                    index=next_index,
                    text=_text(feedback.get("blockReasonMessage"))
                    or _text(feedback.get("blockReason")),
                )
                yield BlockStop(index=next_index)
                next_index += 1
                finished = True
                finish = FinishReason.CONTENT_FILTER
            continue
        if not started:
            started = True
            yield StreamStart(
                id=_text(payload.get("responseId")),
                model=_text(payload.get("modelVersion")),
            )
        candidate = candidates[0]
        if not isinstance(candidate, Mapping):
            raise ValueError("Gemini candidates must contain objects")
        if candidate.get("finishReason"):
            finished = True
            finish = _gemini_finish_reason(candidate.get("finishReason"))
        content = candidate.get("content")
        if not isinstance(content, Mapping):
            continue
        for part in _gemini_parts_to_unified(
            content.get("parts"), role=MessageRole.ASSISTANT
        ):
            if isinstance(part, ToolCallPart):
                if active is not None:
                    yield BlockStop(index=active[0])
                    active = None
                index = next_index
                next_index += 1
                saw_calls = True
                yield BlockStart(
                    index=index,
                    kind=BlockKind.TOOL_CALL,
                    call_id=part.call_id,
                    name=part.name,
                )
                yield ToolCallArgsDelta(index=index, arguments=part.arguments)
                yield BlockStop(index=index)
            elif isinstance(part, TextPart | ReasoningPart):
                kind = (
                    BlockKind.REASONING
                    if isinstance(part, ReasoningPart)
                    else BlockKind.TEXT
                )
                if active is None or active[1] != kind:
                    if active is not None:
                        yield BlockStop(index=active[0])
                    active = (next_index, kind)
                    next_index += 1
                    yield BlockStart(index=active[0], kind=kind)
                if isinstance(part, ReasoningPart):
                    if part.text:
                        yield ReasoningDelta(index=active[0], text=part.text)
                    if part.opaque:
                        yield SignatureDelta(index=active[0], opaque=part.opaque)
                elif part.text:
                    yield TextDelta(index=active[0], text=part.text)
    if not started or not finished:
        raise ValueError("Gemini stream ended before finishReason")
    if active is not None:
        yield BlockStop(index=active[0])
    if finish == FinishReason.END_TURN and saw_calls:
        finish = FinishReason.TOOL_USE
    yield StreamFinish(
        reason=finish,
        usage=_gemini_usage(usage),
        status=ResponseStatus.INCOMPLETE
        if finish in {FinishReason.MAX_TOKENS, FinishReason.CONTENT_FILTER}
        else ResponseStatus.COMPLETED,
        incomplete_reason="max_output_tokens"
        if finish == FinishReason.MAX_TOKENS
        else "content_filter"
        if finish == FinishReason.CONTENT_FILTER
        else "",
    )


async def serialize_gemini_stream(
    events: AsyncIterator[Any], original_model: str
) -> AsyncIterator[bytes]:
    calls: dict[int, ToolCallPart] = {}
    message_id = f"gemini_{uuid.uuid4().hex[:24]}"
    model = original_model

    def emit(parts: list[dict[str, Any]], finish: StreamFinish | None = None) -> bytes:
        candidate: dict[str, Any] = {
            "content": {"role": "model", "parts": parts},
            "index": 0,
        }
        payload: dict[str, Any] = {
            "candidates": [candidate],
            "modelVersion": model,
            "responseId": message_id,
        }
        if finish is not None:
            candidate["finishReason"] = _FINISH_TO_GEMINI[finish.reason]
            payload["usageMetadata"] = _gemini_usage_wire(finish.usage)
        return format_sse_event(None, payload)

    async for event in events:
        if isinstance(event, StreamStart):
            message_id = event.id or message_id
            model = event.model or model
        elif isinstance(event, BlockStart) and event.kind == BlockKind.TOOL_CALL:
            calls[event.index] = ToolCallPart(call_id=event.call_id, name=event.name)
        elif isinstance(event, TextDelta | RefusalDelta):
            yield emit([{"text": event.text}])
        elif isinstance(event, ReasoningDelta):
            yield emit([{"thought": True, "text": event.text}])
        elif isinstance(event, ToolCallArgsDelta):
            if event.index not in calls:
                raise ValueError("Tool arguments arrived before function call")
            calls[event.index].arguments += event.arguments
        elif isinstance(event, BlockStop):
            call = calls.pop(event.index, None)
            if call is not None:
                yield emit([_tool_call_to_gemini(call, pending="")])
        elif isinstance(event, StreamError):
            raise ValueError(event.message)
        elif isinstance(event, StreamFinish):
            for call in calls.values():
                yield emit([_tool_call_to_gemini(call, pending="")])
            yield emit([], finish=event)
            return

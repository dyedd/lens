"""Gemini Interactions API spoke for client and upstream wire formats.

Lens exposes and consumes Google's recommended Interactions API
(``POST /v1beta/interactions``). Conversion to and from other protocols uses
the same Interactions wire format.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Mapping
from typing import Any

from ...models.protocols import ProtocolKind
from .sse import format_sse_event, parse_sse_json_stream
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
from .unified_stream import (
    BlockKind,
    BlockStart,
    BlockStop,
    ReasoningDelta,
    SignatureDelta,
    StreamError,
    StreamFinish,
    StreamStart,
    TextDelta,
    ToolCallArgsDelta,
)
from .validation import required_string

_ORIGIN = ProtocolKind.GEMINI
_TERMINAL_STATUSES = frozenset(
    {"completed", "incomplete", "requires_action", "failed", "cancelled"}
)


def build_gemini_interaction_request(request: UnifiedRequest) -> dict[str, Any]:
    """Build an Interactions API request body from the unified request."""
    body: dict[str, Any] = {
        "model": request.model,
        # Lens carries the full history; do not let Google retain prompts.
        "store": False,
    }
    if request.stream:
        body["stream"] = True

    system_text = _system_text(request.system)
    if system_text:
        body["system_instruction"] = system_text

    steps = _request_steps(request.messages)
    if steps:
        body["input"] = steps

    tools = [_tool_to_interaction(tool) for tool in request.tools]
    if tools:
        body["tools"] = tools

    generation = _generation_to_interaction(request.generation, request.reasoning)
    tool_choice = _tool_choice_to_interaction(request.tool_choice)
    if tool_choice is not None and request.tools:
        generation["tool_choice"] = tool_choice
    if generation:
        body["generation_config"] = generation

    response_format = _response_format_to_interaction(request.response_format)
    if response_format is not None:
        body["response_format"] = response_format
    return body


def parse_gemini_interaction_request(body: Mapping[str, Any]) -> UnifiedRequest:
    """Parse a client Interactions request into the unified request."""
    request = UnifiedRequest(model=_text(body.get("model")))
    request.origin = _ORIGIN
    request.stream = body.get("stream") is True
    system = body.get("system_instruction")
    if isinstance(system, str) and system:
        request.system = [TextPart(text=system)]
    request.messages = _input_to_messages(body.get("input"))
    request.tools = _tools_from_interaction(body.get("tools"))
    generation = body.get("generation_config")
    if isinstance(generation, Mapping):
        request.generation = _generation_from_interaction(generation)
        request.reasoning = _reasoning_from_interaction(generation)
        request.tool_choice = _tool_choice_from_interaction(generation)
    request.response_format = _response_format_from_interaction(
        body.get("response_format")
    )
    return request


def build_gemini_interaction_response(
    response: UnifiedResponse,
) -> dict[str, Any]:
    """Build an Interactions response body from the unified response."""
    steps: list[dict[str, Any]] = []
    content: list[dict[str, Any]] = []

    def flush_content() -> None:
        if content:
            steps.append({"type": "model_output", "content": list(content)})
            content.clear()

    for part in response.parts:
        if isinstance(part, ReasoningPart):
            flush_content()
            thought: dict[str, Any] = {"type": "thought"}
            if part.text:
                thought["summary"] = [{"type": "text", "text": part.text}]
            if part.opaque:
                thought["signature"] = part.opaque
            steps.append(thought)
        elif isinstance(part, ToolCallPart):
            flush_content()
            steps.append(
                {
                    "type": "function_call",
                    "id": part.call_id,
                    "name": part.name,
                    "arguments": _arguments_object(part.arguments),
                }
            )
        elif isinstance(part, ToolResultPart):
            flush_content()
            steps.append(
                {
                    "type": "function_result",
                    "call_id": part.call_id,
                    "result": [{"type": "text", "text": part.content}],
                }
            )
        else:
            converted = _content_to_interaction(part)
            if converted is not None:
                content.append(converted)
    flush_content()

    status = "completed"
    if response.finish == FinishReason.TOOL_USE:
        status = "requires_action"
    elif response.finish == FinishReason.MAX_TOKENS:
        status = "incomplete"
    elif response.finish == FinishReason.CONTENT_FILTER:
        status = "failed"
    return {
        "id": response.id or f"interaction_{uuid.uuid4().hex[:24]}",
        "object": "interaction",
        "model": response.model,
        "status": status,
        "steps": steps,
        "usage": _usage_to_interaction(response.usage),
    }


async def serialize_gemini_interaction_stream(
    events: AsyncIterator[Any], original_model: str
) -> AsyncIterator[bytes]:
    """Serialize unified stream events into an Interactions SSE stream."""
    interaction_id = f"interaction_{uuid.uuid4().hex[:24]}"
    model = original_model
    started = False

    def interaction_payload(status: str) -> dict[str, Any]:
        return {
            "id": interaction_id,
            "object": "interaction",
            "model": model,
            "status": status,
        }

    def created_event() -> bytes:
        return format_sse_event(
            "interaction.created",
            {
                "event_type": "interaction.created",
                "interaction": interaction_payload("in_progress"),
            },
        )

    async for event in events:
        if isinstance(event, StreamStart):
            if event.id:
                interaction_id = event.id
            if event.model:
                model = event.model
            if not started:
                started = True
                yield created_event()
            continue
        if not started:
            started = True
            yield created_event()
        if isinstance(event, BlockStart):
            step: dict[str, Any]
            if event.kind == BlockKind.TOOL_CALL:
                step = {
                    "type": "function_call",
                    "id": event.call_id or f"call_{uuid.uuid4().hex[:24]}",
                    "name": event.name,
                    "arguments": {},
                }
            elif event.kind == BlockKind.REASONING:
                step = {"type": "thought"}
            else:
                step = {"type": "model_output"}
            yield format_sse_event(
                "step.start",
                {
                    "event_type": "step.start",
                    "index": event.index,
                    "step": step,
                },
            )
        elif isinstance(event, TextDelta):
            yield format_sse_event(
                "step.delta",
                {
                    "event_type": "step.delta",
                    "index": event.index,
                    "delta": {"type": "text", "text": event.text},
                },
            )
        elif isinstance(event, ReasoningDelta):
            yield format_sse_event(
                "step.delta",
                {
                    "event_type": "step.delta",
                    "index": event.index,
                    "delta": {
                        "type": "thought_summary",
                        "content": {"type": "text", "text": event.text},
                    },
                },
            )
        elif isinstance(event, SignatureDelta):
            yield format_sse_event(
                "step.delta",
                {
                    "event_type": "step.delta",
                    "index": event.index,
                    "delta": {
                        "type": "thought_signature",
                        "signature": event.opaque,
                    },
                },
            )
        elif isinstance(event, ToolCallArgsDelta):
            yield format_sse_event(
                "step.delta",
                {
                    "event_type": "step.delta",
                    "index": event.index,
                    "delta": {
                        "type": "arguments_delta",
                        "arguments": event.arguments,
                    },
                },
            )
        elif isinstance(event, BlockStop):
            yield format_sse_event(
                "step.stop",
                {"event_type": "step.stop", "index": event.index},
            )
        elif isinstance(event, StreamFinish):
            status = "completed"
            if event.reason == FinishReason.TOOL_USE:
                status = "requires_action"
            elif event.reason in {
                FinishReason.MAX_TOKENS,
                FinishReason.CONTENT_FILTER,
            }:
                status = "incomplete"
            interaction = interaction_payload(status)
            interaction["usage"] = _usage_to_interaction(event.usage)
            yield format_sse_event(
                "interaction.completed",
                {
                    "event_type": "interaction.completed",
                    "interaction": interaction,
                },
            )
        elif isinstance(event, StreamError):
            yield format_sse_event(
                "error",
                {
                    "event_type": "error",
                    "error": {"message": event.message},
                },
            )


def parse_gemini_interaction_response(body: Mapping[str, Any]) -> UnifiedResponse:
    """Parse an Interactions API response body into the unified response."""
    if body.get("object") not in (None, "interaction"):
        raise ValueError("Gemini Interactions response must be an interaction")
    steps = body.get("steps")
    if not isinstance(steps, list):
        raise ValueError("Gemini Interactions response must contain steps")

    parts: list[ContentPart] = []
    for step in steps:
        if not isinstance(step, Mapping):
            raise ValueError("Gemini Interactions steps must contain objects")
        parts.extend(_step_to_unified(step))

    status = _text(body.get("status"))
    finish = _finish_from_interaction_status(status)
    if finish == FinishReason.END_TURN and any(
        isinstance(part, ToolCallPart) for part in parts
    ):
        finish = FinishReason.TOOL_USE
    return UnifiedResponse(
        id=_text(body.get("id")) or f"gemini_{uuid.uuid4().hex[:24]}",
        model=_text(body.get("model")),
        parts=parts,
        finish=finish,
        usage=_interaction_usage(body) or Usage(),
    )


async def parse_gemini_interaction_stream(
    raw_iterator: AsyncIterator[bytes],
) -> AsyncIterator[Any]:
    """Parse an Interactions SSE stream into unified stream events."""
    started = False
    finished = False
    block_indices: set[int] = set()
    model = ""
    stream_usage = Usage()

    async for payload in parse_sse_json_stream(raw_iterator):
        event_type = payload.get("event_type")
        if event_type == "interaction.created":
            interaction = payload.get("interaction")
            if isinstance(interaction, Mapping):
                model = _text(interaction.get("model"))
                started = True
                yield StreamStart(id=_text(interaction.get("id")), model=model)
            continue
        if event_type == "interaction.completed":
            interaction = payload.get("interaction")
            if isinstance(interaction, Mapping):
                yield StreamFinish(
                    reason=_finish_from_interaction_status(
                        _text(interaction.get("status"))
                    ),
                    usage=_interaction_usage(interaction) or stream_usage,
                )
            else:
                yield StreamFinish(usage=stream_usage)
            finished = True
            continue
        if event_type == "error":
            error = payload.get("error")
            message = (
                _text(error.get("message"))
                if isinstance(error, Mapping)
                else "Gemini Interactions stream failed"
            )
            raise ValueError(message or "Gemini Interactions stream failed")
        if event_type not in {"step.start", "step.delta", "step.stop"}:
            continue

        index = _optional_int(payload.get("index"))
        if index is None:
            continue
        if event_type == "step.start":
            step = payload.get("step")
            if not isinstance(step, Mapping):
                continue
            if not started:
                started = True
                yield StreamStart(model=model)
            step_type = step.get("type")
            if step_type == "model_output":
                block_indices.add(index)
                yield BlockStart(index=index, kind=BlockKind.TEXT)
            elif step_type == "thought":
                block_indices.add(index)
                yield BlockStart(index=index, kind=BlockKind.REASONING)
            elif step_type == "function_call":
                block_indices.add(index)
                yield BlockStart(
                    index=index,
                    kind=BlockKind.TOOL_CALL,
                    call_id=_text(step.get("id")),
                    name=_text(step.get("name")),
                )
            continue
        if event_type == "step.delta":
            delta = payload.get("delta")
            if not isinstance(delta, Mapping):
                continue
            delta_type = delta.get("type")
            if delta_type == "text":
                text = delta.get("text")
                if isinstance(text, str) and text:
                    if index not in block_indices:
                        block_indices.add(index)
                        yield BlockStart(index=index, kind=BlockKind.TEXT)
                    yield TextDelta(index=index, text=text)
            elif delta_type == "thought_summary":
                content = delta.get("content")
                text = (
                    _text(content.get("text")) if isinstance(content, Mapping) else ""
                )
                if text:
                    if index not in block_indices:
                        block_indices.add(index)
                        yield BlockStart(index=index, kind=BlockKind.REASONING)
                    yield ReasoningDelta(index=index, text=text)
            elif delta_type == "thought_signature":
                signature = delta.get("signature")
                if isinstance(signature, str) and signature:
                    yield SignatureDelta(index=index, opaque=signature)
            elif delta_type == "arguments_delta":
                arguments = delta.get("arguments")
                if isinstance(arguments, str) and arguments:
                    yield ToolCallArgsDelta(index=index, arguments=arguments)
            continue
        if event_type == "step.stop":
            usage_payload = payload.get("usage")
            if isinstance(usage_payload, Mapping):
                stream_usage = _usage_from_mapping(usage_payload)
            if index in block_indices:
                block_indices.remove(index)
                yield BlockStop(index=index)

    if not started:
        raise ValueError("Gemini Interactions stream ended before any content")
    if not finished:
        yield StreamFinish(usage=stream_usage)


def _flush_model_output(
    steps: list[dict[str, Any]], content_parts: list[dict[str, Any]]
) -> None:
    if not content_parts:
        return
    steps.append({"type": "model_output", "content": list(content_parts)})
    content_parts.clear()


def _request_steps(messages: list[Message]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    tool_names: dict[str, str] = {}
    for message in messages:
        if message.role == MessageRole.TOOL:
            for part in message.parts:
                if isinstance(part, ToolResultPart):
                    step: dict[str, Any] = {
                        "type": "function_result",
                        "call_id": part.call_id,
                        "result": [{"type": "text", "text": part.content}],
                    }
                    name = tool_names.get(part.call_id)
                    if name:
                        step["name"] = name
                    if part.is_error:
                        step["is_error"] = True
                    steps.append(step)
            continue

        if message.role == MessageRole.ASSISTANT:
            content_parts: list[dict[str, Any]] = []
            for part in message.parts:
                if isinstance(part, ReasoningPart):
                    _flush_model_output(steps, content_parts)
                    thought: dict[str, Any] = {"type": "thought"}
                    if part.text:
                        thought["summary"] = [{"type": "text", "text": part.text}]
                    if part.opaque:
                        thought["signature"] = part.opaque
                    steps.append(thought)
                elif isinstance(part, ToolCallPart):
                    _flush_model_output(steps, content_parts)
                    steps.append(
                        {
                            "type": "function_call",
                            "id": part.call_id,
                            "name": part.name,
                            "arguments": _arguments_object(part.arguments),
                        }
                    )
                    tool_names[part.call_id] = part.name
                else:
                    converted = _content_to_interaction(part)
                    if converted is not None:
                        content_parts.append(converted)
            _flush_model_output(steps, content_parts)
            continue

        content = [
            converted
            for part in message.parts
            if (converted := _content_to_interaction(part)) is not None
        ]
        steps.append({"type": "user_input", "content": content})
    return steps


def _step_to_unified(step: Mapping[str, Any]) -> list[ContentPart]:
    step_type = step.get("type")
    if step_type == "model_output":
        content = step.get("content")
        if not isinstance(content, list):
            return []
        parts: list[ContentPart] = []
        for block in content:
            if isinstance(block, Mapping):
                converted = _content_to_unified(block)
                if converted is not None:
                    parts.append(converted)
        return parts
    if step_type == "thought":
        summary = step.get("summary")
        text = ""
        if isinstance(summary, list):
            text = "\n".join(
                _text(block.get("text"))
                for block in summary
                if isinstance(block, Mapping) and block.get("type") == "text"
            )
        signature = step.get("signature")
        return [
            ReasoningPart(
                text=text,
                opaque=signature if isinstance(signature, str) else "",
                origin=_ORIGIN,
            )
        ]
    if step_type == "function_call":
        arguments = step.get("arguments")
        return [
            ToolCallPart(
                call_id=_text(step.get("id")) or f"call_{uuid.uuid4().hex[:24]}",
                name=required_string(
                    step.get("name"), "Gemini function call must contain name"
                ),
                arguments=_arguments_text(arguments),
                origin=_ORIGIN,
            )
        ]
    if step_type == "function_result":
        result = step.get("result")
        if isinstance(result, list):
            content = "\n".join(
                _text(item.get("text"))
                for item in result
                if isinstance(item, Mapping) and item.get("type") == "text"
            )
        elif isinstance(result, str):
            content = result
        else:
            content = (
                json.dumps(result, ensure_ascii=False) if result is not None else ""
            )
        return [
            ToolResultPart(
                call_id=_text(step.get("call_id")),
                content=content,
                is_error=step.get("is_error") is True,
            )
        ]
    return []


def _content_to_interaction(part: ContentPart) -> dict[str, Any] | None:
    if isinstance(part, TextPart):
        return {"type": "text", "text": part.text}
    if isinstance(part, ImagePart):
        block: dict[str, Any] = {"type": "image"}
        if part.url:
            block["uri"] = part.url
        elif part.data:
            block["data"] = part.data
            block["mime_type"] = part.media_type or "image/png"
        else:
            return None
        return block
    if isinstance(part, FilePart):
        media_type = part.media_type or "application/pdf"
        if media_type.startswith("audio/"):
            block_type = "audio"
        elif media_type.startswith("video/"):
            block_type = "video"
        else:
            block_type = "document"
        block = {"type": block_type}
        if part.url:
            block["uri"] = part.url
        elif part.data:
            block["data"] = part.data
            block["mime_type"] = media_type
        else:
            return None
        return block
    return None


def _content_to_unified(block: Mapping[str, Any]) -> ContentPart | None:
    block_type = block.get("type")
    if block_type == "text":
        text = block.get("text")
        return TextPart(text=text if isinstance(text, str) else "")
    if block_type == "image":
        data = _text(block.get("data"))
        url = _text(block.get("uri"))
        if not data and not url:
            return None
        return ImagePart(
            media_type=_text(block.get("mime_type")),
            data=data,
            url=url,
        )
    if block_type in {"audio", "video", "document"}:
        data = _text(block.get("data"))
        url = _text(block.get("uri"))
        if not data and not url:
            return None
        return FilePart(
            media_type=_text(block.get("mime_type")),
            data=data,
            url=url,
        )
    return None


def _generation_to_interaction(
    generation: GenerationConfig, reasoning: ReasoningIntent | None
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if generation.max_output_tokens is not None:
        result["max_output_tokens"] = generation.max_output_tokens
    if generation.temperature is not None:
        result["temperature"] = generation.temperature
    if generation.top_p is not None:
        result["top_p"] = generation.top_p
    if generation.seed is not None:
        result["seed"] = generation.seed
    if generation.stop:
        result["stop_sequences"] = list(generation.stop)
    if reasoning is not None:
        level = _thinking_level(reasoning)
        if level is not None:
            result["thinking_level"] = level
        if reasoning.summarized:
            result["thinking_summaries"] = "auto"
    return result


def _thinking_level(intent: ReasoningIntent) -> str | None:
    effort = (intent.effort or "").strip().lower()
    if effort in {"minimal", "low", "medium", "high"}:
        return effort
    if intent.enabled is False:
        return "minimal"
    budget = intent.budget_tokens
    if budget is None:
        return "high" if intent.enabled else None
    if budget <= 1024:
        return "minimal"
    if budget <= 4096:
        return "low"
    if budget <= 16384:
        return "medium"
    return "high"


def _tool_choice_to_interaction(
    choice: ToolChoice | None,
) -> str | dict[str, Any] | None:
    if choice is None:
        return None
    if choice.mode == ToolChoiceMode.NONE:
        return "none"
    if choice.mode == ToolChoiceMode.REQUIRED:
        return "any"
    if choice.mode == ToolChoiceMode.AUTO:
        return "auto"
    names = [choice.name] if choice.name else list(choice.allowed_names)
    if names:
        return {"allowed_tools": {"mode": "any", "tools": names}}
    return "any"


def _tool_to_interaction(tool: ToolDefinition) -> dict[str, Any]:
    result: dict[str, Any] = {"type": "function", "name": tool.name}
    if tool.description:
        result["description"] = tool.description
    if tool.parameters is not None:
        result["parameters"] = tool.parameters
    return result


def _response_format_to_interaction(format: Any) -> dict[str, Any] | None:
    if format is None:
        return None
    if format.kind == "json_schema":
        return {
            "type": "text",
            "mime_type": "application/json",
            "schema": format.schema or {},
        }
    if format.kind == "json_object":
        return {"type": "text", "mime_type": "application/json"}
    if format.kind:
        return {"type": "text", "mime_type": "text/plain"}
    return None


def _system_text(parts: list[ContentPart]) -> str:
    return "\n".join(
        part.text for part in parts if isinstance(part, TextPart) and part.text
    )


def _arguments_object(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value) if value else {}
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _arguments_text(value: Any) -> str:
    if isinstance(value, str):
        return value or "{}"
    return json.dumps(
        dict(value) if isinstance(value, Mapping) else {},
        ensure_ascii=False,
    )


def _finish_from_interaction_status(status: str) -> FinishReason:
    if status == "incomplete" or status == "budget_exceeded":
        return FinishReason.MAX_TOKENS
    if status == "requires_action":
        return FinishReason.TOOL_USE
    if status == "failed":
        return FinishReason.CONTENT_FILTER
    if status == "cancelled":
        return FinishReason.OTHER
    return FinishReason.END_TURN


def _input_to_messages(value: Any) -> list[Message]:
    if value is None:
        return []
    items = [value] if isinstance(value, Mapping | str) else value
    if not isinstance(items, list):
        raise ValueError("Gemini Interactions input must be a string or array")

    messages: list[Message] = []
    pending_user: list[ContentPart] = []

    def flush_user() -> None:
        if pending_user:
            messages.append(Message(role=MessageRole.USER, parts=list(pending_user)))
            pending_user.clear()

    for item in items:
        if isinstance(item, str):
            pending_user.append(TextPart(text=item))
            continue
        if not isinstance(item, Mapping):
            raise ValueError("Gemini Interactions input must contain objects")
        item_type = item.get("type")
        if item_type is None or item_type in {
            "text",
            "image",
            "audio",
            "video",
            "document",
        }:
            converted = _content_to_unified(item)
            if converted is not None:
                pending_user.append(converted)
            continue
        flush_user()
        if item_type == "user_input":
            messages.append(
                Message(
                    role=MessageRole.USER,
                    parts=_content_list_to_parts(item.get("content")),
                )
            )
        elif item_type == "model_output":
            messages.append(
                Message(
                    role=MessageRole.ASSISTANT,
                    parts=_content_list_to_parts(item.get("content")),
                )
            )
        elif item_type == "thought":
            summary = item.get("summary")
            text = ""
            if isinstance(summary, list):
                text = "\n".join(
                    _text(block.get("text"))
                    for block in summary
                    if isinstance(block, Mapping) and block.get("type") == "text"
                )
            signature = item.get("signature")
            messages.append(
                Message(
                    role=MessageRole.ASSISTANT,
                    parts=[
                        ReasoningPart(
                            text=text,
                            opaque=signature if isinstance(signature, str) else "",
                            origin=_ORIGIN,
                        )
                    ],
                )
            )
        elif item_type == "function_call":
            messages.append(
                Message(
                    role=MessageRole.ASSISTANT,
                    parts=[
                        ToolCallPart(
                            call_id=_text(item.get("id")),
                            name=_text(item.get("name")),
                            arguments=_arguments_text(item.get("arguments")),
                            origin=_ORIGIN,
                        )
                    ],
                )
            )
        elif item_type == "function_result":
            messages.append(
                Message(
                    role=MessageRole.TOOL,
                    parts=[
                        ToolResultPart(
                            call_id=_text(item.get("call_id")),
                            content=_result_text(item.get("result")),
                            is_error=item.get("is_error") is True,
                        )
                    ],
                )
            )
    flush_user()
    return messages


def _content_list_to_parts(value: Any) -> list[ContentPart]:
    if isinstance(value, str):
        return [TextPart(text=value)]
    if not isinstance(value, list):
        return []
    parts: list[ContentPart] = []
    for block in value:
        if isinstance(block, Mapping):
            converted = _content_to_unified(block)
            if converted is not None:
                parts.append(converted)
    return parts


def _result_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(
            _text(item.get("text"))
            for item in value
            if isinstance(item, Mapping) and item.get("type") == "text"
        )
    if value is None:
        return ""
    return json.dumps(value, ensure_ascii=False)


def _tools_from_interaction(value: Any) -> list[ToolDefinition]:
    if not isinstance(value, list):
        return []
    tools: list[ToolDefinition] = []
    for tool in value:
        if not isinstance(tool, Mapping) or tool.get("type") != "function":
            continue
        name = _text(tool.get("name"))
        if not name:
            continue
        parameters = tool.get("parameters")
        tools.append(
            ToolDefinition(
                name=name,
                description=_text(tool.get("description")),
                parameters=parameters if isinstance(parameters, Mapping) else None,
            )
        )
    return tools


def _generation_from_interaction(value: Mapping[str, Any]) -> GenerationConfig:
    stop = value.get("stop_sequences")
    return GenerationConfig(
        max_output_tokens=_optional_int(value.get("max_output_tokens")),
        temperature=_optional_float(value.get("temperature")),
        top_p=_optional_float(value.get("top_p")),
        seed=_optional_int(value.get("seed")),
        stop=tuple(item for item in stop if isinstance(item, str))
        if isinstance(stop, list)
        else (),
    )


def _reasoning_from_interaction(
    value: Mapping[str, Any],
) -> ReasoningIntent | None:
    level = value.get("thinking_level")
    summarized = value.get("thinking_summaries") == "auto"
    if not isinstance(level, str) and not summarized:
        return None
    return ReasoningIntent(
        enabled=level != "minimal",
        effort=level if isinstance(level, str) else None,
        summarized=summarized,
    )


def _tool_choice_from_interaction(
    value: Mapping[str, Any],
) -> ToolChoice | None:
    choice = value.get("tool_choice")
    if isinstance(choice, str):
        if choice == "none":
            return ToolChoice(mode=ToolChoiceMode.NONE)
        if choice in {"any", "validated"}:
            return ToolChoice(mode=ToolChoiceMode.REQUIRED)
        return ToolChoice(mode=ToolChoiceMode.AUTO)
    if not isinstance(choice, Mapping):
        return None
    allowed = choice.get("allowed_tools")
    if not isinstance(allowed, Mapping):
        return None
    names = tuple(name for name in allowed.get("tools", []) if isinstance(name, str))
    return ToolChoice(
        mode=ToolChoiceMode.REQUIRED
        if allowed.get("mode") in {"any", "validated"}
        else ToolChoiceMode.AUTO,
        allowed_names=names,
        name=names[0] if len(names) == 1 else "",
    )


def _response_format_from_interaction(
    value: Any,
) -> ResponseFormat | None:
    if not isinstance(value, Mapping):
        return None
    mime_type = value.get("mime_type")
    schema = value.get("schema")
    if isinstance(schema, Mapping):
        return ResponseFormat(kind="json_schema", schema=dict(schema))
    if mime_type == "application/json":
        return ResponseFormat(kind="json_object")
    if isinstance(mime_type, str):
        return ResponseFormat(kind="text")
    return None


def _usage_to_interaction(usage: Usage) -> dict[str, int]:
    return {
        "total_input_tokens": usage.input_tokens,
        "total_cached_tokens": usage.cached_input_tokens,
        "total_output_tokens": usage.output_tokens,
        "total_thought_tokens": usage.reasoning_tokens,
        "total_tokens": usage.input_tokens + usage.output_tokens,
    }


def _optional_float(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _interaction_usage(payload: Mapping[str, Any]) -> Usage | None:
    source = payload.get("interaction")
    if isinstance(source, Mapping):
        payload = source
    usage = payload.get("usage")
    if not isinstance(usage, Mapping):
        return None
    return _usage_from_mapping(usage)


def _usage_from_mapping(usage: Mapping[str, Any]) -> Usage:
    input_tokens = _optional_int(usage.get("total_input_tokens")) or 0
    cached_tokens = _optional_int(usage.get("total_cached_tokens")) or 0
    return Usage(
        input_tokens=input_tokens,
        output_tokens=_optional_int(usage.get("total_output_tokens")) or 0,
        cached_input_tokens=min(cached_tokens, input_tokens),
        reasoning_tokens=_optional_int(usage.get("total_thought_tokens")) or 0,
    )


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value

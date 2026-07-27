import json
import uuid
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from typing import Any

from ._chat_stream import ChatToolCall, ChatToolCalls
from ._validation import _required_string
from ._sse import (
    FINISH_REASON_CHAT_TO_ANTHROPIC,
    format_sse_event,
    parse_sse_json_stream,
)


def chat_response_to_anthropic(
    chat_body: dict[str, Any], original_model: str
) -> dict[str, Any]:
    """Convert a chat response into an Anthropic response."""
    choice = (chat_body.get("choices") or [{}])[0]
    message = choice.get("message", {})
    finish_reason = choice.get("finish_reason")
    stop_reason = FINISH_REASON_CHAT_TO_ANTHROPIC.get(finish_reason, "end_turn")

    content: list[dict[str, Any]] = []
    has_reasoning, reasoning = _chat_message_reasoning_content(message)
    if has_reasoning:
        content.append({"type": "thinking", "thinking": reasoning})
    text = message.get("content")
    if text:
        content.append({"type": "text", "text": text})
    tool_calls = message.get("tool_calls")
    if tool_calls:
        content.extend(_chat_tool_calls_to_anthropic_content(tool_calls))

    usage = chat_body.get("usage", {})
    return {
        "id": chat_body.get("id", f"msg_{uuid.uuid4().hex[:24]}"),
        "type": "message",
        "role": "assistant",
        "model": chat_body.get("model", original_model),
        "content": content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        },
    }


async def chat_stream_to_anthropic_stream(
    raw_iterator: AsyncIterator[bytes],
    original_model: str,
) -> AsyncIterator[bytes]:
    """Convert a chat SSE stream into an Anthropic SSE stream."""
    state = _AnthropicStreamState(
        message_id=f"msg_{uuid.uuid4().hex[:24]}", model=original_model
    )
    for event in state.start_events():
        yield event
    async for payload in parse_sse_json_stream(raw_iterator, require_done=True):
        for event in state.update(payload):
            yield event
    for event in state.finish_events():
        yield event


@dataclass(slots=True)
class _AnthropicStreamState:
    message_id: str
    model: str
    output_tokens: int = 0
    text_index: int | None = None
    thinking_index: int | None = None
    tool_calls: ChatToolCalls = field(default_factory=ChatToolCalls)
    next_block_index: int = 0
    finish_reason: str | None = None

    def start_events(self) -> list[bytes]:
        return [
            format_sse_event(
                "message_start",
                {
                    "type": "message_start",
                    "message": {
                        "id": self.message_id,
                        "type": "message",
                        "role": "assistant",
                        "model": self.model,
                        "content": [],
                        "stop_reason": None,
                        "stop_sequence": None,
                        "usage": {"input_tokens": 0, "output_tokens": 0},
                    },
                },
            ),
            format_sse_event("ping", {"type": "ping"}),
        ]

    def update(self, payload: Mapping[str, Any]) -> list[bytes]:
        usage = payload.get("usage") or {}
        if usage.get("completion_tokens"):
            self.output_tokens = usage["completion_tokens"]
        events: list[bytes] = []
        for choice in payload.get("choices", []):
            self.finish_reason = choice.get("finish_reason") or self.finish_reason
            delta = choice.get("delta", {})
            events.extend(self._reasoning_events(_chat_delta_reasoning_content(delta)))
            events.extend(self._text_events(delta.get("content")))
            for value in delta.get("tool_calls") or []:
                events.extend(self._tool_events(value))
        return events

    def finish_events(self) -> list[bytes]:
        events = [
            _content_block_stop(index)
            for index in (self.thinking_index, self.text_index)
            if index is not None
        ]
        for tool_call in self.tool_calls:
            if not tool_call.announced:
                events.append(self._announce_tool(tool_call))
            arguments_delta = tool_call.take_argument_delta()
            if arguments_delta:
                events.append(_tool_arguments_delta(tool_call, arguments_delta))
            events.append(_content_block_stop(_tool_block_index(tool_call)))

        stop_reason = FINISH_REASON_CHAT_TO_ANTHROPIC.get(
            self.finish_reason, "end_turn"
        )
        events.extend(
            [
                format_sse_event(
                    "message_delta",
                    {
                        "type": "message_delta",
                        "delta": {
                            "stop_reason": stop_reason,
                            "stop_sequence": None,
                        },
                        "usage": {"output_tokens": self.output_tokens},
                    },
                ),
                format_sse_event("message_stop", {"type": "message_stop"}),
            ]
        )
        return events

    def _reasoning_events(self, delta: str | None) -> list[bytes]:
        if delta is None:
            return []
        events: list[bytes] = []
        if self.thinking_index is None:
            self.thinking_index = self._allocate_block_index()
            events.append(
                _content_block_start(
                    self.thinking_index, {"type": "thinking", "thinking": ""}
                )
            )
        if delta:
            events.append(
                format_sse_event(
                    "content_block_delta",
                    {
                        "type": "content_block_delta",
                        "index": self.thinking_index,
                        "delta": {"type": "thinking_delta", "thinking": delta},
                    },
                )
            )
        return events

    def _text_events(self, delta: Any) -> list[bytes]:
        if not delta:
            return []
        if not isinstance(delta, str):
            raise ValueError("Chat content delta must be a string")
        events: list[bytes] = []
        if self.text_index is None:
            self.text_index = self._allocate_block_index()
            events.append(
                _content_block_start(self.text_index, {"type": "text", "text": ""})
            )
        events.append(
            format_sse_event(
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": self.text_index,
                    "delta": {"type": "text_delta", "text": delta},
                },
            )
        )
        return events

    def _tool_events(self, value: Any) -> list[bytes]:
        tool_call = self.tool_calls.update(value)
        if tool_call.target_index is None:
            tool_call.target_index = self._allocate_block_index()
        events: list[bytes] = []
        if not tool_call.announced and tool_call.call_id and tool_call.name:
            events.append(self._announce_tool(tool_call))
        if tool_call.announced:
            arguments_delta = tool_call.take_argument_delta()
            if arguments_delta:
                events.append(_tool_arguments_delta(tool_call, arguments_delta))
        return events

    def _announce_tool(self, tool_call: ChatToolCall) -> bytes:
        event = _tool_block_start(tool_call)
        tool_call.announced = True
        return event

    def _allocate_block_index(self) -> int:
        index = self.next_block_index
        self.next_block_index += 1
        return index


def _content_block_start(index: int, content_block: dict[str, Any]) -> bytes:
    return format_sse_event(
        "content_block_start",
        {
            "type": "content_block_start",
            "index": index,
            "content_block": content_block,
        },
    )


def _content_block_stop(index: int) -> bytes:
    return format_sse_event(
        "content_block_stop",
        {"type": "content_block_stop", "index": index},
    )


def _tool_block_start(tool_call: ChatToolCall) -> bytes:
    if not tool_call.call_id:
        raise ValueError("Chat tool call stream ended without id")
    if not tool_call.name:
        raise ValueError("Chat tool call stream ended without function.name")
    return _content_block_start(
        _tool_block_index(tool_call),
        {
            "type": "tool_use",
            "id": tool_call.call_id,
            "name": tool_call.name,
            "input": {},
        },
    )


def _tool_arguments_delta(tool_call: ChatToolCall, arguments: str) -> bytes:
    return format_sse_event(
        "content_block_delta",
        {
            "type": "content_block_delta",
            "index": _tool_block_index(tool_call),
            "delta": {
                "type": "input_json_delta",
                "partial_json": arguments,
            },
        },
    )


def _tool_block_index(tool_call: ChatToolCall) -> int:
    if tool_call.target_index is None:
        raise ValueError("Chat tool call stream ended without a content block index")
    return tool_call.target_index


def _chat_tool_calls_to_anthropic_content(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("Chat tool_calls must be an array")
    blocks: list[dict[str, Any]] = []
    for tool_call in value:
        if not isinstance(tool_call, Mapping):
            raise ValueError("Chat tool_calls must contain objects")
        function = tool_call.get("function")
        if not isinstance(function, Mapping):
            raise ValueError("Chat tool calls must contain a function object")
        arguments = _required_string(
            function.get("arguments"),
            "Chat tool calls must contain function.arguments",
            allow_empty=True,
        )
        try:
            parsed_input = json.loads(arguments or "{}")
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid tool call arguments JSON") from exc
        blocks.append(
            {
                "type": "tool_use",
                "id": _required_string(
                    tool_call.get("id"), "Chat tool calls must contain id"
                ),
                "name": _required_string(
                    function.get("name"),
                    "Chat tool calls must contain function.name",
                ),
                "input": parsed_input,
            }
        )
    return blocks


def _chat_message_reasoning_content(message: Mapping[str, Any]) -> tuple[bool, str]:
    for key in ("reasoning_content", "reasoning"):
        if key in message and isinstance(message.get(key), str):
            return True, message[key]
    return False, ""


def _chat_delta_reasoning_content(delta: Mapping[str, Any]) -> str | None:
    for key in ("reasoning_content", "reasoning"):
        if key in delta and isinstance(delta.get(key), str):
            return delta[key]
    return None

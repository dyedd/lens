from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from ._responses import (
    _encode_reasoning_item,
    _reasoning_item_to_anthropic,
    _reasoning_summary_text,
    _usage_int,
    _validate_terminal_response,
)
from ._shared import _required_string
from ._sse import format_sse_event, parse_sse_json_stream

_TERMINAL_EVENTS = {"response.completed", "response.incomplete"}


def responses_response_to_anthropic(
    response: Any, original_model: str
) -> dict[str, Any]:
    """Convert a Responses API response into an Anthropic Message."""
    if not isinstance(response, Mapping):
        raise ValueError("Responses upstream response must be an object")
    output = _validate_terminal_response(response)
    content, has_tool_calls, has_refusal = _responses_output_to_anthropic(output)
    return {
        "id": response.get("id") or f"msg_{uuid.uuid4().hex[:24]}",
        "type": "message",
        "role": "assistant",
        "model": response.get("model") or original_model,
        "content": content,
        "stop_reason": _responses_stop_reason(
            response, has_tool_calls=has_tool_calls, has_refusal=has_refusal
        ),
        "stop_sequence": None,
        "usage": _responses_usage_to_anthropic(response.get("usage")),
    }


def _responses_output_to_anthropic(
    output: list[Any],
) -> tuple[list[dict[str, Any]], bool, bool]:
    content: list[dict[str, Any]] = []
    has_tool_calls = False
    has_refusal = False
    for item in output:
        if not isinstance(item, Mapping):
            raise ValueError("Responses upstream output must contain objects")
        item_type = item.get("type")
        if item_type == "reasoning":
            content.append(_reasoning_item_to_anthropic(item))
        elif item_type == "message":
            raw_content = item.get("content")
            if not isinstance(raw_content, list):
                raise ValueError("Responses message content must be an array")
            for part in raw_content:
                if not isinstance(part, Mapping):
                    raise ValueError("Responses message content must contain objects")
                part_type = part.get("type")
                if part_type == "output_text":
                    content.append(
                        {
                            "type": "text",
                            "text": _required_string(
                                part.get("text"),
                                "Responses output_text must contain text",
                                allow_empty=True,
                            ),
                        }
                    )
                elif part_type == "refusal":
                    has_refusal = True
                    content.append(
                        {
                            "type": "text",
                            "text": _required_string(
                                part.get("refusal"),
                                "Responses refusal must contain refusal text",
                                allow_empty=True,
                            ),
                        }
                    )
        elif item_type == "function_call":
            try:
                tool_input = json.loads(
                    _required_string(
                        item.get("arguments"),
                        "Responses function_call must contain arguments",
                        allow_empty=True,
                    )
                    or "{}"
                )
            except json.JSONDecodeError as exc:
                raise ValueError("Invalid Responses function_call arguments") from exc
            if not isinstance(tool_input, dict):
                raise ValueError("Responses function_call arguments must be an object")
            has_tool_calls = True
            content.append(
                {
                    "type": "tool_use",
                    "id": _required_string(
                        item.get("call_id"),
                        "Responses function_call must contain call_id",
                    ),
                    "name": _required_string(
                        item.get("name"),
                        "Responses function_call must contain name",
                    ),
                    "input": tool_input,
                }
            )
    return content, has_tool_calls, has_refusal


def _responses_stop_reason(
    response: Mapping[str, Any], *, has_tool_calls: bool, has_refusal: bool
) -> str:
    if response.get("status") == "incomplete":
        details = response.get("incomplete_details")
        reason = details.get("reason") if isinstance(details, Mapping) else None
        if reason == "content_filter":
            return "refusal"
        if reason == "model_context_window_exceeded":
            return "model_context_window_exceeded"
        return "max_tokens"
    if has_tool_calls:
        return "tool_use"
    if has_refusal:
        return "refusal"
    return "end_turn"


def _responses_usage_to_anthropic(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {"input_tokens": 0, "output_tokens": 0}
    total_input = _usage_int(value, "input_tokens")
    output_tokens = _usage_int(value, "output_tokens")
    input_details = value.get("input_tokens_details")
    cached_tokens = 0
    cache_write_tokens = 0
    if isinstance(input_details, Mapping):
        cached_tokens = _usage_int(input_details, "cached_tokens")
        cache_write_tokens = _usage_int(input_details, "cache_write_tokens")
    uncached_tokens = total_input - cached_tokens - cache_write_tokens
    if uncached_tokens < 0:
        raise ValueError("Responses cache token counts exceed input_tokens")
    result: dict[str, Any] = {
        "input_tokens": uncached_tokens,
        "output_tokens": output_tokens,
    }
    if isinstance(input_details, Mapping):
        result["cache_creation_input_tokens"] = cache_write_tokens
        result["cache_read_input_tokens"] = cached_tokens
    output_details = value.get("output_tokens_details")
    if isinstance(output_details, Mapping):
        result["output_tokens_details"] = {
            "thinking_tokens": _usage_int(output_details, "reasoning_tokens")
        }
    return result


@dataclass(slots=True)
class _AnthropicStreamState:
    response_id: str = ""
    model: str = ""
    next_block_index: int = 0
    output_blocks: dict[int, int] = field(default_factory=dict)
    text_blocks: dict[tuple[int, int], int] = field(default_factory=dict)
    open_blocks: set[int] = field(default_factory=set)
    reasoning_has_delta: set[int] = field(default_factory=set)

    def update(self, response: Mapping[str, Any]) -> None:
        self.response_id = str(response.get("id") or self.response_id)
        self.model = str(response.get("model") or self.model)

    def new_block(self) -> int:
        index = self.next_block_index
        self.next_block_index += 1
        self.open_blocks.add(index)
        return index


async def responses_stream_to_anthropic_stream(
    raw_iterator: AsyncIterator[bytes], original_model: str
) -> AsyncIterator[bytes]:
    """Convert a Responses API SSE stream into Anthropic Messages events."""
    state = _AnthropicStreamState(model=original_model)
    async for payload in parse_sse_json_stream(raw_iterator):
        event_type = payload.get("type")
        response = payload.get("response")
        if isinstance(response, Mapping):
            state.update(response)

        if event_type == "response.created":
            if not isinstance(response, Mapping):
                raise ValueError("Invalid response.created event")
            yield _anthropic_message_start(state)
            yield format_sse_event("ping", {"type": "ping"})
        elif event_type == "response.reasoning_summary_text.delta":
            for chunk in _reasoning_delta_events(state, payload):
                yield chunk
        elif event_type in {"response.output_text.delta", "response.refusal.delta"}:
            for chunk in _text_delta_events(state, payload):
                yield chunk
        elif event_type == "response.output_item.added":
            for chunk in _output_item_added_events(state, payload):
                yield chunk
        elif event_type == "response.function_call_arguments.delta":
            yield _function_arguments_delta_event(state, payload)
        elif event_type == "response.output_item.done":
            for chunk in _output_item_done_events(state, payload):
                yield chunk
        elif event_type in _TERMINAL_EVENTS:
            if not isinstance(response, Mapping):
                raise ValueError(f"Invalid {event_type} event")
            expected_status = (
                "completed" if event_type == "response.completed" else "incomplete"
            )
            output = _validate_terminal_response(
                response, expected_status=expected_status
            )
            for index in sorted(state.open_blocks):
                yield _content_block_stop(index)
            state.open_blocks.clear()
            has_tool_calls = any(
                isinstance(item, Mapping) and item.get("type") == "function_call"
                for item in output
            )
            has_refusal = _output_has_refusal(output)
            yield format_sse_event(
                "message_delta",
                {
                    "type": "message_delta",
                    "delta": {
                        "stop_reason": _responses_stop_reason(
                            response,
                            has_tool_calls=has_tool_calls,
                            has_refusal=has_refusal,
                        ),
                        "stop_sequence": None,
                    },
                    "usage": _responses_usage_to_anthropic(response.get("usage")),
                },
            )
            yield format_sse_event("message_stop", {"type": "message_stop"})
            return
        elif event_type in {"response.failed", "error"}:
            message = _stream_error_message(payload, response)
            raise ValueError(f"Responses stream failed: {message}")
    raise ValueError("Responses stream ended before terminal event")


def _anthropic_message_start(state: _AnthropicStreamState) -> bytes:
    return format_sse_event(
        "message_start",
        {
            "type": "message_start",
            "message": {
                "id": state.response_id or f"msg_{uuid.uuid4().hex[:24]}",
                "type": "message",
                "role": "assistant",
                "model": state.model,
                "content": [],
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {"input_tokens": 0, "output_tokens": 0},
            },
        },
    )


def _reasoning_delta_events(
    state: _AnthropicStreamState, payload: Mapping[str, Any]
) -> list[bytes]:
    output_index = _event_index(payload, "output_index")
    block_index = state.output_blocks.get(output_index)
    result: list[bytes] = []
    if block_index is None:
        block_index = state.new_block()
        state.output_blocks[output_index] = block_index
        result.append(
            _content_block_start(block_index, {"type": "thinking", "thinking": ""})
        )
    delta = _required_string(
        payload.get("delta"),
        "Responses reasoning summary delta must be a string",
        allow_empty=True,
    )
    state.reasoning_has_delta.add(output_index)
    result.append(
        _content_block_delta(block_index, {"type": "thinking_delta", "thinking": delta})
    )
    return result


def _text_delta_events(
    state: _AnthropicStreamState,
    payload: Mapping[str, Any],
) -> list[bytes]:
    output_index = _event_index(payload, "output_index")
    content_index = _event_index(payload, "content_index")
    key = (output_index, content_index)
    block_index = state.text_blocks.get(key)
    result: list[bytes] = []
    if block_index is None:
        block_index = state.new_block()
        state.text_blocks[key] = block_index
        result.append(_content_block_start(block_index, {"type": "text", "text": ""}))
    result.append(
        _content_block_delta(
            block_index,
            {
                "type": "text_delta",
                "text": _required_string(
                    payload.get("delta"),
                    "Responses text delta must be a string",
                    allow_empty=True,
                ),
            },
        )
    )
    return result


def _output_item_added_events(
    state: _AnthropicStreamState, payload: Mapping[str, Any]
) -> list[bytes]:
    item = payload.get("item")
    if not isinstance(item, Mapping):
        raise ValueError("Responses output_item.added must contain an item")
    if item.get("type") != "function_call":
        return []
    output_index = _event_index(payload, "output_index")
    if output_index in state.output_blocks:
        raise ValueError("Responses output_index was repeated")
    block_index = state.new_block()
    state.output_blocks[output_index] = block_index
    return [
        _content_block_start(
            block_index,
            {
                "type": "tool_use",
                "id": _required_string(
                    item.get("call_id"),
                    "Responses function_call must contain call_id",
                ),
                "name": _required_string(
                    item.get("name"),
                    "Responses function_call must contain name",
                ),
                "input": {},
            },
        )
    ]


def _function_arguments_delta_event(
    state: _AnthropicStreamState, payload: Mapping[str, Any]
) -> bytes:
    output_index = _event_index(payload, "output_index")
    block_index = state.output_blocks.get(output_index)
    if block_index is None:
        raise ValueError("Responses function arguments arrived before function_call")
    return _content_block_delta(
        block_index,
        {
            "type": "input_json_delta",
            "partial_json": _required_string(
                payload.get("delta"),
                "Responses function arguments delta must be a string",
                allow_empty=True,
            ),
        },
    )


def _output_item_done_events(
    state: _AnthropicStreamState, payload: Mapping[str, Any]
) -> list[bytes]:
    item = payload.get("item")
    if not isinstance(item, Mapping):
        raise ValueError("Responses output_item.done must contain an item")
    output_index = _event_index(payload, "output_index")
    item_type = item.get("type")
    if item_type == "reasoning":
        return _reasoning_done_events(state, output_index, item)
    if item_type == "function_call":
        block_index = state.output_blocks.get(output_index)
        return _close_blocks(state, [block_index] if block_index is not None else [])
    if item_type == "message":
        matching = (
            index
            for (item_output_index, _), index in state.text_blocks.items()
            if item_output_index == output_index
        )
        return _close_blocks(state, matching)
    return []


def _reasoning_done_events(
    state: _AnthropicStreamState,
    output_index: int,
    item: Mapping[str, Any],
) -> list[bytes]:
    block_index = state.output_blocks.get(output_index)
    summary = _reasoning_summary_text(item)
    result: list[bytes] = []
    if block_index is None:
        block_index = state.new_block()
        state.output_blocks[output_index] = block_index
        if not summary:
            result.append(
                _content_block_start(block_index, _reasoning_item_to_anthropic(item))
            )
            return result + _close_blocks(state, [block_index])
        result.extend(
            [
                _content_block_start(block_index, {"type": "thinking", "thinking": ""}),
                _content_block_delta(
                    block_index,
                    {"type": "thinking_delta", "thinking": summary},
                ),
            ]
        )
    elif output_index not in state.reasoning_has_delta and summary:
        result.append(
            _content_block_delta(
                block_index,
                {"type": "thinking_delta", "thinking": summary},
            )
        )
    result.append(
        _content_block_delta(
            block_index,
            {
                "type": "signature_delta",
                "signature": _encode_reasoning_item(item),
            },
        )
    )
    return result + _close_blocks(state, [block_index])


def _close_blocks(
    state: _AnthropicStreamState, block_indices: Iterable[int]
) -> list[bytes]:
    result: list[bytes] = []
    for block_index in sorted(block_indices):
        if block_index not in state.open_blocks:
            continue
        result.append(_content_block_stop(block_index))
        state.open_blocks.remove(block_index)
    return result


def _content_block_start(index: int, content_block: dict[str, Any]) -> bytes:
    return format_sse_event(
        "content_block_start",
        {
            "type": "content_block_start",
            "index": index,
            "content_block": content_block,
        },
    )


def _content_block_delta(index: int, delta: dict[str, Any]) -> bytes:
    return format_sse_event(
        "content_block_delta",
        {"type": "content_block_delta", "index": index, "delta": delta},
    )


def _content_block_stop(index: int) -> bytes:
    return format_sse_event(
        "content_block_stop", {"type": "content_block_stop", "index": index}
    )


def _event_index(payload: Mapping[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Responses event must contain {key}")
    return value


def _output_has_refusal(output: list[Any]) -> bool:
    for item in output:
        if not isinstance(item, Mapping) or item.get("type") != "message":
            continue
        content = item.get("content")
        if isinstance(content, list) and any(
            isinstance(part, Mapping) and part.get("type") == "refusal"
            for part in content
        ):
            return True
    return False


def _stream_error_message(payload: Mapping[str, Any], response: Any) -> str:
    if isinstance(response, Mapping):
        error = response.get("error")
        if isinstance(error, Mapping) and isinstance(error.get("message"), str):
            return error["message"]
    error = payload.get("error")
    if isinstance(error, Mapping) and isinstance(error.get("message"), str):
        return error["message"]
    message = payload.get("message")
    return str(message or payload.get("type") or "unknown error")

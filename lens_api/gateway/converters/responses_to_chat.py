from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from typing import Any

from ._responses import (
    _raise_for_failed_response,
    _usage_int,
    _validate_terminal_response,
)
from ._validation import _required_string
from ._sse import format_sse_event, parse_sse_json_stream


def responses_response_to_chat(response: Any, original_model: str) -> dict[str, Any]:
    """Convert a Responses API response into a Chat Completions response."""
    if not isinstance(response, Mapping):
        raise ValueError("Responses upstream response must be an object")
    output = _validate_terminal_response(response)
    message, has_tool_calls = _responses_output_to_chat_message(output)
    result = {
        "id": response.get("id") or "",
        "object": "chat.completion",
        "created": response.get("created_at") or 0,
        "model": response.get("model") or original_model,
        "choices": [
            {
                "index": 0,
                "message": message,
                "logprobs": None,
                "finish_reason": _responses_finish_reason(
                    response, has_tool_calls=has_tool_calls
                ),
            }
        ],
    }
    usage = response.get("usage")
    if isinstance(usage, Mapping):
        result["usage"] = _responses_usage_to_chat(usage)
    return result


def _responses_output_to_chat_message(
    value: list[Any],
) -> tuple[dict[str, Any], bool]:
    text_parts: list[str] = []
    refusal_parts: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise ValueError("Responses upstream output must contain objects")
        if item.get("type") == "message":
            content = item.get("content")
            if not isinstance(content, list):
                raise ValueError("Responses message content must be an array")
            for part in content:
                if not isinstance(part, Mapping):
                    raise ValueError("Responses message content must contain objects")
                if part.get("type") == "output_text":
                    text_parts.append(
                        _required_string(
                            part.get("text"),
                            "Responses output_text must contain text",
                            allow_empty=True,
                        )
                    )
                elif part.get("type") == "refusal":
                    refusal_parts.append(
                        _required_string(
                            part.get("refusal"),
                            "Responses refusal must contain refusal text",
                            allow_empty=True,
                        )
                    )
        elif item.get("type") == "function_call":
            tool_calls.append(
                {
                    "id": _required_string(
                        item.get("call_id"),
                        "Responses function_call must contain call_id",
                    ),
                    "type": "function",
                    "function": {
                        "name": _required_string(
                            item.get("name"),
                            "Responses function_call must contain name",
                        ),
                        "arguments": _required_string(
                            item.get("arguments"),
                            "Responses function_call must contain arguments",
                            allow_empty=True,
                        ),
                    },
                }
            )
    message: dict[str, Any] = {
        "role": "assistant",
        "content": "".join(text_parts) if text_parts else None,
    }
    if refusal_parts:
        message["refusal"] = "".join(refusal_parts)
    if tool_calls:
        message["tool_calls"] = tool_calls
    return message, bool(tool_calls)


def _responses_usage_to_chat(usage: Mapping[str, Any]) -> dict[str, Any]:
    prompt_tokens = _usage_int(usage, "input_tokens")
    completion_tokens = _usage_int(usage, "output_tokens")
    result = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": _usage_int(usage, "total_tokens")
        or prompt_tokens + completion_tokens,
    }
    input_details = usage.get("input_tokens_details")
    if isinstance(input_details, Mapping):
        result["prompt_tokens_details"] = {
            "cached_tokens": _usage_int(input_details, "cached_tokens")
        }
    output_details = usage.get("output_tokens_details")
    if isinstance(output_details, Mapping):
        result["completion_tokens_details"] = {
            "reasoning_tokens": _usage_int(output_details, "reasoning_tokens")
        }
    return result


def _responses_finish_reason(
    response: Mapping[str, Any], *, has_tool_calls: bool
) -> str:
    if response.get("status") == "incomplete":
        details = response.get("incomplete_details")
        reason = details.get("reason") if isinstance(details, Mapping) else None
        return "content_filter" if reason == "content_filter" else "length"
    return "tool_calls" if has_tool_calls else "stop"


@dataclass(slots=True)
class _ChatStreamState:
    response_id: str = ""
    created_at: int = 0
    model: str = ""
    tool_indices: dict[int, int] = field(default_factory=dict)

    def update(self, response: Mapping[str, Any]) -> None:
        self.response_id = str(response.get("id") or self.response_id)
        self.created_at = int(response.get("created_at") or self.created_at)
        self.model = str(response.get("model") or self.model)


async def responses_stream_to_chat_stream(
    raw_iterator: AsyncIterator[bytes],
    original_model: str,
    *,
    include_usage: bool = False,
) -> AsyncIterator[bytes]:
    """Convert a Responses API SSE stream into Chat Completions chunks."""
    state = _ChatStreamState(model=original_model)
    async for payload in parse_sse_json_stream(raw_iterator):
        event_type = payload.get("type")
        response = payload.get("response")
        if isinstance(response, Mapping):
            state.update(response)

        if event_type == "response.created":
            if not isinstance(response, Mapping):
                raise ValueError("Invalid response.created event")
            yield _chat_stream_chunk(state, delta={"role": "assistant", "content": ""})
        elif event_type == "response.output_text.delta":
            yield _chat_stream_chunk(
                state,
                delta={
                    "content": _required_string(
                        payload.get("delta"),
                        "Responses output_text delta must be a string",
                        allow_empty=True,
                    )
                },
            )
        elif event_type == "response.refusal.delta":
            yield _chat_stream_chunk(
                state,
                delta={
                    "refusal": _required_string(
                        payload.get("delta"),
                        "Responses refusal delta must be a string",
                        allow_empty=True,
                    )
                },
            )
        elif event_type == "response.output_item.added":
            chunk = _response_tool_start_chunk(state, payload)
            if chunk is not None:
                yield chunk
        elif event_type == "response.function_call_arguments.delta":
            yield _response_tool_arguments_chunk(state, payload)
        elif event_type in {"response.completed", "response.incomplete"}:
            if not isinstance(response, Mapping):
                raise ValueError(f"Invalid {event_type} event")
            expected_status = (
                "completed" if event_type == "response.completed" else "incomplete"
            )
            output = _validate_terminal_response(
                response, expected_status=expected_status
            )
            has_tool_calls = bool(state.tool_indices) or _output_has_tool_calls(output)
            yield _chat_stream_chunk(
                state,
                delta={},
                finish_reason=_responses_finish_reason(
                    response, has_tool_calls=has_tool_calls
                ),
            )
            usage = response.get("usage")
            if include_usage and isinstance(usage, Mapping):
                yield _chat_stream_usage_chunk(state, _responses_usage_to_chat(usage))
            yield b"data: [DONE]\n\n"
            return
        elif event_type in {"response.failed", "error"}:
            if isinstance(response, Mapping):
                _raise_for_failed_response(response)
            error = payload.get("error")
            message = error.get("message") if isinstance(error, Mapping) else None
            message = message or payload.get("message")
            raise ValueError(f"Responses stream failed: {message or event_type}")
    raise ValueError("Responses stream ended before terminal event")


def _response_tool_start_chunk(
    state: _ChatStreamState, payload: Mapping[str, Any]
) -> bytes | None:
    item = payload.get("item")
    if not isinstance(item, Mapping):
        raise ValueError("Responses output_item.added must contain an item")
    if item.get("type") != "function_call":
        return None
    output_index = payload.get("output_index")
    if isinstance(output_index, bool) or not isinstance(output_index, int):
        raise ValueError("Responses function_call must contain output_index")
    if output_index in state.tool_indices:
        raise ValueError("Responses function_call output_index was repeated")
    tool_index = len(state.tool_indices)
    state.tool_indices[output_index] = tool_index
    return _chat_stream_chunk(
        state,
        delta={
            "tool_calls": [
                {
                    "index": tool_index,
                    "id": _required_string(
                        item.get("call_id"),
                        "Responses function_call must contain call_id",
                    ),
                    "type": "function",
                    "function": {
                        "name": _required_string(
                            item.get("name"),
                            "Responses function_call must contain name",
                        ),
                        "arguments": "",
                    },
                }
            ]
        },
    )


def _response_tool_arguments_chunk(
    state: _ChatStreamState, payload: Mapping[str, Any]
) -> bytes:
    output_index = payload.get("output_index")
    if isinstance(output_index, bool) or not isinstance(output_index, int):
        raise ValueError("Responses function arguments must contain output_index")
    if output_index not in state.tool_indices:
        raise ValueError("Responses function arguments arrived before function_call")
    return _chat_stream_chunk(
        state,
        delta={
            "tool_calls": [
                {
                    "index": state.tool_indices[output_index],
                    "function": {
                        "arguments": _required_string(
                            payload.get("delta"),
                            "Responses function arguments delta must be a string",
                            allow_empty=True,
                        )
                    },
                }
            ]
        },
    )


def _output_has_tool_calls(output: list[Any]) -> bool:
    return any(
        isinstance(item, Mapping) and item.get("type") == "function_call"
        for item in output
    )


def _chat_stream_chunk(
    state: _ChatStreamState,
    *,
    delta: dict[str, Any],
    finish_reason: str | None = None,
) -> bytes:
    return format_sse_event(
        None,
        {
            **_chat_stream_base(state),
            "choices": [
                {
                    "index": 0,
                    "delta": delta,
                    "logprobs": None,
                    "finish_reason": finish_reason,
                }
            ],
        },
    )


def _chat_stream_usage_chunk(state: _ChatStreamState, usage: dict[str, Any]) -> bytes:
    return format_sse_event(
        None, {**_chat_stream_base(state), "choices": [], "usage": usage}
    )


def _chat_stream_base(state: _ChatStreamState) -> dict[str, Any]:
    return {
        "id": state.response_id,
        "object": "chat.completion.chunk",
        "created": state.created_at,
        "model": state.model,
    }

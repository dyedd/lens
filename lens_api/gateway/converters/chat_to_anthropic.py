import uuid
from typing import Any, AsyncIterator

from ._shared import (
    anthropic_content_to_chat_messages,
    anthropic_tool_choice_to_chat,
    anthropic_tools_to_chat_tools,
    chat_tool_calls_to_anthropic_content,
)
from ._sse import (
    FINISH_REASON_CHAT_TO_ANTHROPIC,
    format_sse_event,
    parse_chat_sse_stream,
)


def anthropic_request_to_chat(
    body: dict[str, Any], *, preserve_thinking: bool = False
) -> dict[str, Any]:
    """Convert an Anthropic request into a chat request."""
    chat: dict[str, Any] = {}

    messages: list[dict[str, Any]] = []
    system = body.get("system")
    if system:
        if isinstance(system, str):
            messages.append({"role": "system", "content": system})
        elif isinstance(system, list):
            text = "\n".join(b.get("text", "") for b in system if isinstance(b, dict))
            if text:
                messages.append({"role": "system", "content": text})

    src_messages = body.get("messages", [])
    messages.extend(
        anthropic_content_to_chat_messages(
            src_messages, preserve_thinking=preserve_thinking
        )
    )
    chat["messages"] = messages

    if "max_tokens" in body:
        chat["max_tokens"] = body["max_tokens"]
    for key in ("temperature", "top_p", "stream"):
        if key in body:
            chat[key] = body[key]
    if "stop_sequences" in body:
        chat["stop"] = body["stop_sequences"]

    if "tools" in body:
        chat["tools"] = anthropic_tools_to_chat_tools(body["tools"])
    if "tool_choice" in body:
        tool_choice = anthropic_tool_choice_to_chat(body["tool_choice"])
        if tool_choice is not None:
            chat["tool_choice"] = tool_choice

    return chat


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
        content.extend(chat_tool_calls_to_anthropic_content(tool_calls))

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
    msg_id = f"msg_{uuid.uuid4().hex[:24]}"
    output_tokens = 0
    has_text_started = False
    thinking_index: int | None = None
    tool_index: dict[str, int] = {}
    next_block_index = 0
    finish_reason: str | None = None

    yield format_sse_event(
        "message_start",
        {
            "type": "message_start",
            "message": {
                "id": msg_id,
                "type": "message",
                "role": "assistant",
                "model": original_model,
                "content": [],
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {"input_tokens": 0, "output_tokens": 0},
            },
        },
    )
    yield format_sse_event("ping", {"type": "ping"})

    async for payload in parse_chat_sse_stream(raw_iterator):
        usage = payload.get("usage") or {}
        if usage.get("completion_tokens"):
            output_tokens = usage["completion_tokens"]

        for choice in payload.get("choices", []):
            finish_reason = choice.get("finish_reason") or finish_reason
            delta = choice.get("delta", {})
            reasoning_delta = _chat_delta_reasoning_content(delta)
            text_delta = delta.get("content")
            tc_deltas = delta.get("tool_calls")

            if reasoning_delta is not None:
                if thinking_index is None:
                    thinking_index = next_block_index
                    next_block_index += 1
                    yield format_sse_event(
                        "content_block_start",
                        {
                            "type": "content_block_start",
                            "index": thinking_index,
                            "content_block": {"type": "thinking", "thinking": ""},
                        },
                    )
                if reasoning_delta:
                    yield format_sse_event(
                        "content_block_delta",
                        {
                            "type": "content_block_delta",
                            "index": thinking_index,
                            "delta": {
                                "type": "thinking_delta",
                                "thinking": reasoning_delta,
                            },
                        },
                    )

            if text_delta:
                if not has_text_started:
                    has_text_started = True
                    yield format_sse_event(
                        "content_block_start",
                        {
                            "type": "content_block_start",
                            "index": next_block_index,
                            "content_block": {"type": "text", "text": ""},
                        },
                    )
                    next_block_index += 1
                yield format_sse_event(
                    "content_block_delta",
                    {
                        "type": "content_block_delta",
                        "index": next_block_index - 1,
                        "delta": {"type": "text_delta", "text": text_delta},
                    },
                )

            if tc_deltas:
                for tool_call in tc_deltas:
                    call_id = tool_call.get("id") or ""
                    tc_idx = tool_call.get("index", 0)
                    key = call_id or str(tc_idx)
                    if key not in tool_index:
                        func = tool_call.get("function", {})
                        tool_index[key] = next_block_index
                        next_block_index += 1
                        yield format_sse_event(
                            "content_block_start",
                            {
                                "type": "content_block_start",
                                "index": tool_index[key],
                                "content_block": {
                                    "type": "tool_use",
                                    "id": call_id or f"toolu_{uuid.uuid4().hex[:24]}",
                                    "name": func.get("name", ""),
                                    "input": {},
                                },
                            },
                        )
                    args_delta = (tool_call.get("function") or {}).get("arguments", "")
                    if args_delta:
                        yield format_sse_event(
                            "content_block_delta",
                            {
                                "type": "content_block_delta",
                                "index": tool_index[key],
                                "delta": {
                                    "type": "input_json_delta",
                                    "partial_json": args_delta,
                                },
                            },
                        )

    for i in range(next_block_index):
        yield format_sse_event(
            "content_block_stop",
            {
                "type": "content_block_stop",
                "index": i,
            },
        )

    stop_reason = FINISH_REASON_CHAT_TO_ANTHROPIC.get(finish_reason, "end_turn")
    yield format_sse_event(
        "message_delta",
        {
            "type": "message_delta",
            "delta": {"stop_reason": stop_reason, "stop_sequence": None},
            "usage": {"output_tokens": output_tokens},
        },
    )
    yield format_sse_event("message_stop", {"type": "message_stop"})


def _chat_message_reasoning_content(message: dict[str, Any]) -> tuple[bool, str]:
    for key in ("reasoning_content", "reasoning"):
        if key not in message:
            continue
        value = message.get(key)
        if isinstance(value, str):
            return True, value
    return False, ""


def _chat_delta_reasoning_content(delta: dict[str, Any]) -> str | None:
    for key in ("reasoning_content", "reasoning"):
        if key not in delta:
            continue
        value = delta.get(key)
        if isinstance(value, str):
            return value
    return None

"""Convert between Anthropic Messages API and OpenAI Chat Completions.

Direction: client speaks Anthropic, upstream speaks OpenAI Chat.
- anthropic_request_to_chat(): transform inbound Anthropic request → Chat request
- chat_response_to_anthropic(): transform Chat response → Anthropic response
- chat_stream_to_anthropic_stream(): transform Chat SSE stream → Anthropic SSE stream
"""

from __future__ import annotations

import json
import uuid
from typing import Any, AsyncIterator

from ._shared import (
    FINISH_REASON_CHAT_TO_ANTHROPIC,
    anthropic_content_to_chat_messages,
    anthropic_tool_choice_to_chat,
    anthropic_tools_to_chat_tools,
    chat_tool_calls_to_anthropic_content,
    format_sse_event,
)


def anthropic_request_to_chat(body: dict[str, Any]) -> dict[str, Any]:
    chat: dict[str, Any] = {}

    messages: list[dict[str, Any]] = []
    system = body.get("system")
    if system:
        if isinstance(system, str):
            messages.append({"role": "system", "content": system})
        elif isinstance(system, list):
            text = "\n".join(
                b.get("text", "") for b in system if isinstance(b, dict)
            )
            if text:
                messages.append({"role": "system", "content": text})

    src_messages = body.get("messages", [])
    messages.extend(anthropic_content_to_chat_messages(src_messages))
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
        tc = anthropic_tool_choice_to_chat(body["tool_choice"])
        if tc is not None:
            chat["tool_choice"] = tc

    return chat


def chat_response_to_anthropic(chat_body: dict[str, Any], original_model: str) -> dict[str, Any]:
    choice = (chat_body.get("choices") or [{}])[0]
    message = choice.get("message", {})
    finish_reason = choice.get("finish_reason")
    stop_reason = FINISH_REASON_CHAT_TO_ANTHROPIC.get(finish_reason, "end_turn")

    content: list[dict[str, Any]] = []
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
    msg_id = f"msg_{uuid.uuid4().hex[:24]}"
    input_tokens = 0
    output_tokens = 0
    resolved_model = original_model
    text_started = False
    tool_index: dict[str, int] = {}  # call_id -> content block index
    next_block_index = 0

    yield format_sse_event("message_start", {
        "type": "message_start",
        "message": {
            "id": msg_id,
            "type": "message",
            "role": "assistant",
            "model": resolved_model,
            "content": [],
            "stop_reason": None,
            "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 0},
        },
    })
    yield format_sse_event("ping", {"type": "ping"})

    finish_reason: str | None = None
    buffer = b""

    async for chunk in raw_iterator:
        buffer += chunk
        while b"\n" in buffer:
            line, buffer = buffer.split(b"\n", 1)
            line_str = line.decode("utf-8", errors="replace").strip()
            if not line_str.startswith("data:"):
                continue
            data_str = line_str[5:].strip()
            if data_str == "[DONE]":
                break
            try:
                payload = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            if payload.get("model"):
                resolved_model = payload["model"]
            usage = payload.get("usage") or {}
            if usage.get("prompt_tokens"):
                input_tokens = usage["prompt_tokens"]
            if usage.get("completion_tokens"):
                output_tokens = usage["completion_tokens"]

            for choice in payload.get("choices", []):
                finish_reason = choice.get("finish_reason") or finish_reason
                delta = choice.get("delta", {})
                text_delta = delta.get("content")
                tc_deltas = delta.get("tool_calls")

                if text_delta:
                    if not text_started:
                        text_started = True
                        yield format_sse_event("content_block_start", {
                            "type": "content_block_start",
                            "index": next_block_index,
                            "content_block": {"type": "text", "text": ""},
                        })
                        next_block_index += 1
                    yield format_sse_event("content_block_delta", {
                        "type": "content_block_delta",
                        "index": next_block_index - 1,
                        "delta": {"type": "text_delta", "text": text_delta},
                    })

                if tc_deltas:
                    for tc in tc_deltas:
                        call_id = tc.get("id") or ""
                        tc_idx = tc.get("index", 0)
                        key = call_id or str(tc_idx)
                        if key not in tool_index:
                            func = tc.get("function", {})
                            tool_index[key] = next_block_index
                            next_block_index += 1
                            yield format_sse_event("content_block_start", {
                                "type": "content_block_start",
                                "index": tool_index[key],
                                "content_block": {
                                    "type": "tool_use",
                                    "id": call_id or f"toolu_{uuid.uuid4().hex[:24]}",
                                    "name": func.get("name", ""),
                                    "input": {},
                                },
                            })
                        args_delta = (tc.get("function") or {}).get("arguments", "")
                        if args_delta:
                            yield format_sse_event("content_block_delta", {
                                "type": "content_block_delta",
                                "index": tool_index[key],
                                "delta": {"type": "input_json_delta", "partial_json": args_delta},
                            })

    # close open blocks
    for i in range(next_block_index):
        yield format_sse_event("content_block_stop", {
            "type": "content_block_stop",
            "index": i,
        })

    stop_reason = FINISH_REASON_CHAT_TO_ANTHROPIC.get(finish_reason, "end_turn")
    yield format_sse_event("message_delta", {
        "type": "message_delta",
        "delta": {"stop_reason": stop_reason, "stop_sequence": None},
        "usage": {"output_tokens": output_tokens},
    })
    yield format_sse_event("message_stop", {"type": "message_stop"})

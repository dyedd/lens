from __future__ import annotations

import json
import time
import uuid
from typing import Any, AsyncIterator

from ._shared import (
    FINISH_REASON_CHAT_TO_RESPONSES,
    chat_tool_calls_to_anthropic_content,
    format_sse_event,
    responses_input_to_chat_messages,
    responses_tools_to_chat_tools,
)


def responses_request_to_chat(body: dict[str, Any]) -> dict[str, Any]:
    chat: dict[str, Any] = {}

    messages: list[dict[str, Any]] = []
    instructions = body.get("instructions")
    if instructions:
        messages.append({"role": "system", "content": instructions})

    input_val = body.get("input", [])
    if isinstance(input_val, str):
        messages.append({"role": "user", "content": input_val})
    elif isinstance(input_val, list):
        messages.extend(responses_input_to_chat_messages(input_val))
    chat["messages"] = messages

    if "max_output_tokens" in body:
        chat["max_tokens"] = body["max_output_tokens"]
    for key in ("temperature", "top_p", "stream"):
        if key in body:
            chat[key] = body[key]

    if "tools" in body:
        chat["tools"] = responses_tools_to_chat_tools(body["tools"])
    if "tool_choice" in body:
        chat["tool_choice"] = body["tool_choice"]

    return chat


def chat_response_to_responses(
    chat_body: dict[str, Any], original_model: str
) -> dict[str, Any]:
    choice = (chat_body.get("choices") or [{}])[0]
    message = choice.get("message", {})
    finish_reason = choice.get("finish_reason")
    status = FINISH_REASON_CHAT_TO_RESPONSES.get(finish_reason, "completed")

    output: list[dict[str, Any]] = []
    msg_item: dict[str, Any] = {
        "id": f"msg_{uuid.uuid4().hex[:24]}",
        "type": "message",
        "status": "completed",
        "role": "assistant",
        "content": [],
    }
    text = message.get("content")
    if text:
        msg_item["content"].append(
            {
                "type": "output_text",
                "text": text,
                "annotations": [],
            }
        )
    output.append(msg_item)

    tool_calls = message.get("tool_calls")
    if tool_calls:
        for tc in tool_calls:
            func = tc.get("function", {})
            output.append(
                {
                    "id": f"fc_{uuid.uuid4().hex[:24]}",
                    "type": "function_call",
                    "status": "completed",
                    "name": func.get("name", ""),
                    "arguments": func.get("arguments", "{}"),
                    "call_id": tc.get("id", ""),
                }
            )

    usage = chat_body.get("usage", {})
    inp = usage.get("prompt_tokens", 0)
    out = usage.get("completion_tokens", 0)
    return {
        "id": chat_body.get("id", f"resp_{uuid.uuid4().hex[:24]}"),
        "object": "response",
        "created_at": int(time.time()),
        "model": chat_body.get("model", original_model),
        "status": status,
        "output": output,
        "usage": {
            "input_tokens": inp,
            "output_tokens": out,
            "total_tokens": inp + out,
        },
    }


async def chat_stream_to_responses_stream(
    raw_iterator: AsyncIterator[bytes],
    original_model: str,
) -> AsyncIterator[bytes]:
    resp_id = f"resp_{uuid.uuid4().hex[:24]}"
    msg_id = f"msg_{uuid.uuid4().hex[:24]}"
    resolved_model = original_model
    input_tokens = 0
    output_tokens = 0
    text_started = False
    tool_calls_by_idx: dict[int, dict[str, Any]] = {}
    next_output_index = 0
    finish_reason: str | None = None

    # response.created
    yield format_sse_event(
        "response.created",
        {
            "type": "response.created",
            "response": {
                "id": resp_id,
                "object": "response",
                "created_at": int(time.time()),
                "model": resolved_model,
                "status": "in_progress",
                "output": [],
                "usage": None,
            },
        },
    )

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
                        oi = next_output_index
                        next_output_index += 1
                        yield format_sse_event(
                            "response.output_item.added",
                            {
                                "type": "response.output_item.added",
                                "output_index": oi,
                                "item": {
                                    "id": msg_id,
                                    "type": "message",
                                    "status": "in_progress",
                                    "role": "assistant",
                                    "content": [],
                                },
                            },
                        )
                        yield format_sse_event(
                            "response.content_part.added",
                            {
                                "type": "response.content_part.added",
                                "output_index": oi,
                                "content_index": 0,
                                "part": {
                                    "type": "output_text",
                                    "text": "",
                                    "annotations": [],
                                },
                            },
                        )
                    yield format_sse_event(
                        "response.output_text.delta",
                        {
                            "type": "response.output_text.delta",
                            "output_index": 0,
                            "content_index": 0,
                            "delta": text_delta,
                        },
                    )

                if tc_deltas:
                    for tc in tc_deltas:
                        tc_idx = tc.get("index", 0)
                        if tc_idx not in tool_calls_by_idx:
                            func = tc.get("function", {})
                            call_id = tc.get("id") or f"call_{uuid.uuid4().hex[:24]}"
                            oi = next_output_index
                            next_output_index += 1
                            tool_calls_by_idx[tc_idx] = {
                                "output_index": oi,
                                "call_id": call_id,
                                "name": func.get("name", ""),
                                "arguments": "",
                            }
                            yield format_sse_event(
                                "response.output_item.added",
                                {
                                    "type": "response.output_item.added",
                                    "output_index": oi,
                                    "item": {
                                        "id": f"fc_{uuid.uuid4().hex[:24]}",
                                        "type": "function_call",
                                        "status": "in_progress",
                                        "name": func.get("name", ""),
                                        "arguments": "",
                                        "call_id": call_id,
                                    },
                                },
                            )
                        args_delta = (tc.get("function") or {}).get("arguments", "")
                        if args_delta:
                            info = tool_calls_by_idx[tc_idx]
                            info["arguments"] += args_delta
                            yield format_sse_event(
                                "response.function_call_arguments.delta",
                                {
                                    "type": "response.function_call_arguments.delta",
                                    "output_index": info["output_index"],
                                    "delta": args_delta,
                                },
                            )

    # finalize
    status = FINISH_REASON_CHAT_TO_RESPONSES.get(finish_reason, "completed")
    total = input_tokens + output_tokens
    yield format_sse_event(
        "response.completed",
        {
            "type": "response.completed",
            "response": {
                "id": resp_id,
                "object": "response",
                "created_at": int(time.time()),
                "model": resolved_model,
                "status": status,
                "output": [],
                "usage": {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total,
                },
            },
        },
    )
    yield b"data: [DONE]\n\n"

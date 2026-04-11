"""Shared utilities for protocol conversion between OpenAI Chat and other formats."""

from __future__ import annotations

import json
from typing import Any


FINISH_REASON_CHAT_TO_ANTHROPIC: dict[str | None, str] = {
    "stop": "end_turn",
    "length": "max_tokens",
    "tool_calls": "tool_use",
    "content_filter": "end_turn",
}

FINISH_REASON_CHAT_TO_RESPONSES: dict[str | None, str] = {
    "stop": "completed",
    "length": "incomplete",
    "tool_calls": "completed",
    "content_filter": "failed",
}


def anthropic_content_to_chat_messages(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content")

        if isinstance(content, str):
            result.append({"role": role, "content": content})
            continue
        if not isinstance(content, list):
            result.append({"role": role, "content": content})
            continue

        text_parts: list[str] = []
        image_parts: list[dict[str, Any]] = []
        tool_calls: list[dict[str, Any]] = []
        tool_results: list[dict[str, Any]] = []

        for block in content:
            bt = block.get("type")
            if bt == "text":
                text_parts.append(block.get("text", ""))
            elif bt == "image":
                source = block.get("source", {})
                if source.get("type") == "base64":
                    mt = source.get("media_type", "image/png")
                    data = source.get("data", "")
                    image_parts.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{mt};base64,{data}"},
                    })
                elif source.get("type") == "url":
                    image_parts.append({
                        "type": "image_url",
                        "image_url": {"url": source.get("url", "")},
                    })
            elif bt == "tool_use":
                tool_calls.append({
                    "id": block.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": block.get("name", ""),
                        "arguments": json.dumps(block.get("input", {}), ensure_ascii=False),
                    },
                })
            elif bt == "tool_result":
                trc = block.get("content", "")
                if isinstance(trc, list):
                    trc = "\n".join(
                        p.get("text", "") for p in trc
                        if isinstance(p, dict) and p.get("type") == "text"
                    )
                tool_results.append({
                    "role": "tool",
                    "tool_call_id": block.get("tool_use_id", ""),
                    "content": str(trc),
                })

        if role == "assistant" and tool_calls:
            msg_out: dict[str, Any] = {"role": "assistant", "content": None}
            if text_parts:
                msg_out["content"] = "\n".join(text_parts)
            msg_out["tool_calls"] = tool_calls
            result.append(msg_out)
        elif image_parts:
            parts_out: list[dict[str, Any]] = []
            if text_parts:
                parts_out.append({"type": "text", "text": "\n".join(text_parts)})
            parts_out.extend(image_parts)
            result.append({"role": role, "content": parts_out})
        elif text_parts:
            result.append({"role": role, "content": "\n".join(text_parts)})

        for tr in tool_results:
            result.append(tr)

    return result


def anthropic_tools_to_chat_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": t.get("name", ""),
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {}),
            },
        }
        for t in tools
    ]


def anthropic_tool_choice_to_chat(tool_choice: Any) -> Any:
    if not isinstance(tool_choice, dict):
        return None
    ct = tool_choice.get("type", "auto")
    if ct == "auto":
        return "auto"
    if ct == "any":
        return "required"
    if ct == "tool":
        return {"type": "function", "function": {"name": tool_choice.get("name", "")}}
    if ct == "none":
        return "none"
    return "auto"


def chat_tool_calls_to_anthropic_content(tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for tc in tool_calls:
        func = tc.get("function", {})
        try:
            parsed_input = json.loads(func.get("arguments", "{}"))
        except (json.JSONDecodeError, TypeError):
            parsed_input = {}
        blocks.append({
            "type": "tool_use",
            "id": tc.get("id", ""),
            "name": func.get("name", ""),
            "input": parsed_input,
        })
    return blocks


def responses_input_to_chat_messages(input_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in input_items:
        role = item.get("role", "user")
        content = item.get("content")
        item_type = item.get("type")

        if item_type == "function_call_output":
            result.append({
                "role": "tool",
                "tool_call_id": item.get("call_id", ""),
                "content": item.get("output", ""),
            })
            continue

        if item_type == "function_call":
            result.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": item.get("call_id", ""),
                    "type": "function",
                    "function": {
                        "name": item.get("name", ""),
                        "arguments": item.get("arguments", "{}"),
                    },
                }],
            })
            continue

        if isinstance(content, str):
            result.append({"role": role, "content": content})
            continue

        if isinstance(content, list):
            text_parts: list[str] = []
            image_parts: list[dict[str, Any]] = []
            for block in content:
                btype = block.get("type", "")
                if btype in ("input_text", "output_text", "text"):
                    text_parts.append(block.get("text", ""))
                elif btype == "input_image":
                    url = block.get("image_url", "")
                    if isinstance(url, dict):
                        url = url.get("url", "")
                    image_parts.append({"type": "image_url", "image_url": {"url": url}})
            if image_parts:
                parts_out: list[dict[str, Any]] = []
                if text_parts:
                    parts_out.append({"type": "text", "text": "\n".join(text_parts)})
                parts_out.extend(image_parts)
                result.append({"role": role, "content": parts_out})
            elif text_parts:
                result.append({"role": role, "content": "\n".join(text_parts)})
            continue

        if role or content is not None:
            result.append({"role": role or "user", "content": content})

    return result


def responses_tools_to_chat_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for tool in tools:
        if tool.get("type") != "function":
            continue
        func_def: dict[str, Any] = {"name": tool.get("name", "")}
        if "description" in tool:
            func_def["description"] = tool["description"]
        if "parameters" in tool:
            func_def["parameters"] = tool["parameters"]
        entry: dict[str, Any] = {"type": "function", "function": func_def}
        if tool.get("strict") is not None:
            entry["function"]["strict"] = tool["strict"]
        result.append(entry)
    return result


def format_sse_event(event: str | None, data: dict[str, Any] | str) -> bytes:
    lines: list[str] = []
    if event:
        lines.append(f"event: {event}")
    if isinstance(data, dict):
        lines.append(f"data: {json.dumps(data, ensure_ascii=False)}")
    else:
        lines.append(f"data: {data}")
    lines.append("")
    lines.append("")
    return "\n".join(lines).encode("utf-8")

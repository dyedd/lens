import json
from typing import Any


def _build_chat_tool_call(call_id: str, name: str, arguments: str) -> dict[str, Any]:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }


def _build_chat_image_part(url: str) -> dict[str, Any]:
    return {"type": "image_url", "image_url": {"url": url}}


def _assemble_content_parts(
    text_parts: list[str], image_parts: list[dict[str, Any]]
) -> list[dict[str, Any]] | str:
    if not image_parts:
        return "\n".join(text_parts)
    parts: list[dict[str, Any]] = []
    if text_parts:
        parts.append({"type": "text", "text": "\n".join(text_parts)})
    parts.extend(image_parts)
    return parts


def anthropic_content_to_chat_messages(
    messages: list[dict[str, Any]],
    *,
    preserve_thinking: bool = False,
) -> list[dict[str, Any]]:
    """Convert Anthropic message content into chat messages."""
    result: list[dict[str, Any]] = []
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content")

        if not isinstance(content, list):
            result.append({"role": role, "content": content})
            continue

        text_parts: list[str] = []
        thinking_parts: list[str] = []
        has_thinking = False
        image_parts: list[dict[str, Any]] = []
        tool_calls: list[dict[str, Any]] = []
        tool_results: list[dict[str, Any]] = []

        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "text":
                text_parts.append(block.get("text", ""))
            elif block_type == "thinking":
                has_thinking = True
                thinking = block.get("thinking")
                thinking_parts.append(thinking if isinstance(thinking, str) else "")
            elif block_type == "image":
                source = block.get("source", {})
                if source.get("type") == "base64":
                    media_type = source.get("media_type", "image/png")
                    data = source.get("data", "")
                    image_parts.append(
                        _build_chat_image_part(f"data:{media_type};base64,{data}")
                    )
                elif source.get("type") == "url":
                    image_parts.append(_build_chat_image_part(source.get("url", "")))
            elif block_type == "tool_use":
                tool_calls.append(
                    _build_chat_tool_call(
                        block.get("id", ""),
                        block.get("name", ""),
                        json.dumps(block.get("input", {}), ensure_ascii=False),
                    )
                )
            elif block_type == "tool_result":
                tool_result_content = block.get("content", "")
                if isinstance(tool_result_content, list):
                    tool_result_content = "\n".join(
                        p.get("text", "")
                        for p in tool_result_content
                        if isinstance(p, dict) and p.get("type") == "text"
                    )
                tool_results.append(
                    {
                        "role": "tool",
                        "tool_call_id": block.get("tool_use_id", ""),
                        "content": str(tool_result_content),
                    }
                )

        if role == "assistant" and tool_calls:
            msg_out: dict[str, Any] = {"role": "assistant", "content": None}
            if text_parts:
                msg_out["content"] = "\n".join(text_parts)
            if preserve_thinking and has_thinking:
                msg_out["reasoning_content"] = "\n".join(thinking_parts)
            msg_out["tool_calls"] = tool_calls
            result.append(msg_out)
        elif image_parts or text_parts:
            msg_out = {
                "role": role,
                "content": _assemble_content_parts(text_parts, image_parts),
            }
            if role == "assistant" and preserve_thinking and has_thinking:
                msg_out["reasoning_content"] = "\n".join(thinking_parts)
            result.append(msg_out)
        elif role == "assistant" and preserve_thinking and has_thinking:
            result.append(
                {
                    "role": "assistant",
                    "content": None,
                    "reasoning_content": "\n".join(thinking_parts),
                }
            )

        for tool_result in tool_results:
            result.append(tool_result)

    return result


def anthropic_tools_to_chat_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert Anthropic tool definitions into chat tool definitions."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool.get("name", ""),
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema", {}),
            },
        }
        for tool in tools
    ]


def anthropic_tool_choice_to_chat(tool_choice: Any) -> Any:
    """Convert an Anthropic tool choice into the chat format."""
    if not isinstance(tool_choice, dict):
        return None
    choice_type = tool_choice.get("type", "auto")
    if choice_type == "auto":
        return "auto"
    if choice_type == "any":
        return "required"
    if choice_type == "tool":
        return {"type": "function", "function": {"name": tool_choice.get("name", "")}}
    if choice_type == "none":
        return "none"
    return "auto"


def chat_tool_calls_to_anthropic_content(
    tool_calls: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert chat tool calls into Anthropic content blocks."""
    blocks: list[dict[str, Any]] = []
    for tool_call in tool_calls:
        func = tool_call.get("function", {})
        try:
            parsed_input = json.loads(func.get("arguments", "{}"))
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValueError("Invalid tool call arguments JSON") from exc
        blocks.append(
            {
                "type": "tool_use",
                "id": tool_call.get("id", ""),
                "name": func.get("name", ""),
                "input": parsed_input,
            }
        )
    return blocks


def responses_input_to_chat_messages(
    input_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert Responses API input items into chat messages."""
    result: list[dict[str, Any]] = []
    for item in input_items:
        role = item.get("role", "user")
        content = item.get("content")
        item_type = item.get("type")

        if item_type == "function_call_output":
            result.append(
                {
                    "role": "tool",
                    "tool_call_id": item.get("call_id", ""),
                    "content": item.get("output", ""),
                }
            )
            continue

        if item_type == "function_call":
            result.append(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        _build_chat_tool_call(
                            item.get("call_id", ""),
                            item.get("name", ""),
                            item.get("arguments", "{}"),
                        )
                    ],
                }
            )
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
                    image_parts.append(_build_chat_image_part(url))
            if image_parts or text_parts:
                result.append(
                    {
                        "role": role,
                        "content": _assemble_content_parts(text_parts, image_parts),
                    }
                )
            continue

        if role or content is not None:
            result.append({"role": role or "user", "content": content})

    return result


def responses_tools_to_chat_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert Responses API tools into chat tool definitions."""
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

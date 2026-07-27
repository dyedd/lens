from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ._validation import _required_string


def responses_request_to_chat(body: dict[str, Any]) -> dict[str, Any]:
    """Convert a Responses API request into a chat request."""
    messages: list[dict[str, Any]] = []
    instructions = body.get("instructions")
    if instructions is not None and not isinstance(instructions, str):
        raise ValueError("Responses instructions must be a string")
    if instructions:
        messages.append({"role": "system", "content": instructions})

    input_value = body.get("input", [])
    if isinstance(input_value, str):
        messages.append({"role": "user", "content": input_value})
    elif isinstance(input_value, list):
        messages.extend(_responses_input_to_chat_messages(input_value))
    else:
        raise ValueError("Responses input must be a string or array")

    chat: dict[str, Any] = {"messages": messages}
    if "max_output_tokens" in body:
        chat["max_tokens"] = body["max_output_tokens"]
    for key in ("temperature", "top_p", "stream", "parallel_tool_calls"):
        if key in body:
            chat[key] = body[key]
    if "tools" in body:
        chat["tools"] = _responses_tools_to_chat(body["tools"])
    if "tool_choice" in body:
        chat["tool_choice"] = _responses_tool_choice_to_chat(body["tool_choice"])

    reasoning_effort = _responses_reasoning_effort(body.get("reasoning"))
    if reasoning_effort is not None:
        chat["reasoning_effort"] = reasoning_effort
    response_format = _responses_text_format_to_chat(body.get("text"))
    if response_format is not None:
        chat["response_format"] = response_format
    return chat


def _responses_input_to_chat_messages(
    input_items: list[Any],
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    pending_tool_calls: list[dict[str, Any]] = []

    def flush_tool_calls() -> None:
        if not pending_tool_calls:
            return
        messages.append(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": list(pending_tool_calls),
            }
        )
        pending_tool_calls.clear()

    for item in input_items:
        if not isinstance(item, Mapping):
            raise ValueError("Responses input must contain objects")
        item_type = item.get("type")
        if item_type == "function_call":
            pending_tool_calls.append(_responses_function_call_to_chat(item))
            continue

        flush_tool_calls()
        if item_type == "function_call_output":
            messages.append(_responses_function_output_to_chat(item))
        else:
            messages.append(_responses_message_to_chat(item))

    flush_tool_calls()
    return _place_tool_outputs(messages)


def _responses_function_call_to_chat(item: Mapping[str, Any]) -> dict[str, Any]:
    return _build_chat_tool_call(
        _required_string(
            item.get("call_id"),
            "Responses function_call must contain call_id",
        ),
        _required_string(item.get("name"), "Responses function_call must contain name"),
        _required_string(
            item.get("arguments"),
            "Responses function_call must contain arguments",
            allow_empty=True,
        ),
    )


def _responses_function_output_to_chat(
    item: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "role": "tool",
        "tool_call_id": _required_string(
            item.get("call_id"),
            "Responses function_call_output must contain call_id",
        ),
        "content": _responses_tool_output_to_chat(item.get("output")),
    }


def _responses_message_to_chat(item: Mapping[str, Any]) -> dict[str, Any]:
    item_type = item.get("type")
    if item_type not in {None, "message"}:
        raise ValueError(f"Unsupported Responses input item type: {item_type}")
    role = item.get("role")
    if role not in {"developer", "system", "user", "assistant"}:
        raise ValueError("Responses messages must contain a valid role")
    return {
        "role": role,
        "content": _responses_content_to_chat(item.get("content")),
    }


def _place_tool_outputs(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    consumed: set[int] = set()
    for index, message in enumerate(messages):
        if index in consumed:
            continue
        result.append(message)
        tool_calls = message.get("tool_calls")
        if not isinstance(tool_calls, list):
            continue
        for tool_call in tool_calls:
            call_id = tool_call.get("id") if isinstance(tool_call, Mapping) else None
            output_index = _find_tool_output(
                messages, call_id, after=index, consumed=consumed
            )
            if output_index is not None:
                result.append(messages[output_index])
                consumed.add(output_index)
    return result


def _find_tool_output(
    messages: list[dict[str, Any]],
    call_id: Any,
    *,
    after: int,
    consumed: set[int],
) -> int | None:
    if not isinstance(call_id, str) or not call_id:
        return None
    return next(
        (
            index
            for index in range(after + 1, len(messages))
            if index not in consumed
            and messages[index].get("role") == "tool"
            and messages[index].get("tool_call_id") == call_id
        ),
        None,
    )


def _responses_tool_output_to_chat(value: Any) -> Any:
    if value is None or isinstance(value, str):
        return value or ""
    return _responses_content_to_chat(value)


def _responses_content_to_chat(value: Any) -> Any:
    if isinstance(value, str):
        return value
    if not isinstance(value, list):
        raise ValueError("Responses message content must be a string or array")
    text: list[str] = []
    media: list[dict[str, Any]] = []
    for block in value:
        if not isinstance(block, Mapping):
            raise ValueError("Responses message content must contain objects")
        block_type = block.get("type")
        if block_type in {"input_text", "output_text", "text"}:
            text.append(
                _required_string(
                    block.get("text"),
                    "Responses text parts must contain text",
                    allow_empty=True,
                )
            )
        elif block_type == "input_image":
            media.append(_responses_image_to_chat(block))
        elif block_type == "input_file":
            media.append(_responses_file_to_chat(block))
        else:
            raise ValueError(f"Unsupported Responses content part type: {block_type}")
    if not media:
        return "\n".join(text)
    return [*([{"type": "text", "text": "\n".join(text)}] if text else []), *media]


def _responses_image_to_chat(block: Mapping[str, Any]) -> dict[str, Any]:
    image_url = block.get("image_url")
    if isinstance(image_url, Mapping):
        image_url = image_url.get("url")
    return {
        "type": "image_url",
        "image_url": {
            "url": _required_string(
                image_url,
                "Responses input_image parts must contain image_url",
            )
        },
    }


def _responses_file_to_chat(block: Mapping[str, Any]) -> dict[str, Any]:
    file = {
        key: block[key]
        for key in ("file_id", "file_data", "file_url", "filename")
        if isinstance(block.get(key), str) and block[key]
    }
    if not any(key in file for key in ("file_id", "file_data", "file_url")):
        raise ValueError("Responses input_file parts must contain a file source")
    return {"type": "file", "file": file}


def _responses_tools_to_chat(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("Responses tools must be an array")
    result: list[dict[str, Any]] = []
    for tool in value:
        if not isinstance(tool, Mapping):
            raise ValueError("Responses tools must contain objects")
        if tool.get("type") != "function":
            raise ValueError("Unsupported Responses tool type")
        function: dict[str, Any] = {
            "name": _required_string(
                tool.get("name"),
                "Responses function tools must contain name",
            )
        }
        for key in ("description", "parameters", "strict"):
            if key in tool:
                function[key] = tool[key]
        result.append({"type": "function", "function": function})
    return result


def _responses_tool_choice_to_chat(value: Any) -> Any:
    if isinstance(value, str) and value in {"auto", "none", "required"}:
        return value
    if not isinstance(value, Mapping) or value.get("type") != "function":
        raise ValueError("Unsupported Responses tool_choice")
    return {
        "type": "function",
        "function": {
            "name": _required_string(
                value.get("name"),
                "Responses function tool_choice must contain name",
            )
        },
    }


def _responses_reasoning_effort(value: Any) -> str | None:
    if not isinstance(value, Mapping):
        return None
    effort = value.get("effort")
    return effort if isinstance(effort, str) and effort else None


def _responses_text_format_to_chat(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None
    format_value = value.get("format")
    if not isinstance(format_value, Mapping):
        return None
    format_type = format_value.get("type")
    if format_type in {"text", "json_object"}:
        return {"type": format_type}
    if format_type != "json_schema":
        return None
    json_schema: dict[str, Any] = {
        "name": _required_string(
            format_value.get("name"),
            "Responses json_schema format must contain name",
        )
    }
    schema = format_value.get("schema")
    if not isinstance(schema, Mapping):
        raise ValueError("Responses json_schema format must contain schema")
    json_schema["schema"] = dict(schema)
    if "strict" in format_value:
        json_schema["strict"] = format_value["strict"]
    return {"type": "json_schema", "json_schema": json_schema}


def _build_chat_tool_call(call_id: str, name: str, arguments: str) -> dict[str, Any]:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }

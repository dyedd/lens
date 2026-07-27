from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ._validation import _required_string


def chat_request_to_responses(body: dict[str, Any]) -> dict[str, Any]:
    """Convert a Chat Completions request into a Responses API request."""
    messages = body.get("messages")
    if not isinstance(messages, list):
        raise ValueError("Chat request messages must be an array")

    result: dict[str, Any] = {"input": _chat_messages_to_responses_input(messages)}
    for key in (
        "temperature",
        "top_p",
        "stream",
        "parallel_tool_calls",
        "metadata",
        "store",
        "service_tier",
        "user",
        "safety_identifier",
        "prompt_cache_key",
    ):
        if key in body:
            result[key] = body[key]

    max_output_tokens = body.get("max_completion_tokens", body.get("max_tokens"))
    if max_output_tokens is not None:
        result["max_output_tokens"] = max_output_tokens

    tools = _chat_tools_to_responses(body.get("tools"))
    if tools:
        result["tools"] = tools
    tool_choice = _chat_tool_choice_to_responses(body.get("tool_choice"))
    if tool_choice is not None:
        result["tool_choice"] = tool_choice

    reasoning_effort = body.get("reasoning_effort")
    if reasoning_effort is not None:
        result["reasoning"] = {"effort": reasoning_effort}
    text = _chat_text_config_to_responses(body)
    if text:
        result["text"] = text
    return result


def _chat_messages_to_responses_input(messages: list[Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, dict):
            raise ValueError("Chat request messages must contain objects")
        role = message.get("role")
        if not isinstance(role, str):
            raise ValueError("Chat messages must contain a string role")
        if role == "tool":
            result.append(
                {
                    "type": "function_call_output",
                    "call_id": _required_string(
                        message.get("tool_call_id"),
                        "Chat tool messages must contain tool_call_id",
                    ),
                    "output": _chat_tool_output(message.get("content")),
                }
            )
            continue
        if role not in {"developer", "system", "user", "assistant"}:
            raise ValueError(f"Unsupported Chat message role: {role}")

        content = _chat_content_to_responses(message.get("content"))
        raw_tool_calls = message.get("tool_calls") if role == "assistant" else None
        if raw_tool_calls is not None and not isinstance(raw_tool_calls, list):
            raise ValueError("Chat assistant tool_calls must be an array")
        tool_calls = raw_tool_calls or []
        if content not in (None, "", []) or not tool_calls:
            result.append({"role": role, "content": content})
        if tool_calls:
            result.extend(_chat_tool_calls_to_responses(tool_calls))
    return result


def _chat_content_to_responses(content: Any) -> Any:
    if content is None or isinstance(content, str):
        return content
    if not isinstance(content, list):
        raise ValueError("Chat message content must be a string or array")
    parts: list[dict[str, Any]] = []
    for part in content:
        if not isinstance(part, dict):
            raise ValueError("Chat message content must contain objects")
        part_type = part.get("type")
        if part_type == "text":
            parts.append(
                {
                    "type": "input_text",
                    "text": _required_string(
                        part.get("text"),
                        "Chat text parts must contain text",
                        allow_empty=True,
                    ),
                }
            )
        elif part_type == "image_url":
            image_url = part.get("image_url")
            detail = None
            if isinstance(image_url, dict):
                detail = image_url.get("detail")
                image_url = image_url.get("url")
            image_url = _required_string(
                image_url, "Chat image_url parts must contain a URL"
            )
            image_part: dict[str, Any] = {
                "type": "input_image",
                "image_url": image_url,
            }
            if isinstance(detail, str) and detail in {"auto", "low", "high"}:
                image_part["detail"] = detail
            parts.append(image_part)
        else:
            raise ValueError(f"Unsupported Chat content part type: {part_type}")
    return parts


def _chat_tool_output(content: Any) -> str:
    if isinstance(content, str):
        return content
    if content is None:
        return ""
    if not isinstance(content, list):
        raise ValueError("Chat tool message content must be a string or array")
    text_parts: list[str] = []
    for part in content:
        if not isinstance(part, dict):
            raise ValueError("Chat tool message content must contain objects")
        if part.get("type") == "text":
            text_parts.append(
                _required_string(
                    part.get("text"),
                    "Chat tool text parts must contain text",
                    allow_empty=True,
                )
            )
        else:
            raise ValueError(
                f"Unsupported Chat tool content part type: {part.get('type')}"
            )
    return "".join(text_parts)


def _chat_tool_calls_to_responses(tool_calls: list[Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for tool_call in tool_calls:
        if not isinstance(tool_call, dict):
            raise ValueError("Chat assistant tool_calls must contain objects")
        if tool_call.get("type") != "function":
            raise ValueError("Unsupported Chat tool call type")
        function = tool_call.get("function")
        if not isinstance(function, dict):
            raise ValueError("Chat function tool call must contain a function object")
        result.append(
            {
                "type": "function_call",
                "call_id": _required_string(
                    tool_call.get("id"), "Chat function tool calls must contain id"
                ),
                "name": _required_string(
                    function.get("name"),
                    "Chat function tool calls must contain function.name",
                ),
                "arguments": _required_string(
                    function.get("arguments"),
                    "Chat function tool calls must contain function.arguments",
                    allow_empty=True,
                ),
            }
        )
    return result


def _chat_tools_to_responses(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("Chat tools must be an array")
    result: list[dict[str, Any]] = []
    for tool in value:
        if not isinstance(tool, dict):
            raise ValueError("Chat tools must contain objects")
        if tool.get("type") != "function":
            raise ValueError("Unsupported Chat tool type")
        function = tool.get("function")
        if not isinstance(function, dict):
            raise ValueError("Chat function tools must contain a function object")
        converted: dict[str, Any] = {
            "type": "function",
            "name": _required_string(
                function.get("name"), "Chat function tools must contain name"
            ),
        }
        for key in ("description", "parameters", "strict"):
            if key in function:
                converted[key] = function[key]
        result.append(converted)
    return result


def _chat_tool_choice_to_responses(value: Any) -> Any:
    if isinstance(value, str) and value in {"auto", "none", "required"}:
        return value
    if value is None:
        return None
    if not isinstance(value, dict) or value.get("type") != "function":
        raise ValueError("Unsupported Chat tool_choice")
    function = value.get("function")
    if not isinstance(function, dict):
        raise ValueError("Chat function tool_choice must contain a function object")
    return {
        "type": "function",
        "name": _required_string(
            function.get("name"), "Chat function tool_choice must contain name"
        ),
    }


def _chat_text_config_to_responses(body: Mapping[str, Any]) -> dict[str, Any]:
    text: dict[str, Any] = {}
    response_format = body.get("response_format")
    if isinstance(response_format, Mapping):
        format_type = response_format.get("type")
        if format_type == "json_schema":
            json_schema = response_format.get("json_schema")
            if not isinstance(json_schema, Mapping):
                raise ValueError("Chat json_schema response_format is invalid")
            name = _required_string(
                json_schema.get("name"),
                "Chat json_schema response_format must contain name",
            )
            schema = json_schema.get("schema")
            if not isinstance(schema, Mapping):
                raise ValueError("Chat json_schema response_format must contain schema")
            text["format"] = {"type": "json_schema", "name": name, "schema": schema}
            if "strict" in json_schema:
                text["format"]["strict"] = json_schema["strict"]
        elif format_type in {"json_object", "text"}:
            text["format"] = {"type": format_type}
    if "verbosity" in body:
        text["verbosity"] = body["verbosity"]
    return text

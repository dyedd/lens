from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from ._responses import _decode_reasoning_item
from ._shared import _required_string


def anthropic_request_to_responses(body: dict[str, Any]) -> dict[str, Any]:
    """Convert an Anthropic Messages request into a Responses API request."""
    messages = body.get("messages")
    if not isinstance(messages, list):
        raise ValueError("Anthropic request messages must be an array")

    input_items: list[dict[str, Any]] = []
    system = _anthropic_system_to_responses(body.get("system"))
    if system is not None:
        input_items.append({"role": "system", "content": system})

    has_reasoning_items = False
    for message in messages:
        items, message_has_reasoning = _anthropic_message_to_responses(message)
        input_items.extend(items)
        has_reasoning_items = has_reasoning_items or message_has_reasoning

    result: dict[str, Any] = {"input": input_items, "store": False}
    for key in ("temperature", "top_p", "stream"):
        if key in body:
            result[key] = body[key]
    if "max_tokens" in body:
        result["max_output_tokens"] = body["max_tokens"]

    reasoning, thinking_enabled = _anthropic_reasoning_config(body)
    if reasoning:
        result["reasoning"] = reasoning
    if thinking_enabled or has_reasoning_items:
        result["include"] = ["reasoning.encrypted_content"]

    tools, tool_names = _anthropic_tools_to_responses(body.get("tools"))
    if tools:
        result["tools"] = tools
    tool_choice, parallel_tool_calls = _anthropic_tool_choice_to_responses(
        body.get("tool_choice"), tool_names
    )
    if tool_choice is not None:
        result["tool_choice"] = tool_choice
    if parallel_tool_calls is not None:
        result["parallel_tool_calls"] = parallel_tool_calls

    metadata = body.get("metadata")
    if isinstance(metadata, Mapping) and isinstance(metadata.get("user_id"), str):
        result["safety_identifier"] = metadata["user_id"]

    text_config = _anthropic_text_config_to_responses(body.get("output_config"))
    if text_config:
        result["text"] = text_config
    return result


def _anthropic_system_to_responses(value: Any) -> str | list[dict[str, Any]] | None:
    if value is None or isinstance(value, str):
        return value
    if not isinstance(value, list):
        raise ValueError("Anthropic system must be a string or array")
    parts = _anthropic_content_to_responses(value)
    if parts and all(part.get("type") == "input_text" for part in parts):
        return "\n".join(str(part.get("text") or "") for part in parts)
    return parts or None


def _anthropic_message_to_responses(
    value: Any,
) -> tuple[list[dict[str, Any]], bool]:
    if not isinstance(value, Mapping):
        raise ValueError("Anthropic messages must contain objects")
    role = value.get("role")
    if role not in {"user", "assistant"}:
        raise ValueError("Anthropic messages must contain a valid role")
    content = value.get("content")
    if isinstance(content, str):
        return ([{"role": role, "content": content}], False)
    if not isinstance(content, list):
        raise ValueError("Anthropic message content must be a string or array")

    result: list[dict[str, Any]] = []
    pending_parts: list[dict[str, Any]] = []
    has_reasoning = False

    def flush_parts() -> None:
        if pending_parts:
            result.append({"role": role, "content": list(pending_parts)})
            pending_parts.clear()

    for block in content:
        if not isinstance(block, Mapping):
            raise ValueError("Anthropic message content must contain objects")
        block_type = block.get("type")
        if block_type in {"text", "image", "document"}:
            pending_parts.extend(_anthropic_content_to_responses([block]))
            continue
        flush_parts()
        if block_type in {"thinking", "redacted_thinking"}:
            envelope = block.get("signature" if block_type == "thinking" else "data")
            reasoning_item = _decode_reasoning_item(envelope)
            if reasoning_item is not None:
                result.append(reasoning_item)
                has_reasoning = True
        elif block_type == "tool_use":
            tool_input = block.get("input", {})
            if not isinstance(tool_input, Mapping):
                raise ValueError("Anthropic tool_use input must be an object")
            result.append(
                {
                    "type": "function_call",
                    "call_id": _required_string(
                        block.get("id"), "Anthropic tool_use must contain id"
                    ),
                    "name": _required_string(
                        block.get("name"), "Anthropic tool_use must contain name"
                    ),
                    "arguments": json.dumps(dict(tool_input), ensure_ascii=False),
                }
            )
        elif block_type == "tool_result":
            result.append(
                {
                    "type": "function_call_output",
                    "call_id": _required_string(
                        block.get("tool_use_id"),
                        "Anthropic tool_result must contain tool_use_id",
                    ),
                    "output": _anthropic_tool_result_output(block.get("content")),
                }
            )
    flush_parts()
    if not result:
        result.append({"role": role, "content": []})
    return result, has_reasoning


def _anthropic_content_to_responses(value: list[Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for block in value:
        if not isinstance(block, Mapping):
            raise ValueError("Anthropic content must contain objects")
        block_type = block.get("type")
        if block_type == "text":
            result.append(
                {
                    "type": "input_text",
                    "text": _required_string(
                        block.get("text"),
                        "Anthropic text blocks must contain text",
                        allow_empty=True,
                    ),
                }
            )
        elif block_type == "image":
            result.append(_anthropic_image_to_responses(block.get("source")))
        elif block_type == "document":
            result.extend(_anthropic_document_to_responses(block))
    return result


def _anthropic_image_to_responses(source: Any) -> dict[str, Any]:
    if not isinstance(source, Mapping):
        raise ValueError("Anthropic images must contain a source object")
    source_type = source.get("type")
    if source_type == "url":
        image_url = _required_string(
            source.get("url"), "Anthropic URL images must contain url"
        )
    elif source_type == "base64":
        media_type = _required_string(
            source.get("media_type"),
            "Anthropic base64 images must contain media_type",
        )
        data = _required_string(
            source.get("data"), "Anthropic base64 images must contain data"
        )
        image_url = f"data:{media_type};base64,{data}"
    else:
        raise ValueError("Unsupported Anthropic image source type")
    return {"type": "input_image", "image_url": image_url}


def _anthropic_document_to_responses(
    block: Mapping[str, Any],
) -> list[dict[str, Any]]:
    source = block.get("source")
    if not isinstance(source, Mapping):
        raise ValueError("Anthropic documents must contain a source object")
    source_type = source.get("type")
    filename = block.get("title")
    if not isinstance(filename, str) or not filename:
        filename = "document.pdf"
    if source_type == "url":
        return [
            {
                "type": "input_file",
                "file_url": _required_string(
                    source.get("url"), "Anthropic URL documents must contain url"
                ),
            }
        ]
    if source_type == "base64":
        media_type = _required_string(
            source.get("media_type"),
            "Anthropic base64 documents must contain media_type",
        )
        data = _required_string(
            source.get("data"), "Anthropic base64 documents must contain data"
        )
        return [
            {
                "type": "input_file",
                "file_data": f"data:{media_type};base64,{data}",
                "filename": filename,
            }
        ]
    if source_type == "text":
        return [
            {
                "type": "input_text",
                "text": _required_string(
                    source.get("data"),
                    "Anthropic text documents must contain data",
                    allow_empty=True,
                ),
            }
        ]
    if source_type == "content":
        content = source.get("content")
        if isinstance(content, str):
            return [{"type": "input_text", "text": content}]
        if isinstance(content, list):
            return _anthropic_content_to_responses(content)
        raise ValueError("Anthropic content documents must contain string or array")
    raise ValueError("Unsupported Anthropic document source type")


def _anthropic_tool_result_output(value: Any) -> Any:
    if value is None or isinstance(value, str):
        return value or ""
    if not isinstance(value, list):
        raise ValueError("Anthropic tool_result content must be a string or array")
    parts = _anthropic_content_to_responses(value)
    return parts or ""


def _anthropic_reasoning_config(
    body: Mapping[str, Any],
) -> tuple[dict[str, Any], bool]:
    thinking = body.get("thinking")
    output_config = body.get("output_config")
    effort = output_config.get("effort") if isinstance(output_config, Mapping) else None
    reasoning: dict[str, Any] = {}
    thinking_enabled = False
    if isinstance(thinking, Mapping):
        thinking_type = thinking.get("type")
        if thinking_type == "disabled":
            return {"effort": "none"}, False
        if thinking_type in {"adaptive", "enabled"}:
            thinking_enabled = True
            if thinking.get("display", "summarized") != "omitted":
                reasoning["summary"] = "auto"
    if isinstance(effort, str) and effort:
        reasoning["effort"] = effort
        thinking_enabled = effort != "none"
    return reasoning, thinking_enabled


def _anthropic_tools_to_responses(
    value: Any,
) -> tuple[list[dict[str, Any]], set[str]]:
    if value is None:
        return [], set()
    if not isinstance(value, list):
        raise ValueError("Anthropic tools must be an array")
    result: list[dict[str, Any]] = []
    names: set[str] = set()
    for tool in value:
        if not isinstance(tool, Mapping):
            raise ValueError("Anthropic tools must contain objects")
        if tool.get("type") not in {None, "custom"}:
            continue
        name = _required_string(
            tool.get("name"), "Anthropic custom tools must contain name"
        )
        input_schema = tool.get("input_schema")
        if not isinstance(input_schema, Mapping):
            raise ValueError("Anthropic custom tools must contain input_schema")
        converted: dict[str, Any] = {
            "type": "function",
            "name": name,
            "parameters": dict(input_schema),
        }
        for key in ("description", "strict"):
            if key in tool:
                converted[key] = tool[key]
        result.append(converted)
        names.add(name)
    return result, names


def _anthropic_tool_choice_to_responses(
    value: Any, tool_names: set[str]
) -> tuple[Any, bool | None]:
    if value is None:
        return None, None
    if not isinstance(value, Mapping):
        raise ValueError("Anthropic tool_choice must be an object")
    choice_type = value.get("type", "auto")
    if choice_type == "auto":
        choice: Any = "auto"
    elif choice_type == "any":
        if not tool_names:
            raise ValueError(
                "Anthropic required tool_choice needs a supported custom tool"
            )
        choice = "required"
    elif choice_type == "none":
        choice = "none"
    elif choice_type == "tool":
        name = _required_string(
            value.get("name"), "Anthropic tool_choice tool must contain name"
        )
        if name not in tool_names:
            raise ValueError("Anthropic tool_choice selected an unsupported tool")
        choice = {"type": "function", "name": name}
    else:
        raise ValueError("Unsupported Anthropic tool_choice type")
    disable_parallel = value.get("disable_parallel_tool_use")
    parallel = not disable_parallel if isinstance(disable_parallel, bool) else None
    return choice, parallel


def _anthropic_text_config_to_responses(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    output_format = value.get("format")
    if not isinstance(output_format, Mapping):
        return {}
    if output_format.get("type") != "json_schema":
        return {}
    schema = output_format.get("schema")
    if not isinstance(schema, Mapping):
        raise ValueError("Anthropic output_config format must contain schema")
    return {
        "format": {
            "type": "json_schema",
            "name": "anthropic_output",
            "schema": dict(schema),
            "strict": True,
        }
    }

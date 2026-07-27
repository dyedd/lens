from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from ._validation import _required_string


def anthropic_request_to_chat(
    body: dict[str, Any], *, preserve_thinking: bool = False
) -> dict[str, Any]:
    """Convert an Anthropic request into a chat request."""
    messages = _anthropic_system_to_chat_messages(body.get("system"))
    source_messages = body.get("messages")
    if not isinstance(source_messages, list):
        raise ValueError("Anthropic request messages must be an array")
    for message in source_messages:
        messages.extend(
            _anthropic_message_to_chat(
                message,
                preserve_thinking=preserve_thinking,
            )
        )

    chat: dict[str, Any] = {"messages": messages}
    if "max_tokens" in body:
        chat["max_tokens"] = body["max_tokens"]
    for key in ("temperature", "top_p", "stream"):
        if key in body:
            chat[key] = body[key]
    if "stop_sequences" in body:
        chat["stop"] = body["stop_sequences"]
    if "tools" in body:
        chat["tools"] = _anthropic_tools_to_chat(body["tools"])
    if "tool_choice" in body:
        chat["tool_choice"] = _anthropic_tool_choice_to_chat(body["tool_choice"])
    return chat


def _anthropic_system_to_chat_messages(value: Any) -> list[dict[str, Any]]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [{"role": "system", "content": value}]
    if not isinstance(value, list):
        raise ValueError("Anthropic system must be a string or array")
    text_parts: list[str] = []
    for block in value:
        if not isinstance(block, Mapping):
            raise ValueError("Anthropic system must contain objects")
        if block.get("type") != "text":
            raise ValueError("Unsupported Anthropic system block type")
        text_parts.append(
            _required_string(
                block.get("text"),
                "Anthropic system text blocks must contain text",
                allow_empty=True,
            )
        )
    text = "\n".join(text_parts)
    return [{"role": "system", "content": text}] if text else []


@dataclass(slots=True)
class _AnthropicMessageParts:
    text: list[str] = field(default_factory=list)
    media: list[dict[str, Any]] = field(default_factory=list)
    thinking: list[str] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)


def _anthropic_message_to_chat(
    value: Any,
    *,
    preserve_thinking: bool,
) -> list[dict[str, Any]]:
    if not isinstance(value, Mapping):
        raise ValueError("Anthropic messages must contain objects")
    role = value.get("role")
    if role not in {"user", "assistant"}:
        raise ValueError("Anthropic messages must contain a valid role")
    content = value.get("content")
    if isinstance(content, str):
        return [{"role": role, "content": content}]
    if not isinstance(content, list):
        raise ValueError("Anthropic message content must be a string or array")

    parts = _AnthropicMessageParts()
    for block in content:
        _collect_anthropic_block(
            block,
            role=role,
            preserve_thinking=preserve_thinking,
            parts=parts,
        )
    message = _build_anthropic_chat_message(
        role,
        parts,
        preserve_thinking=preserve_thinking,
    )
    return [*parts.tool_results, *([message] if message else [])]


def _collect_anthropic_block(
    block: Any,
    *,
    role: str,
    preserve_thinking: bool,
    parts: _AnthropicMessageParts,
) -> None:
    if not isinstance(block, Mapping):
        raise ValueError("Anthropic message content must contain objects")
    block_type = block.get("type")
    if block_type == "text":
        parts.text.append(
            _required_string(
                block.get("text"),
                "Anthropic text blocks must contain text",
                allow_empty=True,
            )
        )
    elif block_type == "thinking":
        if role == "assistant" and preserve_thinking:
            parts.thinking.append(
                _required_string(
                    block.get("thinking"),
                    "Anthropic thinking blocks must contain thinking",
                    allow_empty=True,
                )
            )
    elif block_type == "redacted_thinking":
        return
    elif block_type in {"image", "document"}:
        _collect_rich_content_part(block, text=parts.text, media=parts.media)
    elif block_type == "tool_use":
        parts.tool_calls.append(_anthropic_tool_use_to_chat(block))
    elif block_type == "tool_result":
        parts.tool_results.append(_anthropic_tool_result_to_chat(block))
    else:
        raise ValueError(f"Unsupported Anthropic content block type: {block_type}")


def _build_anthropic_chat_message(
    role: str,
    parts: _AnthropicMessageParts,
    *,
    preserve_thinking: bool,
) -> dict[str, Any] | None:
    message: dict[str, Any] = {"role": role}
    if parts.media:
        message["content"] = _assemble_chat_content(parts.text, parts.media)
    elif parts.text:
        message["content"] = "\n".join(parts.text)
    elif parts.tool_calls or (preserve_thinking and parts.thinking):
        message["content"] = None
    else:
        return None
    if role == "assistant" and preserve_thinking and parts.thinking:
        message["reasoning_content"] = "\n".join(parts.thinking)
    if role == "assistant" and parts.tool_calls:
        message["tool_calls"] = parts.tool_calls
    return message


def _anthropic_tool_use_to_chat(block: Mapping[str, Any]) -> dict[str, Any]:
    tool_input = block.get("input", {})
    if not isinstance(tool_input, Mapping):
        raise ValueError("Anthropic tool_use input must be an object")
    return _build_chat_tool_call(
        _required_string(block.get("id"), "Anthropic tool_use must contain id"),
        _required_string(block.get("name"), "Anthropic tool_use must contain name"),
        json.dumps(dict(tool_input), ensure_ascii=False),
    )


def _anthropic_tool_result_to_chat(block: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "role": "tool",
        "tool_call_id": _required_string(
            block.get("tool_use_id"),
            "Anthropic tool_result must contain tool_use_id",
        ),
        "content": _anthropic_tool_result_content(block.get("content")),
    }


def _anthropic_tool_result_content(value: Any) -> Any:
    if value is None or isinstance(value, str):
        return value or ""
    if not isinstance(value, list):
        raise ValueError("Anthropic tool_result content must be a string or array")
    text: list[str] = []
    media: list[dict[str, Any]] = []
    for block in value:
        _collect_rich_content_part(block, text=text, media=media)
    if not media:
        return [{"type": "text", "text": item} for item in text] or ""
    return [*[{"type": "text", "text": item} for item in text], *media]


def _collect_rich_content_part(
    block: Any,
    *,
    text: list[str],
    media: list[dict[str, Any]],
) -> None:
    if not isinstance(block, Mapping):
        raise ValueError("Anthropic content must contain objects")
    block_type = block.get("type")
    if block_type == "text":
        text.append(
            _required_string(
                block.get("text"),
                "Anthropic text blocks must contain text",
                allow_empty=True,
            )
        )
    elif block_type == "image":
        media.append(_anthropic_image_to_chat(block.get("source")))
    elif block_type == "document":
        document_text, document_media = _anthropic_document_to_chat(block)
        text.extend(document_text)
        media.extend(document_media)
    else:
        raise ValueError(f"Unsupported Anthropic content block type: {block_type}")


def _anthropic_image_to_chat(source: Any) -> dict[str, Any]:
    if not isinstance(source, Mapping):
        raise ValueError("Anthropic images must contain a source object")
    source_type = source.get("type")
    if source_type == "url":
        url = _required_string(
            source.get("url"),
            "Anthropic URL images must contain url",
        )
    elif source_type == "base64":
        media_type = _required_string(
            source.get("media_type"),
            "Anthropic base64 images must contain media_type",
        )
        data = _required_string(
            source.get("data"),
            "Anthropic base64 images must contain data",
        )
        url = f"data:{media_type};base64,{data}"
    else:
        raise ValueError("Unsupported Anthropic image source type")
    return {"type": "image_url", "image_url": {"url": url}}


def _anthropic_document_to_chat(
    block: Mapping[str, Any],
) -> tuple[list[str], list[dict[str, Any]]]:
    source = block.get("source")
    if not isinstance(source, Mapping):
        raise ValueError("Anthropic documents must contain a source object")
    filename = block.get("title")
    if not isinstance(filename, str) or not filename:
        filename = "document.pdf"
    source_type = source.get("type")
    if source_type == "url":
        return [], [
            {
                "type": "file",
                "file": {
                    "file_url": _required_string(
                        source.get("url"),
                        "Anthropic URL documents must contain url",
                    ),
                    "filename": filename,
                },
            }
        ]
    if source_type == "base64":
        media_type = _required_string(
            source.get("media_type"),
            "Anthropic base64 documents must contain media_type",
        )
        data = _required_string(
            source.get("data"),
            "Anthropic base64 documents must contain data",
        )
        return [], [
            {
                "type": "file",
                "file": {
                    "file_data": f"data:{media_type};base64,{data}",
                    "filename": filename,
                },
            }
        ]
    if source_type == "text":
        return [
            _required_string(
                source.get("data"),
                "Anthropic text documents must contain data",
                allow_empty=True,
            )
        ], []
    if source_type == "content":
        content = source.get("content")
        if isinstance(content, str):
            return [content], []
        if isinstance(content, list):
            text: list[str] = []
            media: list[dict[str, Any]] = []
            for item in content:
                _collect_rich_content_part(item, text=text, media=media)
            return text, media
        raise ValueError("Anthropic content documents must contain string or array")
    raise ValueError("Unsupported Anthropic document source type")


def _anthropic_tools_to_chat(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("Anthropic tools must be an array")
    result: list[dict[str, Any]] = []
    for tool in value:
        if not isinstance(tool, Mapping):
            raise ValueError("Anthropic tools must contain objects")
        if tool.get("type") not in {None, "custom"}:
            raise ValueError("Unsupported Anthropic tool type")
        input_schema = tool.get("input_schema")
        if not isinstance(input_schema, Mapping):
            raise ValueError("Anthropic tools must contain input_schema")
        result.append(
            {
                "type": "function",
                "function": {
                    "name": _required_string(
                        tool.get("name"),
                        "Anthropic tools must contain name",
                    ),
                    "description": tool.get("description", ""),
                    "parameters": dict(input_schema),
                },
            }
        )
    return result


def _anthropic_tool_choice_to_chat(value: Any) -> Any:
    if not isinstance(value, Mapping):
        raise ValueError("Anthropic tool_choice must be an object")
    choice_type = value.get("type", "auto")
    if choice_type == "auto":
        return "auto"
    if choice_type == "any":
        return "required"
    if choice_type == "none":
        return "none"
    if choice_type == "tool":
        return {
            "type": "function",
            "function": {
                "name": _required_string(
                    value.get("name"),
                    "Anthropic tool_choice tool must contain name",
                )
            },
        }
    raise ValueError("Unsupported Anthropic tool_choice type")


def _build_chat_tool_call(call_id: str, name: str, arguments: str) -> dict[str, Any]:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }


def _assemble_chat_content(
    text: list[str],
    media: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    if text:
        parts.append({"type": "text", "text": "\n".join(text)})
    parts.extend(media)
    return parts

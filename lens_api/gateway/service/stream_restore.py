from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from ...models import ProtocolKind
from .payload_serialization import _dump_log_json
from .usage import _parse_sse_payloads


def _distill_stream_response_content(
    protocol: ProtocolKind, raw_content: str | None
) -> str | None:
    if not raw_content:
        return None

    if protocol == ProtocolKind.OPENAI_RESPONSES:
        payloads = _parse_sse_payloads(raw_content)
        for payload in reversed(payloads):
            if payload.get("type") != "response.completed":
                continue
            response_payload = payload.get("response")
            if isinstance(response_payload, dict):
                compact_payload = _compact_openai_response_payload(
                    _restore_openai_response_output(response_payload, payloads)
                )
                return _dump_log_json(compact_payload) or raw_content
    if protocol == ProtocolKind.ANTHROPIC:
        restored_message = _restore_anthropic_stream_message(
            _parse_sse_payloads(raw_content)
        )
        if restored_message is not None:
            return _dump_log_json(restored_message) or raw_content

    return raw_content


def _restore_anthropic_stream_message(
    payloads: list[dict[str, Any]],
) -> dict[str, Any] | None:
    message: dict[str, Any] | None = None
    input_buffers: dict[int, str] = {}

    for payload in payloads:
        payload_type = str(payload.get("type") or "")

        if payload_type == "message_start":
            start_message = payload.get("message")
            if not isinstance(start_message, dict):
                continue
            message = deepcopy(start_message)
            content = message.get("content")
            message["content"] = deepcopy(content) if isinstance(content, list) else []
            continue

        if message is None:
            continue

        if payload_type == "content_block_start":
            index = _coerce_openai_output_index(payload.get("index"))
            block = payload.get("content_block")
            if index is None or not isinstance(block, dict):
                continue
            content = message.setdefault("content", [])
            if not isinstance(content, list):
                content = []
                message["content"] = content
            while len(content) <= index:
                content.append(None)
            content[index] = deepcopy(block)
            continue

        if payload_type == "content_block_delta":
            index = _coerce_openai_output_index(payload.get("index"))
            delta = payload.get("delta")
            if index is None or not isinstance(delta, dict):
                continue
            content = message.get("content")
            if not isinstance(content, list) or index >= len(content):
                continue
            block = content[index]
            if not isinstance(block, dict):
                continue
            delta_type = str(delta.get("type") or "")
            if delta_type == "text_delta":
                block["text"] = f"{block.get('text') or ''}{delta.get('text') or ''}"
            elif delta_type == "thinking_delta":
                block["thinking"] = (
                    f"{block.get('thinking') or ''}{delta.get('thinking') or ''}"
                )
            elif delta_type == "signature_delta":
                block["signature"] = (
                    f"{block.get('signature') or ''}{delta.get('signature') or ''}"
                )
            elif delta_type == "input_json_delta":
                input_buffers[index] = (
                    f"{input_buffers.get(index, '')}{delta.get('partial_json') or ''}"
                )
            continue

        if payload_type == "content_block_stop":
            index = _coerce_openai_output_index(payload.get("index"))
            if index is None:
                continue
            _finalize_anthropic_tool_use_input(message, index, input_buffers)
            continue

        if payload_type == "message_delta":
            delta = payload.get("delta")
            if isinstance(delta, dict):
                for key, value in delta.items():
                    message[key] = value
            usage = payload.get("usage")
            if isinstance(usage, dict):
                merged_usage = dict(message.get("usage") or {})
                merged_usage.update(usage)
                message["usage"] = merged_usage

    for index in list(input_buffers):
        _finalize_anthropic_tool_use_input(message, index, input_buffers)

    if message is None:
        return None

    content = message.get("content")
    if isinstance(content, list):
        message["content"] = [item for item in content if item is not None]
    return message


def _finalize_anthropic_tool_use_input(
    message: dict[str, Any] | None,
    index: int,
    input_buffers: dict[int, str],
) -> None:
    if message is None:
        return
    content = message.get("content")
    if not isinstance(content, list) or index >= len(content):
        input_buffers.pop(index, None)
        return
    block = content[index]
    if not isinstance(block, dict) or block.get("type") != "tool_use":
        input_buffers.pop(index, None)
        return

    buffer = input_buffers.pop(index, "")
    if not buffer:
        current_input = block.get("input")
        if isinstance(current_input, dict):
            return
        raise ValueError("Invalid Anthropic tool input")

    try:
        parsed_input = json.loads(buffer)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid Anthropic tool input JSON") from exc
    if not isinstance(parsed_input, dict):
        raise ValueError("Invalid Anthropic tool input")
    block["input"] = parsed_input


def _compact_openai_response_payload(payload: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key in (
        "id",
        "object",
        "model",
        "status",
        "created_at",
        "completed_at",
        "error",
        "incomplete_details",
        "output",
        "usage",
    ):
        value = payload.get(key)
        if value is not None:
            compact[key] = value
    return compact


def _restore_openai_response_output(
    response_payload: dict[str, Any],
    payloads: list[dict[str, Any]],
) -> dict[str, Any]:
    existing_output = response_payload.get("output")
    if isinstance(existing_output, list) and existing_output:
        return response_payload

    rebuilt_output = _rebuild_openai_response_output(payloads)
    if not rebuilt_output:
        return response_payload

    restored_payload = dict(response_payload)
    restored_payload["output"] = rebuilt_output
    return restored_payload


def _rebuild_openai_response_output(
    payloads: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    items_by_index: dict[int, dict[str, Any]] = {}
    for payload in payloads:
        payload_type = str(payload.get("type") or "")
        if payload_type in {"response.output_item.added", "response.output_item.done"}:
            output_index = _coerce_openai_output_index(payload.get("output_index"))
            item = payload.get("item")
            if output_index is None or not isinstance(item, dict):
                continue
            items_by_index[output_index] = _merge_openai_output_item(
                items_by_index.get(output_index), item
            )
            continue

        if payload_type in {
            "response.content_part.added",
            "response.content_part.done",
        }:
            output_index = _coerce_openai_output_index(payload.get("output_index"))
            content_index = _coerce_openai_output_index(payload.get("content_index"))
            part = payload.get("part")
            if (
                output_index is None
                or content_index is None
                or not isinstance(part, dict)
            ):
                continue
            item = _ensure_openai_output_message(
                items_by_index, output_index, payload.get("item_id")
            )
            _upsert_openai_content_part(item, content_index, part)
            continue

        if payload_type == "response.output_text.delta":
            delta = payload.get("delta")
            if not isinstance(delta, str) or not delta:
                continue
            output_index = _coerce_openai_output_index(
                payload.get("output_index"), default=0
            )
            content_index = _coerce_openai_output_index(
                payload.get("content_index"), default=0
            )
            item = _ensure_openai_output_message(
                items_by_index, output_index, payload.get("item_id")
            )
            _append_openai_output_text(item, content_index, delta)
            continue

        if payload_type == "response.output_text.done":
            text = payload.get("text")
            if not isinstance(text, str):
                continue
            output_index = _coerce_openai_output_index(
                payload.get("output_index"), default=0
            )
            content_index = _coerce_openai_output_index(
                payload.get("content_index"), default=0
            )
            item = _ensure_openai_output_message(
                items_by_index, output_index, payload.get("item_id")
            )
            _set_openai_output_text(item, content_index, text)

    return [items_by_index[index] for index in sorted(items_by_index)]


def _merge_openai_output_item(
    existing: dict[str, Any] | None, incoming: dict[str, Any]
) -> dict[str, Any]:
    merged = deepcopy(existing) if existing is not None else {}
    for key, value in incoming.items():
        if key == "content" and isinstance(value, list):
            merged[key] = deepcopy(value)
            continue
        merged[key] = value
    if merged.get("type") == "message" and not isinstance(merged.get("content"), list):
        merged["content"] = []
    return merged


def _ensure_openai_output_message(
    items_by_index: dict[int, dict[str, Any]],
    output_index: int,
    item_id: Any,
) -> dict[str, Any]:
    item = items_by_index.get(output_index)
    if item is None:
        item = {"type": "message", "role": "assistant", "content": []}
        items_by_index[output_index] = item
    if item_id and item.get("id") is None:
        item["id"] = str(item_id)
    if item.get("type") == "message" and not isinstance(item.get("content"), list):
        item["content"] = []
    return item


def _upsert_openai_content_part(
    item: dict[str, Any], content_index: int, part: dict[str, Any]
) -> None:
    content = item.setdefault("content", [])
    if not isinstance(content, list):
        content = []
        item["content"] = content
    while len(content) <= content_index:
        content.append(None)
    content[content_index] = deepcopy(part)


def _append_openai_output_text(
    item: dict[str, Any], content_index: int, delta: str
) -> None:
    content = item.setdefault("content", [])
    if not isinstance(content, list):
        content = []
        item["content"] = content
    while len(content) <= content_index:
        content.append(None)
    part = content[content_index]
    if not isinstance(part, dict):
        part = {"type": "output_text", "text": "", "annotations": []}
        content[content_index] = part
    elif part.get("type") != "output_text":
        return
    part["text"] = f"{part.get('text') or ''}{delta}"
    part.setdefault("annotations", [])


def _set_openai_output_text(
    item: dict[str, Any], content_index: int, text: str
) -> None:
    content = item.setdefault("content", [])
    if not isinstance(content, list):
        content = []
        item["content"] = content
    while len(content) <= content_index:
        content.append(None)
    part = content[content_index]
    if not isinstance(part, dict):
        part = {"type": "output_text", "annotations": []}
        content[content_index] = part
    if part.get("type") != "output_text":
        return
    part["text"] = text
    part.setdefault("annotations", [])


def _coerce_openai_output_index(value: Any, default: int | None = None) -> int | None:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default

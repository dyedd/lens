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


from .openai_stream_restore import (
    _coerce_openai_output_index,
    _restore_openai_response_output,
)

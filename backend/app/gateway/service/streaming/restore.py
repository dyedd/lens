from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from ....models.protocols import ProtocolKind
from ..payload_serialization import dump_log_json
from .types import (
    OPENAI_RESPONSES_TERMINAL_EVENTS,
    iter_gemini_candidates,
    iter_gemini_content_parts,
    parse_sse_payloads,
)


def distill_stream_response_content(
    protocol: ProtocolKind, raw_content: str | None
) -> str | None:
    if not raw_content:
        return None

    if protocol == ProtocolKind.OPENAI_CHAT:
        payloads = parse_sse_payloads(raw_content)
        if payloads:
            return dump_log_json(payloads) or raw_content
    if protocol == ProtocolKind.OPENAI_RESPONSES:
        payloads = parse_sse_payloads(raw_content)
        for payload in reversed(payloads):
            if payload.get("type") not in OPENAI_RESPONSES_TERMINAL_EVENTS:
                continue
            response_payload = payload.get("response")
            if isinstance(response_payload, dict):
                compact_payload = _compact_openai_response_payload(
                    _restore_openai_response_output(response_payload, payloads)
                )
                return dump_log_json(compact_payload) or raw_content
    if protocol == ProtocolKind.ANTHROPIC:
        restored_message = _restore_anthropic_stream_message(
            parse_sse_payloads(raw_content)
        )
        if restored_message is not None:
            return dump_log_json(restored_message) or raw_content
    if protocol == ProtocolKind.GEMINI:
        payloads = parse_sse_payloads(raw_content)
        compact_payload = _restore_gemini_stream(payloads)
        if compact_payload is not None:
            return dump_log_json(compact_payload) or raw_content

    return raw_content


def _restore_gemini_stream(payloads: list[dict[str, Any]]) -> dict[str, Any] | None:
    response: dict[str, Any] = {}
    candidates: dict[int, dict[str, Any]] = {}
    for payload in payloads:
        for key, value in payload.items():
            if key == "usageMetadata":
                if isinstance(value, Mapping):
                    response.setdefault(key, {}).update(value)
            elif key != "candidates":
                response[key] = deepcopy(value)
        for candidate in iter_gemini_candidates(payload):
            index = candidate.get("index", 0)
            if isinstance(index, bool) or not isinstance(index, int):
                continue
            target = candidates.setdefault(index, {"index": index})
            for key, value in candidate.items():
                if key != "content":
                    target[key] = deepcopy(value)
            content = candidate.get("content")
            if isinstance(content, Mapping):
                merged = target.setdefault("content", {"role": "model", "parts": []})
                merged["parts"].extend(
                    deepcopy(list(iter_gemini_content_parts(content)))
                )
    if candidates:
        response["candidates"] = [candidates[index] for index in sorted(candidates)]
    return response or None


def _restore_anthropic_stream_message(
    payloads: list[dict[str, Any]],
) -> dict[str, Any] | None:
    message: dict[str, Any] | None = None
    content_blocks: dict[int, Any] = {}
    input_buffers: dict[int, str] = {}

    for payload in payloads:
        payload_type = str(payload.get("type") or "")

        if payload_type == "message_start":
            start_message = payload.get("message")
            if not isinstance(start_message, dict):
                continue
            message = deepcopy(start_message)
            content = message.pop("content", None)
            content_blocks = (
                dict(enumerate(content)) if isinstance(content, list) else {}
            )
            input_buffers.clear()
            continue

        if message is None:
            continue

        if payload_type == "content_block_start":
            index = _coerce_nonnegative_index(payload.get("index"))
            block = payload.get("content_block")
            if index is None or not isinstance(block, dict):
                continue
            content_blocks[index] = deepcopy(block)
            continue

        if payload_type == "content_block_delta":
            index = _coerce_nonnegative_index(payload.get("index"))
            delta = payload.get("delta")
            if index is None or not isinstance(delta, dict):
                continue
            block = content_blocks.get(index)
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
            index = _coerce_nonnegative_index(payload.get("index"))
            if index is not None:
                _finalize_anthropic_tool_use_input(
                    content_blocks.get(index), input_buffers.pop(index, "")
                )
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

    if message is None:
        return None

    for index, buffer in input_buffers.items():
        _finalize_anthropic_tool_use_input(content_blocks.get(index), buffer)
    message["content"] = _ordered_stream_parts(content_blocks)
    return message


def _finalize_anthropic_tool_use_input(block: object, buffer: str) -> None:
    if not isinstance(block, dict) or block.get("type") != "tool_use":
        return

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


def _ordered_stream_parts(parts_by_index: dict[int, Any]) -> list[dict[str, Any]]:
    return [
        part for _, part in sorted(parts_by_index.items()) if isinstance(part, dict)
    ]


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
    parts_by_output_index: dict[int, dict[int, Any]] = {}
    for payload in payloads:
        payload_type = payload.get("type")
        if not isinstance(payload_type, str):
            continue
        is_text_event = payload_type in {
            "response.output_text.delta",
            "response.output_text.done",
        }
        output_index = _coerce_nonnegative_index(
            payload.get("output_index"), default=0 if is_text_event else None
        )
        if output_index is None:
            continue
        if payload_type in {"response.output_item.added", "response.output_item.done"}:
            item = payload.get("item")
            if not isinstance(item, dict):
                continue
            stored_item = items_by_index.setdefault(output_index, {})
            for key, value in item.items():
                if key == "content" and isinstance(value, list):
                    parts_by_output_index[output_index] = dict(
                        enumerate(deepcopy(value))
                    )
                else:
                    stored_item[key] = value
                    if key == "content":
                        parts_by_output_index.pop(output_index, None)
            if stored_item.get("type") == "message":
                parts_by_output_index.setdefault(output_index, {})
            continue

        is_content_event = payload_type in {
            "response.content_part.added",
            "response.content_part.done",
        }
        if not is_content_event and not is_text_event:
            continue
        content_index = _coerce_nonnegative_index(
            payload.get("content_index"), default=0 if is_text_event else None
        )
        if content_index is None:
            continue
        if is_content_event:
            part = payload.get("part")
            if not isinstance(part, dict):
                continue
            parts = parts_by_output_index.setdefault(output_index, {})
            parts[content_index] = deepcopy(part)
        else:
            is_delta = payload_type == "response.output_text.delta"
            text = payload.get("delta" if is_delta else "text")
            if not isinstance(text, str) or (is_delta and not text):
                continue
            parts = parts_by_output_index.setdefault(output_index, {})
            part = parts.get(content_index)
            if not isinstance(part, dict):
                part = {"type": "output_text", "annotations": []}
                parts[content_index] = part
            if part.get("type") == "output_text":
                part["text"] = f"{part.get('text') or ''}{text}" if is_delta else text
                part.setdefault("annotations", [])
        item = items_by_index.setdefault(
            output_index, {"type": "message", "role": "assistant"}
        )
        item_id = payload.get("item_id")
        if item_id and item.get("id") is None:
            item["id"] = str(item_id)

    for index, parts in parts_by_output_index.items():
        items_by_index[index]["content"] = _ordered_stream_parts(parts)
    return [items_by_index[index] for index in sorted(items_by_index)]


def _coerce_nonnegative_index(
    value: object, *, default: int | None = None
) -> int | None:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    if isinstance(value, float) and not value.is_integer():
        return None
    try:
        index = int(value)
    except ValueError:
        return None
    return index if index >= 0 else None

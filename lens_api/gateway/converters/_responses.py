from __future__ import annotations

import base64
import json
from collections.abc import Mapping
from typing import Any

from ._shared import _required_string

_REASONING_ENVELOPE_PREFIX = "lens-responses-reasoning-v1:"


def _usage_int(usage: Mapping[str, Any], key: str) -> int:
    value = usage.get(key)
    if value is None:
        return 0
    if isinstance(value, bool):
        raise ValueError(f"Invalid Responses usage value: {key}")
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid Responses usage value: {key}") from None
    if parsed < 0:
        raise ValueError(f"Invalid negative Responses usage value: {key}")
    return parsed


def _raise_for_failed_response(response: Mapping[str, Any]) -> None:
    status = response.get("status")
    if status not in {"failed", "cancelled"}:
        return
    error = response.get("error")
    message = error.get("message") if isinstance(error, Mapping) else None
    raise ValueError(f"Responses upstream {status}: {message or 'unknown error'}")


def _validate_terminal_response(
    response: Mapping[str, Any], *, expected_status: str | None = None
) -> list[Any]:
    _raise_for_failed_response(response)
    status = response.get("status")
    valid_statuses = (
        {expected_status} if expected_status else {"completed", "incomplete"}
    )
    if status not in valid_statuses:
        raise ValueError(f"Responses upstream returned non-terminal status: {status}")
    output = response.get("output")
    if not isinstance(output, list):
        raise ValueError("Responses upstream output must be an array")
    return output


def _reasoning_item_to_anthropic(item: Mapping[str, Any]) -> dict[str, Any]:
    normalized = _standard_reasoning_item(item)
    envelope = _encode_standard_reasoning_item(normalized)
    thinking = _reasoning_summary_text(normalized)
    if thinking:
        return {"type": "thinking", "thinking": thinking, "signature": envelope}
    return {"type": "redacted_thinking", "data": envelope}


def _reasoning_summary_text(item: Mapping[str, Any]) -> str:
    summary = item.get("summary")
    if not isinstance(summary, list):
        raise ValueError("Responses reasoning summary must be an array")
    text_parts: list[str] = []
    for part in summary:
        if not isinstance(part, Mapping) or part.get("type") != "summary_text":
            continue
        text_parts.append(
            _required_string(
                part.get("text"),
                "Responses reasoning summary must contain text",
                allow_empty=True,
            )
        )
    return "\n\n".join(text_parts)


def _standard_reasoning_item(item: Mapping[str, Any]) -> dict[str, Any]:
    item_id = _required_string(
        item.get("id"), "Responses reasoning item must contain id"
    )
    summary = item.get("summary")
    if not isinstance(summary, list):
        raise ValueError("Responses reasoning summary must be an array")
    normalized_summary: list[dict[str, Any]] = []
    for part in summary:
        if not isinstance(part, Mapping) or part.get("type") != "summary_text":
            continue
        normalized_summary.append(
            {
                "type": "summary_text",
                "text": _required_string(
                    part.get("text"),
                    "Responses reasoning summary must contain text",
                    allow_empty=True,
                ),
            }
        )
    result: dict[str, Any] = {
        "type": "reasoning",
        "id": item_id,
        "summary": normalized_summary,
    }
    encrypted_content = item.get("encrypted_content")
    if isinstance(encrypted_content, str):
        result["encrypted_content"] = encrypted_content
    status = item.get("status")
    if status in {"in_progress", "completed", "incomplete"}:
        result["status"] = status
    return result


def _encode_standard_reasoning_item(item: Mapping[str, Any]) -> str:
    payload = json.dumps(
        item,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    encoded = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    return f"{_REASONING_ENVELOPE_PREFIX}{encoded}"


def _encode_reasoning_item(item: Mapping[str, Any]) -> str:
    return _encode_standard_reasoning_item(_standard_reasoning_item(item))


def _decode_reasoning_item(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, str) or not value.startswith(_REASONING_ENVELOPE_PREFIX):
        return None
    encoded = value.removeprefix(_REASONING_ENVELOPE_PREFIX)
    try:
        padding = "=" * (-len(encoded) % 4)
        payload = base64.urlsafe_b64decode(encoded + padding)
        item = json.loads(payload)
    except ValueError as exc:
        raise ValueError("Invalid Lens Responses reasoning envelope") from exc
    if not isinstance(item, Mapping) or item.get("type") != "reasoning":
        raise ValueError("Invalid Lens Responses reasoning envelope")
    return _standard_reasoning_item(item)

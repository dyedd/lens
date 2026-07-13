from __future__ import annotations

import json
from typing import Any

_INLINE_BASE64_MIN_LENGTH = 256
_DATA_URL_METADATA_SCAN_LIMIT = 256
_BASE64_CHARS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
)
_BASE64_PAYLOAD_KEYS = frozenset({"b64_json", "image_base64"})
_MIME_KEYS = frozenset({"media_type", "mime_type", "mimetype"})
_INLINE_BASE64_CONTENT_MARKERS = (
    b";base64,",
    b";BASE64,",
    b"b64_json",
    b"image_base64",
    b"image_generation_call",
)


def _json_body_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _dump_json(value: Any) -> str | None:
    try:
        return _json_body_bytes(value).decode("utf-8")
    except (TypeError, ValueError):
        return None


def _dump_log_json(value: Any) -> str | None:
    sanitized, has_changed = _sanitize_log_payload(value)
    return _dump_json(sanitized if has_changed else value)


def _decode_content_bytes(content: bytes | None) -> str | None:
    if not content:
        return None
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("utf-8", errors="replace")


def _decode_log_content_bytes(content: bytes | None) -> str | None:
    if not content:
        return None
    if not _content_may_contain_inline_base64(content):
        return _decode_content_bytes(content)
    try:
        payload = json.loads(content)
    except (TypeError, ValueError, UnicodeDecodeError):
        return _decode_content_bytes(content)
    return _dump_log_json(payload)


def _stringify_text_content(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
                continue
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(parts)
    return ""


def _sanitize_log_payload(
    value: Any,
    *,
    key: str | None = None,
    parent_type: str = "",
    parent_has_mime_key: bool = False,
) -> tuple[Any, bool]:
    if isinstance(value, dict):
        next_parent_type = str(value.get("type") or "")
        next_parent_has_mime_key = any(
            str(item).lower() in _MIME_KEYS for item in value
        )
        result: dict[Any, Any] | None = None
        for item_key, item_value in value.items():
            sanitized_value, has_changed = _sanitize_log_payload(
                item_value,
                key=str(item_key),
                parent_type=next_parent_type,
                parent_has_mime_key=next_parent_has_mime_key,
            )
            if result is None and has_changed:
                result = dict(value)
            if result is not None:
                result[item_key] = sanitized_value
        if result is not None:
            return result, True
        return value, False
    if isinstance(value, list):
        result: list[Any] | None = None
        for index, item in enumerate(value):
            sanitized_item, has_changed = _sanitize_log_payload(
                item,
                key=key,
                parent_type=parent_type,
                parent_has_mime_key=parent_has_mime_key,
            )
            if result is None and has_changed:
                result = list(value)
            if result is not None:
                result[index] = sanitized_item
        if result is not None:
            return result, True
        return value, False
    if isinstance(value, str):
        sanitized = _sanitize_log_string(
            value,
            key=(key or "").lower(),
            parent_type=parent_type.lower(),
            parent_has_mime_key=parent_has_mime_key,
        )
        return sanitized, sanitized != value
    return value, False


def _sanitize_log_string(
    value: str,
    *,
    key: str,
    parent_type: str,
    parent_has_mime_key: bool,
) -> str:
    redacted_data_url = _redact_data_url(value)
    if redacted_data_url is not None:
        return redacted_data_url
    if _should_redact_base64_string(
        value,
        key=key,
        parent_type=parent_type,
        parent_has_mime_key=parent_has_mime_key,
    ):
        return _base64_placeholder(value)
    return value


def _redact_data_url(value: str) -> str | None:
    if not value.startswith("data:"):
        return None
    comma_index = value.find(",", 5, _DATA_URL_METADATA_SCAN_LIMIT)
    if comma_index < 0:
        return None
    metadata = value[5:comma_index]
    if not any(part.lower() == "base64" for part in metadata.split(";")):
        return None
    return (
        f"data:{metadata},"
        f"{_base64_placeholder_length(len(value) - comma_index - 1)}"
    )


def _should_redact_base64_string(
    value: str,
    *,
    key: str,
    parent_type: str,
    parent_has_mime_key: bool,
) -> bool:
    if not _looks_like_base64(value):
        return False
    if key in _BASE64_PAYLOAD_KEYS:
        return True
    if key == "result" and parent_type == "image_generation_call":
        return True
    if key == "data" and (parent_type == "base64" or parent_has_mime_key):
        return True
    return False


def _looks_like_base64(value: str) -> bool:
    if len(value) < _INLINE_BASE64_MIN_LENGTH:
        return False
    payload_chars = 0
    for char in value:
        if char.isspace():
            continue
        if char not in _BASE64_CHARS:
            return False
        payload_chars += 1
    return payload_chars >= _INLINE_BASE64_MIN_LENGTH


def _content_may_contain_inline_base64(content: bytes) -> bool:
    return any(marker in content for marker in _INLINE_BASE64_CONTENT_MARKERS)


def _base64_placeholder(value: str) -> str:
    return _base64_placeholder_length(len(value))


def _base64_placeholder_length(length: int) -> str:
    return f"<base64 omitted length={length}>"

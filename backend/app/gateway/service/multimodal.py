from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ...models.protocols import ProtocolKind


def body_has_multimodal_content(
    body: Mapping[str, Any], protocol: ProtocolKind
) -> bool:
    """Return whether a request contains non-text content for its protocol."""
    markers = {
        ProtocolKind.ANTHROPIC: frozenset({"image", "document"}),
        ProtocolKind.OPENAI_CHAT: frozenset(
            {"image_url", "video_url", "input_audio", "file"}
        ),
        ProtocolKind.OPENAI_RESPONSES: frozenset({"input_image", "input_file"}),
        ProtocolKind.GEMINI: frozenset(
            {"inlineData", "inline_data", "fileData", "file_data"}
        ),
    }.get(protocol)
    if not markers:
        return False
    return _contains_marker(body, markers)


def _contains_marker(value: Any, markers: frozenset[str]) -> bool:
    if isinstance(value, Mapping):
        if any(key in markers for key in value):
            return True
        marker_type = value.get("type")
        if isinstance(marker_type, str) and marker_type in markers:
            return True
        return any(_contains_marker(item, markers) for item in value.values())
    if isinstance(value, list):
        return any(_contains_marker(item, markers) for item in value)
    return False


__all__ = ["body_has_multimodal_content"]

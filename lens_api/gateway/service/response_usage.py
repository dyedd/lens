from __future__ import annotations

from typing import Any

import httpx

from ...models import ProtocolKind
from .usage import (
    _EMPTY_USAGE,
    _anthropic_usage,
    _gemini_usage,
    _openai_chat_usage,
    _openai_embedding_usage,
    _openai_image_usage,
    _openai_responses_usage,
    _usage_mapping,
)


def _extract_response_usage(
    protocol: ProtocolKind, response: httpx.Response, fallback_model: Any = None
) -> dict[str, int | str | None]:
    if protocol == ProtocolKind.RERANK:
        empty = dict(_EMPTY_USAGE)
        if isinstance(fallback_model, str) and fallback_model.strip():
            empty["resolved_model"] = fallback_model.strip()
        return empty
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("Upstream response JSON must be an object")
    if protocol == ProtocolKind.OPENAI_CHAT:
        return _openai_chat_usage(payload)
    if protocol == ProtocolKind.OPENAI_RESPONSES:
        return _openai_responses_usage(payload, model=payload.get("model"))
    if protocol == ProtocolKind.OPENAI_IMAGE:
        return _openai_image_usage(payload, model=fallback_model)
    if protocol == ProtocolKind.OPENAI_EMBEDDING:
        return _openai_embedding_usage(payload)
    if protocol == ProtocolKind.ANTHROPIC:
        return _anthropic_usage(
            _usage_mapping(payload.get("usage")), model=payload.get("model")
        )
    return _gemini_usage(payload)

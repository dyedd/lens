"""Context window limits of models offered by channels and model groups."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

MIN_CONTEXT_WINDOW = 1_000
MAX_CONTEXT_WINDOW = 100_000_000

# Model list fields used by OpenRouter, Moonshot, Groq, Mistral, vLLM, Gemini
# and other OpenAI-compatible catalogs, in priority order.
_UPSTREAM_CONTEXT_FIELDS = (
    "context_length",
    "context_window",
    "max_context_length",
    "max_input_tokens",
    "inputTokenLimit",
    "input_token_limit",
    "max_model_len",
    "contextLength",
    "contextWindow",
)


# Error texts upstreams return when a prompt does not fit the model context:
# OpenAI/vLLM/DeepSeek, Anthropic, Bedrock, Gemini, Moonshot, Zhipu, DashScope.
_CONTEXT_WINDOW_EXCEEDED_RE = re.compile(
    r"context_length_exceeded"
    r"|maximum context length"
    r"|context (?:length|window)[^.\n]{0,40}exceed"
    r"|exceed[^.\n]{0,40}context (?:length|window|limit)"
    r"|prompt is too long"
    r"|input is too long"
    r"|prompt exceeds max length"
    r"|exceeded model token limit"
    r"|input token count[^.\n]{0,60}exceeds"
    r"|range of input length"
    r"|reduce the length of the (?:messages|prompt|input)"
    r"|上下文[^。\n]{0,20}(?:超|过长)"
    r"|(?:超出|超过)[^。\n]{0,20}上下文",
    re.IGNORECASE,
)


class ContextWindowSource(str, Enum):
    """Where a channel model's context window came from."""

    MANUAL = "manual"
    UPSTREAM = "upstream"


@dataclass(frozen=True, slots=True)
class ContextWindowResolution:
    context_window: int | None
    source: ContextWindowSource | None


def coerce_context_window(value: Any) -> int | None:
    """Return a supported context window size, or None for unusable values."""
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text.isdecimal():
            return None
        value = int(text)
    if isinstance(value, float):
        if not value.is_integer():
            return None
        value = int(value)
    if not isinstance(value, int):
        return None
    if MIN_CONTEXT_WINDOW <= value <= MAX_CONTEXT_WINDOW:
        return value
    return None


def parse_upstream_model_context_window(payload: Mapping[str, Any]) -> int | None:
    """Read the context window an upstream model list entry reports."""
    for field in _UPSTREAM_CONTEXT_FIELDS:
        size = coerce_context_window(payload.get(field))
        if size is not None:
            return size
    top_provider = payload.get("top_provider")
    if isinstance(top_provider, Mapping):
        return coerce_context_window(top_provider.get("context_length"))
    return None


def is_context_window_exceeded_error(message: str | None) -> bool:
    """Whether an upstream error says the request is longer than its context."""
    return bool(message) and _CONTEXT_WINDOW_EXCEEDED_RE.search(message) is not None


def resolve_channel_model_context_window(
    *,
    context_window: int | None,
    upstream_context_window: int | None,
) -> ContextWindowResolution:
    """Pick a channel model's context window: the manual setting, then upstream.

    Models with no value anywhere stay unknown, so routing never drops them.
    """
    if context_window is not None:
        return ContextWindowResolution(context_window, ContextWindowSource.MANUAL)
    if upstream_context_window is not None:
        return ContextWindowResolution(
            upstream_context_window, ContextWindowSource.UPSTREAM
        )
    return ContextWindowResolution(None, None)


__all__ = [
    "MAX_CONTEXT_WINDOW",
    "MIN_CONTEXT_WINDOW",
    "ContextWindowResolution",
    "ContextWindowSource",
    "coerce_context_window",
    "is_context_window_exceeded_error",
    "parse_upstream_model_context_window",
    "resolve_channel_model_context_window",
]

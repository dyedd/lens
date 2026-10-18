"""Rough request size estimation for context-window aware routing."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ...models.protocols import ProtocolKind

_CONTEXT_PROTOCOLS = frozenset(
    {
        ProtocolKind.OPENAI_CHAT,
        ProtocolKind.OPENAI_RESPONSES,
        ProtocolKind.ANTHROPIC,
        ProtocolKind.GEMINI,
    }
)
# Request settings, binary payloads and opaque replay blobs do not occupy the
# prompt the way text does.
_SKIPPED_KEYS = frozenset(
    {
        "model",
        "stream",
        "stream_options",
        "metadata",
        "user",
        "store",
        "service_tier",
        "previous_response_id",
        "prompt_cache_key",
        "safety_identifier",
        "signature",
        "encrypted_content",
        "thought_signature",
        "data",
        "file_data",
        "image_url",
        "file_id",
    }
)
_OUTPUT_LIMIT_KEYS = ("max_tokens", "max_completion_tokens", "max_output_tokens")
_ASCII_CHARS_PER_TOKEN = 4
# CJK-heavy text is about 0.6 tokens per character for most current
# tokenizers; underestimating is safer because failover still covers misses.
_NON_ASCII_TOKENS_PER_CHAR = 0.6


def estimate_request_context_tokens(
    body: Mapping[str, Any], protocol: ProtocolKind
) -> int | None:
    """Estimate prompt tokens plus requested output tokens for a request.

    Returns None for protocols whose requests do not consume a chat context.
    """
    if protocol not in _CONTEXT_PROTOCOLS:
        return None
    ascii_chars, non_ascii_chars = _count_text_chars(body)
    prompt_tokens = ascii_chars / _ASCII_CHARS_PER_TOKEN
    prompt_tokens += non_ascii_chars * _NON_ASCII_TOKENS_PER_CHAR
    return int(prompt_tokens) + _requested_output_tokens(body, protocol)


def _count_text_chars(value: Any) -> tuple[int, int]:
    ascii_chars = 0
    non_ascii_chars = 0
    pending = [value]
    while pending:
        current = pending.pop()
        if isinstance(current, str):
            if current.startswith("data:"):
                continue
            text_ascii = len(current.encode("ascii", "ignore"))
            ascii_chars += text_ascii
            non_ascii_chars += len(current) - text_ascii
        elif isinstance(current, Mapping):
            for key, item in current.items():
                if key in _SKIPPED_KEYS:
                    continue
                ascii_chars += len(str(key))
                pending.append(item)
        elif isinstance(current, list):
            pending.extend(current)
    return ascii_chars, non_ascii_chars


def _requested_output_tokens(body: Mapping[str, Any], protocol: ProtocolKind) -> int:
    if protocol == ProtocolKind.GEMINI:
        config = body.get("generation_config")
        if not isinstance(config, Mapping):
            return 0
        return _positive_int(config.get("max_output_tokens"))
    for key in _OUTPUT_LIMIT_KEYS:
        tokens = _positive_int(body.get(key))
        if tokens:
            return tokens
    return 0


def _positive_int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return max(value, 0)


__all__ = ["estimate_request_context_tokens"]

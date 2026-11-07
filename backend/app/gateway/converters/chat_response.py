from collections.abc import Mapping
from typing import Any

from .unified_response import FinishReason, Usage


def parse_chat_usage(value: object) -> Usage:
    if not isinstance(value, Mapping):
        return Usage()
    prompt_details = value.get("prompt_tokens_details")
    completion_details = value.get("completion_tokens_details")
    return Usage(
        input_tokens=_usage_int(value, "prompt_tokens"),
        output_tokens=_usage_int(value, "completion_tokens"),
        cached_input_tokens=_usage_int(prompt_details, "cached_tokens"),
        cache_creation_input_tokens=_usage_int(prompt_details, "cache_write_tokens"),
        reasoning_tokens=_usage_int(completion_details, "reasoning_tokens"),
    )


def serialize_chat_usage(usage: Usage) -> dict[str, Any]:
    result: dict[str, Any] = {
        "prompt_tokens": usage.input_tokens,
        "completion_tokens": usage.output_tokens,
        "total_tokens": usage.input_tokens + usage.output_tokens,
    }
    if usage.cached_input_tokens or usage.cache_creation_input_tokens:
        result["prompt_tokens_details"] = {
            "cached_tokens": usage.cached_input_tokens,
            "cache_write_tokens": usage.cache_creation_input_tokens,
        }
    if usage.reasoning_tokens:
        result["completion_tokens_details"] = {
            "reasoning_tokens": usage.reasoning_tokens
        }
    return result


def parse_chat_finish_reason(value: object) -> FinishReason:
    return {
        "stop": FinishReason.END_TURN,
        "length": FinishReason.MAX_TOKENS,
        "tool_calls": FinishReason.TOOL_USE,
        "function_call": FinishReason.TOOL_USE,
        "content_filter": FinishReason.CONTENT_FILTER,
    }.get(value if isinstance(value, str) else "", FinishReason.END_TURN)


def serialize_chat_finish_reason(reason: FinishReason) -> str:
    return {
        FinishReason.END_TURN: "stop",
        FinishReason.MAX_TOKENS: "length",
        FinishReason.TOOL_USE: "tool_calls",
        FinishReason.CONTENT_FILTER: "content_filter",
        FinishReason.STOP_SEQUENCE: "stop",
        FinishReason.OTHER: "stop",
    }[reason]


def _usage_int(usage: object, key: str) -> int:
    value = usage.get(key) if isinstance(usage, Mapping) else None
    return value if isinstance(value, int) and not isinstance(value, bool) else 0

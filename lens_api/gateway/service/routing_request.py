from __future__ import annotations

import json
import re
from collections.abc import Mapping
from copy import deepcopy
from typing import Any
from urllib.parse import urlsplit

from ...models import ChannelConfig, ProtocolKind
from .runtime_types import UpstreamRequestError


def _extract_request_reasoning_effort(
    *bodies: Mapping[str, Any] | None,
) -> str | None:
    """Extract the first valid reasoning-effort value from request bodies."""
    for body in bodies:
        if not isinstance(body, Mapping):
            continue

        for key in (
            "reasoning_effort",
            "reasoningEffort",
            "model_reasoning_effort",
            "modelReasoningEffort",
            "effort",
            "effortLevel",
        ):
            effort = _clean_reasoning_effort(body.get(key))
            if effort:
                return effort

        reasoning = body.get("reasoning")
        if isinstance(reasoning, Mapping):
            effort = _clean_reasoning_effort(reasoning.get("effort"))
            if effort:
                return effort
        else:
            effort = _clean_reasoning_effort(reasoning)
            if effort:
                return effort

        thinking = body.get("thinking")
        if isinstance(thinking, Mapping):
            for key in ("effort", "budget_tokens"):
                effort = _clean_reasoning_effort(thinking.get(key))
                if effort:
                    return effort

        output_config = body.get("output_config")
        if isinstance(output_config, Mapping):
            effort = _clean_reasoning_effort(output_config.get("effort"))
            if effort:
                return effort

        extra_body = body.get("extra_body")
        if isinstance(extra_body, Mapping):
            effort = _extract_request_reasoning_effort(extra_body)
            if effort:
                return effort

    return None


def _apply_deepseek_thinking_compat(
    channel: ChannelConfig, body: dict[str, Any]
) -> dict[str, Any]:
    """Apply DeepSeek thinking-field requirements to an upstream body."""
    if not _is_deepseek_thinking_target(channel, body.get("model")):
        return body
    if _is_thinking_disabled(body):
        return body
    if channel.protocol == ProtocolKind.ANTHROPIC:
        return _apply_deepseek_anthropic_thinking(body)
    if channel.protocol == ProtocolKind.OPENAI_CHAT:
        return _apply_deepseek_chat_reasoning(body)
    return body


def _apply_param_override(
    channel: ChannelConfig, body: dict[str, Any]
) -> dict[str, Any]:
    """Apply a channel's validated JSON parameter override."""
    raw_override = channel.param_override.strip()
    if not raw_override:
        return body

    try:
        override = json.loads(raw_override)
    except json.JSONDecodeError as exc:
        raise UpstreamRequestError(
            status_code=400,
            detail=(
                f"Invalid param override JSON for channel {channel.name}: "
                f"{exc.msg} at line {exc.lineno} column {exc.colno}"
            ),
            router_status_code=None,
        ) from exc

    if not isinstance(override, dict):
        raise UpstreamRequestError(
            status_code=400,
            detail=(
                f"Invalid param override for channel {channel.name}: "
                "expected a JSON object"
            ),
            router_status_code=None,
        )
    if "model" in override:
        raise UpstreamRequestError(
            status_code=400,
            detail=(
                f"Invalid param override for channel {channel.name}: "
                "model cannot be overridden"
            ),
            router_status_code=None,
        )

    return _deep_merge_json_objects(body, override)


def _apply_global_param_override(
    body: dict[str, Any],
    config: Mapping[str, Any] | None,
    model_name: str,
) -> dict[str, Any]:
    """Apply global and first-match model parameter overrides."""
    merged = dict(body)
    if not config:
        return merged
    global_override = config.get("global")
    if isinstance(global_override, Mapping):
        merged = _deep_merge_json_objects(merged, global_override)
    matched_rules = _matching_param_override_rules(config, model_name)
    for rule_override in reversed(matched_rules):
        merged = _deep_merge_json_objects(merged, rule_override)
    return merged


def _clean_reasoning_effort(value: Any) -> str | None:
    if isinstance(value, int) and value > 0:
        return str(value)
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized or len(normalized) > 32:
        return None
    if any(char.isspace() for char in normalized):
        return None
    return normalized


def _is_deepseek_thinking_target(channel: ChannelConfig, model_name: Any) -> bool:
    host = (urlsplit(str(channel.base_url)).hostname or "").lower()
    if host == "api.deepseek.com":
        return True
    if not isinstance(model_name, str):
        return False
    normalized = model_name.lower()
    return "deepseek-v4" in normalized or "deepseek-reasoner" in normalized


def _is_thinking_disabled(body: dict[str, Any]) -> bool:
    thinking = body.get("thinking")
    if not isinstance(thinking, dict):
        return False
    return str(thinking.get("type") or "").lower() == "disabled"


def _apply_deepseek_anthropic_thinking(body: dict[str, Any]) -> dict[str, Any]:
    messages = body.get("messages")
    if not isinstance(messages, list):
        return body
    for message in messages:
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        has_tool_use = any(
            isinstance(block, dict) and block.get("type") == "tool_use"
            for block in content
        )
        has_thinking = any(
            isinstance(block, dict) and block.get("type") == "thinking"
            for block in content
        )
        if has_tool_use and not has_thinking:
            content.insert(0, {"type": "thinking", "thinking": ""})
    return body


def _apply_deepseek_chat_reasoning(body: dict[str, Any]) -> dict[str, Any]:
    messages = body.get("messages")
    if not isinstance(messages, list):
        return body
    for message in messages:
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        if message.get("tool_calls") and message.get("reasoning_content") is None:
            message["reasoning_content"] = ""
    return body


def _deep_merge_json_objects(
    base: dict[str, Any], override: dict[str, Any]
) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, override_value in override.items():
        base_value = merged.get(key)
        if isinstance(base_value, dict) and isinstance(override_value, dict):
            merged[key] = _deep_merge_json_objects(base_value, override_value)
        else:
            merged[key] = deepcopy(override_value)
    return merged


def _matching_param_override_rules(
    config: Mapping[str, Any], model_name: str
) -> list[dict[str, Any]]:
    matched: list[dict[str, Any]] = []
    normalized_model = (model_name or "").strip()
    if not normalized_model:
        return matched
    for rule in config.get("rules", []):
        if not rule.get("enabled", True):
            continue
        if not _param_override_rule_matches(rule, normalized_model):
            continue
        override = rule.get("override")
        if isinstance(override, Mapping):
            matched.append(dict(override))
    return matched


def _param_override_rule_matches(rule: Mapping[str, Any], model_name: str) -> bool:
    match_type = rule.get("match_type", "exact")
    if match_type == "regex":
        pattern = str(rule.get("pattern", "")).strip()
        if not pattern:
            return False
        try:
            return bool(re.search(pattern, model_name))
        except re.error:
            return False
    return model_name in rule.get("models", [])

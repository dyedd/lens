from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from ...core.model_name_parser import ParsedModelName
from ...models.channels import ChannelConfig
from ...models.protocols import ProtocolKind

_REASONING_BUDGET_TOKENS = {
    "minimal": 1024,
    "low": 2048,
    "medium": 4096,
    "high": 8192,
    "xhigh": 16384,
    "max": 32768,
    "auto": 4096,
}


def _apply_reasoning_intent(
    channel: ChannelConfig, body: dict[str, Any], parsed: ParsedModelName | None
) -> dict[str, Any]:
    if parsed is None or not parsed.reasoning_explicit:
        return body
    if channel.protocol == ProtocolKind.OPENAI_CHAT:
        body["reasoning_effort"] = parsed.reasoning_effort or str(
            parsed.reasoning_budget
        )
    elif channel.protocol == ProtocolKind.OPENAI_RESPONSES:
        body["reasoning"] = {
            "effort": parsed.reasoning_effort or str(parsed.reasoning_budget)
        }
    elif channel.protocol == ProtocolKind.ANTHROPIC:
        if parsed.reasoning_effort == "none":
            body["thinking"] = {"type": "disabled"}
        else:
            effort = parsed.reasoning_effort
            budget = parsed.reasoning_budget or _REASONING_BUDGET_TOKENS.get(
                effort or "", 4096
            )
            body["thinking"] = {"type": "enabled", "budget_tokens": budget}
    elif channel.protocol == ProtocolKind.GEMINI:
        budget = parsed.reasoning_budget or _REASONING_BUDGET_TOKENS.get(
            parsed.reasoning_effort or ""
        )
        if budget is not None:
            body.setdefault("generationConfig", {})["thinkingConfig"] = {
                "thinkingBudget": budget
            }
    return body


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
            effort = _clean_reasoning_effort(thinking.get("effort"))
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


def _apply_glm_chat_reasoning_compat(
    channel: ChannelConfig,
    body: dict[str, Any],
    source_body: Mapping[str, Any],
) -> dict[str, Any]:
    if channel.protocol != ProtocolKind.OPENAI_CHAT:
        return body
    model = body.get("model")
    if not isinstance(model, str) or model.casefold().rsplit("/", 1)[-1] != "glm-5.2":
        return body
    output_config = (
        body.pop("output_config")
        if "output_config" in body
        else source_body.get("output_config")
    )
    if isinstance(output_config, Mapping) and "reasoning_effort" not in body:
        effort = _clean_reasoning_effort(output_config.get("effort"))
        if effort:
            body["reasoning_effort"] = effort
    thinking = (
        body.pop("thinking") if "thinking" in body else source_body.get("thinking")
    )
    if isinstance(thinking, Mapping):
        thinking_type = thinking.get("type")
        if thinking_type in {"enabled", "disabled"}:
            body["thinking"] = {"type": thinking_type}
    return body


def _clean_reasoning_effort(value: Any) -> str | None:
    if isinstance(value, int) and value > 0:
        return str(value)
    if not isinstance(value, str):
        return None
    trimmed_value = value.strip()
    if not trimmed_value or len(trimmed_value) > 32:
        return None
    if any(char.isspace() for char in trimmed_value):
        return None
    return trimmed_value


def _is_deepseek_thinking_target(channel: ChannelConfig, model_name: Any) -> bool:
    host = (urlsplit(str(channel.base_url)).hostname or "").lower()
    if host == "api.deepseek.com":
        return True
    if not isinstance(model_name, str):
        return False
    lower_model_name = model_name.lower()
    return "deepseek-v4" in lower_model_name or "deepseek-reasoner" in lower_model_name


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

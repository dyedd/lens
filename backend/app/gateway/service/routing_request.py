from __future__ import annotations

from collections.abc import Mapping
from typing import Any

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


def apply_reasoning_intent(
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


def clean_reasoning_effort(value: Any) -> str | None:
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


def extract_request_reasoning_effort(
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
            effort = clean_reasoning_effort(body.get(key))
            if effort:
                return effort

        reasoning = body.get("reasoning")
        if isinstance(reasoning, Mapping):
            effort = clean_reasoning_effort(reasoning.get("effort"))
            if effort:
                return effort
        else:
            effort = clean_reasoning_effort(reasoning)
            if effort:
                return effort

        thinking = body.get("thinking")
        if isinstance(thinking, Mapping):
            effort = clean_reasoning_effort(thinking.get("effort"))
            if effort:
                return effort

        output_config = body.get("output_config")
        if isinstance(output_config, Mapping):
            effort = clean_reasoning_effort(output_config.get("effort"))
            if effort:
                return effort

        extra_body = body.get("extra_body")
        if isinstance(extra_body, Mapping):
            effort = extract_request_reasoning_effort(extra_body)
            if effort:
                return effort

    return None

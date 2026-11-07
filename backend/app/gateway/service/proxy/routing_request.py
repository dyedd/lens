from __future__ import annotations

from typing import Any

from ....core.model_name_parser import ParsedModelName
from ....models.channels import ChannelConfig
from ....models.protocols import ProtocolKind

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
        from ...converters.spoke_gemini import gemini_thinking_config
        from ...converters.unified import ReasoningIntent

        body.setdefault("generationConfig", {})["thinkingConfig"] = (
            gemini_thinking_config(
                ReasoningIntent(
                    enabled=parsed.reasoning_effort != "none",
                    effort=parsed.reasoning_effort,
                    budget_tokens=parsed.reasoning_budget,
                ),
                parsed.base_model,
            )
        )
    return body

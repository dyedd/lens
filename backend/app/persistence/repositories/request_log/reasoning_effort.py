from __future__ import annotations

import json
from typing import Any


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


def extract_reasoning_effort(request_content: str | None) -> str | None:
    if not request_content:
        return None
    try:
        payload = json.loads(request_content)
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return extract_reasoning_effort_from_payload(payload)


def extract_reasoning_effort_from_payload(payload: dict[str, Any]) -> str | None:
    for key in (
        "reasoning_effort",
        "reasoningEffort",
        "model_reasoning_effort",
        "modelReasoningEffort",
        "effort",
        "effortLevel",
    ):
        effort = clean_reasoning_effort(payload.get(key))
        if effort:
            return effort

    reasoning = payload.get("reasoning")
    if isinstance(reasoning, dict):
        effort = clean_reasoning_effort(reasoning.get("effort"))
        if effort:
            return effort
    else:
        effort = clean_reasoning_effort(reasoning)
        if effort:
            return effort

    thinking = payload.get("thinking")
    if isinstance(thinking, dict):
        effort = clean_reasoning_effort(thinking.get("effort"))
        if effort:
            return effort

    output_config = payload.get("output_config")
    if isinstance(output_config, dict):
        effort = clean_reasoning_effort(output_config.get("effort"))
        if effort:
            return effort

    extra_body = payload.get("extra_body")
    if isinstance(extra_body, dict):
        effort = extract_reasoning_effort_from_payload(extra_body)
        if effort:
            return effort
    return None

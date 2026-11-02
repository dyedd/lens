from __future__ import annotations

from typing import Any

from sqlalchemy import case, func, literal

AGENT_CODEX = "codex"
AGENT_CLAUDE_CODE = "claude_code"
AGENT_OTHER = "other"
AGENT_UNKNOWN = "unknown"

AGENT_LABELS = {
    AGENT_CODEX: "Codex",
    AGENT_CLAUDE_CODE: "Claude Code",
    AGENT_OTHER: "Other",
    AGENT_UNKNOWN: "Unknown",
}


def classify_user_agent(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if not normalized:
        return AGENT_UNKNOWN
    if "codex" in normalized:
        return AGENT_CODEX
    if "claude" in normalized:
        return AGENT_CLAUDE_CODE
    return AGENT_OTHER


def agent_label(key: str) -> str:
    return AGENT_LABELS.get(key, key or AGENT_LABELS[AGENT_UNKNOWN])


def user_agent_sql_expression(column: Any) -> Any:
    normalized = func.lower(column)
    return case(
        (func.trim(column) == "", literal(AGENT_UNKNOWN)),
        (normalized.like("%codex%"), literal(AGENT_CODEX)),
        (normalized.like("%claude%"), literal(AGENT_CLAUDE_CODE)),
        else_=literal(AGENT_OTHER),
    )

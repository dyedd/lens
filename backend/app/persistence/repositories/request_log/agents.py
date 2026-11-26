from __future__ import annotations

from typing import Any

from sqlalchemy import case, func, literal

AGENT_CODEX = "codex"
AGENT_CLAUDE_CODE = "claude_code"
AGENT_OTHER = "other"
AGENT_UNKNOWN = "unknown"

# Ordered matching table: first matching substring classifies the User-Agent.
AGENT_SPECS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("opencode", "OpenCode", ("opencode",)),
    (AGENT_CODEX, "Codex", ("codex",)),
    (AGENT_CLAUDE_CODE, "Claude Code", ("claude",)),
    ("cursor", "Cursor", ("cursor",)),
    ("cline", "Cline", ("cline",)),
    ("roo_code", "Roo Code", ("roo-code", "roocode", "roo code")),
    (
        "cherry_studio",
        "Cherry Studio",
        ("cherrystudio", "cherry-studio", "cherry studio"),
    ),
    ("chatbox", "Chatbox", ("chatbox",)),
    ("openclaw", "OpenClaw", ("openclaw",)),
    ("gemini_cli", "Gemini CLI", ("gemini-cli", "gemini cli")),
    ("python_httpx", "Python HTTPX", ("python-httpx", "httpx/")),
    (
        "openai_sdk",
        "OpenAI SDK",
        ("openai/", "openai-python", "openai-node", "openai-go"),
    ),
    (
        "anthropic_sdk",
        "Anthropic SDK",
        ("anthropic/", "anthropic-typescript", "anthropic-python"),
    ),
    ("curl", "cURL", ("curl/",)),
)

AGENT_LABELS: dict[str, str] = {
    **{key: label for key, label, _ in AGENT_SPECS},
    AGENT_OTHER: "Other",
    AGENT_UNKNOWN: "Unknown",
}


def classify_user_agent(value: str | None) -> str:
    """Map an inbound User-Agent header to a normalized agent key."""
    normalized = (value or "").strip().lower()
    if not normalized:
        return AGENT_UNKNOWN
    for key, _, patterns in AGENT_SPECS:
        if any(pattern in normalized for pattern in patterns):
            return key
    return AGENT_OTHER


def agent_label(key: str) -> str:
    """Return the human-readable label for a normalized agent key."""
    return AGENT_LABELS.get(key, key or AGENT_LABELS[AGENT_UNKNOWN])


def user_agent_sql_expression(column: Any) -> Any:
    """Build a SQL CASE expression matching classify_user_agent."""
    normalized = func.lower(column)
    clauses = [
        (normalized.like(f"%{pattern}%"), literal(key))
        for key, _, patterns in AGENT_SPECS
        for pattern in patterns
    ]
    return case(
        (func.trim(column) == "", literal(AGENT_UNKNOWN)),
        *clauses,
        else_=literal(AGENT_OTHER),
    )

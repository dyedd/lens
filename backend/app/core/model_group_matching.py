from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Literal

MatchRegexOperator = Literal["and", "or"]


def compile_model_group_pattern(pattern: str) -> re.Pattern[str] | None:
    if not pattern.strip():
        return None
    try:
        return re.compile(pattern, re.IGNORECASE)
    except re.error:
        return None


def matches_model_group(
    group_name: str,
    model_name: str,
    patterns: Sequence[re.Pattern[str]] = (),
    operator: MatchRegexOperator = "or",
) -> bool:
    name_matches = bool(group_name.strip()) and (
        group_name.casefold() in model_name.casefold()
    )
    if not patterns:
        return name_matches
    regex_matches = any(pattern.search(model_name) for pattern in patterns)
    return (
        name_matches and regex_matches
        if operator == "and"
        else name_matches or regex_matches
    )

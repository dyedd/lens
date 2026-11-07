from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Literal

MatchRegexOperator = Literal["and", "or"]
MAX_MATCH_REGEX_LENGTH = 10_240


def combine_model_group_patterns(patterns: Sequence[str]) -> str:
    active = [pattern for pattern in patterns if pattern]
    if len(active) < 2:
        combined = active[0] if active else ""
    else:
        branches = []
        for pattern in active:
            try:
                flags = re.compile(pattern).flags
            except re.error as exc:
                raise ValueError(f"Invalid model group regex: {exc}") from exc
            body = pattern
            prefix = r"\(\?[aiLmsux]+\)|\(\?#(?:\\.|[^)])*\)"
            if flags & re.VERBOSE:
                prefix += r"|\s+|\#[^\n]*(?:\n|$)"
            while match := re.match(prefix, body):
                body = body[match.end() :]
            scoped_flags = "".join(
                letter
                for letter, flag in (
                    ("a", re.ASCII),
                    ("i", re.IGNORECASE),
                    ("m", re.MULTILINE),
                    ("s", re.DOTALL),
                    ("x", re.VERBOSE),
                )
                if flags & flag
            )
            # 全局标记改为分支作用域；末尾换行防止注释吞掉闭括号。
            if flags & re.VERBOSE:
                body += "\n"
            branches.append(f"(?{scoped_flags}:{body})")
        combined = "|".join(branches)
    if len(combined) > MAX_MATCH_REGEX_LENGTH:
        raise ValueError(
            f"Model group match regex must be at most {MAX_MATCH_REGEX_LENGTH} characters"
        )
    try:
        re.compile(combined)
    except re.error as exc:
        raise ValueError(f"Cannot combine model group regexes: {exc}") from exc
    return combined


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

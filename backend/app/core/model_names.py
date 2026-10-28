"""Model-name matching for a credential's sync filter.

A filter selects which upstream models one API key keeps. It matches whole
names, so ``gpt-4`` covers exactly ``gpt-4`` while ``gpt-4.*`` covers the
family. A filter without regex characters is a literal name compared
case-insensitively, which keeps ``claude-3.5-sonnet`` from turning its dot
into a wildcard.
"""

from __future__ import annotations

import re
from enum import Enum
from functools import lru_cache

# Characters that make a filter a regex. A dot is common in model names, so it
# only acts as a wildcard when another regex operator makes the filter a regex.
_PATTERN_METACHARACTERS = frozenset("*?+[]{}()^$|\\")

_INLINE_MODIFIER = re.compile(r"\(\?([aiLmsux]+)\)")


class ModelPatternKind(str, Enum):
    """How a filter should be applied."""

    # Empty: leave the current concrete model rows unchanged.
    EMPTY = "empty"
    # "*": every upstream model passes.
    ALL = "all"
    # No regex characters: compare the name itself.
    LITERAL = "literal"
    # A usable regex over whole names.
    REGEX = "regex"
    # Not compilable; the sync keeps every model instead of hiding them all.
    INVALID = "invalid"


def _split_inline_modifier(pattern: str) -> tuple[str, str]:
    """Split a leading ``(?i)``-style modifier from the pattern body."""
    match = _INLINE_MODIFIER.match(pattern)
    if match is None:
        return "", pattern
    return match.group(1), pattern[match.end() :]


@lru_cache(maxsize=512)
def _compile_model_pattern(pattern: str) -> re.Pattern[str] | None:
    """Compile a filter into an anchored, case-insensitive regex."""
    trimmed = pattern.strip()
    if not trimmed or trimmed == "*":
        return None
    _, body = _split_inline_modifier(trimmed)
    # Anchors are implied by whole-name matching, so a leading ``^`` or a
    # trailing ``$`` is redundant.
    body = body.strip().removeprefix("^").removesuffix("$")
    try:
        return re.compile(rf"^(?:{body})$", re.IGNORECASE)
    except re.error:
        return None


def classify_model_pattern(pattern: str) -> ModelPatternKind:
    """Return how a filter should be applied."""
    trimmed = pattern.strip()
    if not trimmed:
        return ModelPatternKind.EMPTY
    if trimmed == "*":
        return ModelPatternKind.ALL
    if not any(char in _PATTERN_METACHARACTERS for char in trimmed):
        return ModelPatternKind.LITERAL
    return (
        ModelPatternKind.REGEX
        if _compile_model_pattern(trimmed) is not None
        else ModelPatternKind.INVALID
    )


def matches_model_pattern(pattern: str, value: str) -> bool:
    """Whether one model name passes a filter."""
    kind = classify_model_pattern(pattern)
    if kind is ModelPatternKind.EMPTY:
        return False
    if kind is ModelPatternKind.ALL:
        return True
    if kind is ModelPatternKind.LITERAL:
        return pattern.strip().casefold() == value.casefold()
    if kind is ModelPatternKind.INVALID:
        # A broken filter must not silently stop matching stored names.
        return True
    compiled = _compile_model_pattern(pattern)
    return compiled is not None and compiled.match(value) is not None


def filter_model_names(names: set[str], pattern: str) -> set[str]:
    """Return the upstream names a filter keeps.

    An invalid filter keeps everything so a typo does not silently empty the
    channel; an empty filter keeps no automatic targets.
    """
    kind = classify_model_pattern(pattern)
    if kind is ModelPatternKind.EMPTY:
        return set()
    if kind in {ModelPatternKind.ALL, ModelPatternKind.INVALID}:
        return set(names)
    if kind is ModelPatternKind.LITERAL:
        folded = pattern.strip().casefold()
        return {name for name in names if name.casefold() == folded}
    compiled = _compile_model_pattern(pattern)
    if compiled is None:
        return set(names)
    return {name for name in names if compiled.match(name) is not None}

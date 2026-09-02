from __future__ import annotations

import re
from dataclasses import dataclass

_REASONING_SUFFIXES = frozenset(
    {"none", "auto", "minimal", "low", "medium", "high", "xhigh", "max"}
)
_MODEL_SUFFIX_RE = re.compile(r"^(?P<base>.+?)\s*\((?P<suffix>[^()]*)\)$")


@dataclass(frozen=True, slots=True)
class ParsedModelName:
    """A model name with an optional explicit reasoning intent."""

    base_model: str
    reasoning_effort: str | None = None
    reasoning_budget: int | None = None
    reasoning_explicit: bool = False


def parse_model_name(value: str) -> ParsedModelName:
    """Parse a model name and its supported trailing reasoning suffix.

    A parenthesized suffix is part of the routing contract. Any parenthesized
    suffix that is not one of the supported effort names or a positive integer
    is rejected instead of being sent to an upstream provider.
    """
    if not isinstance(value, str):
        raise ValueError("Model name must be a string")
    model_name = value.strip()
    if not model_name:
        raise ValueError("Model name must not be empty")

    match = _MODEL_SUFFIX_RE.fullmatch(model_name)
    if match is None:
        if model_name.endswith(")") or "(" in model_name or ")" in model_name:
            raise ValueError(f"Invalid reasoning suffix in model name: {model_name}")
        return ParsedModelName(base_model=model_name)

    base_model = match.group("base").strip()
    suffix = match.group("suffix").strip().casefold()
    if not base_model or not suffix:
        raise ValueError(f"Invalid reasoning suffix in model name: {model_name}")
    if suffix in _REASONING_SUFFIXES:
        return ParsedModelName(
            base_model=base_model,
            reasoning_effort=suffix,
            reasoning_explicit=True,
        )
    if suffix.isdecimal():
        budget = int(suffix)
        if budget <= 0:
            raise ValueError("Reasoning budget must be greater than zero")
        return ParsedModelName(
            base_model=base_model,
            reasoning_budget=budget,
            reasoning_explicit=True,
        )
    raise ValueError(f"Invalid reasoning suffix in model name: {model_name}")


__all__ = ["ParsedModelName", "parse_model_name"]

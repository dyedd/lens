"""Vendor-prefix aliases that map upstream model names to public names.

Sites list prefixes like ``openai`` so an upstream name such as
``openai/gpt-5`` also answers to the short name ``gpt-5``. Matching code
works on the alias list; the last entry is the preferred public name.
"""

from __future__ import annotations

from collections.abc import Sequence


def model_name_aliases(model_name: str, prefixes: Sequence[str]) -> list[str]:
    """Return ``[upstream_name, short_name]`` when a prefix applies."""
    for prefix in prefixes:
        prefix_with_separator = f"{prefix}/"
        if model_name.startswith(prefix_with_separator):
            return [model_name, model_name[len(prefix_with_separator) :]]
    return [model_name]


def public_name_from_aliases(aliases: Sequence[str], model_name: str) -> str:
    """Return the preferred public name for one model's alias list."""
    return aliases[-1] if len(aliases) > 1 else model_name

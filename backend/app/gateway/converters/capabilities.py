"""Helpers for features that protocols provide unevenly.

A converter that meets a part its target cannot carry has three options: drop the
part, replace it with a textual stand-in, or refuse the request. Doing the first
two blindly loses information silently; refusing outright fails requests that
were almost entirely expressible. The reference gateways settle on a per-turn
rule, adopted here:

* a part the target cannot carry is dropped from its turn, and the rest of the
  turn still goes out;
* if a *user* turn ends up with nothing sendable, the request is refused,
  because an emptied user turn breaks the conversation and hides the real
  cause behind a confusing upstream error;
* system and developer content never mask an emptied user turn, and a later
  turn never clears an earlier refusal.

The remaining helpers cover the two degradations that are otherwise lossy:
free-form custom tools (rendered as a single-string function) and namespaced
tool names (flattened to ``ns__tool``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass


class UnsupportedContentError(ValueError):
    """A request turn carried nothing the target protocol could send."""

    def __init__(self, part_type: str) -> None:
        self.part_type = part_type
        super().__init__(
            f"{part_type} content cannot be sent to this upstream protocol"
        )


@dataclass(slots=True)
class ContentDrops:
    """Track parts dropped from user turns and refuse only emptied turns.

    Callers record one ``drop`` per part the target cannot carry, then close the
    turn with the number of parts that were actually sent. ``raise_if_empty``
    reports the first turn that ended up sending nothing.
    """

    _turn: str = ""
    _first: str = ""
    _sendable: int = 0

    def drop(self, part_type: str) -> None:
        """Record that a part of the current turn cannot be sent."""
        if not self._turn:
            self._turn = part_type

    def keep(self, count: int = 1) -> None:
        """Record parts of the current turn that will be sent."""
        self._sendable += count

    def end_turn(self) -> None:
        """Close the current turn, remembering if a drop emptied it."""
        if self._turn and self._sendable <= 0 and not self._first:
            self._first = self._turn
        self._turn = ""
        self._sendable = 0

    def raise_if_empty(self) -> None:
        """Raise for the first user turn that a drop left empty."""
        if self._first:
            raise UnsupportedContentError(self._first)


def custom_tool_as_function(
    description: str, tool_format: dict[str, object] | None
) -> tuple[str, dict[str, object]]:
    """Render a custom (free-form) tool as a single-string function tool.

    Targets without custom tools accept the declaration this way; the call comes
    back as ``{"input": "..."}`` and :func:`unwrap_custom_tool_arguments`
    reverses it.
    """
    schema: dict[str, object] = {
        "type": "object",
        "properties": {
            "input": {
                "type": "string",
                "description": "The raw tool input, exactly as the tool expects it.",
            }
        },
        "required": ["input"],
        "additionalProperties": False,
    }
    grammar = _grammar_text(tool_format)
    if grammar:
        description = (
            f"{description}\n\nInput must match this grammar:\n```\n{grammar}\n```"
        )
    return description, schema


def _grammar_text(tool_format: dict[str, object] | None) -> str:
    if not tool_format:
        return ""
    for key in ("definition", "grammar", "syntax"):
        value = tool_format.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def unwrap_custom_tool_arguments(arguments: str) -> str:
    """Recover raw custom-tool input from the ``{"input": ...}`` wrapper."""
    text = (arguments or "").strip()
    if not text:
        return ""
    try:
        parsed = json.loads(text)
    except ValueError:
        return text
    if isinstance(parsed, dict) and set(parsed) == {"input"}:
        inner = parsed["input"]
        if isinstance(inner, str):
            return inner
    return text


def namespaced_name(namespace: str, name: str) -> str:
    """Flatten a namespaced tool name for protocols without namespaces."""
    if not namespace:
        return name
    return f"{namespace}__{name}"

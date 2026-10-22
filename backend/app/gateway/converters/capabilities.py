"""Degradations for parts a target protocol cannot carry.

A converter that meets such a part has three choices: drop it, replace it with
text, or refuse the request. Dropping silently loses data; refusing fails a
request that was almost entirely expressible. The rule used here works per user
turn: a part the target cannot carry is dropped and the rest of the turn still
goes out, but a turn left with nothing is refused, because an emptied turn
breaks the conversation and hides the cause behind a confusing upstream error.

Two other losses have a reversible stand-in: a free-form custom tool becomes a
single-string function, and a namespaced tool name flattens to ``ns__tool``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass


class UnsupportedContentError(ValueError):
    """A user turn carried nothing the target protocol could send."""


@dataclass(slots=True)
class ContentDrops:
    """Watch user turns and refuse only the ones a drop left empty."""

    _turn: str = ""
    _emptied: str = ""
    _sent: int = 0

    def drop(self, part_type: str) -> None:
        """Record a part of the current turn that cannot be sent."""
        if not self._turn:
            self._turn = part_type

    def keep(self, count: int) -> None:
        """Record how many parts of the current turn will be sent."""
        self._sent += count

    def end_turn(self) -> None:
        """Close the current turn, remembering if a drop emptied it."""
        if self._turn and not self._sent and not self._emptied:
            self._emptied = self._turn
        self._turn = ""
        self._sent = 0

    def raise_if_empty(self) -> None:
        """Raise for the first user turn a drop left empty."""
        if self._emptied:
            raise UnsupportedContentError(
                f"{self._emptied} content cannot be sent to this upstream protocol"
            )


def render_custom_tool(
    description: str, tool_format: dict[str, object] | None
) -> tuple[str, dict[str, object]]:
    """Render a free-form tool as a single-string function.

    The call comes back as ``{"input": "..."}``, which
    :func:`unwrap_custom_tool_input` reverses.
    """
    definition = (tool_format or {}).get("definition")
    if isinstance(definition, str) and definition.strip():
        description = (
            f"{description}\n\nInput must match this grammar:\n"
            f"```\n{definition.strip()}\n```"
        )
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
    return description, schema


def unwrap_custom_tool_input(arguments: str) -> str:
    """Recover the raw input from the ``{"input": ...}`` wrapper."""
    text = (arguments or "").strip()
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
    return f"{namespace}__{name}" if namespace else name


def as_reminder(text: str) -> str:
    """Wrap a mid-conversation instruction so it reads as a directive.

    Only Anthropic and Responses keep system content outside the turn history.
    The others receive it in place, wrapped so the model does not read it as
    something the user said.
    """
    return f"<system-reminder>\n{text}\n</system-reminder>"

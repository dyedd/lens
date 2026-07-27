from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ChatToolCall:
    index: int
    call_id: str = ""
    name: str = ""
    argument_parts: list[str] = field(default_factory=list)
    emitted_argument_parts: int = 0
    target_index: int | None = None
    announced: bool = False

    @property
    def arguments(self) -> str:
        return "".join(self.argument_parts)

    def take_argument_delta(self) -> str:
        delta = "".join(self.argument_parts[self.emitted_argument_parts :])
        self.emitted_argument_parts = len(self.argument_parts)
        return delta


class ChatToolCalls:
    def __init__(self) -> None:
        self._calls: dict[int, ChatToolCall] = {}

    def __iter__(self) -> Iterator[ChatToolCall]:
        return iter(self._calls[index] for index in sorted(self._calls))

    def update(self, value: Any) -> ChatToolCall:
        if not isinstance(value, Mapping):
            raise ValueError("Chat tool call deltas must be objects")
        index = value.get("index", 0)
        if isinstance(index, bool) or not isinstance(index, int):
            raise ValueError("Chat tool call deltas must contain an integer index")

        tool_call = self._calls.setdefault(index, ChatToolCall(index=index))
        _update_stable_string(tool_call, "call_id", value.get("id"), "id")

        function = value.get("function")
        if function is None:
            return tool_call
        if not isinstance(function, Mapping):
            raise ValueError("Chat tool call function must be an object")
        _update_stable_string(
            tool_call,
            "name",
            function.get("name"),
            "function.name",
        )
        arguments = function.get("arguments")
        if arguments is not None:
            if not isinstance(arguments, str):
                raise ValueError("Chat tool call function.arguments must be a string")
            if arguments:
                tool_call.argument_parts.append(arguments)
        return tool_call


def _update_stable_string(
    tool_call: ChatToolCall,
    attribute: str,
    value: Any,
    field_name: str,
) -> None:
    if value is None:
        return
    if not isinstance(value, str):
        raise ValueError(f"Chat tool call {field_name} must be a string")
    if not value:
        return
    current = getattr(tool_call, attribute)
    if current and current != value:
        raise ValueError(f"Chat tool call {field_name} changed during the stream")
    setattr(tool_call, attribute, value)

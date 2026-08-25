from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ChatToolCall:
    index: int
    choice_index: int = 0
    source_index: int = 0
    call_id: str = ""
    call_type: str = ""
    name: str = ""
    argument_parts: list[str] = field(default_factory=list)
    emitted_argument_parts: int = 0
    target_index: int | None = None
    announced: bool = False
    arguments_complete: bool = False

    @property
    def arguments(self) -> str:
        return "".join(self.argument_parts)

    def take_argument_delta(self) -> str:
        delta = "".join(self.argument_parts[self.emitted_argument_parts :])
        self.emitted_argument_parts = len(self.argument_parts)
        return delta


@dataclass(slots=True)
class _ToolCallUpdate:
    tool_call: ChatToolCall
    source_index: int
    value: dict[str, Any]
    force_header: bool = False


class ChatToolCalls:
    def __init__(self) -> None:
        self._calls: dict[tuple[int, int], ChatToolCall] = {}
        self._active: dict[tuple[int, int], ChatToolCall] = {}
        self._used_indices: dict[int, set[int]] = {}
        self._next_indices: dict[int, int] = {}

    def __iter__(self) -> Iterator[ChatToolCall]:
        return iter(
            self._calls[key]
            for key in sorted(self._calls, key=lambda item: (item[0], item[1]))
        )

    def update(self, value: Any, *, choice_index: int = 0) -> ChatToolCall:
        calls = self.update_many(value, choice_index=choice_index)
        if len(calls) != 1:
            raise ValueError("Chat tool call delta produced multiple tool calls")
        return calls[0]

    def update_many(self, value: Any, *, choice_index: int = 0) -> list[ChatToolCall]:
        return [
            update.tool_call
            for update in self._consume(value, choice_index=choice_index)
        ]

    def normalize_tool_call(
        self, value: Any, *, choice_index: int = 0
    ) -> list[dict[str, Any]]:
        return [
            self._render_update(update)
            for update in self._consume(value, choice_index=choice_index)
        ]

    def normalize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        choices = payload.get("choices")
        if not isinstance(choices, list):
            return payload

        normalized_choices = list(choices)
        changed = False
        for position, choice in enumerate(choices):
            if not isinstance(choice, Mapping):
                continue
            delta = choice.get("delta")
            tool_calls = delta.get("tool_calls") if isinstance(delta, Mapping) else None
            if not isinstance(tool_calls, list):
                continue

            normalized_tool_calls: list[Any] = []
            for value in tool_calls:
                if isinstance(value, Mapping):
                    normalized_tool_calls.extend(
                        self.normalize_tool_call(
                            value, choice_index=chat_choice_index(choice)
                        )
                    )
                else:
                    normalized_tool_calls.append(value)
            if normalized_tool_calls == tool_calls:
                continue
            normalized_delta = {**delta, "tool_calls": normalized_tool_calls}
            normalized_choices[position] = {**choice, "delta": normalized_delta}
            changed = True

        return {**payload, "choices": normalized_choices} if changed else payload

    def _consume(self, value: Any, *, choice_index: int) -> list[_ToolCallUpdate]:
        if not isinstance(value, Mapping):
            raise ValueError("Chat tool call deltas must be objects")
        tool_call = dict(value)
        source_index = _tool_call_index(tool_call)
        key = (choice_index, source_index)
        state = self._active.get(key)
        force_header = False

        if state is None:
            state = self._start_call(choice_index, source_index, tool_call)
        elif _is_new_call(state, tool_call):
            state = self._start_call(
                choice_index, source_index, tool_call, previous=state
            )
            force_header = True

        _remember_identity(state, tool_call)
        return self._consume_arguments(
            choice_index,
            source_index,
            state,
            tool_call,
            force_header=force_header,
        )

    def _start_call(
        self,
        choice_index: int,
        source_index: int,
        value: Mapping[str, Any],
        *,
        previous: ChatToolCall | None = None,
    ) -> ChatToolCall:
        function = _function(value)
        incoming_id = _text(value.get("id"))
        incoming_type = _text(value.get("type"))
        incoming_name = _text(function.get("name"))
        if previous is None:
            call_id = incoming_id
            call_type = incoming_type
            name = incoming_name
        else:
            call_id = incoming_id or f"call_{uuid.uuid4().hex}"
            call_type = incoming_type or previous.call_type or "function"
            name = incoming_name or previous.name

        index = self._allocate_index(choice_index, source_index)
        state = ChatToolCall(
            index=index,
            choice_index=choice_index,
            source_index=source_index,
            call_id=call_id,
            call_type=call_type,
            name=name,
        )
        self._active[(choice_index, source_index)] = state
        self._calls[(choice_index, index)] = state
        return state

    def _consume_arguments(
        self,
        choice_index: int,
        source_index: int,
        state: ChatToolCall,
        value: dict[str, Any],
        *,
        force_header: bool,
    ) -> list[_ToolCallUpdate]:
        incoming_arguments = _arguments(value)
        if not incoming_arguments:
            return [_ToolCallUpdate(state, source_index, value, force_header)]

        if state.arguments_complete and _has_new_object(
            state.arguments, incoming_arguments
        ):
            next_state = self._start_call(
                choice_index, source_index, {}, previous=state
            )
            return self._consume_arguments(
                choice_index,
                source_index,
                next_state,
                {"function": {"arguments": incoming_arguments}},
                force_header=True,
            )

        old_length = len(state.arguments)
        combined = state.arguments + incoming_arguments
        boundary = _json_object_end(combined)
        contains_two_objects = (
            not state.arguments_complete
            and boundary is not None
            and boundary > old_length
            and combined[boundary:].strip().startswith("{")
        )
        if contains_two_objects:
            first_arguments = combined[old_length:boundary]
            state.argument_parts.append(first_arguments)
            state.arguments_complete = True
            updates = [_ToolCallUpdate(state, source_index, value, force_header)]
            next_state = self._start_call(
                choice_index, source_index, {}, previous=state
            )
            updates.extend(
                self._consume_arguments(
                    choice_index,
                    source_index,
                    next_state,
                    {"function": {"arguments": combined[boundary:]}},
                    force_header=True,
                )
            )
            return updates

        state.argument_parts.append(incoming_arguments)
        state.arguments_complete = _is_complete_json_object(state.arguments)
        return [_ToolCallUpdate(state, source_index, value, force_header)]

    def _allocate_index(self, choice_index: int, source_index: int) -> int:
        used = self._used_indices.setdefault(choice_index, set())
        next_index = self._next_indices.get(choice_index, 0)
        if source_index not in used:
            logical_index = source_index
        else:
            logical_index = next_index
            while logical_index in used:
                logical_index += 1
        used.add(logical_index)
        while next_index in used:
            next_index += 1
        self._next_indices[choice_index] = next_index
        return logical_index

    @staticmethod
    def _render_update(update: _ToolCallUpdate) -> dict[str, Any]:
        tool_call = update.tool_call
        arguments = _arguments(update.value)
        argument_delta = tool_call.take_argument_delta()
        needs_rewrite = (
            update.force_header
            or tool_call.index != update.source_index
            or argument_delta != arguments
        )
        if not needs_rewrite:
            return update.value

        rendered = {**update.value, "index": tool_call.index}
        function = dict(_function(update.value))
        if "arguments" in function:
            function["arguments"] = argument_delta
        if update.force_header:
            if tool_call.call_id:
                rendered["id"] = tool_call.call_id
            rendered["type"] = tool_call.call_type or "function"
            if tool_call.name:
                function["name"] = tool_call.name
        rendered["function"] = function
        return rendered


def chat_choice_index(choice: Mapping[str, Any]) -> int:
    value = choice.get("index", 0)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _tool_call_index(value: Mapping[str, Any]) -> int:
    index = value.get("index", 0)
    if isinstance(index, bool) or not isinstance(index, int):
        raise ValueError("Chat tool call deltas must contain an integer index")
    return index


def _function(value: Mapping[str, Any]) -> Mapping[str, Any]:
    function = value.get("function")
    if function is None:
        return {}
    if not isinstance(function, Mapping):
        raise ValueError("Chat tool call function must be an object")
    return function


def _arguments(value: Mapping[str, Any]) -> str:
    arguments = _function(value).get("arguments")
    if arguments is None:
        return ""
    if not isinstance(arguments, str):
        raise ValueError("Chat tool call function.arguments must be a string")
    return arguments


def _text(value: Any) -> str:
    return value if isinstance(value, str) and value else ""


def _remember_identity(state: ChatToolCall, value: Mapping[str, Any]) -> None:
    call_id = value.get("id")
    if call_id is not None and not isinstance(call_id, str):
        raise ValueError("Chat tool call id must be a string")
    if call_id:
        if state.call_id and state.call_id != call_id:
            raise ValueError("Chat tool call id changed during the stream")
        state.call_id = call_id

    function = _function(value)
    name = function.get("name")
    if name is not None and not isinstance(name, str):
        raise ValueError("Chat tool call function.name must be a string")
    if name:
        if state.name and state.name != name:
            raise ValueError("Chat tool call function.name changed during the stream")
        state.name = name

    call_type = value.get("type")
    if call_type is not None:
        if not isinstance(call_type, str):
            raise ValueError("Chat tool call type must be a string")
        if call_type:
            state.call_type = call_type


def _is_new_call(state: ChatToolCall, value: Mapping[str, Any]) -> bool:
    incoming_id = _text(value.get("id"))
    incoming_name = _text(_function(value).get("name"))
    return bool(
        (state.call_id and incoming_id and state.call_id != incoming_id)
        or (state.name and incoming_name and state.name != incoming_name)
        or (
            state.arguments_complete
            and _arguments(value)
            and _has_new_object(state.arguments, _arguments(value))
        )
    )


def _has_new_object(existing: str, incoming: str) -> bool:
    boundary = _json_object_end(existing)
    return bool(
        boundary is not None
        and f"{existing[boundary:]}{incoming}".strip().startswith("{")
    )


def _json_object_end(value: str) -> int | None:
    start = len(value) - len(value.lstrip())
    if start >= len(value) or value[start] != "{":
        return None
    try:
        parsed, end = json.JSONDecoder().raw_decode(value, start)
    except json.JSONDecodeError:
        return None
    return end if isinstance(parsed, dict) else None


def _is_complete_json_object(value: str) -> bool:
    boundary = _json_object_end(value)
    return boundary is not None and not value[boundary:].strip()


async def normalize_chat_stream(
    raw_iterator: AsyncIterator[bytes],
    *,
    event_format: str = "sse",
) -> AsyncIterator[bytes]:
    """Normalize malformed OpenAI Chat tool-call indices in a stream."""
    tool_calls = ChatToolCalls()
    buffer = b""
    async for chunk in raw_iterator:
        if not chunk:
            continue
        buffer += chunk
        while True:
            boundary = _stream_boundary(buffer, event_format)
            if boundary is None:
                break
            boundary_index, separator_length = boundary
            frame_end = boundary_index + separator_length
            frame, buffer = buffer[:frame_end], buffer[frame_end:]
            yield _normalize_chat_frame(frame, tool_calls, event_format)
    if buffer:
        yield _normalize_chat_frame(buffer, tool_calls, event_format)


def _stream_boundary(buffer: bytes, event_format: str) -> tuple[int, int] | None:
    if event_format == "ndjson":
        newline = buffer.find(b"\n")
        if newline >= 0:
            return newline, 1
        carriage_return = buffer.find(b"\r")
        return (carriage_return, 1) if carriage_return >= 0 else None

    boundaries = [
        (buffer.find(b"\r\n\r\n"), 4),
        (buffer.find(b"\n\n"), 2),
        (buffer.find(b"\r\r"), 2),
    ]
    valid = [boundary for boundary in boundaries if boundary[0] >= 0]
    return min(valid, key=lambda boundary: boundary[0]) if valid else None


def _normalize_chat_frame(
    frame: bytes,
    tool_calls: ChatToolCalls,
    event_format: str,
) -> bytes:
    try:
        text = frame.decode("utf-8")
    except UnicodeDecodeError:
        return frame

    if event_format == "ndjson":
        return _normalize_ndjson_frame(frame, text, tool_calls)
    return _normalize_sse_frame(frame, text, tool_calls)


def _rewrite_payload_frame(
    body: str,
    tool_calls: ChatToolCalls,
) -> bytes | None:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    normalized = tool_calls.normalize_payload(payload)
    if normalized is payload:
        return None
    return json.dumps(normalized, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )


def _normalize_ndjson_frame(
    frame: bytes,
    text: str,
    tool_calls: ChatToolCalls,
) -> bytes:
    line_ending = ""
    if text.endswith("\r\n"):
        line_ending = "\r\n"
    elif text.endswith(("\n", "\r")):
        line_ending = text[-1]
    body = text[: -len(line_ending)] if line_ending else text
    if not body.strip():
        return frame
    rewritten = _rewrite_payload_frame(body, tool_calls)
    if rewritten is None:
        return frame
    return rewritten + line_ending.encode("utf-8")


def _normalize_sse_frame(
    frame: bytes,
    text: str,
    tool_calls: ChatToolCalls,
) -> bytes:
    separator = next(
        (value for value in ("\r\n\r\n", "\n\n", "\r\r") if text.endswith(value)),
        "",
    )
    body = text[: -len(separator)] if separator else text
    lines = body.splitlines()
    data_indices = [
        index for index, line in enumerate(lines) if line.startswith("data:")
    ]
    if not data_indices:
        return frame
    data = "\n".join(lines[index][5:].strip() for index in data_indices)
    if not data or data == "[DONE]":
        return frame
    rewritten = _rewrite_payload_frame(data, tool_calls)
    if rewritten is None:
        return frame

    line_separator = "\r\n" if "\r\n" in body else "\n"
    first_data = data_indices[0]
    data_index_set = set(data_indices)
    normalized_lines: list[str] = []
    for index, line in enumerate(lines):
        if index == first_data:
            normalized_lines.append("data: " + rewritten.decode("utf-8"))
        elif index not in data_index_set:
            normalized_lines.append(line)
    return (line_separator.join(normalized_lines) + separator).encode("utf-8")

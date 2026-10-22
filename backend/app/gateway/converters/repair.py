"""History repairs applied before a request is rendered.

Converted histories break rules the target enforces, and the upstream answers
with an opaque 400 instead of the real cause. Four repairs cover every pair of
the four chat protocols:

* split parallel calls are merged back into one assistant turn;
* a tool result that lost its ``call_id`` takes the id of the call it answers;
* every call gets a result and every result a call;
* each result sits right after the assistant turn that issued its call.
"""

from __future__ import annotations

from .unified import (
    ContentPart,
    Message,
    MessageRole,
    TextPart,
    ToolCallPart,
    ToolResultPart,
)

INTERRUPTED = "Tool call was interrupted before it returned a result."


def repair_history(messages: list[Message]) -> list[Message]:
    """Run the repairs in dependency order."""
    messages = _join_split_calls(messages)
    messages = _fill_call_ids(messages)
    messages = _pair_calls_and_results(messages)
    return _align_results(messages)


def _call_ids(message: Message) -> list[str]:
    return [
        part.call_id
        for part in message.parts
        if isinstance(part, ToolCallPart) and part.call_id
    ]


def _first_result(message: Message) -> ToolResultPart | None:
    for part in message.parts:
        if isinstance(part, ToolResultPart):
            return part
    return None


def _join_split_calls(messages: list[Message]) -> list[Message]:
    """Merge an assistant turn onto the previous one when it made calls.

    Anthropic reads consecutive assistant messages as one turn, and a client can
    split one turn's parallel calls across two of them. Closing the turn at the
    next assistant message would mark the first calls interrupted.
    """
    merged: list[Message] = []
    for message in messages:
        if (
            merged
            and message.role is MessageRole.ASSISTANT
            and merged[-1].role is MessageRole.ASSISTANT
            and _call_ids(merged[-1])
        ):
            merged[-1].parts.extend(message.parts)
            continue
        merged.append(message)
    return merged


def _fill_call_ids(messages: list[Message]) -> list[Message]:
    """Give a result without a ``call_id`` the id of the call it answers."""
    pending: list[str] = []
    for message in messages:
        if message.role is MessageRole.ASSISTANT:
            pending.extend(_call_ids(message))
            continue
        result = _first_result(message)
        if result is None:
            continue
        if result.call_id:
            if result.call_id in pending:
                pending.remove(result.call_id)
            continue
        if pending:
            result.call_id = pending.pop(0)
    return messages


def _pair_calls_and_results(messages: list[Message]) -> list[Message]:
    """Answer every call and find a home for every stray result."""
    answered = {
        part.call_id
        for message in messages
        for part in message.parts
        if isinstance(part, ToolResultPart) and part.call_id
    }
    calls = {
        part.call_id
        for message in messages
        if message.role is MessageRole.ASSISTANT
        for part in message.parts
        if isinstance(part, ToolCallPart) and part.call_id
    }

    paired: list[Message] = []
    for message in messages:
        paired.append(message)
        if message.role is not MessageRole.ASSISTANT:
            continue
        missing = [
            ToolResultPart(call_id=call_id, content=INTERRUPTED, is_error=True)
            for call_id in _call_ids(message)
            if call_id not in answered
        ]
        if missing:
            paired.append(Message(role=MessageRole.TOOL, parts=missing))
    return _demote_stray_results(paired, calls)


def _demote_stray_results(messages: list[Message], calls: set[str]) -> list[Message]:
    """Keep a result with no call as plain user text instead of dropping it."""
    demoted: list[Message] = []
    for message in messages:
        if message.role is not MessageRole.TOOL:
            demoted.append(message)
            continue
        kept: list[ContentPart] = []
        stray: list[ToolResultPart] = []
        for part in message.parts:
            if not isinstance(part, ToolResultPart):
                kept.append(part)
            elif part.call_id and part.call_id in calls:
                kept.append(part)
            else:
                stray.append(part)
        if kept:
            demoted.append(Message(role=MessageRole.TOOL, parts=kept))
        if stray:
            text = "\n\n".join(
                f"[tool result for unknown call {part.call_id or '<missing>'}]\n"
                f"{part.content}"
                for part in stray
            )
            demoted.append(Message(role=MessageRole.USER, parts=[TextPart(text=text)]))
    return demoted


def _align_results(messages: list[Message]) -> list[Message]:
    """Move each result right after the assistant turn that issued its call."""
    if not any(message.role is MessageRole.TOOL for message in messages):
        return messages

    anchor: dict[str, int] = {}
    for index, message in enumerate(messages):
        if message.role is MessageRole.ASSISTANT:
            for call_id in _call_ids(message):
                anchor[call_id] = index

    moved: dict[int, list[Message]] = {}
    ordered: list[tuple[int, Message]] = []
    for index, message in enumerate(messages):
        if message.role is MessageRole.TOOL:
            result = _first_result(message)
            target = anchor.get(result.call_id) if result is not None else None
            if target is not None and target < index:
                moved.setdefault(target, []).append(message)
                continue
        ordered.append((index, message))

    rebuilt: list[Message] = []
    for index, message in ordered:
        rebuilt.append(message)
        if message.role is MessageRole.ASSISTANT:
            rebuilt.extend(moved.get(index, ()))
    return rebuilt

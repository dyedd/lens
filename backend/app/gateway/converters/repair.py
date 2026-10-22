"""History repairs applied before building a wire request.

Converted histories routinely violate invariants the target protocol enforces,
and the upstream answers with an opaque 400 instead of the real cause. The
reference gateways all normalise the history first; these are the four repairs
that matter across every pair of the four chat protocols:

* ``join_split_calls`` — parallel tool calls split over several assistant
  messages become one turn again, so their results are not treated as orphans.
* ``normalize_call_ids`` — tool results that lost their ``call_id`` recover the
  id of the call they answer.
* ``repair_tool_pairing`` — every call gets a result and every result a call,
  which Anthropic requires and Responses enforces implicitly.
* ``align_tool_messages`` — tool results sit immediately after the assistant
  message that issued the calls, which OpenAI-shaped upstreams require.
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

INTERRUPTED_RESULT = "Tool call was interrupted before it returned a result."


def _call_ids(message: Message) -> list[str]:
    return [
        part.call_id
        for part in message.parts
        if isinstance(part, ToolCallPart) and part.call_id
    ]


def _tool_result_part(message: Message) -> ToolResultPart | None:
    for part in message.parts:
        if isinstance(part, ToolResultPart):
            return part
    return None


def join_split_calls(messages: list[Message]) -> list[Message]:
    """Merge an assistant turn onto the previous one when it made tool calls.

    Anthropic treats consecutive assistant messages as a single turn, and clients
    can split one turn's parallel calls across two of them. A builder that closed
    the turn at the next assistant message would mark the first calls as
    interrupted and lose their real results.
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


def normalize_call_ids(messages: list[Message]) -> list[Message]:
    """Fill in a missing tool-result ``call_id`` from the calls before it.

    Unanswered calls are consumed in order, so several results that all lost
    their ids still land on distinct calls.
    """
    pending: list[str] = []
    for message in messages:
        if message.role is MessageRole.ASSISTANT:
            for call_id in _call_ids(message):
                if call_id:
                    pending.append(call_id)
            continue
        result = _tool_result_part(message)
        if result is None:
            continue
        if result.call_id:
            if result.call_id in pending:
                pending.remove(result.call_id)
            continue
        if not pending:
            continue
        result.call_id = pending.pop(0)
    return messages


def repair_tool_pairing(
    messages: list[Message],
    *,
    synthesize_results: bool = True,
    demote_orphan_results: bool = True,
) -> list[Message]:
    """Make every call and every result have a counterpart.

    ``synthesize_results`` covers calls the client never answered (an aborted
    turn), which Anthropic rejects outright. ``demote_orphan_results`` turns a
    result with no call into plain user text instead of dropping its content.
    """
    if synthesize_results:
        messages = _synthesize_missing_results(messages)
    if demote_orphan_results:
        messages = _demote_orphan_results(messages)
    return messages


def _synthesize_missing_results(messages: list[Message]) -> list[Message]:
    answered: set[str] = {
        part.call_id
        for message in messages
        for part in message.parts
        if isinstance(part, ToolResultPart) and part.call_id
    }
    repaired: list[Message] = []
    for message in messages:
        repaired.append(message)
        if message.role is not MessageRole.ASSISTANT:
            continue
        missing = [
            ToolResultPart(
                call_id=part.call_id,
                content=INTERRUPTED_RESULT,
                is_error=True,
            )
            for part in message.parts
            if isinstance(part, ToolCallPart)
            and part.call_id
            and part.call_id not in answered
        ]
        if missing:
            repaired.append(Message(role=MessageRole.TOOL, parts=list(missing)))
    return repaired


def _demote_orphan_results(messages: list[Message]) -> list[Message]:
    # Collected up front so a result that the client placed before its call is
    # still recognised, rather than demoted because of message order.
    answered: set[str] = {
        call_id
        for message in messages
        if message.role is MessageRole.ASSISTANT
        for call_id in _call_ids(message)
    }
    demoted: list[Message] = []
    for message in messages:
        if message.role is not MessageRole.TOOL:
            demoted.append(message)
            continue
        kept: list[ContentPart] = []
        orphans: list[ToolResultPart] = []
        for part in message.parts:
            if isinstance(part, ToolResultPart):
                if part.call_id and part.call_id in answered:
                    kept.append(part)
                else:
                    orphans.append(part)
            else:
                kept.append(part)
        if kept:
            demoted.append(Message(role=MessageRole.TOOL, parts=kept))
        if orphans:
            text = "\n\n".join(
                f"[tool result for unknown call {part.call_id or '<missing>'}]\n"
                f"{part.content}"
                for part in orphans
            )
            demoted.append(Message(role=MessageRole.USER, parts=[TextPart(text=text)]))
    return demoted


def align_tool_messages(messages: list[Message]) -> list[Message]:
    """Move each tool result directly after the assistant message it answers.

    OpenAI-shaped upstreams reject a ``tool`` message that does not follow the
    assistant turn declaring its call, which any-to-chat conversion readily
    produces when the source protocol batched results differently.
    """
    if not any(message.role is MessageRole.TOOL for message in messages):
        return messages

    anchor: dict[str, int] = {}
    for index, message in enumerate(messages):
        if message.role is not MessageRole.ASSISTANT:
            continue
        for call_id in _call_ids(message):
            anchor[call_id] = index

    anchored: dict[int, list[Message]] = {}
    ordered: list[tuple[int, Message]] = []
    for index, message in enumerate(messages):
        if message.role is MessageRole.TOOL:
            result = _tool_result_part(message)
            target = anchor.get(result.call_id) if result is not None else None
            if target is not None and target < index:
                anchored.setdefault(target, []).append(message)
                continue
        ordered.append((index, message))

    rebuilt: list[Message] = []
    for index, message in ordered:
        rebuilt.append(message)
        if message.role is MessageRole.ASSISTANT:
            rebuilt.extend(anchored.get(index, ()))
    return rebuilt


def repair_history(
    messages: list[Message],
    *,
    synthesize_results: bool = True,
    demote_orphan_results: bool = True,
    align_tools: bool = True,
) -> list[Message]:
    """Apply the full repair sequence in dependency order."""
    messages = join_split_calls(messages)
    messages = normalize_call_ids(messages)
    messages = repair_tool_pairing(
        messages,
        synthesize_results=synthesize_results,
        demote_orphan_results=demote_orphan_results,
    )
    if align_tools:
        messages = align_tool_messages(messages)
    return messages

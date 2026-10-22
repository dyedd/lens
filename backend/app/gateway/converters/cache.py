"""Prompt-cache breakpoint handling for Claude-shaped targets.

Anthropic accepts at most four ``cache_control`` breakpoints per request and a
410-style rejection beyond that, so a client that sent five, or a conversion that
carried breakpoints across from another protocol, would break the request. The
reference gateways trim to the budget by value: the tool block first, then the
system prompt, then messages from the newest backwards.

``cache_control`` objects are forwarded verbatim (including ``ttl``), never
rebuilt from a boolean, because rebuilding silently downgrades 1h caching to the
5m default and moves the breakpoint off the block the client chose.
"""

from __future__ import annotations

from typing import Any

from .unified import (
    ContentPart,
    Message,
    TextPart,
    ToolDefinition,
    UnifiedRequest,
)

MAX_CACHE_BREAKPOINTS = 4

# Anthropic documents ``ttl`` as ``"5m"`` (the default) or ``"1h"``.
_VALID_TTLS = frozenset({"5m", "1h"})


def normalize_cache_control(value: Any) -> dict[str, Any] | None:
    """Return a ``cache_control`` object worth forwarding, or ``None``.

    Anthropic documents ``{"type": "ephemeral"}`` with an optional ``ttl``;
    anything else is not a breakpoint and must not be re-emitted.
    """
    if not isinstance(value, dict):
        return None
    cache_type = value.get("type")
    if cache_type != "ephemeral":
        return None
    normalized = dict(value)
    ttl = normalized.get("ttl")
    if ttl is not None and ttl not in _VALID_TTLS:
        normalized.pop("ttl", None)
    return normalized


def apply_cache_budget(request: UnifiedRequest) -> None:
    """Trim breakpoints to the target's limit, keeping the most valuable ones."""
    tools: list[tuple[str, ToolDefinition]] = []
    system: list[tuple[str, ContentPart]] = []
    messages: list[tuple[int, str, ContentPart]] = []

    for index, tool in enumerate(request.tools):
        if tool.cache_control is not None:
            tools.append((f"tool:{index}", tool))
    for index, part in enumerate(request.system):
        if _part_cache(part) is not None:
            system.append((f"system:{index}", part))
    position = 0
    for message in request.messages:
        for part in message.parts:
            if _part_cache(part) is not None:
                messages.append((position, f"message:{position}", part))
            position += 1

    total = len(tools) + len(system) + len(messages)
    if total <= MAX_CACHE_BREAKPOINTS:
        return

    kept: set[str] = set()
    for key, _ in tools:
        if len(kept) < MAX_CACHE_BREAKPOINTS:
            kept.add(key)
    for key, _ in system:
        if len(kept) < MAX_CACHE_BREAKPOINTS:
            kept.add(key)
    # Messages are kept newest first: the tail of the conversation is what a
    # follow-up turn reuses, while an older breakpoint mostly duplicates it.
    for _, key, _ in sorted(messages, key=lambda item: item[0], reverse=True):
        if len(kept) < MAX_CACHE_BREAKPOINTS:
            kept.add(key)

    for key, holder in tools + system:
        if key not in kept:
            _clear_cache(holder)
    for _, key, holder in messages:
        if key not in kept:
            _clear_cache(holder)


def _part_cache(part: ContentPart) -> dict[str, Any] | None:
    return getattr(part, "cache_control", None)


def _clear_cache(holder: ContentPart | ToolDefinition) -> None:
    holder.cache_control = None


def sink_message_breakpoint(message: Message) -> None:
    """Move a message-level breakpoint onto the last part of the message.

    Anthropic only accepts ``cache_control`` on content blocks, so a client that
    put it on the message object needs it moved to keep the same cache prefix.
    """
    cache = message.cache_control
    if cache is None:
        return
    message.cache_control = None
    for part in reversed(message.parts):
        if isinstance(part, TextPart):
            if part.cache_control is None:
                part.cache_control = cache
            return

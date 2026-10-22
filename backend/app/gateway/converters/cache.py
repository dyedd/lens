"""Prompt-cache breakpoints for Claude-shaped targets.

Anthropic accepts at most four ``cache_control`` breakpoints per request and
rejects the request beyond that, so a client that sent five, or a conversion
that carried breakpoints across from another protocol, would break it.

Objects are forwarded as the client wrote them, ``ttl`` included. Rebuilding one
from a flag would drop ``1h`` back to the ``5m`` default and move the breakpoint
off the block the client chose.
"""

from __future__ import annotations

from typing import Any

from .unified import ContentPart, Message, TextPart, UnifiedRequest

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
    """Trim breakpoints to what Anthropic accepts.

    Value order: the tool block, then the system prompt, then messages from the
    newest backwards. The tail of a conversation is what a follow-up turn
    reuses, so an older breakpoint is the one worth dropping.
    """
    tools = [tool for tool in request.tools if tool.cache_control is not None]
    system = [part for part in request.system if _cache(part) is not None]
    tail = [
        part
        for message in request.messages
        for part in message.parts
        if _cache(part) is not None
    ]

    keep: list[Any] = tools[:MAX_CACHE_BREAKPOINTS]
    keep.extend(system[: max(0, MAX_CACHE_BREAKPOINTS - len(keep))])
    room = MAX_CACHE_BREAKPOINTS - len(keep)
    if room > 0:
        keep.extend(tail[-room:])

    kept = {id(holder) for holder in keep}
    for holder in [*tools, *system, *tail]:
        if id(holder) not in kept:
            holder.cache_control = None


def _cache(part: ContentPart) -> dict[str, Any] | None:
    return getattr(part, "cache_control", None)


def sink_message_breakpoint(message: Message) -> None:
    """Move a message-level breakpoint onto the message's last text part.

    Anthropic only accepts ``cache_control`` on content blocks, so a breakpoint
    the client put on the message object has to move to keep the same prefix.
    """
    if message.cache_control is None:
        return
    cache, message.cache_control = message.cache_control, None
    for part in reversed(message.parts):
        if isinstance(part, TextPart):
            if part.cache_control is None:
                part.cache_control = cache
            return

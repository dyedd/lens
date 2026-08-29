from __future__ import annotations

from collections.abc import Iterable

from ..models.protocols import ProtocolKind

SUPPORTED_CONVERSIONS: frozenset[tuple[ProtocolKind, ProtocolKind]] = frozenset(
    {
        (ProtocolKind.OPENAI_CHAT, ProtocolKind.ANTHROPIC),
        (ProtocolKind.OPENAI_CHAT, ProtocolKind.OPENAI_RESPONSES),
        (ProtocolKind.OPENAI_RESPONSES, ProtocolKind.OPENAI_CHAT),
        (ProtocolKind.OPENAI_RESPONSES, ProtocolKind.ANTHROPIC),
    }
)


def can_reach_protocol(
    upstream_protocol: ProtocolKind, client_protocol: ProtocolKind
) -> bool:
    """Return whether an upstream protocol can serve a client protocol."""
    if upstream_protocol == client_protocol:
        return True
    return (upstream_protocol, client_protocol) in SUPPORTED_CONVERSIONS


def infer_client_protocols(
    upstream_protocols: Iterable[ProtocolKind | None],
) -> list[ProtocolKind]:
    """Return every client protocol served by the configured upstream protocols."""
    upstream_set = {protocol for protocol in upstream_protocols if protocol is not None}
    return [
        client_protocol
        for client_protocol in ProtocolKind
        if any(
            can_reach_protocol(upstream_protocol, client_protocol)
            for upstream_protocol in upstream_set
        )
    ]

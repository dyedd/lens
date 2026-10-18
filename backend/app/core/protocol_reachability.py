from __future__ import annotations

from collections.abc import Iterable

from ..models.protocols import ProtocolKind

CHAT_PROTOCOLS: frozenset[ProtocolKind] = frozenset(
    {
        ProtocolKind.OPENAI_CHAT,
        ProtocolKind.OPENAI_RESPONSES,
        ProtocolKind.ANTHROPIC,
        ProtocolKind.GEMINI,
    }
)

# Every chat protocol can serve every other one, because conversion goes
# through the unified protocol: one parser and one builder per protocol
# instead of a converter per pair. Same-protocol traffic is forwarded without
# converting, and non-chat modalities (embedding, image, rerank) stay native.
SUPPORTED_CONVERSIONS: frozenset[tuple[ProtocolKind, ProtocolKind]] = frozenset(
    (upstream, client)
    for upstream in CHAT_PROTOCOLS
    for client in CHAT_PROTOCOLS
    if upstream != client
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

from __future__ import annotations

from ..models import ProtocolKind

SUPPORTED_CONVERSIONS: frozenset[tuple[str, str]] = frozenset(
    {
        (ProtocolKind.OPENAI_CHAT.value, ProtocolKind.ANTHROPIC.value),
        (ProtocolKind.OPENAI_CHAT.value, ProtocolKind.OPENAI_RESPONSES.value),
    }
)


def can_reach_protocol(
    channel_protocol: ProtocolKind, group_protocol: ProtocolKind
) -> bool:
    """Return whether a channel protocol can serve a group protocol."""
    if channel_protocol == group_protocol:
        return True
    return (channel_protocol.value, group_protocol.value) in SUPPORTED_CONVERSIONS


def needs_conversion(
    client_protocol: ProtocolKind, channel_protocol: ProtocolKind
) -> bool:
    """Return whether serving the client requires protocol conversion."""
    return (channel_protocol.value, client_protocol.value) in SUPPORTED_CONVERSIONS


def build_protocol_conversion_matrix() -> dict[str, list[str]]:
    """Build the supported source-to-target protocol matrix."""
    matrix: dict[str, list[str]] = {p.value: [p.value] for p in ProtocolKind}
    for channel_value, reachable_value in SUPPORTED_CONVERSIONS:
        targets = matrix.setdefault(channel_value, [channel_value])
        if reachable_value not in targets:
            targets.append(reachable_value)
    return matrix

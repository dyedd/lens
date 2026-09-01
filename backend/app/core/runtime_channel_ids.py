from __future__ import annotations

from ..models.protocols import ProtocolKind


def compose_runtime_channel_id(protocol_config_id: str, protocol: ProtocolKind) -> str:
    """Compose a runtime channel identifier for a protocol configuration."""
    return f"{protocol_config_id}_{protocol.value}"


def split_runtime_channel_id(channel_id: str) -> tuple[str, ProtocolKind] | None:
    """Split a runtime channel identifier into its configuration and protocol."""
    for protocol in ProtocolKind:
        suffix = f"_{protocol.value}"
        if channel_id.endswith(suffix):
            return channel_id[: -len(suffix)], protocol
    return None


def protocol_config_id_from_runtime_channel_id(channel_id: str) -> str:
    """Extract the protocol configuration identifier from a runtime channel ID."""
    parsed = split_runtime_channel_id(channel_id)
    return parsed[0] if parsed is not None else channel_id

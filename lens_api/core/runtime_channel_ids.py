from __future__ import annotations

from ..models import ProtocolKind


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


def runtime_channel_protocol(channel_id: str) -> ProtocolKind | None:
    """Extract the protocol encoded in a runtime channel identifier."""
    parsed = split_runtime_channel_id(channel_id)
    return parsed[1] if parsed is not None else None


def extract_protocol_config_id(
    channel_id: str, known_protocol_config_ids: set[str]
) -> str:
    """Resolve a channel ID to a known protocol configuration identifier."""
    if channel_id in known_protocol_config_ids:
        return channel_id
    protocol_config_id = protocol_config_id_from_runtime_channel_id(channel_id)
    if protocol_config_id in known_protocol_config_ids:
        return protocol_config_id
    return channel_id


def resolve_group_item_runtime_channel_id(
    channel_id: str,
    *,
    known_protocol_config_ids: set[str],
    protocols_by_config_id: dict[str, list[ProtocolKind]],
) -> str:
    """Resolve a persisted group item channel ID to its runtime identifier."""
    protocol_config_id = extract_protocol_config_id(
        channel_id, known_protocol_config_ids
    )
    if protocol_config_id not in known_protocol_config_ids:
        return channel_id

    parsed_protocol = runtime_channel_protocol(channel_id)
    available_protocols = protocols_by_config_id.get(protocol_config_id, [])
    if parsed_protocol in available_protocols:
        return compose_runtime_channel_id(protocol_config_id, parsed_protocol)

    return channel_id

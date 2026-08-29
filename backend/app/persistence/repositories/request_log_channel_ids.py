from __future__ import annotations

from collections.abc import Iterable

from ...core.runtime_channel_ids import split_runtime_channel_id
from ...models.protocols import ProtocolKind


def group_channel_ids_by_protocol_config(
    channel_ids: Iterable[str | None],
) -> tuple[dict[str, list[str]], dict[str, ProtocolKind]]:
    """Group runtime channel IDs by protocol configuration."""
    channels_by_protocol_config: dict[str, list[str]] = {}
    protocol_by_channel_id: dict[str, ProtocolKind] = {}
    seen_channel_ids: set[str] = set()

    for raw_channel_id in channel_ids:
        channel_id = raw_channel_id.strip() if isinstance(raw_channel_id, str) else ""
        if not channel_id or channel_id in seen_channel_ids:
            continue
        seen_channel_ids.add(channel_id)

        parsed = split_runtime_channel_id(channel_id)
        protocol_config_id = parsed[0] if parsed is not None else channel_id
        if parsed is not None:
            protocol_by_channel_id[channel_id] = parsed[1]
        channels_by_protocol_config.setdefault(protocol_config_id, []).append(
            channel_id
        )

    return channels_by_protocol_config, protocol_by_channel_id

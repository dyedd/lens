from __future__ import annotations

from functools import lru_cache
import re

from ...models import (
    ChannelConfig,
    ChannelKeyItem,
    ChannelStatus,
    ProtocolKind,
)
from ..converters import can_reach_protocol
from .types import RouteTarget


@lru_cache(maxsize=2048)
def _compile_model_pattern(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern)


def _matches_pattern(pattern: str, value: str) -> bool:
    try:
        return bool(_compile_model_pattern(pattern).search(value))
    except re.error:
        return False


def _matches_model(channel: ChannelConfig, requested_model: str | None) -> bool:
    if not requested_model:
        return True

    if channel.model_patterns:
        return any(
            _matches_pattern(pattern, requested_model)
            for pattern in channel.model_patterns
        )

    return True


def _find_key(channel: ChannelConfig, credential_id: str) -> ChannelKeyItem | None:
    for key in channel.keys:
        if key.id == credential_id:
            return key
    return None


def _candidate_keys(
    channel: ChannelConfig, model_name: str | None
) -> list[ChannelKeyItem]:
    enabled_keys = [key for key in channel.keys if key.enabled]
    if not model_name or not channel.models:
        return enabled_keys

    credential_ids = {
        item.credential_id
        for item in channel.models
        if item.enabled and _matches_pattern(item.model_name, model_name)
    }
    return [key for key in enabled_keys if key.id in credential_ids]


def _expand_target_credentials(target: RouteTarget) -> list[RouteTarget]:
    if target.credential_id:
        key = _find_key(target.channel, target.credential_id)
        if key is None or not key.enabled:
            return []
        return [
            RouteTarget(
                channel=target.channel,
                model_name=target.model_name,
                credential_id=key.id,
                credential_name=target.credential_name or key.remark,
            )
        ]

    if not target.channel.keys:
        return [target]

    return [
        RouteTarget(
            channel=target.channel,
            model_name=target.model_name,
            credential_id=key.id,
            credential_name=key.remark,
        )
        for key in _candidate_keys(target.channel, target.model_name)
    ]


def filter_enabled_targets(
    channels: list[ChannelConfig],
    protocol: ProtocolKind,
    requested_model: str | None,
    allowed_channel_ids: set[str] | None,
    use_model_matching: bool,
    route_targets: list[RouteTarget] | None,
) -> list[RouteTarget]:
    if route_targets is not None:
        active: list[RouteTarget] = []
        for target in route_targets:
            if target.channel.status != ChannelStatus.ENABLED:
                continue
            if not can_reach_protocol(target.channel.protocol, protocol):
                continue
            if (
                allowed_channel_ids is not None
                and target.channel.id not in allowed_channel_ids
            ):
                continue
            active.extend(_expand_target_credentials(target))
        return active

    active: list[RouteTarget] = []
    for channel in sorted(channels, key=lambda item: item.name):
        if channel.protocol != protocol or channel.status != ChannelStatus.ENABLED:
            continue
        if allowed_channel_ids is not None and channel.id not in allowed_channel_ids:
            continue
        if use_model_matching and not _matches_model(channel, requested_model):
            continue
        active.extend(
            _expand_target_credentials(
                RouteTarget(channel=channel, model_name=requested_model)
            )
        )
    return active

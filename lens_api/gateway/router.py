from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import re
from threading import Lock
from time import monotonic

from ..models import ChannelConfig, ChannelHealth, ChannelStatus, ProtocolKind, RoutePreview, RoutePreviewItem, RouteState, RouterSnapshot, RoutingStrategy


@dataclass
class _HealthState:
    consecutive_failures: int = 0
    last_error: str | None = None
    opened_until: float = 0.0


@dataclass
class _RouteCursor:
    next_index: int = 0


@dataclass
class RouteTarget:
    channel: ChannelConfig
    model_name: str | None = None


@dataclass
class RouteSelection:
    primary: RouteTarget
    fallbacks: list[RouteTarget] = field(default_factory=list)


class RoundRobinRouter:
    def __init__(self) -> None:
        self._lock = Lock()
        self._cursors: dict[str, _RouteCursor] = {}
        self._health: dict[str, _HealthState] = defaultdict(_HealthState)

    def select(
        self,
        channels: list[ChannelConfig],
        protocol: ProtocolKind,
        requested_model: str | None = None,
        strategy: RoutingStrategy = RoutingStrategy.ROUND_ROBIN,
        allowed_channel_ids: set[str] | None = None,
        use_model_matching: bool = True,
        route_targets: list[RouteTarget] | None = None,
        cursor_key: str | None = None,
    ) -> RouteSelection:
        active = self._build_active_pool(channels, protocol, requested_model, allowed_channel_ids, use_model_matching, route_targets)
        if not active:
            detail = f"No enabled channels available for protocol={protocol.value}"
            if requested_model:
                detail = f"No enabled channels matched {requested_model}"
            raise LookupError(detail)

        route_key = cursor_key or protocol.value
        if strategy == RoutingStrategy.FAILOVER:
            primary_index = 0
        else:
            with self._lock:
                cursor = self._cursors.setdefault(route_key, _RouteCursor())
                primary_index = cursor.next_index % len(active)
                cursor.next_index = (primary_index + 1) % len(active)

        primary = active[primary_index]
        fallbacks = active[primary_index + 1 :] + active[:primary_index]
        return RouteSelection(primary=primary, fallbacks=fallbacks)

    def record_success(self, channel_id: str) -> None:
        with self._lock:
            self._health[channel_id] = _HealthState()

    def record_failure(
        self,
        channel_id: str,
        error: str,
        *,
        threshold: int = 0,
        cooldown_seconds: int = 0,
        max_cooldown_seconds: int = 0,
    ) -> None:
        with self._lock:
            state = self._health[channel_id]
            state.consecutive_failures += 1
            state.last_error = error
            if threshold > 0 and state.consecutive_failures >= threshold:
                extra_failures = max(state.consecutive_failures - threshold, 0)
                base_cooldown = max(cooldown_seconds, 1)
                max_cooldown = max(max_cooldown_seconds, base_cooldown)
                cooldown = min(base_cooldown * (2 ** extra_failures), max_cooldown)
                state.opened_until = max(state.opened_until, monotonic() + cooldown)

    def is_channel_available(self, channel_id: str) -> bool:
        with self._lock:
            state = self._health[channel_id]
            if state.opened_until <= 0:
                return True
            if state.opened_until <= monotonic():
                state.opened_until = 0.0
                return True
            return False

    def snapshot(self, channels: list[ChannelConfig]) -> RouterSnapshot:
        routes = []
        for protocol in ProtocolKind:
            pool = self._build_active_pool(channels, protocol, None)
            with self._lock:
                next_index = self._cursors.get(protocol.value, _RouteCursor()).next_index

            routes.append(
                RouteState(
                    protocol=protocol,
                    next_index=next_index,
                    channel_ids=[target.channel.id for target in pool],
                    requested_model=None,
                )
            )

        with self._lock:
            health = [
                ChannelHealth(
                    channel_id=channel.id,
                    consecutive_failures=self._health[channel.id].consecutive_failures,
                    last_error=self._health[channel.id].last_error,
                )
                for channel in channels
            ]

        return RouterSnapshot(routes=routes, health=health)

    def preview(
        self,
        channels: list[ChannelConfig],
        protocol: ProtocolKind,
        requested_model: str | None,
        strategy: RoutingStrategy = RoutingStrategy.ROUND_ROBIN,
        allowed_channel_ids: set[str] | None = None,
        use_model_matching: bool = True,
        matched_group_name: str | None = None,
        route_targets: list[RouteTarget] | None = None,
    ) -> RoutePreview:
        pool = self._build_active_pool(channels, protocol, requested_model, allowed_channel_ids, use_model_matching, route_targets)
        return RoutePreview(
            protocol=protocol,
            requested_model=requested_model,
            matched_group_name=matched_group_name,
            strategy=strategy,
            matched_channel_ids=[target.channel.id for target in pool],
            items=[
                RoutePreviewItem(
                    channel_id=target.channel.id,
                    channel_name=target.channel.name,
                    model_name=target.model_name,
                )
                for target in pool
            ],
        )

    @staticmethod
    def _build_active_pool(
        channels: list[ChannelConfig],
        protocol: ProtocolKind,
        requested_model: str | None,
        allowed_channel_ids: set[str] | None = None,
        use_model_matching: bool = True,
        route_targets: list[RouteTarget] | None = None,
    ) -> list[RouteTarget]:
        channel_map = {channel.id: channel for channel in channels}
        if route_targets is not None:
            return [
                target
                for target in route_targets
                if target.channel.status == ChannelStatus.ENABLED
                and (allowed_channel_ids is None or target.channel.id in allowed_channel_ids)
            ]

        active: list[RouteTarget] = []
        for channel in sorted(channels, key=lambda item: item.name):
            if channel.protocol != protocol or channel.status != ChannelStatus.ENABLED:
                continue
            if allowed_channel_ids is not None and channel.id not in allowed_channel_ids:
                continue
            if use_model_matching and not _matches_model(channel, requested_model):
                continue
            resolved = channel_map.get(channel.id, channel)
            active.append(RouteTarget(channel=resolved, model_name=requested_model))
        return active


def _matches_model(channel: ChannelConfig, requested_model: str | None) -> bool:
    if not requested_model:
        return True

    if channel.model_patterns:
        for pattern in channel.model_patterns:
            try:
                if re.search(pattern, requested_model):
                    return True
            except re.error:
                continue
        return False

    return True

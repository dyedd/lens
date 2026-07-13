from __future__ import annotations

from dataclasses import dataclass
from time import monotonic

from ...core.runtime_channel_ids import protocol_config_id_from_runtime_channel_id
from ...models import ChannelConfig, ProtocolKind, RouteState, RoutingStrategy
from .health import _HealthTracker
from .targets import filter_enabled_targets
from .types import RouteSelection, RouteTarget


@dataclass(slots=True)
class _SWRRNode:
    current_weight: int = 0


class _RoutePlanner:
    def __init__(self, health: _HealthTracker) -> None:
        self._health = health
        self._swrr_nodes: dict[tuple[str, str, str], _SWRRNode] = {}

    def select(
        self,
        channels: list[ChannelConfig],
        protocol: ProtocolKind,
        requested_model: str | None,
        strategy: RoutingStrategy,
        allowed_channel_ids: set[str] | None,
        use_model_matching: bool,
        route_targets: list[RouteTarget] | None,
        cursor_key: str | None,
    ) -> RouteSelection:
        active = self._build_active_pool(
            channels,
            protocol,
            requested_model,
            allowed_channel_ids,
            use_model_matching,
            route_targets,
        )
        if not active:
            all_matching = self._build_active_pool(
                channels,
                protocol,
                requested_model,
                allowed_channel_ids,
                use_model_matching,
                route_targets,
                skip_health_filter=True,
            )
            if all_matching:
                detail = f"All {len(all_matching)} matching channels are in cooldown"
            else:
                detail = f"No enabled channels available for protocol={protocol.value}"
                if requested_model:
                    detail = f"No enabled channels matched {requested_model}"
            raise LookupError(detail)

        route_key = cursor_key or protocol.value
        primary_index = (
            0
            if strategy == RoutingStrategy.FAILOVER
            else self._swrr_pick_index(active, route_key, mutate=True)
        )
        primary = active[primary_index]
        fallbacks = active[primary_index + 1 :] + active[:primary_index]
        return RouteSelection(primary=primary, fallbacks=fallbacks)

    def build_route_state(
        self, channels: list[ChannelConfig], protocol: ProtocolKind, *, now: float
    ) -> RouteState:
        pool = self._build_active_pool(
            channels, protocol, None, skip_health_filter=True
        )
        ordered_targets, next_channel_id = self._prepare_diagnostic_targets(
            pool,
            strategy=RoutingStrategy.ROUND_ROBIN,
            cursor_key=protocol.value,
            protocol=protocol,
            now=now,
        )
        availability = [
            self._health.is_target_available(target, now=now)
            for target in ordered_targets
        ]
        return RouteState(
            protocol=protocol,
            next_index=0,
            next_channel_id=next_channel_id,
            channel_ids=[target.channel.id for target in ordered_targets],
            available_channel_ids=[
                target.channel.id
                for target, is_available in zip(ordered_targets, availability)
                if is_available
            ],
            cooldown_channel_ids=[
                target.channel.id
                for target, is_available in zip(ordered_targets, availability)
                if not is_available
            ],
            requested_model=None,
        )

    def _build_active_pool(
        self,
        channels: list[ChannelConfig],
        protocol: ProtocolKind,
        requested_model: str | None,
        allowed_channel_ids: set[str] | None = None,
        use_model_matching: bool = True,
        route_targets: list[RouteTarget] | None = None,
        *,
        skip_health_filter: bool = False,
    ) -> list[RouteTarget]:
        active = filter_enabled_targets(
            channels,
            protocol,
            requested_model,
            allowed_channel_ids,
            use_model_matching,
            route_targets,
        )
        if skip_health_filter:
            return active

        now = monotonic()
        active = [
            target
            for target in active
            if self._health.is_target_available(target, now=now)
        ]
        active = self._prefer_native_targets(active, protocol)
        if len(active) > 1:
            active.sort(
                key=lambda target: self._health.score(target.channel.id), reverse=True
            )
        return active

    @staticmethod
    def _prefer_native_targets(
        targets: list[RouteTarget], protocol: ProtocolKind
    ) -> list[RouteTarget]:
        target_keys = [
            (
                target,
                (
                    protocol_config_id_from_runtime_channel_id(target.channel.id),
                    target.credential_id,
                    target.model_name,
                ),
            )
            for target in targets
        ]
        native_available_by_key: dict[tuple[str, str | None, str | None], bool] = {}
        for target, key in target_keys:
            if target.channel.protocol == protocol:
                native_available_by_key[key] = True
            elif key not in native_available_by_key:
                native_available_by_key[key] = False

        return [
            target
            for target, key in target_keys
            if target.channel.protocol == protocol
            or not native_available_by_key.get(key, False)
        ]

    def _swrr_pick_index(
        self, active: list[RouteTarget], route_key: str, *, mutate: bool
    ) -> int:
        total_weight = 0
        best_index = 0
        next_weights: list[int] = []

        for index, target in enumerate(active):
            node_key = (route_key, target.channel.id, target.credential_id or "")
            node = self._swrr_nodes.get(node_key)
            current_weight = node.current_weight if node is not None else 0
            next_weight = current_weight + 1
            next_weights.append(next_weight)
            total_weight += 1
            if next_weight > next_weights[best_index]:
                best_index = index

        if mutate:
            for index, target in enumerate(active):
                node_key = (route_key, target.channel.id, target.credential_id or "")
                node = self._swrr_nodes.setdefault(node_key, _SWRRNode())
                node.current_weight = next_weights[index]
            best = active[best_index]
            self._swrr_nodes[
                (route_key, best.channel.id, best.credential_id or "")
            ].current_weight -= total_weight
        return best_index

    def _prepare_diagnostic_targets(
        self,
        targets: list[RouteTarget],
        *,
        strategy: RoutingStrategy,
        cursor_key: str | None,
        protocol: ProtocolKind,
        now: float,
    ) -> tuple[list[RouteTarget], str | None]:
        if not targets:
            return [], None
        available: list[RouteTarget] = []
        cooled: list[RouteTarget] = []
        for target in targets:
            (
                available
                if self._health.is_target_available(target, now=now)
                else cooled
            ).append(target)
        available.sort(
            key=lambda target: self._health.score(target.channel.id), reverse=True
        )
        cooled.sort(
            key=lambda target: self._health.score(target.channel.id), reverse=True
        )

        if not available:
            return cooled, None

        route_key = cursor_key or protocol.value
        primary_index = (
            0
            if strategy == RoutingStrategy.FAILOVER
            else self._swrr_pick_index(available, route_key, mutate=False)
        )
        ordered_available = available[primary_index:] + available[:primary_index]
        return ordered_available + cooled, ordered_available[0].channel.id

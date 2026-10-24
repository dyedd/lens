from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic
from typing import Protocol

from ...core.errors import RoutingError
from ...core.runtime_channel_ids import protocol_config_id_from_runtime_channel_id
from ...models.channels import ChannelConfig
from ...models.protocols import ProtocolKind, RoutingStrategy
from ...models.routing import RouteState
from .targets import (
    RouteTarget,
    build_route_targets,
    endpoint_priority,
    target_key,
)


@dataclass(slots=True)
class RouteSelection:
    """Contain the selected primary route and every remaining candidate.

    ``fallbacks`` also carries targets that are cooling right now: the failover
    loop claims a single recovery probe on them instead of failing the request.
    """

    primary: RouteTarget
    fallbacks: list[RouteTarget] = field(default_factory=list)

    def ordered(self) -> list[RouteTarget]:
        """Return the primary followed by every fallback in selection order."""
        return [self.primary, *self.fallbacks]


class RouteHealth(Protocol):
    """What route planning needs to know about target health."""

    def is_target_available(self, target: RouteTarget, *, now: float) -> bool: ...

    def cooldown_remaining_seconds(
        self, target: RouteTarget, *, now: float
    ) -> float: ...

    def score(self, target: RouteTarget) -> float: ...

    def cooldown_reason(self, target: RouteTarget, *, now: float) -> str: ...


@dataclass(slots=True)
class _SWRRNode:
    current_weight: int = 0


def _keep_targets_fitting_context(
    targets: list[RouteTarget], required_context_tokens: int | None
) -> list[RouteTarget]:
    """Drop targets whose known context window is too small for the request.

    Targets without a configured context window stay in the pool, and when no
    target is known to fit the pool is left unchanged: the request size is an
    estimate, and members that reject it still fail over to the next one.
    """
    if not required_context_tokens:
        return targets
    fitting = [
        target
        for target in targets
        if target.context_window is None
        or target.context_window >= required_context_tokens
    ]
    return fitting or targets


class RoutePlanner:
    def __init__(self, health: RouteHealth) -> None:
        self._health = health
        self._swrr_nodes: dict[tuple[str, str, str, str], _SWRRNode] = {}
        self._affinity_seconds = 0.0
        self._affinity: dict[str, tuple[RouteTarget, float]] = {}
        self._affinity_armed: set[str] = set()

    def configure_affinity(self, seconds: float) -> None:
        self._affinity_seconds = max(seconds, 0.0)
        if self._affinity_seconds <= 0:
            self._affinity.clear()

    def note_failure(self, route_key: str) -> None:
        self._affinity_armed.add(route_key)

    def note_success(self, route_key: str, target: RouteTarget) -> None:
        if route_key not in self._affinity_armed:
            return
        self._affinity_armed.discard(route_key)
        if self._affinity_seconds > 0:
            self._affinity[route_key] = (target, monotonic() + self._affinity_seconds)

    def reset_weights(self) -> None:
        self._swrr_nodes.clear()

    def discard_channels(self, channel_ids: set[str]) -> None:
        if not channel_ids:
            return
        for node_key in list(self._swrr_nodes):
            if node_key[1] in channel_ids:
                self._swrr_nodes.pop(node_key, None)

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
        required_context_tokens: int | None = None,
    ) -> RouteSelection:
        pool = self._build_active_pool(
            channels,
            protocol,
            requested_model,
            allowed_channel_ids,
            use_model_matching,
            route_targets,
            required_context_tokens=required_context_tokens,
        )
        now = monotonic()
        available = [
            target
            for target in pool
            if self._health.is_target_available(target, now=now)
        ]
        cooling = [
            target
            for target in pool
            if not self._health.is_target_available(target, now=now)
        ]
        if not available and not cooling:
            detail = f"No enabled channels available for protocol={protocol.value}"
            if requested_model:
                detail = f"No enabled channels matched {requested_model}"
            raise RoutingError(detail)

        route_key = cursor_key or protocol.value
        preferred_priority = max(
            (endpoint_priority(target.channel, protocol) for target in available),
            default=0,
        )
        preferred_available = [
            target
            for target in available
            if endpoint_priority(target.channel, protocol) == preferred_priority
        ]
        fallback_available = [
            target
            for target in available
            if endpoint_priority(target.channel, protocol) < preferred_priority
        ]
        ordered_available = [
            *self._order_available(preferred_available, route_key, strategy),
            *self._order_available(fallback_available, route_key, strategy),
        ]
        affinity = self._affinity.get(route_key)
        if affinity is not None:
            affinity_target, until = affinity
            if until <= now:
                self._affinity.pop(route_key, None)
            else:
                for index, target in enumerate(ordered_available):
                    if target_key(target) == target_key(affinity_target):
                        ordered_available.insert(0, ordered_available.pop(index))
                        break
        cooling.sort(
            key=lambda target: (
                -endpoint_priority(target.channel, protocol),
                self._health.cooldown_remaining_seconds(target, now=now),
            )
        )
        primary = ordered_available[0] if ordered_available else cooling[0]
        remaining = ordered_available[1:] if ordered_available else cooling[1:]
        if cooling and ordered_available:
            remaining = [*remaining, *cooling]
        return RouteSelection(primary=primary, fallbacks=remaining)

    def _order_available(
        self,
        available: list[RouteTarget],
        route_key: str,
        strategy: RoutingStrategy,
    ) -> list[RouteTarget]:
        if not available:
            return []
        if strategy == RoutingStrategy.FAILOVER:
            return list(available)
        primary_index = self._swrr_pick_index(available, route_key, mutate=True)
        primary = available[primary_index]
        fallbacks = [
            target for index, target in enumerate(available) if index != primary_index
        ]
        fallbacks.sort(key=self._health.score, reverse=True)
        return [primary, *fallbacks]

    def build_route_state(
        self, channels: list[ChannelConfig], protocol: ProtocolKind, *, now: float
    ) -> RouteState:
        pool = self._build_active_pool(channels, protocol, None)
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
                for target, is_available in zip(
                    ordered_targets, availability, strict=True
                )
                if is_available
            ],
            cooldown_channel_ids=[
                target.channel.id
                for target, is_available in zip(
                    ordered_targets, availability, strict=True
                )
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
        required_context_tokens: int | None = None,
    ) -> list[RouteTarget]:
        pool = _keep_targets_fitting_context(
            build_route_targets(
                channels,
                protocol,
                requested_model,
                allowed_channel_ids,
                use_model_matching,
                route_targets,
            ),
            required_context_tokens,
        )
        # Native protocol targets win over converted ones regardless of health:
        # a converted sibling must not shadow the channel's own protocol.
        return self._prefer_native_targets(pool, protocol)

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
        node_keys: list[tuple[str, str, str, str]] = []

        for index, target in enumerate(active):
            node_key = (
                route_key,
                target.channel.id,
                target.credential_id or "",
                target.model_name or "",
            )
            node_keys.append(node_key)
            node = self._swrr_nodes.get(node_key)
            current_weight = node.current_weight if node is not None else 0
            effective_weight = max(int(self._health.score(target) * 1000), 1)
            next_weight = current_weight + effective_weight
            next_weights.append(next_weight)
            total_weight += effective_weight
            if next_weight > next_weights[best_index]:
                best_index = index

        if mutate:
            active_node_keys = set(node_keys)
            for node_key in list(self._swrr_nodes):
                if node_key[0] == route_key and node_key not in active_node_keys:
                    self._swrr_nodes.pop(node_key, None)
            for index, node_key in enumerate(node_keys):
                node = self._swrr_nodes.setdefault(node_key, _SWRRNode())
                node.current_weight = next_weights[index]
            self._swrr_nodes[node_keys[best_index]].current_weight -= total_weight
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
        if not available:
            return cooled, None

        route_key = cursor_key or protocol.value
        preferred_priority = max(
            endpoint_priority(target.channel, protocol) for target in available
        )
        preferred_available = [
            target
            for target in available
            if endpoint_priority(target.channel, protocol) == preferred_priority
        ]
        fallback_available = [
            target
            for target in available
            if endpoint_priority(target.channel, protocol) < preferred_priority
        ]

        def order_group(group: list[RouteTarget]) -> list[RouteTarget]:
            if not group:
                return []
            primary_index = (
                0
                if strategy == RoutingStrategy.FAILOVER
                else self._swrr_pick_index(group, route_key, mutate=False)
            )
            primary = group[primary_index]
            remaining = [
                target for index, target in enumerate(group) if index != primary_index
            ]
            if strategy != RoutingStrategy.FAILOVER:
                remaining.sort(key=self._health.score, reverse=True)
            return [primary, *remaining]

        ordered_available = [
            *order_group(preferred_available),
            *order_group(fallback_available),
        ]
        cooled.sort(key=lambda target: -endpoint_priority(target.channel, protocol))
        return ordered_available + cooled, ordered_available[0].channel.id

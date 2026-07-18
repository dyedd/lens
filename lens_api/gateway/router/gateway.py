from __future__ import annotations

from threading import Lock
from time import monotonic

from ...models import (
    ChannelConfig,
    ChannelKeyItem,
    ProtocolKind,
    RouterSnapshot,
    RoutingStrategy,
)
from .health import _HealthTracker
from .routing import _RoutePlanner
from .types import RouteSelection, RouteTarget


class GatewayRouter:
    """Select gateway routes and track their runtime health."""

    def __init__(
        self,
        *,
        health_window_seconds: int = 300,
        health_penalty_weight: float = 0.5,
        health_min_samples: int = 10,
    ) -> None:
        self._lock = Lock()
        self._health = _HealthTracker(
            health_window_seconds=health_window_seconds,
            health_penalty_weight=health_penalty_weight,
            health_min_samples=health_min_samples,
        )
        self._routes = _RoutePlanner(self._health)

    def configure_health_scoring(
        self,
        *,
        health_window_seconds: int,
        health_penalty_weight: float,
        health_min_samples: int,
    ) -> None:
        """Configure the health scoring window and penalty settings."""
        with self._lock:
            self._health.configure(
                health_window_seconds=health_window_seconds,
                health_penalty_weight=health_penalty_weight,
                health_min_samples=health_min_samples,
            )

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
        """Select a primary route and ordered fallbacks."""
        with self._lock:
            return self._routes.select(
                channels,
                protocol,
                requested_model,
                strategy,
                allowed_channel_ids,
                use_model_matching,
                route_targets,
                cursor_key,
            )

    def snapshot(self, channels: list[ChannelConfig]) -> RouterSnapshot:
        """Build a snapshot of route ordering and channel health."""
        with self._lock:
            now = monotonic()
            routes = [
                self._routes.build_route_state(channels, protocol, now=now)
                for protocol in ProtocolKind
            ]
            health = [
                self._health.build_channel_health(channel, now=now)
                for channel in channels
            ]
        return RouterSnapshot(routes=routes, health=health)

    def record_success(
        self, channel_id: str, *, credential_id: str | None = None
    ) -> None:
        """Record a successful channel or credential request."""
        with self._lock:
            self._health.record_success(channel_id, credential_id=credential_id)

    def record_failure(
        self,
        channel_id: str,
        error: str,
        *,
        status_code: int | None = None,
        credential_id: str | None = None,
        channel_keys: list[ChannelKeyItem] | None = None,
        threshold: int = 0,
        cooldown_seconds: int = 0,
        max_cooldown_seconds: int = 0,
    ) -> None:
        """Record a failed request and apply any required cooldown."""
        with self._lock:
            self._health.record_failure(
                channel_id,
                error,
                status_code=status_code,
                credential_id=credential_id,
                channel_keys=channel_keys,
                threshold=threshold,
                cooldown_seconds=cooldown_seconds,
                max_cooldown_seconds=max_cooldown_seconds,
            )

    def record_key_failure(
        self,
        channel_id: str,
        key_id: str,
        status_code: int | None = None,
        *,
        max_cooldown_seconds: int = 0,
    ) -> None:
        """Record a credential failure and apply its cooldown."""
        with self._lock:
            self._health.record_key_failure(
                channel_id, key_id, status_code, max_cooldown_seconds
            )

    def record_key_success(self, channel_id: str, key_id: str) -> None:
        """Clear the recorded cooldown state for a credential."""
        with self._lock:
            self._health.record_key_success(channel_id, key_id)

    def is_channel_available(self, channel_id: str) -> bool:
        """Return whether a channel is currently available."""
        with self._lock:
            return self._health.is_channel_available(channel_id)

    def is_target_available(self, target: RouteTarget) -> bool:
        """Return whether a route target is currently available."""
        with self._lock:
            return self._health.is_target_available(target, now=monotonic())


__all__ = ["GatewayRouter"]

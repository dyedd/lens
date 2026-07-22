from __future__ import annotations

from threading import Lock
from time import monotonic

from ...models import (
    ChannelConfig,
    ProtocolKind,
    RouterSnapshot,
    RoutingStrategy,
)
from .cooldown import CooldownPolicy, ErrorCategory
from .health import _HealthTracker
from .routing import _RoutePlanner
from .types import RouteSelection, RouteTarget


class GatewayRouter:
    """Select gateway routes and track their runtime health."""

    def __init__(
        self,
        *,
        health_scoring_enabled: bool = True,
        health_window_seconds: int = 300,
        health_penalty_weight: float = 0.5,
        health_min_samples: int = 10,
    ) -> None:
        self._lock = Lock()
        self._health = _HealthTracker(
            health_scoring_enabled=health_scoring_enabled,
            health_window_seconds=health_window_seconds,
            health_penalty_weight=health_penalty_weight,
            health_min_samples=health_min_samples,
        )
        self._routes = _RoutePlanner(self._health)

    def configure(
        self,
        *,
        health_scoring_enabled: bool,
        health_window_seconds: int,
        health_penalty_weight: float,
        health_min_samples: int,
        cooldown_policy: CooldownPolicy,
        routing_environment_signature: tuple[str, str],
    ) -> None:
        """Apply runtime cooldown and health-scoring settings."""
        with self._lock:
            if self._health.configure(
                health_scoring_enabled=health_scoring_enabled,
                health_window_seconds=health_window_seconds,
                health_penalty_weight=health_penalty_weight,
                health_min_samples=health_min_samples,
                cooldown_policy=cooldown_policy,
                routing_environment_signature=routing_environment_signature,
            ):
                self._routes.reset_weights()

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
            self._routes.discard_channels(self._health.sync_channels(channels))
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
            self._routes.discard_channels(self._health.sync_channels(channels))
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
        self,
        channel_id: str,
        *,
        credential_id: str | None = None,
        model_name: str | None = None,
        started_revision: int | None = None,
    ) -> None:
        """Record success for exactly one executed route target."""
        with self._lock:
            self._health.record_success(
                channel_id,
                credential_id=credential_id,
                model_name=model_name,
                started_revision=started_revision,
            )

    def current_failure_revision(self) -> int:
        """Return a stable marker for failures observed before an attempt starts."""
        with self._lock:
            return self._health.failure_revision

    def record_failure(
        self,
        channel_id: str,
        error: str,
        *,
        category: ErrorCategory,
        credential_id: str | None = None,
        model_name: str | None = None,
        cooldown_seconds: float | None = None,
    ) -> None:
        """Record failure for its target or credential fault domain."""
        with self._lock:
            self._health.record_failure(
                channel_id,
                error,
                category=category,
                credential_id=credential_id,
                model_name=model_name,
                cooldown_seconds=cooldown_seconds,
            )

    def is_target_available(self, target: RouteTarget) -> bool:
        """Return whether a route target is currently available."""
        with self._lock:
            return self._health.is_target_available(target, now=monotonic())


__all__ = ["GatewayRouter"]

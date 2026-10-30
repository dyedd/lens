from __future__ import annotations

from threading import Lock
from time import monotonic

from ...models.channels import ChannelConfig
from ...models.protocols import ProtocolKind, RoutingStrategy
from ...models.routing import RouterSnapshot
from .cooldown import ClaimDecision, CooldownPolicy, ErrorCategory
from .health import HealthTracker
from .routing import RoutePlanner, RouteSelection, SeatOrderer
from .targets import RouteTarget

# 冷却到期后的探测在该目标上独占多久，避免全部请求同时涌入。
PROBE_LEASE_SECONDS = 60.0


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
        self._health = HealthTracker(
            health_scoring_enabled=health_scoring_enabled,
            health_window_seconds=health_window_seconds,
            health_penalty_weight=health_penalty_weight,
            health_min_samples=health_min_samples,
        )
        self._routes = RoutePlanner(self._health)

    def configure(
        self,
        *,
        health_scoring_enabled: bool,
        health_window_seconds: int,
        health_penalty_weight: float,
        health_min_samples: int,
        cooldown_policy: CooldownPolicy,
        affinity_seconds: float = 0.0,
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
            self._routes.configure_affinity(affinity_seconds)

    # ponytail: routes with the registry's current hook set, not the request's; pass the request's hooks through select() to pin them
    def set_seat_orderer(self, orderer: SeatOrderer) -> None:
        with self._lock:
            self._routes.seat_orderer = orderer

    def select(
        self,
        channels: list[ChannelConfig],
        protocol: ProtocolKind,
        requested_model: str | None = None,
        strategy: str = RoutingStrategy.FAILOVER.value,
        allowed_channel_ids: set[str] | None = None,
        use_model_matching: bool = True,
        route_targets: list[RouteTarget] | None = None,
        cursor_key: str | None = None,
        required_context_tokens: int | None = None,
    ) -> RouteSelection:
        """Select a primary route and its ordered candidates."""
        with self._lock:
            self._routes.discard_channels(self._health.reconcile_channels(channels))
            return self._routes.select(
                channels,
                protocol,
                requested_model,
                strategy,
                allowed_channel_ids,
                use_model_matching,
                route_targets,
                cursor_key,
                required_context_tokens,
            )

    def snapshot(self, channels: list[ChannelConfig]) -> RouterSnapshot:
        """Build a snapshot of route ordering and channel health."""
        with self._lock:
            self._routes.discard_channels(self._health.reconcile_channels(channels))
            now = monotonic()
            routes = [
                self._routes.build_route_state(channels, protocol, now=now)
                for protocol in ProtocolKind
            ]
            health = [
                self._health.project_channel_health(channel, now=now)
                for channel in channels
            ]
        return RouterSnapshot(routes=routes, health=health)

    def record_success(
        self,
        channel_id: str,
        *,
        credential_id: str | None = None,
        model_name: str | None = None,
        fault_protocol: str = "",
        started_revision: int | None = None,
    ) -> None:
        """Record success for exactly one executed route target."""
        with self._lock:
            self._health.record_success(
                channel_id,
                credential_id=credential_id,
                model_name=model_name,
                fault_protocol=fault_protocol,
                started_revision=started_revision,
            )

    def current_failure_revision(self) -> int:
        """Return a stable marker for failures observed before an attempt starts."""
        with self._lock:
            return self._health.failure_revision

    @property
    def cooldown_detection_rules(self):
        """Return the compiled upstream error detection rules."""
        with self._lock:
            return self._health.cooldown_detection_rules

    def record_failure(
        self,
        channel_id: str,
        error: str,
        *,
        category: ErrorCategory,
        credential_id: str | None = None,
        model_name: str | None = None,
        fault_protocol: str = "",
        scope: str = "model",
        cooldown_seconds: float | None = None,
        was_probe: bool = False,
        retry_action: str | None = None,
    ) -> None:
        """Record failure for its target or credential fault domain."""
        with self._lock:
            self._health.record_failure(
                channel_id,
                error,
                category=category,
                credential_id=credential_id,
                model_name=model_name,
                fault_protocol=fault_protocol,
                scope=scope,
                cooldown_seconds=cooldown_seconds,
                was_probe=was_probe,
                retry_action=retry_action,
            )

    def claim_target(
        self, target: RouteTarget, *, lease_seconds: float = PROBE_LEASE_SECONDS
    ) -> ClaimDecision:
        """Return whether this request may use the target right now."""
        with self._lock:
            return self._health.claim_target(
                target,
                now=monotonic(),
                lease_seconds=lease_seconds,
            )

    def release_probe(self, target: RouteTarget) -> None:
        with self._lock:
            self._health.release_probe(target)

    def cooldown_remaining_seconds(self, target: RouteTarget) -> float:
        """Return how long the target stays unusable; 0 when available."""
        with self._lock:
            return self._health.cooldown_remaining_seconds(target, now=monotonic())

    def cooldown_reason(self, target: RouteTarget) -> str:
        """Name the fault domain and remaining cooldown of a cooling target."""
        with self._lock:
            return self._health.cooldown_reason(target, now=monotonic())

    def note_success(self, route_key: str, target: RouteTarget) -> None:
        with self._lock:
            self._routes.note_success(route_key, target)

    def note_failure(self, route_key: str) -> None:
        with self._lock:
            self._routes.note_failure(route_key)


__all__ = ["GatewayRouter"]

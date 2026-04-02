from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import re
from threading import Lock

from ..models import ProtocolKind, ProviderConfig, ProviderHealth, ProviderStatus, RoutePreview, RoutePreviewItem, RouteState, RouterSnapshot, RoutingStrategy


@dataclass
class _HealthState:
    consecutive_failures: int = 0
    last_error: str | None = None


@dataclass
class _RouteCursor:
    next_index: int = 0


@dataclass
class RouteTarget:
    provider: ProviderConfig
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
        providers: list[ProviderConfig],
        protocol: ProtocolKind,
        requested_model: str | None = None,
        strategy: RoutingStrategy = RoutingStrategy.WEIGHTED,
        allowed_provider_ids: set[str] | None = None,
        use_model_matching: bool = True,
        route_targets: list[RouteTarget] | None = None,
        cursor_key: str | None = None,
    ) -> RouteSelection:
        active = self._build_active_pool(providers, protocol, requested_model, allowed_provider_ids, use_model_matching, route_targets)
        if not active:
            detail = f"No enabled providers available for protocol={protocol.value}"
            if requested_model:
                detail = f"No enabled providers matched protocol={protocol.value} model={requested_model}"
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

    def record_success(self, provider_id: str) -> None:
        with self._lock:
            self._health[provider_id] = _HealthState()

    def record_failure(self, provider_id: str, error: str) -> None:
        with self._lock:
            state = self._health[provider_id]
            state.consecutive_failures += 1
            state.last_error = error

    def snapshot(self, providers: list[ProviderConfig]) -> RouterSnapshot:
        routes = []
        for protocol in ProtocolKind:
            pool = self._build_active_pool(providers, protocol, None)
            with self._lock:
                next_index = self._cursors.get(protocol.value, _RouteCursor()).next_index

            routes.append(
                RouteState(
                    protocol=protocol,
                    next_index=next_index,
                    provider_ids=[target.provider.id for target in pool],
                    requested_model=None,
                )
            )

        with self._lock:
            health = [
                ProviderHealth(
                    provider_id=provider.id,
                    consecutive_failures=self._health[provider.id].consecutive_failures,
                    last_error=self._health[provider.id].last_error,
                )
                for provider in providers
            ]

        return RouterSnapshot(routes=routes, health=health)

    def preview(
        self,
        providers: list[ProviderConfig],
        protocol: ProtocolKind,
        requested_model: str | None,
        strategy: RoutingStrategy = RoutingStrategy.WEIGHTED,
        allowed_provider_ids: set[str] | None = None,
        use_model_matching: bool = True,
        matched_group_name: str | None = None,
        route_targets: list[RouteTarget] | None = None,
    ) -> RoutePreview:
        pool = self._build_active_pool(providers, protocol, requested_model, allowed_provider_ids, use_model_matching, route_targets)
        return RoutePreview(
            protocol=protocol,
            requested_model=requested_model,
            matched_group_name=matched_group_name,
            strategy=strategy,
            matched_provider_ids=[target.provider.id for target in pool],
            items=[
                RoutePreviewItem(
                    provider_id=target.provider.id,
                    provider_name=target.provider.name,
                    model_name=target.model_name,
                )
                for target in pool
            ],
        )

    @staticmethod
    def _build_active_pool(
        providers: list[ProviderConfig],
        protocol: ProtocolKind,
        requested_model: str | None,
        allowed_provider_ids: set[str] | None = None,
        use_model_matching: bool = True,
        route_targets: list[RouteTarget] | None = None,
    ) -> list[RouteTarget]:
        provider_map = {provider.id: provider for provider in providers}
        if route_targets is not None:
            return [
                target
                for target in route_targets
                if target.provider.status == ProviderStatus.ENABLED and target.provider.protocol == protocol
            ]

        active: list[RouteTarget] = []
        for provider in sorted(providers, key=lambda item: item.name):
            if provider.protocol != protocol or provider.status != ProviderStatus.ENABLED:
                continue
            if allowed_provider_ids is not None and provider.id not in allowed_provider_ids:
                continue
            if use_model_matching and not _matches_model(provider, requested_model):
                continue
            resolved = provider_map.get(provider.id, provider)
            active.append(RouteTarget(provider=resolved, model_name=requested_model))
        return active


def _matches_model(provider: ProviderConfig, requested_model: str | None) -> bool:
    if not requested_model:
        return True

    if provider.model_patterns:
        for pattern in provider.model_patterns:
            try:
                if re.search(pattern, requested_model):
                    return True
            except re.error:
                continue
        return False

    return True

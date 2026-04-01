from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import re
from threading import Lock

from ..models import ProtocolKind, ProviderConfig, ProviderHealth, ProviderStatus, RoutePreview, RouteState, RouterSnapshot, RoutingStrategy


@dataclass
class _HealthState:
    consecutive_failures: int = 0
    last_error: str | None = None


@dataclass
class _RouteCursor:
    next_index: int = 0


@dataclass
class RouteSelection:
    primary: ProviderConfig
    fallbacks: list[ProviderConfig] = field(default_factory=list)


class RoundRobinRouter:
    def __init__(self) -> None:
        self._lock = Lock()
        self._cursors: dict[ProtocolKind, _RouteCursor] = {}
        self._health: dict[str, _HealthState] = defaultdict(_HealthState)

    def select(
        self,
        providers: list[ProviderConfig],
        protocol: ProtocolKind,
        requested_model: str | None = None,
        strategy: RoutingStrategy = RoutingStrategy.WEIGHTED,
        allowed_provider_ids: set[str] | None = None,
        use_model_matching: bool = True,
    ) -> RouteSelection:
        active = self._build_active_pool(
            providers,
            protocol,
            requested_model,
            strategy,
            allowed_provider_ids,
            use_model_matching,
        )
        if not active:
            detail = f"No enabled providers available for protocol={protocol.value}"
            if requested_model:
                detail = f"No enabled providers matched protocol={protocol.value} model={requested_model}"
            raise LookupError(detail)

        with self._lock:
            cursor = self._cursors.setdefault(protocol, _RouteCursor())
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
                next_index = self._cursors.get(protocol, _RouteCursor()).next_index

            routes.append(
                RouteState(
                    protocol=protocol,
                    next_index=next_index,
                    provider_ids=[provider.id for provider in pool],
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
    ) -> RoutePreview:
        pool = self._build_active_pool(
            providers,
            protocol,
            requested_model,
            strategy,
            allowed_provider_ids,
            use_model_matching,
        )
        return RoutePreview(
            protocol=protocol,
            requested_model=requested_model,
            matched_group_name=matched_group_name,
            strategy=strategy,
            matched_provider_ids=[provider.id for provider in pool],
        )

    @staticmethod
    def _build_active_pool(
        providers: list[ProviderConfig],
        protocol: ProtocolKind,
        requested_model: str | None,
        strategy: RoutingStrategy = RoutingStrategy.ROUND_ROBIN,
        allowed_provider_ids: set[str] | None = None,
        use_model_matching: bool = True,
    ) -> list[ProviderConfig]:
        active = [
            provider
            for provider in sorted(providers, key=lambda item: item.name)
            if provider.protocol == protocol
            and provider.status == ProviderStatus.ENABLED
            and (allowed_provider_ids is None or provider.id in allowed_provider_ids)
            and (not use_model_matching or _matches_model(provider, requested_model))
        ]

        if strategy == RoutingStrategy.FAILOVER:
            return active

        if strategy == RoutingStrategy.ROUND_ROBIN:
            return active

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

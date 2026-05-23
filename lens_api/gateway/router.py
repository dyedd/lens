from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
import re
from threading import Lock
from time import monotonic

from ..models import (
    ChannelConfig,
    ChannelHealth,
    ChannelKeyHealth,
    ChannelKeyItem,
    ChannelStatus,
    ProtocolKind,
    RoutePreview,
    RoutePreviewItem,
    RouteState,
    RouterSnapshot,
    RoutingStrategy,
)


class ErrorCategory(Enum):
    AUTH = "auth"
    RATE_LIMIT = "rate_limit"
    SERVER = "server"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


_DEFAULT_INITIAL_COOLDOWN: dict[ErrorCategory, int] = {
    ErrorCategory.AUTH: 300,
    ErrorCategory.RATE_LIMIT: 60,
    ErrorCategory.SERVER: 120,
    ErrorCategory.TIMEOUT: 60,
    ErrorCategory.UNKNOWN: 60,
}


def classify_error(status_code: int | None) -> ErrorCategory:
    if status_code is None:
        return ErrorCategory.TIMEOUT
    if status_code in (401, 403):
        return ErrorCategory.AUTH
    if status_code == 429:
        return ErrorCategory.RATE_LIMIT
    if 500 <= status_code < 600:
        return ErrorCategory.SERVER
    return ErrorCategory.UNKNOWN


@dataclass
class _HealthState:
    consecutive_failures: int = 0
    last_error: str | None = None
    last_error_category: ErrorCategory | None = None
    opened_until: float = 0.0
    last_cooldown: float = 0.0


@dataclass
class _KeyHealthState:
    cooled_until: float = 0.0
    last_cooldown: float = 0.0
    consecutive_failures: int = 0


@dataclass
class _HealthWindow:
    successes: int = 0
    failures: int = 0
    window_start: float = 0.0

    @property
    def total(self) -> int:
        return self.successes + self.failures

    @property
    def failure_rate(self) -> float:
        return self.failures / self.total if self.total > 0 else 0.0

    def confidence(self, min_samples: int = 10) -> float:
        return min(1.0, self.total / min_samples)


@dataclass
class _SWRRNode:
    current_weight: int = 0


@dataclass
class RouteTarget:
    channel: ChannelConfig
    model_name: str | None = None
    credential_id: str | None = None
    credential_name: str | None = None


@dataclass
class RouteSelection:
    primary: RouteTarget
    fallbacks: list[RouteTarget] = field(default_factory=list)


class RoundRobinRouter:
    def __init__(
        self,
        *,
        health_window_seconds: int = 300,
        health_penalty_weight: float = 0.5,
        health_min_samples: int = 10,
    ) -> None:
        self._lock = Lock()
        self._health: dict[str, _HealthState] = defaultdict(_HealthState)
        self._key_health: dict[tuple[str, str], _KeyHealthState] = {}
        self._health_windows: dict[str, _HealthWindow] = defaultdict(_HealthWindow)
        self._swrr_nodes: dict[tuple[str, str, str], _SWRRNode] = {}
        self._health_window_seconds = health_window_seconds
        self._health_penalty_weight = health_penalty_weight
        self._health_min_samples = health_min_samples

    def configure_health_scoring(
        self,
        *,
        health_window_seconds: int,
        health_penalty_weight: float,
        health_min_samples: int,
    ) -> None:
        with self._lock:
            self._health_window_seconds = max(health_window_seconds, 1)
            self._health_penalty_weight = max(health_penalty_weight, 0.0)
            self._health_min_samples = max(health_min_samples, 1)

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
        with self._lock:
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
                    detail = (
                        f"All {len(all_matching)} matching channels are in cooldown"
                    )
                else:
                    detail = (
                        f"No enabled channels available for protocol={protocol.value}"
                    )
                    if requested_model:
                        detail = f"No enabled channels matched {requested_model}"
                raise LookupError(detail)

            route_key = cursor_key or protocol.value
            if strategy == RoutingStrategy.FAILOVER:
                primary_index = 0
            else:
                primary_index = self._swrr_pick_index(active, route_key, mutate=True)

            primary = active[primary_index]
            fallbacks = active[primary_index + 1 :] + active[:primary_index]

            return RouteSelection(primary=primary, fallbacks=fallbacks)

    def record_success(
        self, channel_id: str, *, credential_id: str | None = None
    ) -> None:
        with self._lock:
            self._health[channel_id] = _HealthState()
            if credential_id:
                self._key_health.pop((channel_id, credential_id), None)
            self._update_health_window(channel_id, success=True)

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
        category = classify_error(status_code)
        with self._lock:
            state = self._health[channel_id]
            state.consecutive_failures += 1
            state.last_error = error
            state.last_error_category = category
            self._update_health_window(channel_id, success=False)

            should_cooldown_channel = True
            if (
                category in (ErrorCategory.AUTH, ErrorCategory.RATE_LIMIT)
                and credential_id
                and channel_keys
                and sum(1 for k in channel_keys if k.enabled) > 1
            ):
                self._record_key_failure_locked(
                    channel_id, credential_id, status_code, max_cooldown_seconds
                )
                should_cooldown_channel = self._all_keys_cooled_locked(
                    channel_id, channel_keys
                )

            if should_cooldown_channel:
                self._apply_channel_cooldown_locked(
                    state,
                    category,
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
        with self._lock:
            self._record_key_failure_locked(
                channel_id, key_id, status_code, max_cooldown_seconds
            )

    def record_key_success(self, channel_id: str, key_id: str) -> None:
        with self._lock:
            self._key_health.pop((channel_id, key_id), None)

    def is_channel_available(self, channel_id: str) -> bool:
        with self._lock:
            state = self._health[channel_id]
            if state.opened_until <= 0:
                return True
            if state.opened_until <= monotonic():
                state.opened_until = 0.0
                return True
            return False

    def is_target_available(self, target: RouteTarget) -> bool:
        with self._lock:
            return self._target_is_available(target, now=monotonic())

    def snapshot(self, channels: list[ChannelConfig]) -> RouterSnapshot:
        with self._lock:
            now = monotonic()
            routes = [
                self._build_route_state(channels, protocol, now=now)
                for protocol in ProtocolKind
            ]
            health = [
                self._build_channel_health(channel, now=now) for channel in channels
            ]

        return RouterSnapshot(routes=routes, health=health)

    def _build_route_state(
        self,
        channels: list[ChannelConfig],
        protocol: ProtocolKind,
        *,
        now: float,
    ) -> RouteState:
        pool = self._build_active_pool(
            channels, protocol, None, skip_health_filter=True
        )
        ordered_targets, _, next_channel_id = self._prepare_diagnostic_targets(
            pool,
            strategy=RoutingStrategy.ROUND_ROBIN,
            cursor_key=protocol.value,
            protocol=protocol,
        )
        availability = [
            self._target_is_available(target, now=now) for target in ordered_targets
        ]
        return RouteState(
            protocol=protocol,
            next_index=0,
            next_channel_id=next_channel_id,
            channel_ids=[target.channel.id for target in ordered_targets],
            available_channel_ids=[
                target.channel.id
                for target, available in zip(ordered_targets, availability)
                if available
            ],
            cooldown_channel_ids=[
                target.channel.id
                for target, available in zip(ordered_targets, availability)
                if not available
            ],
            requested_model=None,
        )

    def preview(
        self,
        channels: list[ChannelConfig],
        protocol: ProtocolKind,
        requested_model: str | None,
        strategy: RoutingStrategy = RoutingStrategy.ROUND_ROBIN,
        allowed_channel_ids: set[str] | None = None,
        use_model_matching: bool = True,
        requested_group_name: str | None = None,
        resolved_group_name: str | None = None,
        route_targets: list[RouteTarget] | None = None,
        cursor_key: str | None = None,
    ) -> RoutePreview:
        with self._lock:
            pool = self._build_active_pool(
                channels,
                protocol,
                requested_model,
                allowed_channel_ids,
                use_model_matching,
                route_targets,
                skip_health_filter=True,
            )
            ordered_targets, _, _ = self._prepare_diagnostic_targets(
                pool,
                strategy=strategy,
                cursor_key=cursor_key,
                protocol=protocol,
            )
            now = monotonic()
            return RoutePreview(
                protocol=protocol,
                requested_group_name=requested_group_name,
                resolved_group_name=resolved_group_name,
                strategy=strategy,
                matched_channel_ids=[target.channel.id for target in ordered_targets],
                items=[
                    self._build_preview_item(target, now=now)
                    for target in ordered_targets
                ],
            )

    def _build_preview_item(
        self, target: RouteTarget, *, now: float
    ) -> RoutePreviewItem:
        available = self._target_is_available(target, now=now)
        return RoutePreviewItem(
            channel_id=target.channel.id,
            channel_name=target.channel.name,
            model_name=target.model_name,
            credential_id=target.credential_id,
            credential_name=target.credential_name,
            available=available,
            in_cooldown=not available,
            cooldown_remaining_seconds=self._target_cooldown_remaining_seconds(
                target, now=now
            ),
            score=self._score(target.channel.id),
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
        active = self._filter_enabled_targets(
            channels,
            protocol,
            requested_model,
            allowed_channel_ids,
            use_model_matching,
            route_targets,
        )

        if not skip_health_filter:
            now = monotonic()
            active = [
                target
                for target in active
                if self._target_is_available(target, now=now)
            ]
            if len(active) > 1:
                active.sort(key=lambda t: self._score(t.channel.id), reverse=True)

        return active

    def _filter_enabled_targets(
        self,
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
                if (
                    allowed_channel_ids is not None
                    and target.channel.id not in allowed_channel_ids
                ):
                    continue
                active.extend(self._expand_target_credentials(target))
            return active

        active: list[RouteTarget] = []
        for channel in sorted(channels, key=lambda item: item.name):
            if channel.protocol != protocol or channel.status != ChannelStatus.ENABLED:
                continue
            if (
                allowed_channel_ids is not None
                and channel.id not in allowed_channel_ids
            ):
                continue
            if use_model_matching and not _matches_model(channel, requested_model):
                continue
            active.extend(
                self._expand_target_credentials(
                    RouteTarget(channel=channel, model_name=requested_model)
                )
            )
        return active

    def _expand_target_credentials(self, target: RouteTarget) -> list[RouteTarget]:
        if target.credential_id:
            key = self._find_key(target.channel, target.credential_id)
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
            for key in self._candidate_keys(target.channel, target.model_name)
        ]

    def _candidate_keys(
        self, channel: ChannelConfig, model_name: str | None
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

    @staticmethod
    def _find_key(channel: ChannelConfig, credential_id: str) -> ChannelKeyItem | None:
        for key in channel.keys:
            if key.id == credential_id:
                return key
        return None

    def _score(self, channel_id: str) -> float:
        window = self._expire_window_if_needed(channel_id)
        penalty = (
            window.failure_rate
            * self._health_penalty_weight
            * window.confidence(self._health_min_samples)
        )
        return 1.0 - penalty

    def _update_health_window(self, channel_id: str, *, success: bool) -> None:
        window = self._expire_window_if_needed(channel_id)
        if window.window_start == 0:
            window.window_start = monotonic()
        if success:
            window.successes += 1
        else:
            window.failures += 1

    def _expire_window_if_needed(self, channel_id: str) -> _HealthWindow:
        window = self._health_windows[channel_id]
        now = monotonic()
        if (
            window.window_start > 0
            and now - window.window_start > self._health_window_seconds
        ):
            window = _HealthWindow(window_start=now)
            self._health_windows[channel_id] = window
        return window

    def _swrr_pick_index(
        self, active: list[RouteTarget], route_key: str, *, mutate: bool
    ) -> int:
        total_weight = 0
        best_idx = 0
        next_weights: list[int] = []

        for i, target in enumerate(active):
            node_key = (route_key, target.channel.id, target.credential_id or "")
            node = self._swrr_nodes.get(node_key)
            current_weight = node.current_weight if node is not None else 0
            weight = 1
            next_weight = current_weight + weight
            next_weights.append(next_weight)
            total_weight += weight
            if next_weight > next_weights[best_idx]:
                best_idx = i

        if mutate:
            for i, target in enumerate(active):
                node_key = (route_key, target.channel.id, target.credential_id or "")
                node = self._swrr_nodes.get(node_key)
                if node is None:
                    node = _SWRRNode()
                    self._swrr_nodes[node_key] = node
                node.current_weight = next_weights[i]
            best = active[best_idx]
            self._swrr_nodes[
                (route_key, best.channel.id, best.credential_id or "")
            ].current_weight -= total_weight
        return best_idx

    def _record_key_failure_locked(
        self,
        channel_id: str,
        key_id: str,
        status_code: int | None,
        max_cooldown_seconds: int,
    ) -> None:
        category = classify_error(status_code)
        state = self._key_health.setdefault((channel_id, key_id), _KeyHealthState())
        state.consecutive_failures += 1
        initial = _DEFAULT_INITIAL_COOLDOWN.get(category, 60)
        cooldown = self._calculate_exponential_cooldown(
            state.last_cooldown, initial, max(max_cooldown_seconds, initial)
        )
        state.last_cooldown = cooldown
        state.cooled_until = monotonic() + cooldown

    def _all_keys_cooled_locked(
        self, channel_id: str, keys: list[ChannelKeyItem]
    ) -> bool:
        now = monotonic()
        enabled = [k for k in keys if k.enabled]
        if not enabled:
            return True
        return not any(
            self._is_key_available(channel_id, k.id, now=now) for k in enabled
        )

    def _apply_channel_cooldown_locked(
        self,
        state: _HealthState,
        category: ErrorCategory,
        *,
        threshold: int,
        cooldown_seconds: int,
        max_cooldown_seconds: int,
    ) -> None:
        effective_threshold = self._cooldown_threshold(category, threshold)
        if state.consecutive_failures >= effective_threshold:
            initial = self._initial_cooldown(category, cooldown_seconds)
            cooldown = self._calculate_exponential_cooldown(
                state.last_cooldown, initial, max(max_cooldown_seconds, initial)
            )
            state.last_cooldown = cooldown
            state.opened_until = max(state.opened_until, monotonic() + cooldown)

    @staticmethod
    def _calculate_exponential_cooldown(
        last_cooldown: float, initial: int, max_cooldown: int
    ) -> float:
        if last_cooldown > 0:
            return min(last_cooldown * 2, max_cooldown)
        return initial

    def _target_is_available(self, target: RouteTarget, *, now: float) -> bool:
        if self._health[target.channel.id].opened_until > now:
            return False
        if target.credential_id:
            return self._is_key_available(
                target.channel.id, target.credential_id, now=now
            )
        if target.channel.keys:
            return self._has_available_key(target.channel, now=now)
        return True

    def _has_available_key(self, channel: ChannelConfig, *, now: float) -> bool:
        return any(
            self._is_key_available(channel.id, key.id, now=now)
            for key in channel.keys
            if key.enabled
        )

    def _is_key_available(self, channel_id: str, key_id: str, *, now: float) -> bool:
        state = self._key_health.get((channel_id, key_id))
        return state is None or state.cooled_until <= now

    def _prepare_diagnostic_targets(
        self,
        targets: list[RouteTarget],
        *,
        strategy: RoutingStrategy,
        cursor_key: str | None,
        protocol: ProtocolKind,
    ) -> tuple[list[RouteTarget], int, str | None]:
        if not targets:
            return [], 0, None
        now = monotonic()
        available: list[RouteTarget] = []
        cooled: list[RouteTarget] = []
        for target in targets:
            (
                available if self._target_is_available(target, now=now) else cooled
            ).append(target)
        available.sort(key=lambda target: self._score(target.channel.id), reverse=True)
        cooled.sort(key=lambda target: self._score(target.channel.id), reverse=True)

        if not available:
            return cooled, 0, None

        route_key = cursor_key or protocol.value
        if strategy == RoutingStrategy.FAILOVER:
            primary_index = 0
        else:
            primary_index = self._swrr_pick_index(available, route_key, mutate=False)
        ordered_available = available[primary_index:] + available[:primary_index]
        return (
            ordered_available + cooled,
            primary_index,
            ordered_available[0].channel.id,
        )

    def _build_channel_health(
        self, channel: ChannelConfig, *, now: float
    ) -> ChannelHealth:
        state = self._health[channel.id]
        key_health = [
            self._build_key_health(channel.id, key.id, now=now)
            for key in channel.keys
            if key.enabled
        ]
        available_key_count = sum(1 for item in key_health if item.available)
        cooled_key_count = sum(1 for item in key_health if not item.available)
        return ChannelHealth(
            channel_id=channel.id,
            consecutive_failures=state.consecutive_failures,
            last_error=state.last_error,
            last_error_category=(
                state.last_error_category.value if state.last_error_category else None
            ),
            opened_until=state.opened_until,
            cooldown_remaining_seconds=self._remaining_seconds(
                state.opened_until, now=now
            ),
            last_cooldown_seconds=int(state.last_cooldown),
            score=self._score(channel.id),
            available=state.opened_until <= now,
            available_key_count=available_key_count,
            cooled_key_count=cooled_key_count,
            key_health=key_health,
        )

    def _build_key_health(
        self, channel_id: str, key_id: str, *, now: float
    ) -> ChannelKeyHealth:
        state = self._key_health.get((channel_id, key_id))
        cooled_until = state.cooled_until if state is not None else 0.0
        last_cooldown = state.last_cooldown if state is not None else 0.0
        consecutive_failures = state.consecutive_failures if state is not None else 0
        return ChannelKeyHealth(
            credential_id=key_id,
            consecutive_failures=consecutive_failures,
            cooled_until=cooled_until,
            cooldown_remaining_seconds=self._remaining_seconds(cooled_until, now=now),
            last_cooldown_seconds=int(last_cooldown),
            available=cooled_until <= now,
        )

    def _target_cooldown_remaining_seconds(
        self, target: RouteTarget, *, now: float
    ) -> int:
        if target.credential_id:
            key_state = self._key_health.get((target.channel.id, target.credential_id))
            if key_state is not None and key_state.cooled_until > now:
                return self._remaining_seconds(key_state.cooled_until, now=now)
        channel_state = self._health[target.channel.id]
        return self._remaining_seconds(channel_state.opened_until, now=now)

    @staticmethod
    def _remaining_seconds(until: float, *, now: float) -> int:
        if until <= now:
            return 0
        return max(int(until - now), 0)

    @staticmethod
    def _cooldown_threshold(category: ErrorCategory, configured_threshold: int) -> int:
        if category in (ErrorCategory.AUTH, ErrorCategory.RATE_LIMIT):
            return 1
        if category == ErrorCategory.TIMEOUT:
            return 2
        return max(configured_threshold, 1)

    @staticmethod
    def _initial_cooldown(category: ErrorCategory, configured_cooldown: int) -> int:
        if category == ErrorCategory.SERVER and configured_cooldown > 0:
            return configured_cooldown
        return _DEFAULT_INITIAL_COOLDOWN[category]


def _matches_model(channel: ChannelConfig, requested_model: str | None) -> bool:
    if not requested_model:
        return True

    if channel.model_patterns:
        for pattern in channel.model_patterns:
            if _matches_pattern(pattern, requested_model):
                return True
        return False

    return True


def _matches_pattern(pattern: str, value: str) -> bool:
    try:
        return bool(re.search(pattern, value))
    except re.error:
        return False

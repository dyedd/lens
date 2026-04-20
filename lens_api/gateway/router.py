from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
import re
from threading import Lock
from time import monotonic

from ..models import ChannelConfig, ChannelHealth, ChannelKeyHealth, ChannelKeyItem, ChannelStatus, ProtocolKind, RoutePreview, RoutePreviewItem, RouteState, RouterSnapshot, RoutingStrategy


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
    channel_id: str
    current_weight: int = 0


@dataclass
class RouteTarget:
    channel: ChannelConfig
    model_name: str | None = None
    credential_id: str | None = None


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
        self._key_cursors: dict[str, int] = {}
        self._health_windows: dict[str, _HealthWindow] = defaultdict(_HealthWindow)
        self._swrr_nodes: dict[tuple[str, str], _SWRRNode] = {}
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
                channels, protocol, requested_model,
                allowed_channel_ids, use_model_matching, route_targets,
            )
            if not active:
                all_matching = self._build_active_pool(
                    channels, protocol, requested_model,
                    allowed_channel_ids, use_model_matching, route_targets,
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
            if strategy == RoutingStrategy.FAILOVER:
                primary_index = 0
            else:
                primary_index = self._swrr_select(active, route_key)

            primary = active[primary_index]
            fallbacks = active[primary_index + 1 :] + active[:primary_index]

            for target in [primary, *fallbacks]:
                if target.credential_id is None and target.channel.keys:
                    target.credential_id = self._select_key(target.channel)

            return RouteSelection(primary=primary, fallbacks=fallbacks)

    def record_success(self, channel_id: str, *, credential_id: str | None = None) -> None:
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

            if category in (ErrorCategory.AUTH, ErrorCategory.RATE_LIMIT):
                if credential_id and channel_keys and self._enabled_key_count(channel_keys) > 1:
                    self._record_key_failure_locked(channel_id, credential_id, status_code, max_cooldown_seconds)
                    if self._all_keys_cooled_locked(channel_id, channel_keys):
                        self._apply_channel_cooldown_locked(
                            state,
                            category,
                            threshold=threshold,
                            cooldown_seconds=cooldown_seconds,
                            max_cooldown_seconds=max_cooldown_seconds,
                        )
                else:
                    self._apply_channel_cooldown_locked(
                        state,
                        category,
                        threshold=threshold,
                        cooldown_seconds=cooldown_seconds,
                        max_cooldown_seconds=max_cooldown_seconds,
                    )
            else:
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
            self._record_key_failure_locked(channel_id, key_id, status_code, max_cooldown_seconds)

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

    def snapshot(self, channels: list[ChannelConfig]) -> RouterSnapshot:
        with self._lock:
            routes = []
            for protocol in ProtocolKind:
                pool = self._build_active_pool(channels, protocol, None, skip_health_filter=True)
                ordered_targets, _, next_channel_id = self._prepare_diagnostic_targets(
                    pool,
                    strategy=RoutingStrategy.ROUND_ROBIN,
                    cursor_key=protocol.value,
                    protocol=protocol,
                )
                now = monotonic()
                routes.append(
                    RouteState(
                        protocol=protocol,
                        next_index=0,
                        next_channel_id=next_channel_id,
                        channel_ids=[target.channel.id for target in ordered_targets],
                        available_channel_ids=[
                            target.channel.id
                            for target in ordered_targets
                            if self._target_is_available(target, now=now)
                        ],
                        cooldown_channel_ids=[
                            target.channel.id
                            for target in ordered_targets
                            if not self._target_is_available(target, now=now)
                        ],
                        requested_model=None,
                    )
                )

            health = [
                self._build_channel_health(channel)
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
        requested_group_name: str | None = None,
        resolved_group_name: str | None = None,
        route_targets: list[RouteTarget] | None = None,
        cursor_key: str | None = None,
    ) -> RoutePreview:
        with self._lock:
            pool = self._build_active_pool(
                channels, protocol, requested_model,
                allowed_channel_ids, use_model_matching, route_targets,
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
                    RoutePreviewItem(
                        channel_id=target.channel.id,
                        channel_name=target.channel.name,
                        model_name=target.model_name,
                        credential_id=target.credential_id,
                        available=self._target_is_available(target, now=now),
                        in_cooldown=not self._target_is_available(target, now=now),
                        cooldown_remaining_seconds=self._target_cooldown_remaining_seconds(target, now=now),
                        score=self._score(target.channel.id),
                    )
                    for target in ordered_targets
                ],
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
        channel_map = {channel.id: channel for channel in channels}
        if route_targets is not None:
            active = [
                target
                for target in route_targets
                if target.channel.status == ChannelStatus.ENABLED
                and (allowed_channel_ids is None or target.channel.id in allowed_channel_ids)
            ]
        else:
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

        if not skip_health_filter:
            now = monotonic()
            active = [
                target for target in active
                if self._target_is_available(target, now=now)
            ]
            if len(active) > 1:
                active.sort(key=lambda t: self._score(t.channel.id), reverse=True)

        return active

    def _score(self, channel_id: str) -> float:
        window = self._health_windows[channel_id]
        now = monotonic()
        if window.window_start > 0 and now - window.window_start > self._health_window_seconds:
            self._health_windows[channel_id] = _HealthWindow(window_start=now)
            return 1.0
        penalty = window.failure_rate * self._health_penalty_weight * window.confidence(self._health_min_samples)
        return 1.0 - penalty

    def _update_health_window(self, channel_id: str, *, success: bool) -> None:
        window = self._health_windows[channel_id]
        now = monotonic()
        if window.window_start > 0 and now - window.window_start > self._health_window_seconds:
            window = _HealthWindow(window_start=now)
            self._health_windows[channel_id] = window
        if window.window_start == 0:
            window.window_start = now
        if success:
            window.successes += 1
        else:
            window.failures += 1

    def _select_key(self, channel: ChannelConfig) -> str | None:
        enabled_keys = [k for k in channel.keys if k.enabled]
        if not enabled_keys:
            return None
        now = monotonic()
        cursor = self._key_cursors.get(channel.id, 0)
        for i in range(len(enabled_keys)):
            idx = (cursor + i) % len(enabled_keys)
            key = enabled_keys[idx]
            state = self._key_health.get((channel.id, key.id))
            if state is None or state.cooled_until <= now:
                self._key_cursors[channel.id] = (idx + 1) % len(enabled_keys)
                return key.id
        return None

    def _effective_key_count(self, channel: ChannelConfig) -> int:
        now = monotonic()
        enabled_keys = [k for k in channel.keys if k.enabled]
        cooled = sum(
            1 for k in enabled_keys
            if (state := self._key_health.get((channel.id, k.id)))
            and state.cooled_until > now
        )
        return max(len(enabled_keys) - cooled, 0)

    def _swrr_select(self, active: list[RouteTarget], route_key: str) -> int:
        return self._swrr_pick_index(active, route_key, mutate=True)

    def _swrr_peek(self, active: list[RouteTarget], route_key: str) -> int:
        return self._swrr_pick_index(active, route_key, mutate=False)

    def _swrr_pick_index(self, active: list[RouteTarget], route_key: str, *, mutate: bool) -> int:
        total_weight = 0
        best_idx = 0
        next_weights: list[int] = []

        for i, target in enumerate(active):
            cid = target.channel.id
            node_key = (route_key, cid)
            node = self._swrr_nodes.get(node_key)
            current_weight = node.current_weight if node is not None and node.channel_id == cid else 0
            weight = max(self._effective_key_count(target.channel), 1)
            next_weight = current_weight + weight
            next_weights.append(next_weight)
            total_weight += weight
            if next_weight > next_weights[best_idx]:
                best_idx = i

        if mutate:
            for i, target in enumerate(active):
                cid = target.channel.id
                node_key = (route_key, cid)
                node = self._swrr_nodes.get(node_key)
                if node is None or node.channel_id != cid:
                    node = _SWRRNode(channel_id=cid)
                    self._swrr_nodes[node_key] = node
                node.current_weight = next_weights[i]
            best_cid = active[best_idx].channel.id
            self._swrr_nodes[(route_key, best_cid)].current_weight -= total_weight
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
        max_cd = max(max_cooldown_seconds, initial)
        if state.last_cooldown > 0:
            cooldown = min(state.last_cooldown * 2, max_cd)
        else:
            cooldown = initial
        state.last_cooldown = cooldown
        state.cooled_until = monotonic() + cooldown

    def _all_keys_cooled_locked(self, channel_id: str, keys: list[ChannelKeyItem]) -> bool:
        now = monotonic()
        enabled = [k for k in keys if k.enabled]
        if not enabled:
            return True
        return all(
            (state := self._key_health.get((channel_id, k.id)))
            and state.cooled_until > now
            for k in enabled
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
            max_cd = max(max_cooldown_seconds, initial)
            if state.last_cooldown > 0:
                cooldown = min(state.last_cooldown * 2, max_cd)
            else:
                cooldown = initial
            state.last_cooldown = cooldown
            state.opened_until = max(state.opened_until, monotonic() + cooldown)

    @staticmethod
    def _enabled_key_count(keys: list[ChannelKeyItem]) -> int:
        return sum(1 for key in keys if key.enabled)

    def _target_is_available(self, target: RouteTarget, *, now: float) -> bool:
        if self._health[target.channel.id].opened_until > now:
            return False
        if target.credential_id:
            return self._is_key_available(target.channel.id, target.credential_id, now=now)
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
        available = [target for target in targets if self._target_is_available(target, now=now)]
        cooled = [target for target in targets if not self._target_is_available(target, now=now)]
        available.sort(key=lambda target: self._score(target.channel.id), reverse=True)
        cooled.sort(key=lambda target: self._score(target.channel.id), reverse=True)

        if not available:
            ordered = cooled
            return ordered, 0, None

        route_key = cursor_key or protocol.value
        if strategy == RoutingStrategy.FAILOVER:
            primary_index = 0
        else:
            primary_index = self._swrr_peek(available, route_key)
        ordered_available = available[primary_index:] + available[:primary_index]
        ordered = ordered_available + cooled
        return ordered, primary_index, ordered_available[0].channel.id

    def _build_channel_health(self, channel: ChannelConfig) -> ChannelHealth:
        now = monotonic()
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
            last_error_category=state.last_error_category.value if state.last_error_category else None,
            opened_until=state.opened_until,
            cooldown_remaining_seconds=self._remaining_seconds(state.opened_until, now=now),
            last_cooldown_seconds=int(state.last_cooldown),
            score=self._score(channel.id),
            available=state.opened_until <= now,
            available_key_count=available_key_count,
            cooled_key_count=cooled_key_count,
            key_health=key_health,
        )

    def _build_key_health(self, channel_id: str, key_id: str, *, now: float) -> ChannelKeyHealth:
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

    def _target_cooldown_remaining_seconds(self, target: RouteTarget, *, now: float) -> int:
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
            try:
                if re.search(pattern, requested_model):
                    return True
            except re.error:
                continue
        return False

    return True

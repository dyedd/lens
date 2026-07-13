from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from time import monotonic

from ...models import (
    ChannelConfig,
    ChannelHealth,
    ChannelKeyHealth,
    ChannelKeyItem,
)
from .cooldown import (
    DEFAULT_INITIAL_COOLDOWN,
    ErrorCategory,
    calculate_exponential_cooldown,
    classify_error,
    cooldown_threshold,
    initial_cooldown,
)
from .types import RouteTarget


@dataclass(slots=True)
class _HealthState:
    consecutive_failures: int = 0
    last_error: str | None = None
    last_error_category: ErrorCategory | None = None
    opened_until: float = 0.0
    last_cooldown: float = 0.0


@dataclass(slots=True)
class _KeyHealthState:
    cooled_until: float = 0.0
    last_cooldown: float = 0.0
    consecutive_failures: int = 0


@dataclass(slots=True)
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


class _HealthTracker:
    def __init__(
        self,
        *,
        health_window_seconds: int,
        health_penalty_weight: float,
        health_min_samples: int,
    ) -> None:
        self._health: dict[str, _HealthState] = defaultdict(_HealthState)
        self._key_health: dict[tuple[str, str], _KeyHealthState] = {}
        self._health_windows: dict[str, _HealthWindow] = defaultdict(_HealthWindow)
        self._health_window_seconds = health_window_seconds
        self._health_penalty_weight = health_penalty_weight
        self._health_min_samples = health_min_samples

    def configure(
        self,
        *,
        health_window_seconds: int,
        health_penalty_weight: float,
        health_min_samples: int,
    ) -> None:
        self._health_window_seconds = max(health_window_seconds, 1)
        self._health_penalty_weight = max(health_penalty_weight, 0.0)
        self._health_min_samples = max(health_min_samples, 1)

    def record_success(
        self, channel_id: str, *, credential_id: str | None = None
    ) -> None:
        self._health[channel_id] = _HealthState()
        if credential_id:
            self._key_health.pop((channel_id, credential_id), None)
        self._update_health_window(channel_id, success=True)

    def record_failure(
        self,
        channel_id: str,
        error: str,
        *,
        status_code: int | None,
        credential_id: str | None,
        channel_keys: list[ChannelKeyItem] | None,
        threshold: int,
        cooldown_seconds: int,
        max_cooldown_seconds: int,
    ) -> None:
        category = classify_error(status_code)
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
            and sum(1 for key in channel_keys if key.enabled) > 1
        ):
            self.record_key_failure(
                channel_id, credential_id, status_code, max_cooldown_seconds
            )
            should_cooldown_channel = self._all_keys_cooled(channel_id, channel_keys)

        if should_cooldown_channel:
            self._apply_channel_cooldown(
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
        status_code: int | None,
        max_cooldown_seconds: int,
    ) -> None:
        category = classify_error(status_code)
        state = self._key_health.setdefault((channel_id, key_id), _KeyHealthState())
        state.consecutive_failures += 1
        initial = DEFAULT_INITIAL_COOLDOWN.get(category, 60)
        cooldown = calculate_exponential_cooldown(
            state.last_cooldown, initial, max(max_cooldown_seconds, initial)
        )
        state.last_cooldown = cooldown
        state.cooled_until = monotonic() + cooldown

    def record_key_success(self, channel_id: str, key_id: str) -> None:
        self._key_health.pop((channel_id, key_id), None)

    def is_channel_available(self, channel_id: str) -> bool:
        state = self._health[channel_id]
        if state.opened_until <= 0:
            return True
        if state.opened_until <= monotonic():
            state.opened_until = 0.0
            return True
        return False

    def is_target_available(self, target: RouteTarget, *, now: float) -> bool:
        if self._health[target.channel.id].opened_until > now:
            return False
        if target.credential_id:
            return self._is_key_available(
                target.channel.id, target.credential_id, now=now
            )
        if target.channel.keys:
            return any(
                self._is_key_available(target.channel.id, key.id, now=now)
                for key in target.channel.keys
                if key.enabled
            )
        return True

    def score(self, channel_id: str) -> float:
        window = self._expire_window_if_needed(channel_id)
        penalty = (
            window.failure_rate
            * self._health_penalty_weight
            * window.confidence(self._health_min_samples)
        )
        return 1.0 - penalty

    def build_channel_health(
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
        is_available = state.opened_until <= now and (
            not channel.keys or available_key_count > 0
        )
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
            score=self.score(channel.id),
            available=is_available,
            available_key_count=available_key_count,
            cooled_key_count=cooled_key_count,
            key_health=key_health,
        )

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

    def _all_keys_cooled(
        self, channel_id: str, channel_keys: list[ChannelKeyItem]
    ) -> bool:
        now = monotonic()
        return not any(
            key.enabled and self._is_key_available(channel_id, key.id, now=now)
            for key in channel_keys
        )

    def _apply_channel_cooldown(
        self,
        state: _HealthState,
        category: ErrorCategory,
        *,
        threshold: int,
        cooldown_seconds: int,
        max_cooldown_seconds: int,
    ) -> None:
        effective_threshold = cooldown_threshold(category, threshold)
        if state.consecutive_failures < effective_threshold:
            return
        initial = initial_cooldown(category, cooldown_seconds)
        cooldown = calculate_exponential_cooldown(
            state.last_cooldown, initial, max(max_cooldown_seconds, initial)
        )
        state.last_cooldown = cooldown
        state.opened_until = max(state.opened_until, monotonic() + cooldown)

    def _is_key_available(self, channel_id: str, key_id: str, *, now: float) -> bool:
        state = self._key_health.get((channel_id, key_id))
        return state is None or state.cooled_until <= now

    def _build_key_health(
        self, channel_id: str, key_id: str, *, now: float
    ) -> ChannelKeyHealth:
        state = self._key_health.get((channel_id, key_id))
        cooled_until = state.cooled_until if state is not None else 0.0
        last_cooldown = state.last_cooldown if state is not None else 0.0
        failures = state.consecutive_failures if state is not None else 0
        return ChannelKeyHealth(
            credential_id=key_id,
            consecutive_failures=failures,
            cooled_until=cooled_until,
            cooldown_remaining_seconds=self._remaining_seconds(cooled_until, now=now),
            last_cooldown_seconds=int(last_cooldown),
            available=cooled_until <= now,
        )

    @staticmethod
    def _remaining_seconds(until: float, *, now: float) -> int:
        if until <= now:
            return 0
        return max(int(until - now), 0)


__all__ = ["ErrorCategory", "classify_error"]

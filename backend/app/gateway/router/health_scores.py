from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from math import ceil
from time import monotonic

from .cooldown import ModelKey


@dataclass(slots=True)
class _HealthBucket:
    started_at: int
    successes: int = 0
    failures: int = 0


@dataclass(slots=True)
class _HealthWindow:
    buckets: deque[_HealthBucket] = field(default_factory=deque)
    successes: int = 0
    failures: int = 0

    def record(self, *, now: float, bucket_seconds: int, success: bool) -> None:
        bucket_started_at = int(now // bucket_seconds) * bucket_seconds
        if not self.buckets or self.buckets[-1].started_at != bucket_started_at:
            self.buckets.append(_HealthBucket(started_at=bucket_started_at))
        bucket = self.buckets[-1]
        if success:
            bucket.successes += 1
            self.successes += 1
        else:
            bucket.failures += 1
            self.failures += 1

    def prune(self, *, now: float, window_seconds: int, bucket_seconds: int) -> None:
        oldest = now - window_seconds
        while self.buckets and self.buckets[0].started_at + bucket_seconds <= oldest:
            bucket = self.buckets.popleft()
            self.successes -= bucket.successes
            self.failures -= bucket.failures


class HealthScores:
    """Own the sliding-window success rates that weight route selection."""

    def __init__(
        self,
        *,
        health_scoring_enabled: bool,
        health_window_seconds: int,
        health_penalty_weight: float,
        health_min_samples: int,
    ) -> None:
        self._windows: dict[ModelKey, _HealthWindow] = defaultdict(_HealthWindow)
        self._scoring_enabled = bool(health_scoring_enabled)
        self._window_seconds = max(health_window_seconds, 1)
        self._bucket_seconds = _bucket_seconds(self._window_seconds)
        self._penalty_weight = min(max(health_penalty_weight, 0.0), 1.0)
        self._min_samples = max(health_min_samples, 1)

    @property
    def window_seconds(self) -> int:
        return self._window_seconds

    def configure(
        self,
        *,
        health_scoring_enabled: bool,
        health_window_seconds: int,
        health_penalty_weight: float,
        health_min_samples: int,
    ) -> bool:
        effective_enabled = bool(health_scoring_enabled)
        bounded_window_seconds = max(health_window_seconds, 1)
        bucket_seconds = _bucket_seconds(bounded_window_seconds)
        bounded_penalty_weight = min(max(health_penalty_weight, 0.0), 1.0)
        bounded_min_samples = max(health_min_samples, 1)
        changed = (
            effective_enabled != self._scoring_enabled
            or bounded_window_seconds != self._window_seconds
            or bounded_penalty_weight != self._penalty_weight
            or bounded_min_samples != self._min_samples
        )
        if bucket_seconds != self._bucket_seconds:
            self._windows.clear()
        self._scoring_enabled = effective_enabled
        self._window_seconds = bounded_window_seconds
        self._bucket_seconds = bucket_seconds
        self._penalty_weight = bounded_penalty_weight
        self._min_samples = bounded_min_samples
        return changed

    def clear(self) -> None:
        self._windows.clear()

    def record_success(self, key: ModelKey) -> None:
        self._windows[key].record(
            now=monotonic(), bucket_seconds=self._bucket_seconds, success=True
        )

    def record_failure(self, key: ModelKey) -> None:
        self._windows[key].record(
            now=monotonic(), bucket_seconds=self._bucket_seconds, success=False
        )

    def score(self, key: ModelKey) -> float:
        if not self._scoring_enabled:
            return 1.0
        window = self._windows.get(key)
        if window is None:
            return 1.0
        window.prune(
            now=monotonic(),
            window_seconds=self._window_seconds,
            bucket_seconds=self._bucket_seconds,
        )
        total = window.successes + window.failures
        if total == 0:
            return 1.0
        confidence = min(1.0, total / self._min_samples)
        penalty = window.failures / total * self._penalty_weight * confidence
        return max(1.0 - penalty, 0.0)

    def model_keys(self) -> set[ModelKey]:
        return set(self._windows)

    def evict(self, keys: set[ModelKey]) -> None:
        for key in keys:
            self._windows.pop(key, None)

    def prune(self, *, now: float) -> None:
        for key, window in list(self._windows.items()):
            window.prune(
                now=now,
                window_seconds=self._window_seconds,
                bucket_seconds=self._bucket_seconds,
            )
            if not window.buckets:
                self._windows.pop(key, None)


def _bucket_seconds(window_seconds: int) -> int:
    return max(ceil(window_seconds / 300), 1)

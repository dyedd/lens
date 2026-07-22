from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from math import ceil
from time import monotonic

from ...models import ChannelConfig, ChannelHealth, ChannelKeyHealth, ModelHealth
from .cooldown import (
    CooldownPolicy,
    ErrorCategory,
    calculate_exponential_cooldown,
)
from .types import RouteTarget

_ModelKey = tuple[str, str]
_CredentialKey = tuple[str, str]


@dataclass(slots=True)
class _CooldownState:
    consecutive_failures: int = 0
    last_error: str | None = None
    last_error_category: ErrorCategory | None = None
    cooled_until: float = 0.0
    last_cooldown: float = 0.0
    last_failure_at: float = 0.0
    failure_revision: int = 0


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


class _HealthTracker:
    def __init__(
        self,
        *,
        health_scoring_enabled: bool,
        health_window_seconds: int,
        health_penalty_weight: float,
        health_min_samples: int,
        cooldown_policy: CooldownPolicy | None = None,
    ) -> None:
        self._model_health: dict[_ModelKey, _CooldownState] = {}
        self._credential_health: dict[_CredentialKey, _CooldownState] = {}
        self._health_windows: dict[_ModelKey, _HealthWindow] = defaultdict(
            _HealthWindow
        )
        self._health_scoring_enabled = bool(health_scoring_enabled)
        self._health_window_seconds = max(health_window_seconds, 1)
        self._health_bucket_seconds = self._bucket_seconds(self._health_window_seconds)
        self._health_penalty_weight = min(max(health_penalty_weight, 0.0), 1.0)
        self._health_min_samples = max(health_min_samples, 1)
        self._cooldown_policy = cooldown_policy or CooldownPolicy()
        self._failure_revision = 0
        self._channel_signature: tuple[object, ...] | None = None
        self._channel_execution_signatures: dict[str, tuple[object, ...]] = {}
        self._credential_signatures: dict[_CredentialKey, str] = {}
        self._routing_environment_signature: tuple[str, str] | None = None
        self._next_stale_prune_at = 0.0

    def configure(
        self,
        *,
        health_scoring_enabled: bool,
        health_window_seconds: int,
        health_penalty_weight: float,
        health_min_samples: int,
        cooldown_policy: CooldownPolicy,
        routing_environment_signature: tuple[str, str],
    ) -> bool:
        normalized_enabled = bool(health_scoring_enabled)
        normalized_window_seconds = max(health_window_seconds, 1)
        bucket_seconds = self._bucket_seconds(normalized_window_seconds)
        normalized_penalty_weight = min(max(health_penalty_weight, 0.0), 1.0)
        normalized_min_samples = max(health_min_samples, 1)
        scoring_changed = (
            normalized_enabled != self._health_scoring_enabled
            or normalized_window_seconds != self._health_window_seconds
            or normalized_penalty_weight != self._health_penalty_weight
            or normalized_min_samples != self._health_min_samples
        )
        if (
            not scoring_changed
            and cooldown_policy == self._cooldown_policy
            and routing_environment_signature == self._routing_environment_signature
        ):
            return False

        self._health_scoring_enabled = normalized_enabled
        if bucket_seconds != self._health_bucket_seconds:
            self._health_windows.clear()
        self._health_window_seconds = normalized_window_seconds
        self._health_bucket_seconds = bucket_seconds
        self._health_penalty_weight = normalized_penalty_weight
        self._health_min_samples = normalized_min_samples
        self._cooldown_policy = cooldown_policy
        routing_environment_changed = (
            self._routing_environment_signature is not None
            and routing_environment_signature != self._routing_environment_signature
        )
        if routing_environment_changed:
            self._model_health.clear()
            self._credential_health.clear()
            self._health_windows.clear()
        self._routing_environment_signature = routing_environment_signature
        now = monotonic()
        self._apply_policy_to_active_cooldowns(now=now)
        self._next_stale_prune_at = 0.0
        self._prune_stale_states(now=now)
        return scoring_changed or routing_environment_changed

    @property
    def failure_revision(self) -> int:
        return self._failure_revision

    def record_success(
        self,
        channel_id: str,
        *,
        credential_id: str | None,
        model_name: str | None,
        started_revision: int | None,
    ) -> None:
        now = monotonic()
        model_key = self._model_key(channel_id, model_name)
        model_state = self._model_health.get(model_key)
        if model_state is not None and (
            started_revision is None or model_state.failure_revision <= started_revision
        ):
            self._model_health.pop(model_key, None)
        credential_key = self._credential_key(channel_id, credential_id)
        credential_state = self._credential_health.get(credential_key)
        if credential_state is not None and (
            started_revision is None
            or credential_state.failure_revision <= started_revision
        ):
            self._credential_health.pop(credential_key, None)
        self._health_windows[model_key].record(
            now=now,
            bucket_seconds=self._health_bucket_seconds,
            success=True,
        )
        self._prune_stale_states(now=now)

    def record_failure(
        self,
        channel_id: str,
        error: str,
        *,
        category: ErrorCategory,
        credential_id: str | None,
        model_name: str | None,
        cooldown_seconds: float | None,
    ) -> None:
        now = monotonic()
        self._failure_revision += 1
        if category == ErrorCategory.AUTH:
            state = self._credential_health.setdefault(
                self._credential_key(channel_id, credential_id), _CooldownState()
            )
        else:
            model_key = self._model_key(channel_id, model_name)
            self._health_windows[model_key].record(
                now=now,
                bucket_seconds=self._health_bucket_seconds,
                success=False,
            )
            state = self._model_health.setdefault(model_key, _CooldownState())
        self._record_cooldown_failure(
            state,
            error,
            category,
            cooldown_seconds=cooldown_seconds,
            now=now,
            failure_revision=self._failure_revision,
        )
        self._prune_stale_states(now=now)

    def is_target_available(self, target: RouteTarget, *, now: float) -> bool:
        model_state = self._model_health.get(
            self._model_key(target.channel.id, target.model_name)
        )
        if model_state is not None and model_state.cooled_until > now:
            return False
        credential_state = self._credential_health.get(
            self._credential_key(target.channel.id, target.credential_id)
        )
        if credential_state is not None and credential_state.cooled_until > now:
            return False
        return True

    def score(self, target: RouteTarget) -> float:
        return self._score_model(self._model_key(target.channel.id, target.model_name))

    def build_channel_health(
        self, channel: ChannelConfig, *, now: float
    ) -> ChannelHealth:
        configured_models = self._configured_model_names(channel)
        model_names = configured_models | {
            model_name
            for channel_id, model_name in set(self._model_health)
            | set(self._health_windows)
            if channel_id == channel.id
        }
        model_health = [
            self._build_model_health(channel.id, model_name, now=now)
            for model_name in sorted(model_names)
        ]
        key_health = [
            self._build_key_health(channel.id, key.id, now=now)
            for key in channel.keys
            if key.enabled
        ]
        if not channel.keys:
            key_health.append(self._build_key_health(channel.id, "", now=now))
        configured_bindings = self._configured_bindings(channel)
        target_available_at = [
            self._binding_available_at(channel.id, credential_id, model_name)
            for credential_id, model_name in configured_bindings
        ]
        available_binding_count = sum(
            available_at <= now for available_at in target_available_at
        )
        channel_cooled_until = (
            min(target_available_at)
            if target_available_at and available_binding_count == 0
            else 0.0
        )

        states = [
            state
            for (channel_id, _), state in self._model_health.items()
            if channel_id == channel.id
        ]
        states.extend(
            state
            for (channel_id, _), state in self._credential_health.items()
            if channel_id == channel.id
        )
        latest_state = max(
            states, key=lambda state: state.last_failure_at, default=None
        )
        available_key_count = sum(item.available for item in key_health)
        available_model_count = sum(item.available for item in model_health)
        return ChannelHealth(
            channel_id=channel.id,
            consecutive_failures=max(
                (state.consecutive_failures for state in states), default=0
            ),
            last_error=latest_state.last_error if latest_state else None,
            last_error_category=(
                latest_state.last_error_category.value
                if latest_state and latest_state.last_error_category
                else None
            ),
            opened_until=channel_cooled_until,
            cooldown_remaining_seconds=self._remaining_seconds(
                channel_cooled_until, now=now
            ),
            last_cooldown_seconds=int(
                max((state.last_cooldown for state in states), default=0.0)
            ),
            score=max((item.score for item in model_health), default=1.0),
            available=available_binding_count > 0,
            available_key_count=available_key_count,
            cooled_key_count=len(key_health) - available_key_count,
            available_model_count=available_model_count,
            cooled_model_count=len(model_health) - available_model_count,
            key_health=key_health,
            model_health=model_health,
        )

    def sync_channels(self, channels: list[ChannelConfig]) -> set[str]:
        execution_signatures = {
            channel.id: self._channel_execution_signature(channel)
            for channel in channels
        }
        credential_signatures_by_channel = {
            channel.id: self._channel_credential_signatures(channel)
            for channel in channels
        }
        credential_signatures = {
            self._credential_key(channel_id, credential_id): secret
            for channel_id, items in credential_signatures_by_channel.items()
            for credential_id, secret in items
        }
        signature = tuple(
            (
                channel.id,
                execution_signatures[channel.id],
                credential_signatures_by_channel[channel.id],
                tuple(
                    sorted(
                        (model.credential_id, model.model_name)
                        for model in channel.models
                        if model.enabled
                    )
                ),
            )
            for channel in channels
        )
        now = monotonic()
        if signature == self._channel_signature:
            self._prune_stale_states(now=now)
            return set()

        changed_channels = {
            channel_id
            for channel_id, current in execution_signatures.items()
            if channel_id in self._channel_execution_signatures
            and current != self._channel_execution_signatures[channel_id]
        }
        changed_credentials = {
            key
            for key, current in credential_signatures.items()
            if key in self._credential_signatures
            and current != self._credential_signatures[key]
        }
        changed_route_channels = (
            changed_channels
            | {key[0] for key in changed_credentials}
            | (set(self._channel_execution_signatures) - set(execution_signatures))
        )
        self._channel_signature = signature
        self._channel_execution_signatures = execution_signatures
        self._credential_signatures = credential_signatures
        channel_map = {channel.id: channel for channel in channels}
        valid_credentials = {
            channel.id: (
                {key.id for key in channel.keys if key.enabled}
                if channel.keys
                else {""}
            )
            for channel in channels
        }
        configured_models = {
            channel.id: self._configured_model_names(channel)
            for channel in channels
            if channel.models
        }
        for key in list(self._credential_health):
            if (
                key[0] not in channel_map
                or key[0] in changed_channels
                or key in changed_credentials
                or key[1] not in valid_credentials[key[0]]
            ):
                self._credential_health.pop(key, None)
        for key in set(self._model_health) | set(self._health_windows):
            channel_id, model_name = key
            if (
                channel_id not in channel_map
                or channel_id in changed_channels
                or (
                    channel_id in configured_models
                    and model_name not in configured_models[channel_id]
                )
            ):
                self._model_health.pop(key, None)
                self._health_windows.pop(key, None)
        self._prune_stale_states(now=now)
        return changed_route_channels

    def _record_cooldown_failure(
        self,
        state: _CooldownState,
        error: str,
        category: ErrorCategory,
        *,
        cooldown_seconds: float | None,
        now: float,
        failure_revision: int,
    ) -> None:
        if state.cooled_until > now:
            state.failure_revision = failure_revision
            return
        failure_gap_started_at = max(state.last_failure_at, state.cooled_until)
        if (
            failure_gap_started_at > 0
            and now - failure_gap_started_at
            > self._cooldown_policy.failure_window_seconds
        ):
            state.consecutive_failures = 0
            state.last_cooldown = 0.0
        if state.last_error_category != category:
            state.consecutive_failures = 0
            state.last_cooldown = 0.0

        state.last_error = error
        state.last_error_category = category
        state.last_failure_at = now
        state.failure_revision = failure_revision
        initial_cooldown = self._cooldown_policy.initial_cooldown(category)
        if initial_cooldown <= 0 or self._cooldown_policy.max_cooldown_seconds <= 0:
            state.consecutive_failures = 0
            state.last_cooldown = 0.0
            state.cooled_until = 0.0
            return

        state.consecutive_failures += 1
        threshold = (
            1
            if cooldown_seconds is not None
            else self._cooldown_policy.threshold(category)
        )
        if state.consecutive_failures < threshold:
            return
        if cooldown_seconds is not None:
            cooldown = min(
                max(cooldown_seconds, 0.0),
                float(self._cooldown_policy.max_cooldown_seconds),
            )
        else:
            cooldown = calculate_exponential_cooldown(
                state.last_cooldown,
                initial_cooldown,
                self._cooldown_policy.backoff_multiplier,
                self._cooldown_policy.max_cooldown_seconds,
            )
        state.last_cooldown = cooldown
        state.cooled_until = now + cooldown if cooldown > 0 else 0.0

    def _apply_policy_to_active_cooldowns(self, *, now: float) -> None:
        for state in [*self._model_health.values(), *self._credential_health.values()]:
            category = state.last_error_category
            if category is None:
                continue
            if (
                self._cooldown_policy.max_cooldown_seconds <= 0
                or self._cooldown_policy.initial_cooldown(category) <= 0
            ):
                state.cooled_until = 0.0
                state.last_cooldown = 0.0
                state.consecutive_failures = 0
                continue
            state.last_cooldown = min(
                state.last_cooldown,
                float(self._cooldown_policy.max_cooldown_seconds),
            )
            state.cooled_until = min(
                state.cooled_until,
                now + self._cooldown_policy.max_cooldown_seconds,
            )

    def _score_model(self, model_key: _ModelKey) -> float:
        if not self._health_scoring_enabled:
            return 1.0
        window = self._health_windows.get(model_key)
        if window is None:
            return 1.0
        window.prune(
            now=monotonic(),
            window_seconds=self._health_window_seconds,
            bucket_seconds=self._health_bucket_seconds,
        )
        successes, failures = window.successes, window.failures
        total = successes + failures
        if total == 0:
            return 1.0
        confidence = min(1.0, total / self._health_min_samples)
        penalty = failures / total * self._health_penalty_weight * confidence
        return max(1.0 - penalty, 0.0)

    def _build_model_health(
        self, channel_id: str, model_name: str, *, now: float
    ) -> ModelHealth:
        model_key = self._model_key(channel_id, model_name)
        state = self._model_health.get(model_key)
        cooled_until = state.cooled_until if state else 0.0
        return ModelHealth(
            model_name=model_name or None,
            consecutive_failures=state.consecutive_failures if state else 0,
            last_error=state.last_error if state else None,
            last_error_category=(
                state.last_error_category.value
                if state and state.last_error_category
                else None
            ),
            cooled_until=cooled_until,
            cooldown_remaining_seconds=self._remaining_seconds(cooled_until, now=now),
            last_cooldown_seconds=int(state.last_cooldown if state else 0.0),
            score=self._score_model(model_key),
            available=cooled_until <= now,
        )

    def _build_key_health(
        self, channel_id: str, key_id: str, *, now: float
    ) -> ChannelKeyHealth:
        state = self._credential_health.get((channel_id, key_id))
        cooled_until = state.cooled_until if state else 0.0
        return ChannelKeyHealth(
            credential_id=key_id,
            consecutive_failures=state.consecutive_failures if state else 0,
            cooled_until=cooled_until,
            cooldown_remaining_seconds=self._remaining_seconds(cooled_until, now=now),
            last_cooldown_seconds=int(state.last_cooldown if state else 0.0),
            available=cooled_until <= now,
        )

    def _binding_available_at(
        self, channel_id: str, credential_id: str, model_name: str
    ) -> float:
        model_state = self._model_health.get(self._model_key(channel_id, model_name))
        credential_state = self._credential_health.get(
            self._credential_key(channel_id, credential_id)
        )
        return max(
            model_state.cooled_until if model_state else 0.0,
            credential_state.cooled_until if credential_state else 0.0,
        )

    def _configured_bindings(self, channel: ChannelConfig) -> set[tuple[str, str]]:
        enabled_credentials = {key.id for key in channel.keys if key.enabled}
        bindings = {
            (model.credential_id, model.model_name)
            for model in channel.models
            if model.enabled
            and (not channel.keys or model.credential_id in enabled_credentials)
        }
        if bindings:
            return bindings
        if channel.models:
            return set()
        if channel.keys and not enabled_credentials:
            return set()
        credentials = enabled_credentials or {""}
        models = self._configured_model_names(channel) or {""}
        return {
            (credential_id, model_name)
            for credential_id in credentials
            for model_name in models
        }

    @staticmethod
    def _configured_model_names(channel: ChannelConfig) -> set[str]:
        return {model.model_name for model in channel.models if model.enabled}

    @staticmethod
    def _channel_execution_signature(channel: ChannelConfig) -> tuple[object, ...]:
        return (
            channel.protocol.value,
            str(channel.base_url),
            tuple(sorted(channel.headers.items())),
            channel.proxy_mode.value,
            channel.channel_proxy,
            channel.param_override,
        )

    @staticmethod
    def _channel_credential_signatures(
        channel: ChannelConfig,
    ) -> tuple[tuple[str, str], ...]:
        if not channel.keys:
            return (("", channel.api_key),)
        return tuple(sorted((key.id, key.key) for key in channel.keys if key.enabled))

    def _prune_stale_states(self, *, now: float) -> None:
        if now < self._next_stale_prune_at:
            return
        prune_interval = min(
            self._cooldown_policy.failure_window_seconds,
            self._health_window_seconds,
            60,
        )
        self._next_stale_prune_at = now + max(prune_interval, 1)
        stale_before = now - self._cooldown_policy.failure_window_seconds
        for key, state in list(self._model_health.items()):
            if (
                state.cooled_until <= now
                and max(state.last_failure_at, state.cooled_until) < stale_before
            ):
                self._model_health.pop(key, None)
        for key, state in list(self._credential_health.items()):
            if (
                state.cooled_until <= now
                and max(state.last_failure_at, state.cooled_until) < stale_before
            ):
                self._credential_health.pop(key, None)
        for key, window in list(self._health_windows.items()):
            window.prune(
                now=now,
                window_seconds=self._health_window_seconds,
                bucket_seconds=self._health_bucket_seconds,
            )
            if not window.buckets:
                self._health_windows.pop(key, None)

    @staticmethod
    def _model_key(channel_id: str, model_name: str | None) -> _ModelKey:
        return channel_id, model_name or ""

    @staticmethod
    def _bucket_seconds(window_seconds: int) -> int:
        return max(ceil(window_seconds / 300), 1)

    @staticmethod
    def _credential_key(channel_id: str, credential_id: str | None) -> _CredentialKey:
        return channel_id, credential_id or ""

    @staticmethod
    def _remaining_seconds(until: float, *, now: float) -> int:
        if until <= now:
            return 0
        return max(ceil(until - now), 0)

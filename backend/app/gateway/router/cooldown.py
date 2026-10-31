from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from math import ceil
from time import monotonic
from typing import NamedTuple

from ...core.cooldown_rules import (
    CompiledCooldownDetectionRule,
    CooldownScope,
    ErrorCategory,
    compile_detection_rules,
)


class ErrorClassification(NamedTuple):
    category: ErrorCategory
    scope: CooldownScope
    cooldown_seconds: float | None = None
    action: str | None = None


@dataclass(frozen=True, slots=True)
class CooldownPolicy:
    failure_threshold: int = 3
    failure_window_seconds: int = 300
    timeout_threshold: int = 2
    network_threshold: int = 2
    server_cooldown_seconds: int = 60
    auth_cooldown_seconds: int = 300
    not_found_cooldown_seconds: int = 300
    rate_limit_cooldown_seconds: int = 60
    timeout_cooldown_seconds: int = 60
    network_cooldown_seconds: int = 60
    backoff_multiplier: float = 2.0
    max_cooldown_seconds: int = 600
    # 同一个实际模型上一把 Key 的失败不足以证明整条渠道故障。窗口内命中的
    # 不同 Key 达到该数量时，才把冷却升级到模型域；0 表示从不升级。
    escalate_threshold: int = 2
    escalate_window_seconds: int = 60
    detection_rules: tuple[CompiledCooldownDetectionRule, ...] = ()

    def threshold(self, category: ErrorCategory) -> int:
        if category in (
            ErrorCategory.AUTH,
            ErrorCategory.NOT_FOUND,
            ErrorCategory.RATE_LIMIT,
        ):
            return 1
        if category == ErrorCategory.TIMEOUT:
            return max(self.timeout_threshold, 1)
        if category == ErrorCategory.NETWORK:
            return max(self.network_threshold, 1)
        return max(self.failure_threshold, 1)

    def initial_cooldown(self, category: ErrorCategory) -> int:
        return {
            ErrorCategory.AUTH: self.auth_cooldown_seconds,
            ErrorCategory.NOT_FOUND: self.not_found_cooldown_seconds,
            ErrorCategory.RATE_LIMIT: self.rate_limit_cooldown_seconds,
            ErrorCategory.SERVER: self.server_cooldown_seconds,
            ErrorCategory.TIMEOUT: self.timeout_cooldown_seconds,
            ErrorCategory.NETWORK: self.network_cooldown_seconds,
        }[category]


def parse_cooldown_seconds(value: object, *, absolute: bool = False) -> float | None:
    """Parse a relative duration or UTC timestamp into non-negative seconds."""
    seconds = _parse_duration_or_timestamp(value, absolute=absolute)
    if seconds is None:
        return None
    return seconds if seconds >= 0 else 0.0


def _parse_duration_or_timestamp(value: object, *, absolute: bool) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        seconds = float(value)
        return seconds - datetime.now(UTC).timestamp() if absolute else seconds
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        pass
    try:
        timestamp = parsedate_to_datetime(text)
    except (TypeError, ValueError, OverflowError):
        try:
            timestamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    return (timestamp - datetime.now(UTC)).total_seconds()


def _relative_cooldown_from_headers(
    headers: Mapping[str, str] | None,
) -> float | None:
    if not headers:
        return None
    for name, value in headers.items():
        if name.lower() == "retry-after":
            return parse_cooldown_seconds(value)
    return None


def default_scope(category: ErrorCategory) -> CooldownScope:
    """Return the narrowest fault domain a category proves on its own.

    Auth and rate-limit responses belong to one credential: a throttled or
    revoked key says nothing about its sibling keys on the same channel.
    Not-found, server, timeout and network failures belong to the channel
    model endpoint, so they cool every key serving that model.
    """
    if category in (ErrorCategory.AUTH, ErrorCategory.RATE_LIMIT):
        return "key"
    return "model"


def _status_category(status_code: int | None) -> ErrorCategory | None:
    if status_code in (401, 403):
        return ErrorCategory.AUTH
    if status_code == 429:
        return ErrorCategory.RATE_LIMIT
    if status_code == 404:
        return ErrorCategory.NOT_FOUND
    if status_code in (408, 504):
        return ErrorCategory.TIMEOUT
    if status_code is not None and 500 <= status_code < 600:
        return ErrorCategory.SERVER
    return None


def classify_error(
    status_code: int | None,
    error_body: str | None = None,
    detection_rules: tuple[CompiledCooldownDetectionRule, ...] = (),
    error_headers: Mapping[str, str] | None = None,
) -> ErrorClassification | None:
    """Classify an upstream error using configured rules before status defaults."""
    body = error_body or ""
    header_cooldown = _relative_cooldown_from_headers(error_headers)
    for rule in sorted(detection_rules, key=lambda item: (-item.priority, item.order)):
        if rule.status_code is not None and rule.status_code != status_code:
            continue
        if rule.body_pattern is not None and rule.body_pattern.search(body) is None:
            continue
        return ErrorClassification(
            rule.category,
            rule.scope,
            header_cooldown
            if header_cooldown is not None
            else float(rule.cooldown_seconds),
            rule.action,
        )

    category = _status_category(status_code)
    if category is None:
        return None
    return ErrorClassification(category, default_scope(category), header_cooldown)


def calculate_exponential_cooldown(
    last_cooldown: float,
    initial: float,
    multiplier: float,
    max_cooldown: int,
) -> float:
    """Return a cooldown that always respects zero values and the hard maximum."""
    if initial <= 0 or max_cooldown <= 0:
        return 0.0
    next_cooldown = initial if last_cooldown <= 0 else last_cooldown * multiplier
    return min(max(next_cooldown, 0.0), float(max_cooldown))


ModelKey = tuple[str, str, str]
CredentialKey = tuple[str, str, str]


class ClaimDecision(NamedTuple):
    """Whether one request may use a target, and whether it acts as a probe."""

    allowed: bool
    is_probe: bool = False


@dataclass(slots=True)
class CooldownState:
    consecutive_failures: int = 0
    last_error: str | None = None
    last_error_category: ErrorCategory | None = None
    cooled_until: float = 0.0
    last_cooldown: float = 0.0
    last_failure_at: float = 0.0
    failure_revision: int = 0
    # 冷却到期后只允许一个请求探测该目标，成功后才会放行全量流量。
    probe_lease_until: float = 0.0


def model_key(
    channel_id: str, model_name: str | None, fault_protocol: str = ""
) -> ModelKey:
    """Model fault-domain key; the empty model name is the channel-wide domain.

    ``fault_protocol`` splits an auto channel's domains by client protocol.
    """
    return channel_id, model_name or "", fault_protocol


def credential_key(
    channel_id: str, credential_id: str | None, fault_protocol: str = ""
) -> CredentialKey:
    """Credential fault-domain key; the empty credential id means the channel key."""
    return channel_id, credential_id or "", fault_protocol


def remaining_seconds(until: float, *, now: float) -> int:
    if until <= now:
        return 0
    return max(ceil(until - now), 0)


class CooldownLedger:
    """Own the per-target cooldown state for model and credential fault domains."""

    def __init__(self, policy: CooldownPolicy | None = None) -> None:
        self._policy = policy or CooldownPolicy()
        self._model_states: dict[ModelKey, CooldownState] = {}
        self._credential_states: dict[CredentialKey, CooldownState] = {}
        self._failure_revision = 0

    @property
    def policy(self) -> CooldownPolicy:
        return self._policy

    @property
    def detection_rules(self):
        return self._policy.detection_rules

    @property
    def failure_revision(self) -> int:
        return self._failure_revision

    def clear(self) -> None:
        self._model_states.clear()
        self._credential_states.clear()

    def configure_policy(self, policy: CooldownPolicy) -> None:
        self._policy = policy
        self._clamp_active_cooldowns(now=monotonic())

    def record_model_failure(
        self,
        key: ModelKey,
        *,
        error: str,
        category: ErrorCategory,
        cooldown_seconds: float | None,
        was_probe: bool = False,
    ) -> None:
        now = monotonic()
        self._failure_revision += 1
        state = self._model_states.setdefault(key, CooldownState())
        self._record_failure(
            state,
            error,
            category,
            cooldown_seconds=cooldown_seconds,
            now=now,
            was_probe=was_probe,
        )

    def record_credential_failure(
        self,
        key: CredentialKey,
        *,
        error: str,
        category: ErrorCategory,
        cooldown_seconds: float | None,
        was_probe: bool = False,
    ) -> None:
        now = monotonic()
        self._failure_revision += 1
        state = self._credential_states.setdefault(key, CooldownState())
        self._record_failure(
            state,
            error,
            category,
            cooldown_seconds=cooldown_seconds,
            now=now,
            was_probe=was_probe,
        )

    def record_success(
        self,
        model: ModelKey,
        credential: CredentialKey,
        *,
        started_revision: int | None,
    ) -> None:
        model_state = self._model_states.get(model)
        if model_state is not None and (
            started_revision is None or model_state.failure_revision <= started_revision
        ):
            self._model_states.pop(model, None)
        credential_state = self._credential_states.get(credential)
        if credential_state is not None and (
            started_revision is None
            or credential_state.failure_revision <= started_revision
        ):
            self._credential_states.pop(credential, None)

    def model_state(self, key: ModelKey) -> CooldownState | None:
        return self._model_states.get(key)

    def credential_state(self, key: CredentialKey) -> CooldownState | None:
        return self._credential_states.get(key)

    def model_keys(self) -> set[ModelKey]:
        return set(self._model_states)

    def credential_keys(self) -> set[CredentialKey]:
        return set(self._credential_states)

    def states_for_channel(self, channel_id: str) -> list[CooldownState]:
        """All cooldown states recorded for a channel's fault domains."""
        return [
            state
            for states in (self._model_states, self._credential_states)
            for key, state in states.items()
            if key[0] == channel_id
        ]

    def evict(self, keys: set[ModelKey] | set[CredentialKey]) -> None:
        for key in keys:
            self._model_states.pop(key, None)  # type: ignore[arg-type]
            self._credential_states.pop(key, None)  # type: ignore[arg-type]

    def cooldown_reason(
        self, model: ModelKey, credential: CredentialKey, *, now: float
    ) -> str:
        """Name the fault domain and remaining cooldown of an unavailable target."""
        states = [
            state
            for state in (
                self._model_states.get(model),
                self._credential_states.get(credential),
            )
            if state is not None and state.cooled_until > now
        ]
        if not states:
            return ""
        state = max(states, key=lambda item: item.cooled_until)
        category = (
            state.last_error_category.value
            if state.last_error_category is not None
            else "unknown"
        )
        detail = state.last_error or category
        return (
            f"{detail} ({category}, "
            f"{remaining_seconds(state.cooled_until, now=now)}s left)"
        )

    def remaining_seconds_for(
        self,
        model: ModelKey,
        credential: CredentialKey,
        *,
        now: float,
        channel_model_key: ModelKey | None = None,
    ) -> float:
        """Seconds until every fault domain of a target recovers; 0 when available."""
        return max(
            (
                state.cooled_until - now
                for state in self._target_states(model, credential, channel_model_key)
                if state is not None and state.cooled_until > now
            ),
            default=0.0,
        )

    def claim_probe(
        self,
        model: ModelKey,
        credential: CredentialKey,
        *,
        now: float,
        lease_seconds: float,
        channel_model_key: ModelKey | None = None,
    ) -> ClaimDecision:
        """Allow a request for one target, leasing a single probe when cooling.

        A target with no active cooldown is always claimable. While cooling, the
        first request takes a short lease and every concurrent request is turned
        away until that probe either succeeds (cooldown cleared) or fails (a new
        cooldown starts the next lease window).
        """
        states = [
            state
            for state in self._target_states(model, credential, channel_model_key)
            if state is not None
        ]
        # 冷却未到期时一律拒绝，等待到期后才放行探测。
        if any(state.cooled_until > now for state in states):
            return ClaimDecision(allowed=False)
        recovering = [
            state
            for state in states
            if state.cooled_until > 0 or state.last_cooldown > 0
        ]
        if not recovering:
            return ClaimDecision(allowed=True)
        # 冷却刚到期时只放行一个探测请求，避免全部请求同时涌入。
        if any(state.probe_lease_until > now for state in recovering):
            return ClaimDecision(allowed=False)
        lease_until = now + max(lease_seconds, 0.0)
        for state in recovering:
            state.probe_lease_until = lease_until
        return ClaimDecision(allowed=True, is_probe=True)

    def release_probe(
        self,
        model: ModelKey,
        credential: CredentialKey,
        *,
        channel_model_key: ModelKey | None = None,
    ) -> None:
        for state in self._target_states(model, credential, channel_model_key):
            if state is not None:
                state.probe_lease_until = 0.0

    def _target_states(
        self,
        model: ModelKey,
        credential: CredentialKey,
        channel_model_key: ModelKey | None,
    ) -> tuple[CooldownState | None, ...]:
        """Every cooldown domain that decides whether one target is usable."""
        channel_state = (
            self._model_states.get(channel_model_key)
            if channel_model_key is not None
            else None
        )
        return (
            channel_state,
            self._model_states.get(model),
            self._credential_states.get(credential),
        )

    def prune_stale(self, *, now: float) -> None:
        stale_before = now - self._policy.failure_window_seconds
        for key, state in list(self._model_states.items()):
            if (
                state.cooled_until <= now
                and max(state.last_failure_at, state.cooled_until) < stale_before
            ):
                self._model_states.pop(key, None)
        for key, state in list(self._credential_states.items()):
            if (
                state.cooled_until <= now
                and max(state.last_failure_at, state.cooled_until) < stale_before
            ):
                self._credential_states.pop(key, None)

    def _record_failure(
        self,
        state: CooldownState,
        error: str,
        category: ErrorCategory,
        *,
        cooldown_seconds: float | None,
        now: float,
        was_probe: bool = False,
    ) -> None:
        if state.cooled_until > now:
            state.failure_revision = self._failure_revision
            if was_probe:
                state.last_failure_at = now
                state.last_error = error
                state.last_error_category = category
                state.probe_lease_until = 0.0
                state.consecutive_failures += 1
                cooldown = calculate_exponential_cooldown(
                    state.last_cooldown,
                    self._policy.initial_cooldown(category),
                    self._policy.backoff_multiplier,
                    self._policy.max_cooldown_seconds,
                )
                state.last_cooldown = cooldown
                state.cooled_until = now + cooldown if cooldown > 0 else 0.0
            return
        failure_gap_started_at = max(state.last_failure_at, state.cooled_until)
        if (
            failure_gap_started_at > 0
            and now - failure_gap_started_at > self._policy.failure_window_seconds
        ):
            state.consecutive_failures = 0
            state.last_cooldown = 0.0
        if state.last_error_category != category:
            state.consecutive_failures = 0
            state.last_cooldown = 0.0

        state.last_error = error
        state.last_error_category = category
        state.last_failure_at = now
        state.failure_revision = self._failure_revision
        state.probe_lease_until = 0.0
        initial_cooldown = self._policy.initial_cooldown(category)
        if initial_cooldown <= 0 or self._policy.max_cooldown_seconds <= 0:
            state.consecutive_failures = 0
            state.last_cooldown = 0.0
            state.cooled_until = 0.0
            return

        state.consecutive_failures += 1
        threshold = self._policy.threshold(category)
        if state.consecutive_failures < threshold:
            return
        # 只有探测失败才重新放大退避：被冷却拒之门外的常规请求不该把恢复推远。
        if cooldown_seconds is not None and not was_probe:
            cooldown = min(
                max(cooldown_seconds, 0.0), float(self._policy.max_cooldown_seconds)
            )
        else:
            cooldown = calculate_exponential_cooldown(
                state.last_cooldown,
                initial_cooldown,
                self._policy.backoff_multiplier,
                self._policy.max_cooldown_seconds,
            )
        state.last_cooldown = cooldown
        state.cooled_until = now + cooldown if cooldown > 0 else 0.0

    def _clamp_active_cooldowns(self, *, now: float) -> None:
        for state in [*self._model_states.values(), *self._credential_states.values()]:
            category = state.last_error_category
            if category is None:
                continue
            if (
                self._policy.max_cooldown_seconds <= 0
                or self._policy.initial_cooldown(category) <= 0
            ):
                state.cooled_until = 0.0
                state.last_cooldown = 0.0
                state.consecutive_failures = 0
                continue
            state.last_cooldown = min(
                state.last_cooldown, float(self._policy.max_cooldown_seconds)
            )
            state.cooled_until = min(
                state.cooled_until, now + self._policy.max_cooldown_seconds
            )


__all__ = [
    "CompiledCooldownDetectionRule",
    "CooldownLedger",
    "CooldownPolicy",
    "CooldownScope",
    "CooldownState",
    "ErrorCategory",
    "ErrorClassification",
    "calculate_exponential_cooldown",
    "classify_error",
    "compile_detection_rules",
    "credential_key",
    "default_scope",
    "model_key",
    "parse_cooldown_seconds",
    "remaining_seconds",
]

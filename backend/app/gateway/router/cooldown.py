from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from enum import Enum
from math import ceil
from re import Pattern
from time import monotonic
from typing import Literal, NamedTuple


class ErrorCategory(Enum):
    """Identify the fault domain and cooldown policy for an upstream error."""

    AUTH = "auth"
    NOT_FOUND = "not_found"
    RATE_LIMIT = "rate_limit"
    SERVER = "server"
    TIMEOUT = "timeout"
    NETWORK = "network"


CooldownScope = Literal["key", "model", "channel"]


@dataclass(frozen=True, slots=True)
class CompiledCooldownDetectionRule:
    name: str
    status_code: int | None
    body_pattern: Pattern[str] | None
    scope: CooldownScope
    category: ErrorCategory
    cooldown_seconds: int
    priority: int
    order: int


class ErrorClassification(NamedTuple):
    category: ErrorCategory
    scope: CooldownScope
    cooldown_seconds: float | None = None


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
        )

    category: ErrorCategory | None
    scope: CooldownScope
    if status_code in (401, 403):
        category, scope = ErrorCategory.AUTH, "key"
    elif status_code == 429:
        category, scope = ErrorCategory.RATE_LIMIT, "model"
    elif status_code == 404:
        category, scope = ErrorCategory.NOT_FOUND, "model"
    elif status_code in (408, 504):
        category, scope = ErrorCategory.TIMEOUT, "model"
    elif status_code is not None and 500 <= status_code < 600:
        category, scope = ErrorCategory.SERVER, "model"
    else:
        return None
    return ErrorClassification(category, scope, header_cooldown)


def compile_detection_rules(
    rules: tuple[object, ...] | list[object],
) -> tuple[CompiledCooldownDetectionRule, ...]:
    """Compile validated detection rule patterns once while loading settings."""
    compiled: list[CompiledCooldownDetectionRule] = []
    for order, rule in enumerate(rules):
        status_code = rule.status_code
        body_regex = rule.body_regex
        compiled.append(
            CompiledCooldownDetectionRule(
                name=rule.name,
                status_code=status_code,
                body_pattern=re.compile(body_regex) if body_regex else None,
                scope=rule.scope,
                category=ErrorCategory(rule.category),
                cooldown_seconds=rule.cooldown_seconds,
                priority=rule.priority,
                order=order,
            )
        )
    return tuple(compiled)


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


ModelKey = tuple[str, str]
CredentialKey = tuple[str, str]


@dataclass(slots=True)
class CooldownState:
    consecutive_failures: int = 0
    last_error: str | None = None
    last_error_category: ErrorCategory | None = None
    cooled_until: float = 0.0
    last_cooldown: float = 0.0
    last_failure_at: float = 0.0
    failure_revision: int = 0


def model_key(channel_id: str, model_name: str | None) -> ModelKey:
    """Model fault-domain key; the empty model name is the channel-wide domain."""
    return channel_id, model_name or ""


def credential_key(channel_id: str, credential_id: str | None) -> CredentialKey:
    """Credential fault-domain key; the empty credential id means the channel key."""
    return channel_id, credential_id or ""


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
        channel_id: str,
        model_name: str | None,
        *,
        error: str,
        category: ErrorCategory,
        cooldown_seconds: float | None,
    ) -> None:
        now = monotonic()
        self._failure_revision += 1
        state = self._model_states.setdefault(
            model_key(channel_id, model_name), CooldownState()
        )
        self._record_failure(
            state, error, category, cooldown_seconds=cooldown_seconds, now=now
        )

    def record_credential_failure(
        self,
        channel_id: str,
        credential_id: str | None,
        *,
        error: str,
        category: ErrorCategory,
        cooldown_seconds: float | None,
    ) -> None:
        now = monotonic()
        self._failure_revision += 1
        state = self._credential_states.setdefault(
            credential_key(channel_id, credential_id), CooldownState()
        )
        self._record_failure(
            state, error, category, cooldown_seconds=cooldown_seconds, now=now
        )

    def record_success(
        self,
        channel_id: str,
        *,
        credential_id: str | None,
        model_name: str | None,
        started_revision: int | None,
    ) -> None:
        model_state = self._model_states.get(model_key(channel_id, model_name))
        if model_state is not None and (
            started_revision is None or model_state.failure_revision <= started_revision
        ):
            self._model_states.pop(model_key(channel_id, model_name), None)
        credential_state = self._credential_states.get(
            credential_key(channel_id, credential_id)
        )
        if credential_state is not None and (
            started_revision is None
            or credential_state.failure_revision <= started_revision
        ):
            self._credential_states.pop(credential_key(channel_id, credential_id), None)

    def model_state(
        self, channel_id: str, model_name: str | None
    ) -> CooldownState | None:
        return self._model_states.get(model_key(channel_id, model_name))

    def credential_state(
        self, channel_id: str, credential_id: str | None
    ) -> CooldownState | None:
        return self._credential_states.get(credential_key(channel_id, credential_id))

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

    def model_cooled_until(
        self, channel_id: str, model_name: str | None, *, now: float
    ) -> float:
        state = self._model_states.get(model_key(channel_id, model_name))
        return state.cooled_until if state else 0.0

    def credential_cooled_until(
        self, channel_id: str, credential_id: str | None, *, now: float
    ) -> float:
        state = self._credential_states.get(credential_key(channel_id, credential_id))
        return state.cooled_until if state else 0.0

    def cooldown_reason(
        self,
        channel_id: str,
        model_name: str | None,
        credential_id: str | None,
        *,
        now: float,
    ) -> str:
        """Name the fault domain and remaining cooldown of an unavailable target."""
        states = [
            state
            for state in (
                self._model_states.get(model_key(channel_id, model_name)),
                self._credential_states.get(credential_key(channel_id, credential_id)),
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
        return f"{category}, {remaining_seconds(state.cooled_until, now=now)}s left"

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
    ) -> None:
        if state.cooled_until > now:
            state.failure_revision = self._failure_revision
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
        initial_cooldown = self._policy.initial_cooldown(category)
        if initial_cooldown <= 0 or self._policy.max_cooldown_seconds <= 0:
            state.consecutive_failures = 0
            state.last_cooldown = 0.0
            state.cooled_until = 0.0
            return

        state.consecutive_failures += 1
        threshold = (
            1 if cooldown_seconds is not None else self._policy.threshold(category)
        )
        if state.consecutive_failures < threshold:
            return
        if cooldown_seconds is not None:
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
    "model_key",
    "parse_cooldown_seconds",
    "remaining_seconds",
]

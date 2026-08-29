from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from enum import Enum
from re import Pattern
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
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        seconds = float(value)
        if absolute:
            seconds -= datetime.now(UTC).timestamp()
        return seconds if seconds >= 0 else 0.0
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        seconds = float(text)
    except ValueError:
        try:
            timestamp = parsedate_to_datetime(text)
        except (TypeError, ValueError, OverflowError):
            try:
                timestamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError:
                return None
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        seconds = (timestamp - datetime.now(UTC)).total_seconds()
        return seconds if seconds >= 0 else 0.0
    if absolute:
        seconds -= datetime.now(UTC).timestamp()
    return seconds if seconds >= 0 else 0.0


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


__all__ = [
    "CompiledCooldownDetectionRule",
    "CooldownPolicy",
    "CooldownScope",
    "ErrorCategory",
    "ErrorClassification",
    "calculate_exponential_cooldown",
    "classify_error",
    "compile_detection_rules",
    "parse_cooldown_seconds",
]

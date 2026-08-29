from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ErrorCategory(Enum):
    """Identify the fault domain and cooldown policy for an upstream error."""

    AUTH = "auth"
    NOT_FOUND = "not_found"
    RATE_LIMIT = "rate_limit"
    SERVER = "server"
    TIMEOUT = "timeout"
    NETWORK = "network"


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


def classify_error(status_code: int | None) -> ErrorCategory | None:
    """Classify only errors that provide evidence about future target health."""
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
    "CooldownPolicy",
    "ErrorCategory",
    "classify_error",
]

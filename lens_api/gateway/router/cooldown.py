from __future__ import annotations

from enum import Enum


class ErrorCategory(Enum):
    """Identify the cooldown policy for an upstream error."""

    AUTH = "auth"
    RATE_LIMIT = "rate_limit"
    SERVER = "server"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


DEFAULT_INITIAL_COOLDOWN: dict[ErrorCategory, int] = {
    ErrorCategory.AUTH: 300,
    ErrorCategory.RATE_LIMIT: 60,
    ErrorCategory.SERVER: 120,
    ErrorCategory.TIMEOUT: 60,
    ErrorCategory.UNKNOWN: 60,
}


def classify_error(status_code: int | None) -> ErrorCategory:
    """Classify an upstream status code for cooldown handling."""
    if status_code is None:
        return ErrorCategory.TIMEOUT
    if status_code in (401, 403):
        return ErrorCategory.AUTH
    if status_code == 429:
        return ErrorCategory.RATE_LIMIT
    if 500 <= status_code < 600:
        return ErrorCategory.SERVER
    return ErrorCategory.UNKNOWN


def calculate_exponential_cooldown(
    last_cooldown: float, initial: int, max_cooldown: int
) -> float:
    if last_cooldown > 0:
        return min(last_cooldown * 2, max_cooldown)
    return initial


def cooldown_threshold(category: ErrorCategory, configured_threshold: int) -> int:
    if category in (ErrorCategory.AUTH, ErrorCategory.RATE_LIMIT):
        return 1
    if category == ErrorCategory.TIMEOUT:
        return 2
    return max(configured_threshold, 1)


def initial_cooldown(category: ErrorCategory, configured_cooldown: int) -> int:
    if category == ErrorCategory.SERVER and configured_cooldown > 0:
        return configured_cooldown
    return DEFAULT_INITIAL_COOLDOWN[category]


__all__ = ["ErrorCategory", "classify_error"]

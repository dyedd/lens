from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from re import Pattern
from typing import Literal


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
    action: str | None
    category: ErrorCategory
    cooldown_seconds: int
    priority: int
    order: int


def compile_detection_rules(
    rules: tuple[object, ...] | list[object],
) -> tuple[CompiledCooldownDetectionRule, ...]:
    """Compile validated detection rule patterns once while loading settings."""
    compiled: list[CompiledCooldownDetectionRule] = []
    for order, rule in enumerate(rules):
        body_regex = rule.body_regex
        compiled.append(
            CompiledCooldownDetectionRule(
                name=rule.name,
                status_code=rule.status_code,
                body_pattern=re.compile(body_regex) if body_regex else None,
                scope=rule.scope,
                action=rule.action,
                category=ErrorCategory(rule.category),
                cooldown_seconds=rule.cooldown_seconds,
                priority=rule.priority,
                order=order,
            )
        )
    return tuple(compiled)


__all__ = [
    "CompiledCooldownDetectionRule",
    "CooldownScope",
    "ErrorCategory",
    "compile_detection_rules",
]

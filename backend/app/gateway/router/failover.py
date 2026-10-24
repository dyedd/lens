from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from .cooldown import ClaimDecision, CooldownScope, ErrorCategory
from .targets import RouteTarget, TargetKey, target_key


class RetryAction(StrEnum):
    """Name the dimension the failover loop advances after a failed attempt."""

    RETRY_KEY = "retry_key"
    RETRY_CHANNEL = "retry_channel"
    TERMINAL = "terminal"


@dataclass(frozen=True, slots=True)
class FailurePolicy:
    """Decide what a failure cools and which dimension to advance."""

    category: ErrorCategory
    scope: CooldownScope
    action: RetryAction


# A throttled or rejected key proves nothing about its siblings, so both advance
# within the channel. Every other failure belongs to the channel's model
# endpoint, so the loop skips that channel's remaining keys.
_ACTIONS: dict[ErrorCategory, RetryAction] = {
    ErrorCategory.AUTH: RetryAction.RETRY_KEY,
    ErrorCategory.RATE_LIMIT: RetryAction.RETRY_KEY,
    ErrorCategory.NOT_FOUND: RetryAction.RETRY_CHANNEL,
    ErrorCategory.SERVER: RetryAction.RETRY_CHANNEL,
    ErrorCategory.TIMEOUT: RetryAction.RETRY_CHANNEL,
    ErrorCategory.NETWORK: RetryAction.RETRY_CHANNEL,
}


def policy_for(category: ErrorCategory, scope: CooldownScope) -> FailurePolicy:
    """Build the policy for an already classified failure."""
    return FailurePolicy(
        category=category,
        scope=scope,
        action=_ACTIONS[category],
    )


def _ordered_tiers(
    remaining: Sequence[RouteTarget],
    failed: RouteTarget | None,
    action: RetryAction,
) -> list[list[RouteTarget]]:
    """Rank untried targets by how far the action wants to move."""
    if failed is None:
        return [list(remaining)]
    if action is RetryAction.RETRY_KEY:
        preferred = [
            target
            for target in remaining
            if target.channel.id == failed.channel.id
            and target.model_name == failed.model_name
        ]
    else:
        preferred = [
            target for target in remaining if target.channel.id != failed.channel.id
        ]
    preferred_keys = {target_key(target) for target in preferred}
    rest = [target for target in remaining if target_key(target) not in preferred_keys]
    return [preferred, rest]


def next_candidate(
    ordered: Sequence[RouteTarget],
    *,
    failed: RouteTarget | None,
    tried: set[TargetKey],
    action: RetryAction,
    claim: Callable[[RouteTarget], ClaimDecision],
) -> tuple[RouteTarget, bool] | None:
    """Return the next claimable target and whether it acts as a recovery probe.

    ``claim`` both filters unavailable targets and leases the single recovery
    probe of a cooling target, so it must be called exactly once per candidate.
    """
    if action is RetryAction.TERMINAL:
        return None
    remaining = [target for target in ordered if target_key(target) not in tried]
    for tier in _ordered_tiers(remaining, failed, action):
        for target in tier:
            decision = claim(target)
            if decision.allowed:
                return target, decision.is_probe
    return None


__all__ = [
    "FailurePolicy",
    "RetryAction",
    "next_candidate",
    "policy_for",
]

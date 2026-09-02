from __future__ import annotations

from time import monotonic

from ...models.channels import ChannelConfig
from .cooldown import (
    CooldownLedger,
    CooldownPolicy,
    ErrorCategory,
    credential_key,
    model_key,
)
from .health_report import build_channel_health
from .health_scores import HealthScores
from .types import RouteTarget

_ChannelSignature = tuple[object, ...] | None


class _HealthTracker:
    """Compose the cooldown ledger and success-rate scores behind one interface.

    Owns configuration reconciliation (signature diffing, policy re-clamping)
    and dispatches observations to the two timelines it composes; the cooldown
    state machine lives in ``cooldown.CooldownLedger`` and windowed scoring in
    ``health_scores.HealthScores``.
    """

    def __init__(
        self,
        *,
        health_scoring_enabled: bool,
        health_window_seconds: int,
        health_penalty_weight: float,
        health_min_samples: int,
        cooldown_policy: CooldownPolicy | None = None,
    ) -> None:
        self._cooldowns = CooldownLedger(cooldown_policy)
        self._scores = HealthScores(
            health_scoring_enabled=health_scoring_enabled,
            health_window_seconds=health_window_seconds,
            health_penalty_weight=health_penalty_weight,
            health_min_samples=health_min_samples,
        )
        self._routing_environment_signature: tuple[str, str] | None = None
        self._next_stale_prune_at = 0.0
        self._channel_signature: _ChannelSignature = None
        self._channel_execution_signatures: dict[str, tuple[object, ...]] = {}
        self._credential_signatures: dict[tuple[str, str], str] = {}

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
        scoring_changed = self._scores.configure(
            health_scoring_enabled=health_scoring_enabled,
            health_window_seconds=health_window_seconds,
            health_penalty_weight=health_penalty_weight,
            health_min_samples=health_min_samples,
        )
        policy_changed = cooldown_policy != self._cooldowns.policy
        routing_environment_changed = (
            self._routing_environment_signature is not None
            and routing_environment_signature != self._routing_environment_signature
        )
        if (
            not scoring_changed
            and not policy_changed
            and not routing_environment_changed
        ):
            return False

        self._cooldowns.configure_policy(cooldown_policy)
        if routing_environment_changed:
            self._cooldowns.clear()
            self._scores.clear()
        self._routing_environment_signature = routing_environment_signature
        self._next_stale_prune_at = 0.0
        self._prune_stale_states(now=monotonic())
        return scoring_changed or routing_environment_changed

    @property
    def failure_revision(self) -> int:
        return self._cooldowns.failure_revision

    @property
    def cooldown_detection_rules(self):
        return self._cooldowns.detection_rules

    def record_success(
        self,
        channel_id: str,
        *,
        credential_id: str | None,
        model_name: str | None,
        started_revision: int | None,
    ) -> None:
        self._cooldowns.record_success(
            channel_id,
            credential_id=credential_id,
            model_name=model_name,
            started_revision=started_revision,
        )
        self._scores.record_success(model_key(channel_id, model_name))
        self._prune_stale_states(now=monotonic())

    def record_failure(
        self,
        channel_id: str,
        error: str,
        *,
        category: ErrorCategory,
        credential_id: str | None,
        model_name: str | None,
        scope: str,
        cooldown_seconds: float | None,
    ) -> None:
        if category == ErrorCategory.AUTH or scope == "key":
            self._cooldowns.record_credential_failure(
                channel_id,
                credential_id,
                error=error,
                category=category,
                cooldown_seconds=cooldown_seconds,
            )
        else:
            state_model_name = "" if scope == "channel" else model_name
            self._scores.record_failure(model_key(channel_id, state_model_name))
            self._cooldowns.record_model_failure(
                channel_id,
                state_model_name,
                error=error,
                category=category,
                cooldown_seconds=cooldown_seconds,
            )
        self._prune_stale_states(now=monotonic())

    def is_target_available(self, target: RouteTarget, *, now: float) -> bool:
        channel_id = target.channel.id
        cooled = (
            self._cooldowns.model_cooled_until(channel_id, "", now=now),
            self._cooldowns.model_cooled_until(channel_id, target.model_name, now=now),
            self._cooldowns.credential_cooled_until(
                channel_id, target.credential_id, now=now
            ),
        )
        return max(cooled) <= now

    def score(self, target: RouteTarget) -> float:
        return self._scores.score(model_key(target.channel.id, target.model_name))

    def cooldown_reason(self, target: RouteTarget, *, now: float) -> str:
        """Name the fault domain and remaining cooldown of an unavailable target."""
        return self._cooldowns.cooldown_reason(
            target.channel.id,
            target.model_name,
            target.credential_id,
            now=now,
        )

    def build_channel_health(self, channel: ChannelConfig, *, now: float):
        return build_channel_health(self._cooldowns, self._scores, channel, now=now)

    def sync_channels(self, channels: list[ChannelConfig]) -> set[str]:
        execution_signatures = {
            channel.id: _channel_execution_signature(channel) for channel in channels
        }
        credential_signatures_by_channel = {
            channel.id: _channel_credential_signatures(channel) for channel in channels
        }
        credential_signatures = {
            credential_key(channel_id, credential_id): secret
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
        channel_ids = {channel.id for channel in channels}
        valid_credentials = {
            channel.id: (
                {key.id for key in channel.keys if key.enabled}
                if channel.keys
                else {""}
            )
            for channel in channels
        }
        configured_models = {
            channel.id: _configured_model_names(channel)
            for channel in channels
            if channel.models
        }
        evicted_credentials = {
            key
            for key in self._cooldowns.credential_keys()
            if key[0] not in channel_ids
            or key[0] in changed_channels
            or key in changed_credentials
            or key[1] not in valid_credentials[key[0]]
        }
        evicted_models = {
            key
            for key in self._cooldowns.model_keys() | self._scores.model_keys()
            if key[0] not in channel_ids
            or key[0] in changed_channels
            or (key[0] in configured_models and key[1] not in configured_models[key[0]])
        }
        self._cooldowns.evict(evicted_credentials | evicted_models)
        self._scores.evict(evicted_models)
        self._prune_stale_states(now=now)
        return changed_route_channels

    def _prune_stale_states(self, *, now: float) -> None:
        if now < self._next_stale_prune_at:
            return
        prune_interval = min(
            self._cooldowns.policy.failure_window_seconds,
            self._scores.window_seconds,
            60,
        )
        self._next_stale_prune_at = now + max(prune_interval, 1)
        self._cooldowns.prune_stale(now=now)
        self._scores.prune(now=now)


def _configured_model_names(channel: ChannelConfig) -> set[str]:
    return {model.model_name for model in channel.models if model.enabled}


def _channel_execution_signature(channel: ChannelConfig) -> tuple[object, ...]:
    return (
        channel.protocol.value,
        str(channel.base_url),
        tuple(
            tuple(sorted(rule.model_dump(mode="json").items()))
            for rule in channel.headers
        ),
        channel.proxy_mode.value,
        channel.channel_proxy,
        tuple(
            tuple(sorted(rule.model_dump(mode="json").items()))
            for rule in channel.param_override
        ),
    )


def _channel_credential_signatures(
    channel: ChannelConfig,
) -> tuple[tuple[str, str], ...]:
    if not channel.keys:
        return (("", channel.api_key),)
    return tuple(sorted((key.id, key.key) for key in channel.keys if key.enabled))

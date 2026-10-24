from __future__ import annotations

from collections.abc import Iterable
from time import monotonic

from ...models.channels import ChannelConfig
from ...models.routing import ChannelCredentialHealth, ChannelHealth, ModelHealth
from .cooldown import (
    ClaimDecision,
    CooldownLedger,
    CooldownPolicy,
    CooldownState,
    CredentialKey,
    ErrorCategory,
    ModelKey,
    credential_key,
    model_key,
    remaining_seconds,
)
from .health_scores import HealthScores
from .targets import RouteTarget

_ChannelSignature = tuple[object, ...] | None


class HealthTracker:
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
        # (channel, model, fault protocol) -> {credential id: last failure time}
        self._escalations: dict[tuple[str, str, str], dict[str, float]] = {}

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
        if policy_changed or routing_environment_changed:
            self._escalations.clear()
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
        fault_protocol: str,
        started_revision: int | None,
    ) -> None:
        model = model_key(channel_id, model_name, fault_protocol)
        self._cooldowns.record_success(
            model,
            credential_key(channel_id, credential_id, fault_protocol),
            started_revision=started_revision,
        )
        self._scores.record_success(model)
        self._prune_stale_states(now=monotonic())

    def record_failure(
        self,
        channel_id: str,
        error: str,
        *,
        category: ErrorCategory,
        credential_id: str | None,
        model_name: str | None,
        fault_protocol: str,
        scope: str,
        cooldown_seconds: float | None,
        was_probe: bool = False,
    ) -> None:
        if category == ErrorCategory.AUTH or scope == "key":
            self._cooldowns.record_credential_failure(
                credential_key(channel_id, credential_id, fault_protocol),
                error=error,
                category=category,
                cooldown_seconds=cooldown_seconds,
                was_probe=was_probe,
            )
            self._escalate_throttled_model(
                channel_id,
                model_name,
                fault_protocol,
                category,
                credential_id,
                error=error,
                cooldown_seconds=cooldown_seconds,
                was_probe=was_probe,
            )
        else:
            state_key = (
                model_key(channel_id, "")
                if scope == "channel"
                else model_key(channel_id, model_name, fault_protocol)
            )
            self._scores.record_failure(state_key)
            self._cooldowns.record_model_failure(
                state_key,
                error=error,
                category=category,
                cooldown_seconds=cooldown_seconds,
                was_probe=was_probe,
            )
        self._prune_stale_states(now=monotonic())

    def _escalate_throttled_model(
        self,
        channel_id: str,
        model_name: str | None,
        fault_protocol: str,
        category: ErrorCategory,
        credential_id: str | None,
        *,
        error: str,
        cooldown_seconds: float | None,
        was_probe: bool,
    ) -> None:
        """Cool the whole model once several keys of it throttle at once.

        A single throttled key says nothing about its siblings, so cooling only
        keys keeps paying for the same discovery on every request.
        """
        policy = self._cooldowns.policy
        if (
            was_probe
            or category is not ErrorCategory.RATE_LIMIT
            or policy.escalate_threshold <= 0
            or policy.escalate_window_seconds <= 0
        ):
            return
        now = monotonic()
        key = (channel_id, model_name or "", fault_protocol)
        seen = self._escalations.setdefault(key, {})
        cutoff = now - policy.escalate_window_seconds
        for seen_credential, seen_at in list(seen.items()):
            if seen_at <= cutoff:
                seen.pop(seen_credential, None)
        seen[credential_id or ""] = now
        if len(seen) < policy.escalate_threshold:
            return
        seen.clear()
        self._cooldowns.record_model_failure(
            model_key(channel_id, model_name, fault_protocol),
            error=error,
            category=category,
            cooldown_seconds=cooldown_seconds,
        )

    def claim_target(
        self, target: RouteTarget, *, now: float, lease_seconds: float
    ) -> ClaimDecision:
        """Whether one request may use this target, leasing its recovery probe."""
        return self._cooldowns.claim_probe(
            _target_model_key(target),
            _target_credential_key(target),
            now=now,
            lease_seconds=lease_seconds,
            channel_model_key=model_key(target.channel.id, ""),
        )

    def cooldown_remaining_seconds(self, target: RouteTarget, *, now: float) -> float:
        """Seconds until the target becomes usable again; 0 means available now."""
        return self._cooldowns.remaining_seconds_for(
            _target_model_key(target),
            _target_credential_key(target),
            now=now,
            channel_model_key=model_key(target.channel.id, ""),
        )

    def is_target_available(self, target: RouteTarget, *, now: float) -> bool:
        return self.cooldown_remaining_seconds(target, now=now) <= 0.0

    def score(self, target: RouteTarget) -> float:
        return self._scores.score(_target_model_key(target))

    def cooldown_reason(self, target: RouteTarget, *, now: float) -> str:
        """Name the fault domain and remaining cooldown of an unavailable target."""
        return self._cooldowns.cooldown_reason(
            _target_model_key(target), _target_credential_key(target), now=now
        )

    def project_channel_health(self, channel: ChannelConfig, *, now: float):
        return build_channel_health(self._cooldowns, self._scores, channel, now=now)

    def reconcile_channels(self, channels: list[ChannelConfig]) -> set[str]:
        execution_signatures = {
            channel.id: _channel_execution_signature(channel) for channel in channels
        }
        credential_signatures_by_channel = {
            channel.id: _channel_credential_signatures(channel) for channel in channels
        }
        credential_signatures = {
            (channel_id, credential_id): secret
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
            channel.id: ({key.id for key in channel.keys} if channel.keys else {""})
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
            or key[:2] in changed_credentials
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
        self._prune_escalations(now=now)

    def _prune_escalations(self, *, now: float) -> None:
        window = self._cooldowns.policy.escalate_window_seconds
        if window <= 0:
            self._escalations.clear()
            return
        cutoff = now - window
        for key, seen in list(self._escalations.items()):
            for credential, seen_at in list(seen.items()):
                if seen_at <= cutoff:
                    seen.pop(credential, None)
            if not seen:
                self._escalations.pop(key, None)


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
    return tuple(sorted((key.id, key.key) for key in channel.keys))


def _target_model_key(target: RouteTarget) -> ModelKey:
    return model_key(target.channel.id, target.model_name, target.fault_protocol)


def _target_credential_key(target: RouteTarget) -> CredentialKey:
    return credential_key(
        target.channel.id, target.credential_id, target.fault_protocol
    )


def _fault_protocols(channel: ChannelConfig) -> tuple[str, ...]:
    del channel
    return ("",)


def _most_restrictive_state(
    states: Iterable[CooldownState | None],
) -> CooldownState | None:
    """Admin views show a channel by its most restrictive client protocol."""
    return max(
        (state for state in states if state is not None),
        key=lambda state: (state.cooled_until, state.last_failure_at),
        default=None,
    )


def _model_state(
    cooldowns: CooldownLedger,
    channel_id: str,
    model_name: str,
    fault_protocols: tuple[str, ...],
) -> CooldownState | None:
    return _most_restrictive_state(
        cooldowns.model_state(model_key(channel_id, model_name, fault_protocol))
        for fault_protocol in fault_protocols
    )


def _credential_state(
    cooldowns: CooldownLedger,
    channel_id: str,
    credential_id: str,
    fault_protocols: tuple[str, ...],
) -> CooldownState | None:
    return _most_restrictive_state(
        cooldowns.credential_state(
            credential_key(channel_id, credential_id, fault_protocol)
        )
        for fault_protocol in fault_protocols
    )


def build_channel_health(
    cooldowns: CooldownLedger,
    scores: HealthScores,
    channel: ChannelConfig,
    *,
    now: float,
) -> ChannelHealth:
    """Project the runtime cooldown and score timelines into admin DTOs."""
    fault_protocols = _fault_protocols(channel)
    configured_models = _configured_model_names(channel)
    model_names = configured_models | {
        key[1]
        for key in cooldowns.model_keys() | scores.model_keys()
        if key[0] == channel.id
    }
    model_health = [
        _build_model_health(
            cooldowns, scores, channel.id, model_name, fault_protocols, now=now
        )
        for model_name in sorted(model_names)
    ]
    credential_health = [
        _build_credential_health(
            cooldowns, channel.id, key.id, fault_protocols, now=now
        )
        for key in channel.keys
    ]
    if not channel.keys:
        credential_health.append(
            _build_credential_health(
                cooldowns, channel.id, "", fault_protocols, now=now
            )
        )
    configured_bindings = _configured_bindings(channel)
    target_available_at = [
        _binding_available_at(
            cooldowns, channel.id, credential_id, model_name, fault_protocols
        )
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

    states = cooldowns.states_for_channel(channel.id)
    latest_state = max(states, key=lambda state: state.last_failure_at, default=None)
    available_key_count = sum(item.available for item in credential_health)
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
        cooldown_remaining_seconds=remaining_seconds(channel_cooled_until, now=now),
        last_cooldown_seconds=int(
            max((state.last_cooldown for state in states), default=0.0)
        ),
        score=max((item.score for item in model_health), default=1.0),
        available=available_binding_count > 0,
        available_key_count=available_key_count,
        cooled_key_count=len(credential_health) - available_key_count,
        available_model_count=available_model_count,
        cooled_model_count=len(model_health) - available_model_count,
        credential_health=credential_health,
        model_health=model_health,
    )


def _build_model_health(
    cooldowns: CooldownLedger,
    scores: HealthScores,
    channel_id: str,
    model_name: str,
    fault_protocols: tuple[str, ...],
    *,
    now: float,
) -> ModelHealth:
    state = _model_state(cooldowns, channel_id, model_name, fault_protocols)
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
        cooldown_remaining_seconds=remaining_seconds(cooled_until, now=now),
        last_cooldown_seconds=int(state.last_cooldown if state else 0.0),
        score=min(
            scores.score(model_key(channel_id, model_name, fault_protocol))
            for fault_protocol in fault_protocols
        ),
        available=cooled_until <= now,
    )


def _build_credential_health(
    cooldowns: CooldownLedger,
    channel_id: str,
    key_id: str,
    fault_protocols: tuple[str, ...],
    *,
    now: float,
) -> ChannelCredentialHealth:
    state = _credential_state(cooldowns, channel_id, key_id, fault_protocols)
    cooled_until = state.cooled_until if state else 0.0
    return ChannelCredentialHealth(
        credential_id=key_id,
        consecutive_failures=state.consecutive_failures if state else 0,
        cooled_until=cooled_until,
        cooldown_remaining_seconds=remaining_seconds(cooled_until, now=now),
        last_cooldown_seconds=int(state.last_cooldown if state else 0.0),
        available=cooled_until <= now,
    )


def _binding_available_at(
    cooldowns: CooldownLedger,
    channel_id: str,
    credential_id: str,
    model_name: str,
    fault_protocols: tuple[str, ...],
) -> float:
    model_state = _model_state(cooldowns, channel_id, model_name, fault_protocols)
    credential_state = _credential_state(
        cooldowns, channel_id, credential_id, fault_protocols
    )
    return max(
        model_state.cooled_until if model_state else 0.0,
        credential_state.cooled_until if credential_state else 0.0,
    )


def _configured_bindings(channel: ChannelConfig) -> set[tuple[str, str]]:
    credential_ids = {key.id for key in channel.keys}
    bindings = {
        (model.credential_id, model.model_name)
        for model in channel.models
        if model.enabled and (not channel.keys or model.credential_id in credential_ids)
    }
    if bindings:
        return bindings
    if channel.models:
        return set()
    credentials = credential_ids or {""}
    models = _configured_model_names(channel) or {""}
    return {
        (credential_id, model_name)
        for credential_id in credentials
        for model_name in models
    }

from __future__ import annotations

from ...models.channels import ChannelConfig
from ...models.routing import ChannelCredentialHealth, ChannelHealth, ModelHealth
from .cooldown import CooldownLedger, model_key, remaining_seconds
from .health_scores import HealthScores


def build_channel_health(
    cooldowns: CooldownLedger,
    scores: HealthScores,
    channel: ChannelConfig,
    *,
    now: float,
) -> ChannelHealth:
    """Project the runtime cooldown and score timelines into admin DTOs."""
    configured_models = _configured_model_names(channel)
    model_names = configured_models | {
        model_name
        for channel_id, model_name in cooldowns.model_keys() | scores.model_keys()
        if channel_id == channel.id
    }
    model_health = [
        _build_model_health(cooldowns, scores, channel.id, model_name, now=now)
        for model_name in sorted(model_names)
    ]
    credential_health = [
        _build_credential_health(cooldowns, channel.id, key.id, now=now)
        for key in channel.keys
        if key.enabled
    ]
    if not channel.keys:
        credential_health.append(
            _build_credential_health(cooldowns, channel.id, "", now=now)
        )
    configured_bindings = _configured_bindings(channel)
    target_available_at = [
        _binding_available_at(cooldowns, channel.id, credential_id, model_name)
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
    *,
    now: float,
) -> ModelHealth:
    state = cooldowns.model_state(channel_id, model_name)
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
        score=scores.score(model_key(channel_id, model_name)),
        available=cooled_until <= now,
    )


def _build_credential_health(
    cooldowns: CooldownLedger, channel_id: str, key_id: str, *, now: float
) -> ChannelCredentialHealth:
    state = cooldowns.credential_state(channel_id, key_id)
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
    cooldowns: CooldownLedger, channel_id: str, credential_id: str, model_name: str
) -> float:
    model_state = cooldowns.model_state(channel_id, model_name)
    credential_state = cooldowns.credential_state(channel_id, credential_id)
    return max(
        model_state.cooled_until if model_state else 0.0,
        credential_state.cooled_until if credential_state else 0.0,
    )


def _configured_bindings(channel: ChannelConfig) -> set[tuple[str, str]]:
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
    models = _configured_model_names(channel) or {""}
    return {
        (credential_id, model_name)
        for credential_id in credentials
        for model_name in models
    }


def _configured_model_names(channel: ChannelConfig) -> set[str]:
    return {model.model_name for model in channel.models if model.enabled}

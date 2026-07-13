from __future__ import annotations

from typing import Any

from fastapi import Depends

from ....core.time_zone import resolve_time_zone
from ....models import (
    SettingItem,
    SettingsUpdate,
    normalize_upstream_headers_config_json,
    normalize_upstream_param_override_config_json,
)
from ....persistence.shared import (
    SETTING_CIRCUIT_BREAKER_COOLDOWN,
    SETTING_CIRCUIT_BREAKER_MAX_COOLDOWN,
    SETTING_CIRCUIT_BREAKER_THRESHOLD,
    SETTING_HEALTH_MIN_SAMPLES,
    SETTING_HEALTH_PENALTY_WEIGHT,
    SETTING_HEALTH_WINDOW_SECONDS,
    SETTING_RELAY_LOG_BODY_ENABLED,
    SETTING_RELAY_LOG_KEEP_PERIOD,
    SETTING_SITE_LOGO_URL,
    SETTING_SITE_NAME,
    SETTING_TIME_ZONE,
    SETTING_UPSTREAM_HEADERS_CONFIG,
    SETTING_UPSTREAM_PARAM_OVERRIDE_CONFIG,
)
from ..auth import get_current_admin
from ..app_state import app_state

INTEGER_SETTING_KEYS = {
    SETTING_RELAY_LOG_KEEP_PERIOD,
    SETTING_CIRCUIT_BREAKER_THRESHOLD,
    SETTING_CIRCUIT_BREAKER_COOLDOWN,
    SETTING_CIRCUIT_BREAKER_MAX_COOLDOWN,
    SETTING_HEALTH_WINDOW_SECONDS,
    SETTING_HEALTH_MIN_SAMPLES,
}
FLOAT_SETTING_KEYS = {SETTING_HEALTH_PENALTY_WEIGHT}
BOOLEAN_SETTING_KEYS = {SETTING_RELAY_LOG_BODY_ENABLED}


async def list_settings(_: Any = Depends(get_current_admin)) -> list[SettingItem]:
    """List administrative settings."""
    return await app_state.settings_repo.list_settings()


async def update_settings(
    payload: SettingsUpdate, _: Any = Depends(get_current_admin)
) -> list[SettingItem]:
    """Normalize and persist administrative settings."""
    normalized_items = []
    current_time_zone = None
    next_time_zone = None
    next_time_zone_value = None
    if any(item.key == SETTING_TIME_ZONE for item in payload.items):
        runtime = await app_state.settings_repo.get_runtime_settings()
        current_time_zone = str(runtime["time_zone"])
    for item in payload.items:
        if item.key == SETTING_SITE_NAME:
            normalized_items.append(
                SettingItem(key=item.key, value=item.value.strip() or "Lens")
            )
            continue
        if item.key == SETTING_SITE_LOGO_URL:
            normalized_items.append(SettingItem(key=item.key, value=item.value.strip()))
            continue
        if item.key == SETTING_TIME_ZONE:
            time_zone = resolve_time_zone(item.value)
            next_time_zone = time_zone.key
            next_time_zone_value = time_zone
            normalized_items.append(SettingItem(key=item.key, value=time_zone.key))
            continue
        if item.key == SETTING_UPSTREAM_HEADERS_CONFIG:
            normalized_items.append(
                SettingItem(
                    key=item.key,
                    value=normalize_upstream_headers_config_json(item.value),
                )
            )
            continue
        if item.key == SETTING_UPSTREAM_PARAM_OVERRIDE_CONFIG:
            normalized_items.append(
                SettingItem(
                    key=item.key,
                    value=normalize_upstream_param_override_config_json(item.value),
                )
            )
            continue
        if item.key in INTEGER_SETTING_KEYS:
            value = item.value.strip()
            _parse_integer_setting(item.key, value)
            normalized_items.append(SettingItem(key=item.key, value=value))
            continue
        if item.key in FLOAT_SETTING_KEYS:
            value = item.value.strip()
            _parse_float_setting(item.key, value)
            normalized_items.append(SettingItem(key=item.key, value=value))
            continue
        if item.key in BOOLEAN_SETTING_KEYS:
            normalized_items.append(
                SettingItem(
                    key=item.key,
                    value=(
                        "true"
                        if _parse_boolean_setting(item.key, item.value)
                        else "false"
                    ),
                )
            )
            continue
        normalized_items.append(SettingItem(key=item.key, value=item.value.strip()))
    stored_items = await app_state.settings_repo.upsert_settings(normalized_items)
    if next_time_zone is not None and next_time_zone != current_time_zone:
        await app_state.request_log_store.persist_request_log_stats(force=True)
        if next_time_zone_value is not None:
            await app_state.cronjob_runner.reschedule_cronjobs(next_time_zone_value)
    return stored_items


def _parse_integer_setting(key: str, value: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"Invalid integer setting: {key}") from exc


def _parse_float_setting(key: str, value: str) -> float:
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"Invalid numeric setting: {key}") from exc


def _parse_boolean_setting(key: str, value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean setting: {key}")

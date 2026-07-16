from __future__ import annotations

from collections.abc import Iterable, Mapping
from math import isfinite

from ..core.time_zone import normalize_time_zone
from ..models import (
    SettingItem,
    normalize_upstream_headers_config_json,
    normalize_upstream_param_override_config_json,
)
from .shared import (
    SETTING_AUTH_ACCESS_TOKEN_MINUTES,
    SETTING_CIRCUIT_BREAKER_COOLDOWN,
    SETTING_CIRCUIT_BREAKER_MAX_COOLDOWN,
    SETTING_CIRCUIT_BREAKER_THRESHOLD,
    SETTING_CORS_ALLOW_ORIGINS,
    SETTING_HEALTH_MIN_SAMPLES,
    SETTING_HEALTH_PENALTY_WEIGHT,
    SETTING_HEALTH_WINDOW_SECONDS,
    SETTING_MAX_REQUEST_BODY_BYTES,
    SETTING_MODEL_LIST_COMPAT_MODE_ENABLED,
    SETTING_MODEL_TEST_PROMPTS,
    SETTING_PROXY_URL,
    SETTING_RELAY_LOG_BODY_ENABLED,
    SETTING_RELAY_LOG_KEEP_ENABLED,
    SETTING_RELAY_LOG_KEEP_PERIOD,
    SETTING_REQUEST_TIMEOUT_SECONDS,
    SETTING_SITE_LOGO_URL,
    SETTING_SITE_NAME,
    SETTING_TIME_ZONE,
    SETTING_UPSTREAM_HEADERS_CONFIG,
    SETTING_UPSTREAM_PARAM_OVERRIDE_CONFIG,
)

EDITABLE_SETTING_DEFAULTS: dict[str, str] = {
    SETTING_AUTH_ACCESS_TOKEN_MINUTES: "720",
    SETTING_PROXY_URL: "",
    SETTING_CORS_ALLOW_ORIGINS: "*",
    SETTING_RELAY_LOG_BODY_ENABLED: "false",
    SETTING_RELAY_LOG_KEEP_ENABLED: "true",
    SETTING_RELAY_LOG_KEEP_PERIOD: "7",
    SETTING_CIRCUIT_BREAKER_THRESHOLD: "3",
    SETTING_CIRCUIT_BREAKER_COOLDOWN: "60",
    SETTING_CIRCUIT_BREAKER_MAX_COOLDOWN: "600",
    SETTING_HEALTH_WINDOW_SECONDS: "300",
    SETTING_HEALTH_PENALTY_WEIGHT: "0.5",
    SETTING_HEALTH_MIN_SAMPLES: "10",
    SETTING_MODEL_LIST_COMPAT_MODE_ENABLED: "false",
    SETTING_REQUEST_TIMEOUT_SECONDS: "180",
    SETTING_MAX_REQUEST_BODY_BYTES: "32000000",
    SETTING_MODEL_TEST_PROMPTS: "",
    SETTING_UPSTREAM_HEADERS_CONFIG: "",
    SETTING_UPSTREAM_PARAM_OVERRIDE_CONFIG: "",
    SETTING_SITE_NAME: "Lens",
    SETTING_SITE_LOGO_URL: "",
    SETTING_TIME_ZONE: "Asia/Shanghai",
}
EDITABLE_SETTING_KEYS = tuple(EDITABLE_SETTING_DEFAULTS)

AUTH_ACCESS_TOKEN_MINUTES_MAX = 525_600
RELAY_LOG_KEEP_PERIOD_MAX = 36_500
CIRCUIT_BREAKER_COOLDOWN_SECONDS_MAX = 604_800
REQUEST_TIMEOUT_SECONDS_MAX = 86_400.0

_BOOLEAN_SETTING_KEYS = {
    SETTING_RELAY_LOG_BODY_ENABLED,
    SETTING_RELAY_LOG_KEEP_ENABLED,
    SETTING_MODEL_LIST_COMPAT_MODE_ENABLED,
}
_POSITIVE_INTEGER_SETTING_KEYS = {
    SETTING_AUTH_ACCESS_TOKEN_MINUTES,
    SETTING_RELAY_LOG_KEEP_PERIOD,
    SETTING_CIRCUIT_BREAKER_THRESHOLD,
    SETTING_HEALTH_WINDOW_SECONDS,
    SETTING_HEALTH_MIN_SAMPLES,
}
_NONNEGATIVE_INTEGER_SETTING_KEYS = {
    SETTING_CIRCUIT_BREAKER_COOLDOWN,
    SETTING_CIRCUIT_BREAKER_MAX_COOLDOWN,
    SETTING_MAX_REQUEST_BODY_BYTES,
}
_NONNEGATIVE_FLOAT_SETTING_KEYS = {
    SETTING_HEALTH_PENALTY_WEIGHT,
    SETTING_REQUEST_TIMEOUT_SECONDS,
}
_INTEGER_SETTING_MAXIMUMS = {
    SETTING_AUTH_ACCESS_TOKEN_MINUTES: AUTH_ACCESS_TOKEN_MINUTES_MAX,
    SETTING_RELAY_LOG_KEEP_PERIOD: RELAY_LOG_KEEP_PERIOD_MAX,
    SETTING_CIRCUIT_BREAKER_COOLDOWN: CIRCUIT_BREAKER_COOLDOWN_SECONDS_MAX,
    SETTING_CIRCUIT_BREAKER_MAX_COOLDOWN: CIRCUIT_BREAKER_COOLDOWN_SECONDS_MAX,
}
_FLOAT_SETTING_MAXIMUMS = {
    SETTING_REQUEST_TIMEOUT_SECONDS: REQUEST_TIMEOUT_SECONDS_MAX,
}


def normalize_editable_setting_items(items: Iterable[SettingItem]) -> list[SettingItem]:
    normalized: list[SettingItem] = []
    seen: set[str] = set()
    for item in items:
        if item.key in seen:
            raise ValueError(f"Duplicate setting key: {item.key}")
        seen.add(item.key)
        normalized.append(
            SettingItem(
                key=item.key, value=normalize_editable_setting(item.key, item.value)
            )
        )
    return normalized


def effective_editable_setting_items(items: Iterable[SettingItem]) -> list[SettingItem]:
    stored = {
        item.key: item.value for item in items if item.key in EDITABLE_SETTING_DEFAULTS
    }
    effective: list[SettingItem] = []
    for key, default in EDITABLE_SETTING_DEFAULTS.items():
        value = _normalize_effective_setting(key, stored.get(key, default), default)
        effective.append(SettingItem(key=key, value=value))
    return effective


def normalize_editable_setting(key: str, raw_value: str) -> str:
    if key not in EDITABLE_SETTING_DEFAULTS:
        raise ValueError(f"Unknown setting key: {key}")

    value = raw_value.strip()
    if key in _BOOLEAN_SETTING_KEYS:
        return "true" if _parse_boolean(key, value) else "false"
    if key in _POSITIVE_INTEGER_SETTING_KEYS:
        parsed = _parse_integer(key, value)
        if parsed <= 0:
            raise ValueError(f"Setting must be greater than zero: {key}")
        _validate_maximum(key, parsed, _INTEGER_SETTING_MAXIMUMS)
        return str(parsed)
    if key in _NONNEGATIVE_INTEGER_SETTING_KEYS:
        parsed = _parse_integer(key, value)
        if parsed < 0:
            raise ValueError(f"Setting must not be negative: {key}")
        _validate_maximum(key, parsed, _INTEGER_SETTING_MAXIMUMS)
        return str(parsed)
    if key in _NONNEGATIVE_FLOAT_SETTING_KEYS:
        parsed = _parse_float(key, value)
        if parsed < 0:
            raise ValueError(f"Setting must not be negative: {key}")
        _validate_maximum(key, parsed, _FLOAT_SETTING_MAXIMUMS)
        return str(parsed)
    if key == SETTING_TIME_ZONE:
        return normalize_time_zone(value)
    if key == SETTING_UPSTREAM_HEADERS_CONFIG:
        return normalize_upstream_headers_config_json(value)
    if key == SETTING_UPSTREAM_PARAM_OVERRIDE_CONFIG:
        return normalize_upstream_param_override_config_json(value)
    if key == SETTING_SITE_NAME:
        return value or "Lens"
    if key == SETTING_CORS_ALLOW_ORIGINS:
        return value or "*"
    return value


def _parse_boolean(key: str, value: str) -> bool:
    normalized = value.lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean setting: {key}")


def _parse_integer(key: str, value: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"Invalid integer setting: {key}") from exc


def _parse_float(key: str, value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"Invalid numeric setting: {key}") from exc
    if not isfinite(parsed):
        raise ValueError(f"Invalid numeric setting: {key}")
    return parsed


def _normalize_effective_setting(key: str, raw_value: str, default: str) -> str:
    try:
        return normalize_editable_setting(key, raw_value)
    except ValueError:
        legacy_numeric_value = _normalize_legacy_numeric_setting(key, raw_value)
        if legacy_numeric_value is not None:
            return legacy_numeric_value
        return normalize_editable_setting(key, default)


def _normalize_legacy_numeric_setting(key: str, raw_value: str) -> str | None:
    value = raw_value.strip()
    if key in _POSITIVE_INTEGER_SETTING_KEYS | _NONNEGATIVE_INTEGER_SETTING_KEYS:
        try:
            parsed: int | float = int(value)
        except ValueError:
            return None
        minimum = 1 if key in _POSITIVE_INTEGER_SETTING_KEYS else 0
    elif key in _NONNEGATIVE_FLOAT_SETTING_KEYS:
        try:
            parsed = float(value)
        except ValueError:
            return None
        if not isfinite(parsed):
            return None
        minimum = 0
    else:
        return None

    maximum = _INTEGER_SETTING_MAXIMUMS.get(key)
    if maximum is None:
        maximum = _FLOAT_SETTING_MAXIMUMS.get(key)
    normalized = max(parsed, minimum)
    if maximum is not None:
        normalized = min(normalized, maximum)
    if key in _NONNEGATIVE_FLOAT_SETTING_KEYS:
        return str(float(normalized))
    return str(int(normalized))


def _validate_maximum(
    key: str,
    value: int | float,
    maximums: Mapping[str, int | float],
) -> None:
    maximum = maximums.get(key)
    if maximum is not None and value > maximum:
        raise ValueError(f"Setting must not exceed {maximum:g}: {key}")

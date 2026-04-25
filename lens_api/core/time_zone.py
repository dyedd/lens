from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_APP_TIME_ZONE = "Asia/Shanghai"


def normalize_time_zone(value: str | None) -> str:
    normalized = (value or DEFAULT_APP_TIME_ZONE).strip() or DEFAULT_APP_TIME_ZONE
    try:
        return ZoneInfo(normalized).key
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Invalid IANA time zone: {normalized}") from exc


def resolve_time_zone(value: str | None) -> ZoneInfo:
    return ZoneInfo(normalize_time_zone(value))

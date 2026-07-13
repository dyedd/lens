from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_APP_TIME_ZONE = "Asia/Shanghai"


def normalize_time_zone(value: str | None) -> str:
    """Normalize and validate an IANA time zone name."""
    normalized = value.strip() if value else ""
    if not normalized:
        normalized = DEFAULT_APP_TIME_ZONE
    try:
        return ZoneInfo(normalized).key
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Invalid IANA time zone: {normalized}") from exc


def resolve_time_zone(value: str | None) -> ZoneInfo:
    """Resolve an optional time zone name to a ZoneInfo instance."""
    return ZoneInfo(normalize_time_zone(value))

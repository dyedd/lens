from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_APP_TIME_ZONE = "Asia/Shanghai"


def validate_time_zone_name(value: str | None) -> str:
    """Trim and validate an IANA time zone name."""
    time_zone_name = value.strip() if value else ""
    if not time_zone_name:
        time_zone_name = DEFAULT_APP_TIME_ZONE
    try:
        return ZoneInfo(time_zone_name).key
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Invalid IANA time zone: {time_zone_name}") from exc


def load_time_zone(value: str | None) -> ZoneInfo:
    """Resolve an optional time zone name to a ZoneInfo instance."""
    return ZoneInfo(validate_time_zone_name(value))

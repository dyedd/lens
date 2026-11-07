from __future__ import annotations

from datetime import UTC, datetime

from pydantic import TypeAdapter

from ...models.backups import ConfigBackupRequestLogAttempt
from ..cronjob_store import decode_weekdays
from ..json_columns import load_json_column

_ATTEMPTS = TypeAdapter(list[ConfigBackupRequestLogAttempt])


def parse_backup_datetime(value: str) -> datetime:
    """Parse a backup timestamp into a naive UTC datetime."""
    trimmed_value = value.strip()
    if trimmed_value.endswith("Z"):
        trimmed_value = trimmed_value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(trimmed_value)
    if parsed.tzinfo is None:
        return parsed
    return parsed.astimezone(UTC).replace(tzinfo=None)


def parse_optional_datetime(value: str | None) -> datetime | None:
    """Parse an optional backup timestamp."""
    if value is None or not value.strip():
        return None
    return parse_backup_datetime(value)


def format_optional_datetime(value: datetime | None) -> str | None:
    """Format an optional datetime as a UTC timestamp."""
    if value is None:
        return None
    return value.replace(tzinfo=UTC).isoformat()


def parse_weekdays(raw_value: str | None) -> list[int]:
    """Load canonical/sorted cron job weekdays from stored JSON."""
    return list(decode_weekdays(raw_value))


def parse_attempts(raw_value: str | None) -> list[ConfigBackupRequestLogAttempt]:
    """Parse request log attempts from stored JSON."""
    return load_json_column(raw_value or "[]", _ATTEMPTS, "attempts_json")

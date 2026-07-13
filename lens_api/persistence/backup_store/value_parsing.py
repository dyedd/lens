from __future__ import annotations

import json
from datetime import UTC, datetime

from ...models import RequestLogAttempt
from ..cronjob_store import decode_weekdays


def parse_backup_datetime(value: str) -> datetime:
    """Parse a backup timestamp into a naive UTC datetime."""
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
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


def load_allowed_models(raw_value: str | None) -> list[str]:
    """Load and normalize allowed model names from stored JSON."""
    if not raw_value:
        return []
    payload = json.loads(raw_value)
    if not isinstance(payload, list):
        raise ValueError("Invalid gateway API key allowed models JSON")
    models: list[str] = []
    seen: set[str] = set()
    for item in payload:
        normalized = str(item).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        models.append(normalized)
    return models


def load_weekdays(raw_value: str | None) -> list[int]:
    """Load normalized cron job weekdays from stored JSON."""
    return list(decode_weekdays(raw_value))


def parse_attempts(raw_value: str | None) -> list[RequestLogAttempt]:
    """Parse request log attempts from stored JSON."""
    if not raw_value:
        return []
    payload = json.loads(raw_value)
    if not isinstance(payload, list):
        raise ValueError("Invalid request log attempts JSON")
    attempts: list[RequestLogAttempt] = []
    for item in payload:
        attempts.append(RequestLogAttempt.model_validate(item))
    return attempts

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, time, timedelta
from typing import Sequence
from zoneinfo import ZoneInfo

from .types import (
    MIN_CRONJOB_INTERVAL_HOURS,
    RUN_AT_TIME_PATTERN,
    SCHEDULE_TYPE_DAILY,
    SCHEDULE_TYPE_INTERVAL,
    SCHEDULE_TYPES,
    CronjobSchedule,
)


def normalize_cronjob_schedule(
    *,
    schedule_type: str | None,
    interval_hours: int | None,
    run_at_time: str | None,
    weekdays: Sequence[int] | None,
) -> CronjobSchedule:
    """Normalize and validate a cron job schedule."""
    schedule_type_value = (schedule_type or SCHEDULE_TYPE_INTERVAL).strip()
    if schedule_type_value not in SCHEDULE_TYPES:
        raise ValueError(f"Invalid cron job type: {schedule_type_value}")

    interval_value = max(interval_hours or 0, MIN_CRONJOB_INTERVAL_HOURS)
    run_at_time_value = _normalize_run_at_time(run_at_time)
    weekdays_value = normalize_weekdays(weekdays or ())

    if schedule_type_value == SCHEDULE_TYPE_INTERVAL:
        return CronjobSchedule(
            schedule_type=schedule_type_value,
            interval_hours=interval_value,
            run_at_time=None,
            weekdays=(),
        )
    if run_at_time_value is None:
        raise ValueError("Cron job run time is required")
    if schedule_type_value == SCHEDULE_TYPE_DAILY:
        return CronjobSchedule(
            schedule_type=schedule_type_value,
            interval_hours=interval_value,
            run_at_time=run_at_time_value,
            weekdays=(),
        )
    if not weekdays_value:
        raise ValueError("Weekly cron jobs require at least one weekday")
    return CronjobSchedule(
        schedule_type=schedule_type_value,
        interval_hours=interval_value,
        run_at_time=run_at_time_value,
        weekdays=weekdays_value,
    )


def next_cronjob_run_at(
    schedule: CronjobSchedule,
    *,
    now: datetime,
    time_zone: ZoneInfo,
) -> datetime:
    """Calculate the next UTC run time for a cron job schedule."""
    if schedule.schedule_type == SCHEDULE_TYPE_INTERVAL:
        return now + timedelta(hours=schedule.interval_hours)

    local_now = now.replace(tzinfo=UTC).astimezone(time_zone)
    hour_text, minute_text = schedule.run_at_time.split(":", 1)
    run_time = time(hour=int(hour_text), minute=int(minute_text))
    if schedule.schedule_type == SCHEDULE_TYPE_DAILY:
        candidate = datetime.combine(local_now.date(), run_time, tzinfo=time_zone)
        if candidate <= local_now:
            candidate += timedelta(days=1)
        return candidate.astimezone(UTC).replace(tzinfo=None)

    weekdays = set(schedule.weekdays)
    for offset_days in range(8):
        candidate_date = local_now.date() + timedelta(days=offset_days)
        if candidate_date.isoweekday() not in weekdays:
            continue
        candidate = datetime.combine(candidate_date, run_time, tzinfo=time_zone)
        if candidate > local_now:
            return candidate.astimezone(UTC).replace(tzinfo=None)
    raise ValueError("Unable to resolve next weekly cron job run")


def normalize_weekdays(weekdays: Sequence[int]) -> tuple[int, ...]:
    """Normalize weekday values into a sorted unique tuple."""
    normalized: list[int] = []
    seen: set[int] = set()
    for item in weekdays:
        weekday = int(item)
        if weekday < 1 or weekday > 7:
            raise ValueError("Weekday must be between 1 and 7")
        if weekday in seen:
            continue
        seen.add(weekday)
        normalized.append(weekday)
    return tuple(sorted(normalized))


def encode_weekdays(weekdays: Sequence[int]) -> str:
    """Encode normalized weekdays as compact JSON."""
    return json.dumps(list(normalize_weekdays(weekdays)), separators=(",", ":"))


def decode_weekdays(value: str | None) -> tuple[int, ...]:
    """Decode and normalize weekdays from stored JSON."""
    if not value:
        return ()
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid cron job weekdays") from exc
    if not isinstance(parsed, list):
        raise ValueError("Invalid cron job weekdays")
    return normalize_weekdays(parsed)


def _normalize_run_at_time(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if not RUN_AT_TIME_PATTERN.fullmatch(normalized):
        raise ValueError("Cron job run time must use HH:mm")
    return normalized

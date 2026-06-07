from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

MIN_CRONJOB_INTERVAL_HOURS = 1
SCHEDULE_TYPE_INTERVAL = "interval"
SCHEDULE_TYPE_DAILY = "daily"
SCHEDULE_TYPE_WEEKLY = "weekly"
SCHEDULE_TYPES = {
    SCHEDULE_TYPE_INTERVAL,
    SCHEDULE_TYPE_DAILY,
    SCHEDULE_TYPE_WEEKLY,
}
RUN_AT_TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


@dataclass(frozen=True, slots=True)
class CronjobSpec:
    id: str
    name: str
    description: str
    default_interval_hours: int
    default_enabled: bool = True
    default_schedule_type: str = SCHEDULE_TYPE_INTERVAL
    default_run_at_time: str | None = None
    default_weekdays: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class CronjobSchedule:
    schedule_type: str
    interval_hours: int
    run_at_time: str | None
    weekdays: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class CronjobRecord:
    id: str
    enabled: bool
    schedule_type: str
    interval_hours: int
    run_at_time: str | None
    weekdays: tuple[int, ...]
    status: str
    last_started_at: datetime | None
    last_finished_at: datetime | None
    last_error: str
    next_run_at: datetime | None
    lease_owner: str
    lease_until: datetime | None

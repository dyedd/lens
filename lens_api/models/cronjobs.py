from pydantic import Field, field_validator, model_validator

from .common import StrictBaseModel
from .protocols import CronjobScheduleType, CronjobStatus


def _normalize_weekdays_list(value: list[int]) -> list[int]:
    normalized: list[int] = []
    seen: set[int] = set()
    for item in value:
        weekday = int(item)
        if weekday < 1 or weekday > 7:
            raise ValueError("Weekday must be between 1 and 7")
        if weekday in seen:
            continue
        seen.add(weekday)
        normalized.append(weekday)
    return sorted(normalized)


def _validate_cronjob_schedule(
    schedule_type: CronjobScheduleType | None,
    run_at_time: str | None,
    weekdays: list[int] | None,
) -> None:
    if schedule_type == CronjobScheduleType.DAILY and not run_at_time:
        raise ValueError("Daily cron jobs require run_at_time")
    if schedule_type == CronjobScheduleType.WEEKLY:
        if not run_at_time:
            raise ValueError("Weekly cron jobs require run_at_time")
        if not weekdays:
            raise ValueError("Weekly cron jobs require weekdays")


class CronjobItem(StrictBaseModel):
    id: str
    name: str
    description: str = ""
    enabled: bool
    schedule_type: CronjobScheduleType = CronjobScheduleType.INTERVAL
    interval_hours: int
    run_at_time: str | None = None
    weekdays: list[int] = Field(default_factory=list)
    status: CronjobStatus
    last_started_at: str | None = None
    last_finished_at: str | None = None
    last_error: str | None = None
    next_run_at: str | None = None


class CronjobUpdate(StrictBaseModel):
    enabled: bool | None = None
    schedule_type: CronjobScheduleType | None = None
    interval_hours: int | None = Field(default=None, ge=1)
    run_at_time: str | None = Field(
        default=None, pattern=r"^([01]\d|2[0-3]):([0-5]\d)$"
    )
    weekdays: list[int] | None = None

    @field_validator("weekdays")
    @classmethod
    def normalize_weekdays(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return None
        return _normalize_weekdays_list(value)

    @model_validator(mode="after")
    def validate_schedule(self) -> "CronjobUpdate":
        _validate_cronjob_schedule(self.schedule_type, self.run_at_time, self.weekdays)
        return self


class CronjobRunResult(StrictBaseModel):
    cronjob: CronjobItem

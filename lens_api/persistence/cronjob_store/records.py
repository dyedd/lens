from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from ...models import CronjobItem, CronjobStatus
from ..entities import CronjobEntity
from .scheduling import (
    decode_weekdays,
    encode_weekdays,
    next_cronjob_run_at,
    normalize_cronjob_schedule,
)
from .types import CronjobRecord, CronjobSchedule, CronjobSpec


def _apply_schedule(entity: CronjobEntity, schedule: CronjobSchedule) -> None:
    entity.schedule_type = schedule.schedule_type
    entity.interval_hours = schedule.interval_hours
    entity.run_at_time = schedule.run_at_time
    entity.weekdays_json = encode_weekdays(schedule.weekdays)


def _update_run_state(
    entity: CronjobEntity,
    *,
    next_schedule: CronjobSchedule,
    has_schedule_changed: bool,
    was_enabled: bool,
    now: datetime,
    time_zone: ZoneInfo,
) -> None:
    is_lease_active = (
        bool(entity.lease_owner)
        and entity.lease_until is not None
        and entity.lease_until > now
    )
    if not entity.enabled:
        entity.next_run_at = None
        if not is_lease_active:
            entity.status = CronjobStatus.DISABLED.value
        return
    if not was_enabled or has_schedule_changed or entity.next_run_at is None:
        entity.next_run_at = next_cronjob_run_at(
            next_schedule, now=now, time_zone=time_zone
        )
        if entity.status == CronjobStatus.DISABLED.value:
            entity.status = CronjobStatus.IDLE.value


def _to_record(entity: CronjobEntity) -> CronjobRecord:
    schedule = _entity_schedule(entity)
    return CronjobRecord(
        id=entity.id,
        enabled=bool(entity.enabled),
        schedule_type=schedule.schedule_type,
        interval_hours=schedule.interval_hours,
        run_at_time=schedule.run_at_time,
        weekdays=schedule.weekdays,
        status=entity.status,
        last_started_at=entity.last_started_at,
        last_finished_at=entity.last_finished_at,
        last_error=entity.last_error,
        next_run_at=entity.next_run_at,
        lease_owner=entity.lease_owner,
        lease_until=entity.lease_until,
    )


def _entity_schedule(entity: CronjobEntity) -> CronjobSchedule:
    return normalize_cronjob_schedule(
        schedule_type=entity.schedule_type,
        interval_hours=entity.interval_hours,
        run_at_time=entity.run_at_time,
        weekdays=decode_weekdays(entity.weekdays_json),
    )


def _to_item(spec: CronjobSpec, record: CronjobRecord, *, now: datetime) -> CronjobItem:
    is_lease_active = (
        bool(record.lease_owner)
        and record.lease_until is not None
        and record.lease_until > now
    )
    if is_lease_active:
        status = CronjobStatus.RUNNING
    elif not record.enabled:
        status = CronjobStatus.DISABLED
    elif record.status == CronjobStatus.SUCCEEDED.value:
        status = CronjobStatus.SUCCEEDED
    elif record.status in (CronjobStatus.FAILED.value, CronjobStatus.RUNNING.value):
        status = CronjobStatus.FAILED
    else:
        status = CronjobStatus.IDLE
    next_run_at = None if status == CronjobStatus.DISABLED else record.next_run_at
    return CronjobItem(
        id=spec.id,
        name=spec.name,
        description=spec.description,
        enabled=record.enabled,
        schedule_type=record.schedule_type,
        interval_hours=record.interval_hours,
        run_at_time=record.run_at_time,
        weekdays=list(record.weekdays),
        status=status,
        last_started_at=_format_datetime(record.last_started_at),
        last_finished_at=_format_datetime(record.last_finished_at),
        last_error=record.last_error or None,
        next_run_at=_format_datetime(next_run_at),
    )


def _format_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC).isoformat()
    return value.astimezone(UTC).isoformat()

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Sequence
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..models import CronjobItem, CronjobStatus
from .entities import CronjobEntity


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


@dataclass(frozen=True)
class CronjobSpec:
    id: str
    name: str
    description: str
    default_interval_hours: int
    default_enabled: bool = True
    default_schedule_type: str = SCHEDULE_TYPE_INTERVAL
    default_run_at_time: str | None = None
    default_weekdays: tuple[int, ...] = ()


@dataclass(frozen=True)
class CronjobSchedule:
    schedule_type: str
    interval_hours: int
    run_at_time: str | None
    weekdays: tuple[int, ...]


@dataclass(frozen=True)
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


class CronjobStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def ensure_cronjobs(self, specs: Sequence[CronjobSpec]) -> None:
        now = self._utc_now()
        async with self._session_factory() as session:
            result = await session.execute(select(CronjobEntity.id))
            existing_ids = {str(row[0]) for row in result.all()}
            for spec in specs:
                if spec.id in existing_ids:
                    continue
                schedule = normalize_cronjob_schedule(
                    schedule_type=spec.default_schedule_type,
                    interval_hours=spec.default_interval_hours,
                    run_at_time=spec.default_run_at_time,
                    weekdays=spec.default_weekdays,
                )
                session.add(
                    CronjobEntity(
                        id=spec.id,
                        enabled=1 if spec.default_enabled else 0,
                        schedule_type=schedule.schedule_type,
                        interval_hours=schedule.interval_hours,
                        run_at_time=schedule.run_at_time,
                        weekdays_json=encode_weekdays(schedule.weekdays),
                        status="idle" if spec.default_enabled else "disabled",
                        last_error="",
                        next_run_at=now if spec.default_enabled else None,
                        lease_owner="",
                        created_at=now,
                        updated_at=now,
                    )
                )
            await session.commit()

    async def list_records(self, specs: Sequence[CronjobSpec]) -> dict[str, CronjobRecord]:
        spec_ids = [spec.id for spec in specs]
        if not spec_ids:
            return {}

        async with self._session_factory() as session:
            result = await session.execute(
                select(CronjobEntity).where(CronjobEntity.id.in_(spec_ids))
            )
            return {
                entity.id: self._to_record(entity)
                for entity in result.scalars().all()
            }

    async def get_record(self, task_id: str) -> CronjobRecord | None:
        async with self._session_factory() as session:
            entity = await session.get(CronjobEntity, task_id)
            if entity is None:
                return None
            return self._to_record(entity)

    async def update_cronjob(
        self,
        task_id: str,
        *,
        enabled: bool | None,
        schedule_type: str | None,
        interval_hours: int | None,
        run_at_time: str | None,
        weekdays: Sequence[int] | None,
        time_zone: ZoneInfo,
    ) -> CronjobRecord:
        now = self._utc_now()
        async with self._session_factory() as session:
            entity = await session.get(CronjobEntity, task_id)
            if entity is None:
                raise KeyError(task_id)

            was_enabled = bool(entity.enabled)
            current_schedule = self._entity_schedule(entity)
            next_schedule = normalize_cronjob_schedule(
                schedule_type=schedule_type or current_schedule.schedule_type,
                interval_hours=(
                    interval_hours
                    if interval_hours is not None
                    else current_schedule.interval_hours
                ),
                run_at_time=(
                    run_at_time
                    if run_at_time is not None
                    else current_schedule.run_at_time
                ),
                weekdays=weekdays if weekdays is not None else current_schedule.weekdays,
            )
            schedule_changed = next_schedule != current_schedule
            self._apply_schedule(entity, next_schedule)
            if enabled is not None:
                entity.enabled = 1 if enabled else 0

            if not entity.enabled:
                entity.next_run_at = None
                if not self._is_lease_active(entity, now):
                    entity.status = CronjobStatus.DISABLED.value
            elif not was_enabled or schedule_changed or entity.next_run_at is None:
                entity.next_run_at = next_cronjob_run_at(
                    next_schedule,
                    now=now,
                    time_zone=time_zone,
                )
                if entity.status == CronjobStatus.DISABLED.value:
                    entity.status = CronjobStatus.IDLE.value

            entity.updated_at = now
            await session.commit()
            await session.refresh(entity)
            return self._to_record(entity)

    async def reschedule_cronjobs(
        self,
        task_ids: Sequence[str],
        *,
        time_zone: ZoneInfo,
    ) -> None:
        if not task_ids:
            return
        now = self._utc_now()
        async with self._session_factory() as session:
            result = await session.execute(
                select(CronjobEntity).where(
                    CronjobEntity.id.in_(task_ids),
                    CronjobEntity.enabled == 1,
                    CronjobEntity.schedule_type != SCHEDULE_TYPE_INTERVAL,
                )
            )
            for entity in result.scalars().all():
                entity.next_run_at = next_cronjob_run_at(
                    self._entity_schedule(entity),
                    now=now,
                    time_zone=time_zone,
                )
                entity.updated_at = now
            await session.commit()

    async def list_due_cronjob_ids(self, task_ids: Sequence[str]) -> list[str]:
        if not task_ids:
            return []
        now = self._utc_now()
        async with self._session_factory() as session:
            result = await session.execute(
                select(CronjobEntity.id)
                .where(
                    CronjobEntity.id.in_(task_ids),
                    CronjobEntity.enabled == 1,
                    or_(
                        CronjobEntity.next_run_at.is_(None),
                        CronjobEntity.next_run_at <= now,
                    ),
                    or_(
                        CronjobEntity.lease_until.is_(None),
                        CronjobEntity.lease_until <= now,
                    ),
                )
                .order_by(CronjobEntity.next_run_at.asc())
            )
            return [str(row[0]) for row in result.all()]

    async def acquire_cronjob(
        self,
        task_id: str,
        *,
        owner: str,
        lease_seconds: int,
        require_enabled: bool,
        require_due: bool,
    ) -> bool:
        now = self._utc_now()
        conditions = [
            CronjobEntity.id == task_id,
            or_(
                CronjobEntity.lease_until.is_(None),
                CronjobEntity.lease_until <= now,
            ),
        ]
        if require_enabled:
            conditions.append(CronjobEntity.enabled == 1)
        if require_due:
            conditions.append(
                or_(
                    CronjobEntity.next_run_at.is_(None),
                    CronjobEntity.next_run_at <= now,
                )
            )

        async with self._session_factory() as session:
            result = await session.execute(
                update(CronjobEntity)
                .where(*conditions)
                .values(
                    status=CronjobStatus.RUNNING.value,
                    last_started_at=now,
                    last_error="",
                    lease_owner=owner,
                    lease_until=now + timedelta(seconds=max(lease_seconds, MIN_CRONJOB_INTERVAL_HOURS * 60 * 60)),
                    updated_at=now,
                )
            )
            await session.commit()
            return bool(result.rowcount)

    async def finish_cronjob(
        self,
        task_id: str,
        *,
        owner: str,
        success: bool,
        error: str,
        time_zone: ZoneInfo,
    ) -> CronjobRecord | None:
        now = self._utc_now()
        async with self._session_factory() as session:
            entity = await session.get(CronjobEntity, task_id)
            if entity is None or entity.lease_owner != owner:
                return None

            enabled = bool(entity.enabled)
            entity.status = (
                CronjobStatus.SUCCEEDED.value
                if success
                else CronjobStatus.FAILED.value
            )
            entity.last_finished_at = now
            entity.last_error = error[:2000]
            entity.next_run_at = (
                next_cronjob_run_at(
                    self._entity_schedule(entity),
                    now=now,
                    time_zone=time_zone,
                )
                if enabled
                else None
            )
            entity.lease_owner = ""
            entity.lease_until = None
            entity.updated_at = now
            await session.commit()
            await session.refresh(entity)
            return self._to_record(entity)

    def to_item(self, spec: CronjobSpec, record: CronjobRecord) -> CronjobItem:
        status = self._display_status(record)
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
            last_started_at=self._format_datetime(record.last_started_at),
            last_finished_at=self._format_datetime(record.last_finished_at),
            last_error=record.last_error or None,
            next_run_at=self._format_datetime(next_run_at),
        )

    @classmethod
    def _display_status(cls, record: CronjobRecord) -> CronjobStatus:
        now = cls._utc_now()
        if cls._record_lease_active(record, now):
            return CronjobStatus.RUNNING
        if not record.enabled:
            return CronjobStatus.DISABLED
        if record.status == CronjobStatus.SUCCEEDED.value:
            return CronjobStatus.SUCCEEDED
        if record.status == CronjobStatus.FAILED.value:
            return CronjobStatus.FAILED
        if record.status == CronjobStatus.RUNNING.value:
            return CronjobStatus.FAILED
        return CronjobStatus.IDLE

    @staticmethod
    def _to_record(entity: CronjobEntity) -> CronjobRecord:
        schedule = CronjobStore._entity_schedule(entity)
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
            last_error=entity.last_error or "",
            next_run_at=entity.next_run_at,
            lease_owner=entity.lease_owner or "",
            lease_until=entity.lease_until,
        )

    @staticmethod
    def _entity_schedule(entity: CronjobEntity) -> CronjobSchedule:
        return normalize_cronjob_schedule(
            schedule_type=entity.schedule_type,
            interval_hours=entity.interval_hours,
            run_at_time=entity.run_at_time,
            weekdays=decode_weekdays(entity.weekdays_json),
        )

    @staticmethod
    def _apply_schedule(
        entity: CronjobEntity,
        schedule: CronjobSchedule,
    ) -> None:
        entity.schedule_type = schedule.schedule_type
        entity.interval_hours = schedule.interval_hours
        entity.run_at_time = schedule.run_at_time
        entity.weekdays_json = encode_weekdays(schedule.weekdays)

    @classmethod
    def _is_lease_active(cls, entity: CronjobEntity, now: datetime) -> bool:
        return bool(entity.lease_owner) and entity.lease_until is not None and entity.lease_until > now

    @staticmethod
    def _record_lease_active(record: CronjobRecord, now: datetime) -> bool:
        return bool(record.lease_owner) and record.lease_until is not None and record.lease_until > now

    @staticmethod
    def _format_datetime(value: datetime | None) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC).isoformat()
        return value.astimezone(UTC).isoformat()

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(UTC).replace(tzinfo=None)


def normalize_cronjob_schedule(
    *,
    schedule_type: str | None,
    interval_hours: int | None,
    run_at_time: str | None,
    weekdays: Sequence[int] | None,
) -> CronjobSchedule:
    schedule_type_value = (schedule_type or SCHEDULE_TYPE_INTERVAL).strip()
    if schedule_type_value not in SCHEDULE_TYPES:
        raise ValueError(f"Invalid cron job type: {schedule_type_value}")

    interval_value = max(int(interval_hours or 0), MIN_CRONJOB_INTERVAL_HOURS)
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
    if schedule.schedule_type == SCHEDULE_TYPE_INTERVAL:
        return now + timedelta(hours=max(schedule.interval_hours, MIN_CRONJOB_INTERVAL_HOURS))

    local_now = now.replace(tzinfo=UTC).astimezone(time_zone)
    run_time = _parse_run_at_time(schedule.run_at_time)
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
    return json.dumps(list(normalize_weekdays(weekdays)), separators=(",", ":"))


def decode_weekdays(value: str | None) -> tuple[int, ...]:
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


def _parse_run_at_time(value: str | None) -> time:
    normalized = _normalize_run_at_time(value)
    if normalized is None:
        raise ValueError("Cron job run time is required")
    hour_text, minute_text = normalized.split(":", 1)
    return time(hour=int(hour_text), minute=int(minute_text))

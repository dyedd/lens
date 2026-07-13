from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Sequence
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...models import CronjobItem, CronjobStatus
from ..entities import CronjobEntity
from .records import (
    _apply_schedule,
    _entity_schedule,
    _to_item,
    _to_record,
    _update_run_state,
)
from .scheduling import (
    encode_weekdays,
    next_cronjob_run_at,
    normalize_cronjob_schedule,
)
from .types import (
    MIN_CRONJOB_INTERVAL_HOURS,
    SCHEDULE_TYPE_INTERVAL,
    CronjobRecord,
    CronjobSchedule,
    CronjobSpec,
)


class CronjobStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def ensure_cronjobs(self, specs: Sequence[CronjobSpec]) -> None:
        """Create persisted records for cronjob specifications that are missing."""
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

    async def list_records(
        self, specs: Sequence[CronjobSpec]
    ) -> dict[str, CronjobRecord]:
        """Return persisted cronjob records keyed by specification identifier."""
        spec_ids = [spec.id for spec in specs]
        if not spec_ids:
            return {}

        async with self._session_factory() as session:
            result = await session.execute(
                select(CronjobEntity).where(CronjobEntity.id.in_(spec_ids))
            )
            return {entity.id: _to_record(entity) for entity in result.scalars().all()}

    async def find_record(self, task_id: str) -> CronjobRecord | None:
        """Return a cronjob record by identifier when it exists."""
        async with self._session_factory() as session:
            entity = await session.get(CronjobEntity, task_id)
            if entity is None:
                return None
            return _to_record(entity)

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
        """Update a cronjob schedule and return its persisted record."""
        now = self._utc_now()
        async with self._session_factory() as session:
            entity = await session.get(CronjobEntity, task_id)
            if entity is None:
                raise KeyError(task_id)

            was_enabled = bool(entity.enabled)
            current_schedule = _entity_schedule(entity)
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
                weekdays=(
                    weekdays if weekdays is not None else current_schedule.weekdays
                ),
            )
            _apply_schedule(entity, next_schedule)
            if enabled is not None:
                entity.enabled = 1 if enabled else 0

            _update_run_state(
                entity,
                next_schedule=next_schedule,
                has_schedule_changed=next_schedule != current_schedule,
                was_enabled=was_enabled,
                now=now,
                time_zone=time_zone,
            )
            entity.updated_at = now
            await session.commit()
            await session.refresh(entity)
            return _to_record(entity)

    async def reschedule_cronjobs(
        self,
        task_ids: Sequence[str],
        *,
        time_zone: ZoneInfo,
    ) -> None:
        """Recalculate next run times for enabled calendar cronjobs."""
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
                    _entity_schedule(entity),
                    now=now,
                    time_zone=time_zone,
                )
                entity.updated_at = now
            await session.commit()

    async def list_due_cronjob_ids(self, task_ids: Sequence[str]) -> list[str]:
        """Return identifiers for enabled, unleased cronjobs that are due."""
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
        """Acquire a cronjob lease when the requested conditions are satisfied."""
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
                    lease_until=now
                    + timedelta(
                        seconds=max(lease_seconds, MIN_CRONJOB_INTERVAL_HOURS * 60 * 60)
                    ),
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
        """Finish an owned cronjob lease and schedule its next run."""
        now = self._utc_now()
        async with self._session_factory() as session:
            entity = await session.get(CronjobEntity, task_id)
            if entity is None or entity.lease_owner != owner:
                return None

            enabled = bool(entity.enabled)
            entity.status = (
                CronjobStatus.SUCCEEDED.value if success else CronjobStatus.FAILED.value
            )
            entity.last_finished_at = now
            entity.last_error = error[:2000]
            entity.next_run_at = (
                next_cronjob_run_at(
                    _entity_schedule(entity),
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
            return _to_record(entity)

    def to_item(self, spec: CronjobSpec, record: CronjobRecord) -> CronjobItem:
        """Build the API cronjob representation from a specification and record."""
        return _to_item(spec, record, now=self._utc_now())

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(UTC).replace(tzinfo=None)

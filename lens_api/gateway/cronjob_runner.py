from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable, Sequence
from zoneinfo import ZoneInfo

from sqlalchemy.exc import OperationalError

from ..models import CronjobItem
from ..persistence.cronjob_store import CronjobSpec, CronjobStore


TaskHandler = Callable[[], Awaitable[None]]
TimeZoneProvider = Callable[[], Awaitable[ZoneInfo]]


class CronjobAlreadyRunningError(RuntimeError):
    pass


class CronjobRunner:
    def __init__(
        self,
        *,
        store: CronjobStore,
        specs: Sequence[CronjobSpec],
        handlers: dict[str, TaskHandler],
        time_zone_provider: TimeZoneProvider,
        logger: logging.Logger,
        poll_seconds: int = 30,
    ) -> None:
        self._store = store
        self._specs = list(specs)
        self._specs_by_id = {spec.id: spec for spec in specs}
        self._handlers = handlers
        self._time_zone_provider = time_zone_provider
        self._logger = logger
        self._poll_seconds = max(poll_seconds, 5)
        self._owner = uuid.uuid4().hex
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        await self._store.ensure_cronjobs(self._specs)
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def list_cronjobs(self) -> list[CronjobItem]:
        await self._store.ensure_cronjobs(self._specs)
        records = await self._store.list_records(self._specs)
        return [
            self._store.to_item(spec, records[spec.id])
            for spec in self._specs
            if spec.id in records
        ]

    async def update_cronjob(
        self,
        task_id: str,
        *,
        enabled: bool | None,
        schedule_type: str | None,
        interval_hours: int | None,
        run_at_time: str | None,
        weekdays: Sequence[int] | None,
    ) -> CronjobItem:
        spec = self._specs_by_id.get(task_id)
        if spec is None:
            raise KeyError(task_id)
        record = await self._store.update_cronjob(
            task_id,
            enabled=enabled,
            schedule_type=schedule_type,
            interval_hours=interval_hours,
            run_at_time=run_at_time,
            weekdays=weekdays,
            time_zone=await self._time_zone_provider(),
        )
        return self._store.to_item(spec, record)

    async def run_cronjob_now(self, task_id: str) -> CronjobItem:
        return await self._run_cronjob(task_id, manual=True)

    async def reschedule_cronjobs(self, time_zone: ZoneInfo) -> None:
        await self._store.reschedule_cronjobs(
            [spec.id for spec in self._specs],
            time_zone=time_zone,
        )

    async def _loop(self) -> None:
        while True:
            try:
                due_task_ids = await self._store.list_due_cronjob_ids(
                    [spec.id for spec in self._specs]
                )
                for task_id in due_task_ids:
                    try:
                        await self._run_cronjob(task_id, manual=False)
                    except CronjobAlreadyRunningError:
                        continue
                    except Exception:
                        self._logger.exception("Cron job failed: %s", task_id)
            except OperationalError as exc:
                self._logger.warning("Cron job polling skipped: %s", exc)
            except Exception:
                self._logger.exception("Cron job polling failed")
            await asyncio.sleep(self._poll_seconds)

    async def _run_cronjob(self, task_id: str, *, manual: bool) -> CronjobItem:
        spec = self._specs_by_id.get(task_id)
        if spec is None:
            raise KeyError(task_id)
        handler = self._handlers.get(task_id)
        if handler is None:
            raise KeyError(task_id)

        record = await self._store.get_record(task_id)
        if record is None:
            await self._store.ensure_cronjobs(self._specs)
            record = await self._store.get_record(task_id)
        if record is None:
            raise KeyError(task_id)

        acquired = await self._store.acquire_cronjob(
            task_id,
            owner=self._owner,
            lease_seconds=max(record.interval_hours * 60 * 60, 600),
            require_enabled=not manual,
            require_due=not manual,
        )
        if not acquired:
            raise CronjobAlreadyRunningError(task_id)

        error = ""
        success = True
        try:
            await handler()
        except asyncio.CancelledError:
            success = False
            error = "cancelled"
            raise
        except Exception as exc:
            success = False
            error = str(exc) or exc.__class__.__name__
            raise
        finally:
            finished_record = await self._store.finish_cronjob(
                task_id,
                owner=self._owner,
                success=success,
                error=error,
                time_zone=await self._time_zone_provider(),
            )

        if finished_record is None:
            record = await self._store.get_record(task_id)
            if record is None:
                raise KeyError(task_id)
            return self._store.to_item(spec, record)
        return self._store.to_item(spec, finished_record)

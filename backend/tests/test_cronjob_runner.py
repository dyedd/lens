from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest
from conftest import run_async
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.dml import Update

from app.gateway.cronjob_runner import CronjobRunner
from app.gateway.service.app_state import AppState
from app.models.protocols import CronjobStatus
from app.persistence.cronjob_store import CronjobRecord, CronjobSpec, CronjobStore
from app.persistence.entities import CronjobEntity


def test_cronjob_finalization_preserves_handler_cancellation() -> None:
    record = CronjobRecord(
        id="task",
        enabled=True,
        schedule_type="interval",
        interval_hours=1,
        run_at_time=None,
        weekdays=(),
        status="running",
        last_started_at=None,
        last_finished_at=None,
        last_error="",
        next_run_at=None,
        lease_owner="owner",
        lease_until=None,
    )
    store = SimpleNamespace(
        find_record=AsyncMock(return_value=record),
        acquire_cronjob=AsyncMock(return_value=True),
        finish_cronjob=AsyncMock(),
    )

    async def cancel_handler() -> None:
        raise asyncio.CancelledError("handler cancellation")

    async def cancel_time_zone_lookup() -> ZoneInfo:
        raise asyncio.CancelledError("time zone lookup cancellation")

    runner = CronjobRunner(
        store=cast(CronjobStore, store),
        specs=[
            CronjobSpec(
                id="task", name="Task", description="", default_interval_hours=1
            )
        ],
        handlers={"task": cancel_handler},
        time_zone_provider=cancel_time_zone_lookup,
        logger=logging.getLogger(__name__),
    )

    with pytest.raises(asyncio.CancelledError, match="handler cancellation"):
        run_async(runner.run_cronjob_now("task"))


def test_cronjob_completion_preserves_the_new_run_after_lease_expiry(
    app_state: AppState, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = app_state.cronjob_store
    specification = CronjobSpec(
        id="task", name="Task", description="", default_interval_hours=1
    )
    now = datetime(2026, 1, 1)
    monkeypatch.setattr(store, "_utc_now", lambda: now)

    async def exercise() -> None:
        nonlocal now
        first_started = asyncio.Event()
        second_started = asyncio.Event()
        finish_first = asyncio.Event()
        finish_second = asyncio.Event()

        async def handler() -> None:
            if first_started.is_set():
                second_started.set()
                await finish_second.wait()
            else:
                first_started.set()
                await finish_first.wait()

        async def time_zone() -> ZoneInfo:
            return ZoneInfo("UTC")

        runner = CronjobRunner(
            store=store,
            specs=[specification],
            handlers={specification.id: handler},
            time_zone_provider=time_zone,
            logger=logging.getLogger(__name__),
        )
        await store.ensure_cronjobs([specification])
        async with asyncio.timeout(10), asyncio.TaskGroup() as tasks:
            first = tasks.create_task(runner.run_cronjob_now(specification.id))
            await first_started.wait()
            now += timedelta(hours=1, seconds=1)
            second = tasks.create_task(runner.run_cronjob_now(specification.id))
            await second_started.wait()
            finish_first.set()
            await first

            record = await store.find_record(specification.id)
            assert record is not None
            assert record.status == CronjobStatus.RUNNING
            assert record.lease_until == now + timedelta(hours=1)
            assert record.last_finished_at is None

            finish_second.set()
            assert (await second).status == CronjobStatus.SUCCEEDED

    run_async(exercise())


def test_cronjob_store_does_not_finish_a_lease_reacquired_during_finalization(
    app_state: AppState, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = app_state.cronjob_store
    specification = CronjobSpec(
        id="task", name="Task", description="", default_interval_hours=1
    )
    now = datetime(2026, 1, 1)
    monkeypatch.setattr(store, "_utc_now", lambda: now)

    async def exercise() -> None:
        nonlocal now
        await store.ensure_cronjobs([specification])
        assert await store.acquire_cronjob(
            specification.id,
            owner="first-run",
            lease_seconds=3600,
            require_enabled=False,
            require_due=False,
        )
        now += timedelta(hours=1, seconds=1)

        original_execute = AsyncSession.execute
        lease_reacquired = False

        async def execute_with_lease_handoff(
            session: AsyncSession,
            statement: Any,
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            nonlocal lease_reacquired
            if not lease_reacquired and isinstance(statement, Update):
                lease_reacquired = True
                await original_execute(
                    session,
                    update(CronjobEntity)
                    .where(
                        CronjobEntity.id == specification.id,
                        CronjobEntity.lease_owner == "first-run",
                    )
                    .values(
                        lease_owner="second-run",
                        lease_until=now + timedelta(hours=1),
                    ),
                )
                await session.commit()
            return await original_execute(session, statement, *args, **kwargs)

        monkeypatch.setattr(AsyncSession, "execute", execute_with_lease_handoff)
        finished_record = await store.finish_cronjob(
            specification.id,
            owner="first-run",
            success=True,
            error="",
            time_zone=ZoneInfo("UTC"),
        )

        assert lease_reacquired
        assert finished_record is None
        current_record = await store.find_record(specification.id)
        assert current_record is not None
        assert current_record.status == CronjobStatus.RUNNING
        assert current_record.lease_owner == "second-run"
        assert current_record.lease_until == now + timedelta(hours=1)
        assert current_record.last_finished_at is None

    run_async(exercise())

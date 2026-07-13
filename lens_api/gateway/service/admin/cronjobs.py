from __future__ import annotations

from typing import Any

from fastapi import Depends

from ....models import CronjobItem, CronjobRunResult, CronjobUpdate
from ..auth import get_current_admin
from ..app_state import app_state


async def list_cronjobs(
    _: Any = Depends(get_current_admin),
) -> list[CronjobItem]:
    """List registered cron jobs and their schedules."""
    return await app_state.cronjob_runner.list_cronjobs()


async def update_cronjob(
    task_id: str,
    payload: CronjobUpdate,
    _: Any = Depends(get_current_admin),
) -> CronjobItem:
    """Update a cron job schedule."""
    return await app_state.cronjob_runner.update_cronjob(
        task_id,
        enabled=payload.enabled,
        schedule_type=(
            payload.schedule_type.value if payload.schedule_type is not None else None
        ),
        interval_hours=payload.interval_hours,
        run_at_time=payload.run_at_time,
        weekdays=payload.weekdays,
    )


async def run_cronjob(
    task_id: str,
    _: Any = Depends(get_current_admin),
) -> CronjobRunResult:
    """Run a cron job immediately."""
    task = await app_state.cronjob_runner.run_cronjob_now(task_id)
    return CronjobRunResult(cronjob=task)

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.channels import ChannelModelSyncResponse
from app.persistence.entities import ModelSyncRunEntity

# Older runs are pruned on write; the record is for review, not an audit log.
MAX_MODEL_SYNC_RUNS = 100


def _to_naive_utc(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(tzinfo=None)


class ModelSyncRunRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_run(
        self, run: ChannelModelSyncResponse
    ) -> ChannelModelSyncResponse:
        """Save a finished sync run and prune the oldest beyond the limit."""
        if run.started_at is None or run.finished_at is None:
            raise ValueError("Model sync run needs start and finish times")
        saved = run.model_copy(update={"id": str(uuid.uuid4())})
        async with self._session_factory() as session:
            session.add(
                ModelSyncRunEntity(
                    id=saved.id,
                    started_at=_to_naive_utc(run.started_at),
                    finished_at=_to_naive_utc(run.finished_at),
                    report_json=saved.model_dump_json(),
                )
            )
            await session.flush()
            stale_ids = (
                (
                    await session.execute(
                        select(ModelSyncRunEntity.id)
                        .order_by(ModelSyncRunEntity.started_at.desc())
                        .offset(MAX_MODEL_SYNC_RUNS)
                    )
                )
                .scalars()
                .all()
            )
            if stale_ids:
                await session.execute(
                    delete(ModelSyncRunEntity).where(
                        ModelSyncRunEntity.id.in_(stale_ids)
                    )
                )
            await session.commit()
        return saved

    async def list_runs(self, *, limit: int) -> list[ChannelModelSyncResponse]:
        """Return the latest sync runs, newest first."""
        async with self._session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(ModelSyncRunEntity.report_json)
                        .order_by(ModelSyncRunEntity.started_at.desc())
                        .limit(limit)
                    )
                )
                .scalars()
                .all()
            )
        return [ChannelModelSyncResponse.model_validate_json(row) for row in rows]

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..shared import (
    REQUEST_LOG_RUNNING_STATUSES,
    RequestLogEntity,
    RequestLogLifecycleStatus,
    UTC,
    datetime,
    delete,
    select,
)


class _RequestLogMaintenanceMixin:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def update_request_log_runtime(
        self,
        log_id: int,
        *,
        first_token_latency_ms: int | None = None,
        latency_ms: int | None = None,
    ) -> None:
        """Update runtime latency fields for an existing request log."""
        async with self._session_factory() as session:
            entity = await session.get(RequestLogEntity, log_id)
            if entity is None:
                return
            if first_token_latency_ms is not None:
                entity.first_token_latency_ms = max(first_token_latency_ms, 0)
            if latency_ms is not None:
                entity.latency_ms = max(latency_ms, 0)
            await session.commit()

    async def clear_request_logs(self) -> None:
        """Archive statistics and delete all request logs."""
        await self.persist_request_log_stats(force=True)
        async with self._session_factory() as session:
            await session.execute(delete(RequestLogEntity))
            await session.commit()

    async def prune_request_logs(self) -> None:
        """Archive statistics and delete request logs beyond retention."""
        runtime = await self._settings_repo.get_runtime_settings()
        if not runtime["relay_log_keep_enabled"]:
            return
        await self.persist_request_log_stats(force=True)
        keep_days = int(runtime["relay_log_keep_period"])
        cutoff = self._request_log_prune_cutoff(
            keep_days=keep_days,
            time_zone=self._runtime_time_zone(runtime),
        )
        async with self._session_factory() as session:
            await session.execute(
                delete(RequestLogEntity).where(RequestLogEntity.created_at < cutoff)
            )
            await session.commit()

    async def fail_running_request_logs(
        self, *, interrupted_latency_cap_ms: int | None = None
    ) -> None:
        """Mark request logs left running by an interruption as failed."""
        now = datetime.now(UTC).replace(tzinfo=None)
        latency_cap_ms = (
            max(interrupted_latency_cap_ms, 0)
            if interrupted_latency_cap_ms is not None
            else None
        )
        async with self._session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(RequestLogEntity).where(
                            RequestLogEntity.lifecycle_status.in_(
                                REQUEST_LOG_RUNNING_STATUSES
                            )
                        )
                    )
                )
                .scalars()
                .all()
            )
            for entity in rows:
                created_at = entity.created_at
                if created_at.tzinfo is not None:
                    created_at = created_at.astimezone(UTC).replace(tzinfo=None)
                elapsed_ms = max(int((now - created_at).total_seconds() * 1000), 0)
                if latency_cap_ms is not None:
                    elapsed_ms = min(elapsed_ms, latency_cap_ms)
                entity.lifecycle_status = RequestLogLifecycleStatus.FAILED.value
                entity.success = 0
                entity.status_code = None
                entity.latency_ms = max(entity.latency_ms, elapsed_ms)
                if not (entity.error_message or "").strip():
                    entity.error_message = (
                        "Request interrupted while the service was not running"
                    )
                entity.stats_archived = 0
            await session.commit()

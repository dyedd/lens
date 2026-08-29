from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.protocols import RequestLogLifecycleStatus
from app.persistence.entities import RequestLogEntity
from app.persistence.request_log_constants import REQUEST_LOG_RUNNING_STATUSES

from .ports import RuntimeTimeZone, SettingsPort, StatisticsPort


class RequestLogMaintenance:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings_repo: SettingsPort,
        statistics: StatisticsPort,
        runtime_time_zone: RuntimeTimeZone,
    ) -> None:
        self.session_factory = session_factory
        self.settings_repo = settings_repo
        self.statistics = statistics
        self.runtime_time_zone = runtime_time_zone

    async def clear_request_logs(self) -> None:
        """Archive statistics and delete all request logs."""
        await self.statistics.persist_request_log_stats(force=True)
        async with self.session_factory() as session:
            await session.execute(delete(RequestLogEntity))
            await session.commit()

    async def prune_request_logs(self) -> None:
        """Archive statistics and delete request logs beyond retention."""
        runtime = await self.settings_repo.get_runtime_settings()
        if not runtime["relay_log_keep_enabled"]:
            return
        await self.statistics.persist_request_log_stats(force=True)
        keep_days = int(runtime["relay_log_keep_period"])
        cutoff = self.statistics.request_log_prune_cutoff(
            keep_days=keep_days, time_zone=self.runtime_time_zone(runtime)
        )
        async with self.session_factory() as session:
            await session.execute(
                delete(RequestLogEntity).where(RequestLogEntity.created_at < cutoff)
            )
            await session.commit()

    async def fail_running_request_logs(self) -> None:
        """Mark request logs left running by an interruption as failed."""
        async with self.session_factory() as session:
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
                entity.lifecycle_status = RequestLogLifecycleStatus.FAILED.value
                entity.success = 0
                entity.status_code = None
                if not (entity.error_message or "").strip():
                    entity.error_message = (
                        "Request interrupted while the service was not running"
                    )
                entity.stats_archived = 0
            await session.commit()

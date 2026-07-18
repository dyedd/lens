from __future__ import annotations

from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lens_api.persistence.entities import RequestLogEntity
from lens_api.persistence.stats_entities import (
    ImportedStatsDailyEntity,
    ImportedStatsTotalEntity,
    OverviewModelDailyStatsEntity,
    RequestLogDailyStatsEntity,
)


def validate_supported_groups(payload: dict) -> None:
    """Reject Octopus group settings that Lens cannot preserve."""
    for group in payload.get("groups", []):
        group_name = str(group.get("name") or group.get("id") or "<unknown>")
        if int(group.get("mode") or 0) == 2:
            raise ValueError(
                f"Group '{group_name}' uses weighted routing, which Lens does not support"
            )
        if str(group.get("match_regex") or "").strip():
            raise ValueError(
                f"Group '{group_name}' has match_regex, which has no Lens equivalent"
            )


async def replace_imported_stats(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    total: dict | list[dict] | None,
    daily: list[dict],
) -> None:
    """Replace imported Octopus totals and daily statistics."""
    async with session_factory() as session:
        await session.execute(delete(ImportedStatsDailyEntity))
        await session.execute(delete(ImportedStatsTotalEntity))
        await session.execute(delete(RequestLogDailyStatsEntity))
        await session.execute(delete(OverviewModelDailyStatsEntity))
        await session.execute(update(RequestLogEntity).values(stats_archived=0))

        if isinstance(total, list):
            total_item = total[0] if total else None
        else:
            total_item = total
        if total_item is not None:
            session.add(
                ImportedStatsTotalEntity(
                    id=1,
                    input_token=int(total_item.get("input_token") or 0),
                    output_token=int(total_item.get("output_token") or 0),
                    input_cost=float(total_item.get("input_cost") or 0.0),
                    output_cost=float(total_item.get("output_cost") or 0.0),
                    wait_time=int(total_item.get("wait_time") or 0),
                    request_success=int(total_item.get("request_success") or 0),
                    request_failed=int(total_item.get("request_failed") or 0),
                )
            )

        for item in daily:
            date_value = str(item.get("date") or "")
            if len(date_value) != 8:
                continue
            session.add(
                ImportedStatsDailyEntity(
                    date=date_value,
                    input_token=int(item.get("input_token") or 0),
                    output_token=int(item.get("output_token") or 0),
                    input_cost=float(item.get("input_cost") or 0.0),
                    output_cost=float(item.get("output_cost") or 0.0),
                    wait_time=int(item.get("wait_time") or 0),
                    request_success=int(item.get("request_success") or 0),
                    request_failed=int(item.get("request_failed") or 0),
                )
            )

        await session.commit()

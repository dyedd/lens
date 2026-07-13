from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..shared import (
    CHANNEL_HEALTH_BUCKET_COUNT,
    CHANNEL_HEALTH_BUCKET_SECONDS,
    REQUEST_LOG_TERMINAL_STATUSES,
    RequestLogEntity,
    SiteChannelHealthBucket,
    SiteChannelRuntimeSummary,
    SiteEntity,
    SiteProtocolConfigEntity,
    SiteRuntimeSummary,
    UTC,
    _parse_supported_protocols_json,
    _runtime_channel_id,
    datetime,
    func,
    literal,
    select,
    timedelta,
)


class _RequestLogSiteRuntimeReadMixin:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def list_site_runtime_summaries(self) -> list[SiteRuntimeSummary]:
        """Return recent request and health summaries for configured sites."""
        async with self._session_factory() as session:
            site_rows = (
                (
                    await session.execute(
                        select(SiteEntity).order_by(SiteEntity.name.asc())
                    )
                )
                .scalars()
                .all()
            )
            if not site_rows:
                return []

            channel_rows = await session.execute(
                select(
                    SiteProtocolConfigEntity.site_id.label("site_id"),
                    SiteProtocolConfigEntity.id.label("protocol_config_id"),
                    SiteProtocolConfigEntity.protocols_json.label("protocols_json"),
                ).order_by(
                    SiteProtocolConfigEntity.site_id.asc(),
                    SiteProtocolConfigEntity.id.asc(),
                )
            )
            channel_ids_by_site: dict[str, list[str]] = {
                site.id: [] for site in site_rows
            }
            for row in channel_rows.all():
                site_id = str(row.site_id)
                protocol_config_id = str(row.protocol_config_id)
                for protocol in _parse_supported_protocols_json(row.protocols_json):
                    channel_ids_by_site.setdefault(site_id, []).append(
                        _runtime_channel_id(protocol_config_id, protocol)
                    )

            recent_request_logs = (
                select(RequestLogEntity.channel_id.label("channel_id"))
                .where(RequestLogEntity.channel_id.is_not(None))
                .where(
                    RequestLogEntity.lifecycle_status.in_(REQUEST_LOG_TERMINAL_STATUSES)
                )
                .order_by(
                    RequestLogEntity.created_at.desc(), RequestLogEntity.id.desc()
                )
                .limit(100)
                .subquery()
            )
            recent_count_rows = await session.execute(
                select(
                    SiteProtocolConfigEntity.site_id.label("site_id"),
                    func.count().label("recent_request_count"),
                )
                .select_from(recent_request_logs)
                .join(
                    SiteProtocolConfigEntity,
                    recent_request_logs.c.channel_id.like(
                        SiteProtocolConfigEntity.id + literal("_%")
                    ),
                )
                .group_by(SiteProtocolConfigEntity.site_id)
            )
            recent_request_count_by_site = {
                str(row.site_id): int(row.recent_request_count)
                for row in recent_count_rows.all()
            }

            ranked_logs = (
                select(
                    SiteProtocolConfigEntity.site_id.label("site_id"),
                    RequestLogEntity.channel_id.label("channel_id"),
                    RequestLogEntity.channel_name.label("channel_name"),
                    RequestLogEntity.status_code.label("status_code"),
                    RequestLogEntity.success.label("success"),
                    RequestLogEntity.error_message.label("error_message"),
                    RequestLogEntity.created_at.label("created_at"),
                    func.row_number()
                    .over(
                        partition_by=SiteProtocolConfigEntity.site_id,
                        order_by=(
                            RequestLogEntity.created_at.desc(),
                            RequestLogEntity.id.desc(),
                        ),
                    )
                    .label("row_number"),
                )
                .join(
                    SiteProtocolConfigEntity,
                    RequestLogEntity.channel_id.like(
                        SiteProtocolConfigEntity.id + literal("_%")
                    ),
                )
                .where(
                    RequestLogEntity.lifecycle_status.in_(REQUEST_LOG_TERMINAL_STATUSES)
                )
                .subquery()
            )

            latest_rows = await session.execute(
                select(
                    ranked_logs.c.site_id,
                    ranked_logs.c.channel_id,
                    ranked_logs.c.channel_name,
                    ranked_logs.c.status_code,
                    ranked_logs.c.success,
                    ranked_logs.c.error_message,
                    ranked_logs.c.created_at,
                ).where(ranked_logs.c.row_number == 1)
            )
            latest_by_site = {str(row.site_id): row for row in latest_rows.all()}

            bucket_anchor = datetime.now(UTC).replace(second=0, microsecond=0)
            bucket_anchor -= timedelta(minutes=bucket_anchor.minute % 5)
            bucket_start = bucket_anchor - timedelta(
                seconds=CHANNEL_HEALTH_BUCKET_SECONDS
                * (CHANNEL_HEALTH_BUCKET_COUNT - 1)
            )
            bucket_end = bucket_anchor + timedelta(
                seconds=CHANNEL_HEALTH_BUCKET_SECONDS
            )
            bucket_ranges = [
                (
                    bucket_start
                    + timedelta(seconds=CHANNEL_HEALTH_BUCKET_SECONDS * index),
                    bucket_start
                    + timedelta(seconds=CHANNEL_HEALTH_BUCKET_SECONDS * (index + 1)),
                )
                for index in range(CHANNEL_HEALTH_BUCKET_COUNT)
            ]
            bucket_counts_by_channel = {
                channel_id: [
                    {"success_count": 0, "total_count": 0}
                    for _ in range(CHANNEL_HEALTH_BUCKET_COUNT)
                ]
                for channel_ids in channel_ids_by_site.values()
                for channel_id in channel_ids
            }
            bucket_rows = await session.execute(
                select(
                    RequestLogEntity.channel_id.label("channel_id"),
                    RequestLogEntity.success.label("success"),
                    RequestLogEntity.created_at.label("created_at"),
                )
                .where(
                    RequestLogEntity.channel_id.is_not(None),
                    RequestLogEntity.lifecycle_status.in_(
                        REQUEST_LOG_TERMINAL_STATUSES
                    ),
                    RequestLogEntity.created_at >= bucket_start.replace(tzinfo=None),
                    RequestLogEntity.created_at < bucket_end.replace(tzinfo=None),
                )
                .order_by(RequestLogEntity.created_at.asc(), RequestLogEntity.id.asc())
            )
            for row in bucket_rows.all():
                if row.channel_id is None or row.created_at is None:
                    continue

                channel_id = str(row.channel_id)
                counts = bucket_counts_by_channel.get(channel_id)
                if counts is None:
                    continue

                created_at = row.created_at
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=UTC)
                else:
                    created_at = created_at.astimezone(UTC)

                bucket_index = int(
                    (created_at - bucket_start).total_seconds()
                    // CHANNEL_HEALTH_BUCKET_SECONDS
                )
                if bucket_index < 0 or bucket_index >= CHANNEL_HEALTH_BUCKET_COUNT:
                    continue

                counts[bucket_index]["total_count"] += 1
                if row.success:
                    counts[bucket_index]["success_count"] += 1

            items: list[SiteRuntimeSummary] = []
            for site in site_rows:
                latest = latest_by_site.get(site.id)
                channel_summaries: list[SiteChannelRuntimeSummary] = []
                for channel_id in channel_ids_by_site.get(site.id, []):
                    bucket_counts = bucket_counts_by_channel.get(channel_id) or [
                        {"success_count": 0, "total_count": 0}
                        for _ in range(CHANNEL_HEALTH_BUCKET_COUNT)
                    ]
                    channel_summaries.append(
                        SiteChannelRuntimeSummary(
                            channel_id=channel_id,
                            health_buckets=[
                                SiteChannelHealthBucket(
                                    started_at=start.isoformat(),
                                    ended_at=end.isoformat(),
                                    success_count=bucket_counts[index]["success_count"],
                                    total_count=bucket_counts[index]["total_count"],
                                )
                                for index, (start, end) in enumerate(bucket_ranges)
                            ],
                        )
                    )
                items.append(
                    SiteRuntimeSummary(
                        site_id=site.id,
                        site_name=site.name,
                        recent_request_count=recent_request_count_by_site.get(
                            site.id, 0
                        ),
                        latest_request_at=(
                            latest.created_at.replace(tzinfo=UTC).isoformat()
                            if latest is not None and latest.created_at is not None
                            else None
                        ),
                        latest_success=(
                            bool(latest.success)
                            if latest is not None and latest.success is not None
                            else None
                        ),
                        latest_status_code=(
                            int(latest.status_code)
                            if latest is not None and latest.status_code is not None
                            else None
                        ),
                        latest_error_message=(
                            str(latest.error_message)
                            if latest is not None and latest.error_message is not None
                            else None
                        ),
                        latest_channel_id=(
                            str(latest.channel_id)
                            if latest is not None and latest.channel_id is not None
                            else None
                        ),
                        latest_channel_name=(
                            str(latest.channel_name)
                            if latest is not None and latest.channel_name is not None
                            else None
                        ),
                        channel_summaries=channel_summaries,
                    )
                )
            return items

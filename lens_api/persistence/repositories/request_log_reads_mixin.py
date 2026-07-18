from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, literal, select
from ..shared import (
    CHANNEL_HEALTH_BUCKET_COUNT,
    CHANNEL_HEALTH_BUCKET_SECONDS,
    REQUEST_LOG_TERMINAL_STATUSES,
    ProtocolKind,
    RequestLogDetail,
    RequestLogEntity,
    RequestLogFilterOption,
    RequestLogPage,
    RequestLogSortMode,
    RequestLogStatusFilter,
    SiteChannelHealthBucket,
    SiteChannelRuntimeSummary,
    SiteEntity,
    SiteProtocolConfigEntity,
    SiteRuntimeSummary,
    _parse_supported_protocols_json,
    _runtime_channel_id,
)


class RequestLogReadMixin:
    async def list_request_log_page(
        self,
        limit: int = 100,
        days: int = 0,
        offset: int = 0,
        gateway_key_id: str | None = None,
        model_prefix: str | None = None,
        status_filter: RequestLogStatusFilter | None = None,
        protocol: ProtocolKind | None = None,
        channel: str | None = None,
        keyword: str | None = None,
        sort: RequestLogSortMode = RequestLogSortMode.LATEST,
    ) -> RequestLogPage:
        """Return a filtered page of request logs and filter options."""
        time_zone = self._runtime_time_zone(
            await self._settings_repo.get_runtime_settings()
        )
        async with self._session_factory() as session:
            items_stmt = select(RequestLogEntity)
            items_stmt = self._apply_request_log_filters(
                items_stmt,
                days=days,
                time_zone=time_zone,
                gateway_key_id=gateway_key_id,
                model_prefix=model_prefix,
                status_filter=status_filter,
                protocol=protocol,
                channel=channel,
                keyword=keyword,
            )
            items_stmt = self._apply_request_log_sort(items_stmt, sort=sort)
            items_stmt = items_stmt.offset(max(offset, 0)).limit(max(limit, 0))

            total_stmt = select(func.count()).select_from(RequestLogEntity)
            total_stmt = self._apply_request_log_filters(
                total_stmt,
                days=days,
                time_zone=time_zone,
                gateway_key_id=gateway_key_id,
                model_prefix=model_prefix,
                status_filter=status_filter,
                protocol=protocol,
                channel=channel,
                keyword=keyword,
            )

            channel_label_expr = func.coalesce(
                func.nullif(func.trim(RequestLogEntity.channel_name), ""),
                RequestLogEntity.channel_id,
                literal("n/a"),
            )
            channel_stmt = (
                select(
                    RequestLogEntity.channel_id,
                    channel_label_expr.label("label"),
                )
                .select_from(RequestLogEntity)
                .distinct()
            )
            channel_stmt = self._apply_request_log_filters(
                channel_stmt,
                days=days,
                time_zone=time_zone,
                gateway_key_id=gateway_key_id,
                model_prefix=model_prefix,
                status_filter=status_filter,
                protocol=protocol,
                keyword=keyword,
            )

            gateway_key_stmt = (
                select(RequestLogEntity.gateway_key_id)
                .select_from(RequestLogEntity)
                .distinct()
            )
            gateway_key_stmt = self._apply_request_log_filters(
                gateway_key_stmt,
                days=days,
                time_zone=time_zone,
                model_prefix=model_prefix,
                status_filter=status_filter,
                protocol=protocol,
                channel=channel,
                keyword=keyword,
            )

            model_name_stmt = (
                select(
                    RequestLogEntity.resolved_group_name,
                    RequestLogEntity.requested_group_name,
                    RequestLogEntity.upstream_model_name,
                )
                .select_from(RequestLogEntity)
                .distinct()
            )
            model_name_stmt = self._apply_request_log_filters(
                model_name_stmt,
                days=days,
                time_zone=time_zone,
                gateway_key_id=gateway_key_id,
                status_filter=status_filter,
                protocol=protocol,
                channel=channel,
                keyword=keyword,
            )

            items_result = await session.execute(items_stmt)
            total = await session.scalar(total_stmt)
            channel_result = await session.execute(channel_stmt)
            gateway_key_result = await session.execute(gateway_key_stmt)
            model_name_result = await session.execute(model_name_stmt)
            entities = items_result.scalars().all()
            channel_options_by_id: dict[str, str] = {}
            for channel_id, label in channel_result.all():
                option_id = str(channel_id) if channel_id is not None else "n/a"
                channel_options_by_id[option_id] = str(label or option_id)
            channels = [
                RequestLogFilterOption(id=option_id, label=label)
                for option_id, label in sorted(
                    channel_options_by_id.items(),
                    key=lambda item: (item[1].lower(), item[0]),
                )
            ]
            gateway_key_options_by_id = {
                str(value) if value is not None else "n/a"
                for value in gateway_key_result.scalars().all()
            }
            gateway_key_ids = sorted(
                key_id for key_id in gateway_key_options_by_id if key_id != "n/a"
            )
            gateway_key_remarks = (
                await self._gateway_key_repo._gateway_key_remarks_by_id(
                    session, gateway_key_ids
                )
            )
            gateway_has_multiple_keys = await self._gateway_has_multiple_keys(session)
            gateway_keys = [
                RequestLogFilterOption(
                    id=key_id,
                    label=(
                        "n/a"
                        if key_id == "n/a"
                        else gateway_key_remarks.get(key_id, "") or key_id
                    ),
                )
                for key_id in sorted(
                    gateway_key_options_by_id,
                    key=lambda item: (
                        (
                            "n/a"
                            if item == "n/a"
                            else gateway_key_remarks.get(item, "") or item
                        ).lower(),
                        item,
                    ),
                )
            ]
            model_name_values = set()
            for row in model_name_result.all():
                for value in row:
                    if value is None:
                        continue
                    normalized_value = str(value).strip()
                    if normalized_value:
                        model_name_values.add(normalized_value)
            model_names = sorted(model_name_values)

            return RequestLogPage(
                items=await self._hydrate_request_logs(
                    session,
                    entities,
                    gateway_has_multiple_keys=gateway_has_multiple_keys,
                ),
                total=int(total),
                limit=max(limit, 0),
                offset=max(offset, 0),
                channels=channels,
                gateway_keys=gateway_keys,
                gateway_has_multiple_keys=gateway_has_multiple_keys,
                model_names=model_names,
            )

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

    async def get_request_log(self, log_id: int) -> RequestLogDetail:
        """Return a hydrated request log by identifier."""
        async with self._session_factory() as session:
            entity = await session.get(RequestLogEntity, log_id)
            if entity is None:
                raise KeyError(log_id)
            remarks = await self._gateway_key_repo._gateway_key_remarks_by_id(
                session, [entity.gateway_key_id]
            )
            gateway_has_multiple_keys = await self._gateway_has_multiple_keys(session)
            credential_counts = await self._request_log_channel_credential_counts(
                session, [entity.channel_id]
            )
            return self._to_request_log_detail(
                entity,
                gateway_key_remark=remarks.get(entity.gateway_key_id or ""),
                gateway_has_multiple_keys=gateway_has_multiple_keys,
                channel_has_multiple_credentials=(
                    credential_counts.get(entity.channel_id or "", 0) > 1
                ),
            )

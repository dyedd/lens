from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import func, literal, select

from ..shared import (
    HealthBucket,
    HealthItem,
    HealthSummary,
    ModelGroupEntity,
    REQUEST_LOG_HEALTH_STATUSES,
    ProtocolKind,
    RequestLogDetail,
    RequestLogEntity,
    RequestLogFilterOption,
    RequestLogLifecycleStatus,
    RequestLogPage,
    RequestLogSortMode,
    RequestLogStatusFilter,
    SiteEntity,
    SiteProtocolConfigEntity,
)


class RequestLogReadMixin:
    async def list_model_health(
        self,
        *,
        hours: int,
        mode: Literal["model", "channel"],
        query: str = "",
        limit: int = 24,
        offset: int = 0,
    ) -> HealthSummary:
        """Return a paged request-health summary grouped by model or site."""
        bucket_count = 60
        bucket_seconds = hours * 3600 // bucket_count
        ended_at = datetime.now(UTC)
        started_at = ended_at - timedelta(hours=hours)
        bucket_ranges = [
            (
                started_at + timedelta(seconds=bucket_seconds * index),
                started_at + timedelta(seconds=bucket_seconds * (index + 1)),
            )
            for index in range(bucket_count)
        ]
        normalized_query = query.strip()
        normalized_limit = min(max(limit, 1), 100)
        normalized_offset = max(offset, 0)

        async with self._session_factory() as session:
            if mode == "model":
                item_stmt = select(
                    ModelGroupEntity.name.label("key"),
                    ModelGroupEntity.name.label("name"),
                ).where(ModelGroupEntity.route_group_id == "")
                if normalized_query:
                    item_stmt = item_stmt.where(
                        ModelGroupEntity.name.ilike(f"%{normalized_query}%")
                    )
                item_stmt = item_stmt.order_by(
                    func.lower(ModelGroupEntity.name), ModelGroupEntity.name
                )
                item_rows = await session.execute(
                    item_stmt.offset(normalized_offset).limit(normalized_limit + 1)
                )
                request_logs_stmt = select(
                    RequestLogEntity.resolved_group_name.label("key"),
                    RequestLogEntity.lifecycle_status,
                    RequestLogEntity.created_at,
                )
            else:
                item_stmt = select(
                    SiteEntity.id.label("key"),
                    SiteEntity.name.label("name"),
                ).where(SiteEntity.enabled == 1)
                if normalized_query:
                    item_stmt = item_stmt.where(
                        SiteEntity.name.ilike(f"%{normalized_query}%")
                    )
                item_stmt = item_stmt.order_by(
                    func.lower(SiteEntity.name), SiteEntity.name
                )
                item_rows = await session.execute(
                    item_stmt.offset(normalized_offset).limit(normalized_limit + 1)
                )
                request_logs_stmt = select(
                    SiteProtocolConfigEntity.site_id.label("key"),
                    RequestLogEntity.lifecycle_status,
                    RequestLogEntity.created_at,
                ).join(
                    SiteProtocolConfigEntity,
                    RequestLogEntity.channel_id.like(
                        SiteProtocolConfigEntity.id + literal("_%")
                    ),
                )

            rows = item_rows.all()
            has_next_page = len(rows) > normalized_limit
            rows = rows[:normalized_limit]
            items_by_key = {
                str(row.key).strip(): str(row.name).strip()
                for row in rows
                if str(row.key).strip() and str(row.name).strip()
            }
            bucket_counts = {
                key: [
                    {"success_count": 0, "total_count": 0} for _ in range(bucket_count)
                ]
                for key in items_by_key
            }
            if items_by_key:
                request_logs_stmt = request_logs_stmt.where(
                    RequestLogEntity.lifecycle_status.in_(REQUEST_LOG_HEALTH_STATUSES),
                    RequestLogEntity.created_at >= started_at.replace(tzinfo=None),
                    RequestLogEntity.created_at < ended_at.replace(tzinfo=None),
                )
                if mode == "model":
                    request_logs_stmt = request_logs_stmt.where(
                        RequestLogEntity.resolved_group_name.in_(items_by_key)
                    )
                else:
                    request_logs_stmt = request_logs_stmt.where(
                        SiteProtocolConfigEntity.site_id.in_(items_by_key)
                    )
                request_rows = await session.execute(request_logs_stmt)
                for row in request_rows.all():
                    key = str(row.key).strip()
                    counts = bucket_counts.get(key)
                    if counts is None or row.created_at is None:
                        continue
                    created_at = row.created_at
                    if created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=UTC)
                    else:
                        created_at = created_at.astimezone(UTC)
                    bucket_index = int(
                        (created_at - started_at).total_seconds() // bucket_seconds
                    )
                    if bucket_index < 0 or bucket_index >= bucket_count:
                        continue
                    counts[bucket_index]["total_count"] += 1
                    if (
                        row.lifecycle_status
                        == RequestLogLifecycleStatus.SUCCEEDED.value
                    ):
                        counts[bucket_index]["success_count"] += 1

        return HealthSummary(
            started_at=started_at.isoformat(),
            ended_at=ended_at.isoformat(),
            next_offset=(
                normalized_offset + normalized_limit if has_next_page else None
            ),
            items=[
                HealthItem(
                    name=items_by_key[key],
                    success_count=sum(item["success_count"] for item in counts),
                    total_count=sum(item["total_count"] for item in counts),
                    buckets=[
                        HealthBucket(
                            started_at=start.isoformat(),
                            ended_at=end.isoformat(),
                            success_count=counts[index]["success_count"],
                            total_count=counts[index]["total_count"],
                        )
                        for index, (start, end) in enumerate(bucket_ranges)
                    ],
                )
                for key, counts in sorted(
                    bucket_counts.items(),
                    key=lambda item: items_by_key[item[0]].casefold(),
                )
            ],
        )

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
            channel_ids = [entity.channel_id]
            for attempt in self._parse_attempts_json(entity.attempts_json):
                attempt_channel_id = attempt.get("channel_id")
                if isinstance(attempt_channel_id, str):
                    channel_ids.append(attempt_channel_id)
            credential_counts, credential_metadata = (
                await self._request_log_channel_credentials(session, channel_ids)
            )
            return self._to_request_log_detail(
                entity,
                gateway_key_remark=remarks.get(entity.gateway_key_id or ""),
                gateway_has_multiple_keys=gateway_has_multiple_keys,
                channel_has_multiple_credentials=(
                    credential_counts.get(entity.channel_id or "", 0) > 1
                ),
                credential_metadata=credential_metadata,
                channel_credential_counts=credential_counts,
            )

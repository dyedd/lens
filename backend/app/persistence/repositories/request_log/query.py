from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

from sqlalchemy import String, cast, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import ResourceNotFoundError
from app.models.health import (
    HealthBucket,
    HealthItem,
    HealthSummary,
    health_tier,
)
from app.models.protocols import (
    ProtocolKind,
    RequestLogLifecycleStatus,
    RequestLogSortMode,
    RequestLogStatusFilter,
)
from app.models.request_logs import (
    RequestLogAttempt,
    RequestLogDetail,
    RequestLogFilterOption,
    RequestLogItem,
    RequestLogPage,
)
from app.persistence.entities import (
    GatewayApiKeyEntity,
    ModelGroupEntity,
    RequestLogEntity,
    SiteCredentialEntity,
    SiteEntity,
    SiteProtocolConfigCredentialEntity,
    SiteProtocolConfigEntity,
)

from .types import (
    REQUEST_LOG_HEALTH_STATUSES,
    REQUEST_LOG_MODEL_FAMILY_PREFIXES,
    REQUEST_LOG_RUNNING_STATUSES,
    GatewayKeyPort,
    HydratorPort,
    RuntimeTimeZone,
    SettingsPort,
    clean_reasoning_effort,
    extract_reasoning_effort,
    group_channel_ids_by_protocol_config,
)


def primary_attempt(
    attempts: list[dict[str, Any]], channel_id: str | None
) -> dict[str, Any]:
    if channel_id:
        for attempt in reversed(attempts):
            if str(attempt.get("channel_id") or "") == channel_id:
                return attempt
        return {}
    return attempts[-1] if attempts else {}


def credential_values(
    channel_id: str | None,
    credential_id: Any,
    credential_name: Any,
    credential_metadata: dict[tuple[str, str], tuple[str, int]],
) -> tuple[str | None, str, int]:
    gateway_key_id = credential_id.strip() if isinstance(credential_id, str) else None
    snapshot_name = credential_name.strip() if isinstance(credential_name, str) else ""
    current = credential_metadata.get(
        ((channel_id or "").strip(), gateway_key_id or "")
    )
    if current is None:
        return gateway_key_id, snapshot_name, 0
    current_name, current_number = current
    return gateway_key_id, current_name.strip(), current_number


def to_request_log(
    entity: RequestLogEntity,
    *,
    gateway_key_remark: str | None = None,
    gateway_has_multiple_keys: bool = False,
    channel_has_multiple_credentials: bool = False,
    credential_metadata: dict[tuple[str, str], tuple[str, int]] | None = None,
) -> RequestLogItem:
    attempts = parse_attempts_json(entity.attempts_json)
    primary = primary_attempt(attempts, entity.channel_id)
    credential_id, credential_name, credential_number = credential_values(
        entity.channel_id,
        primary.get("credential_id"),
        primary.get("credential_name"),
        credential_metadata or {},
    )
    reasoning_effort = extract_reasoning_effort(
        entity.request_content
    ) or clean_reasoning_effort(primary.get("reasoning_effort"))
    return RequestLogItem(
        id=entity.id,
        protocol=entity.protocol,
        user_agent=entity.user_agent,
        requested_group_name=entity.requested_group_name,
        resolved_group_name=entity.resolved_group_name,
        upstream_model_name=entity.upstream_model_name,
        channel_id=entity.channel_id,
        channel_name=entity.channel_name,
        credential_id=credential_id,
        credential_name=credential_name,
        credential_number=credential_number,
        channel_has_multiple_credentials=channel_has_multiple_credentials,
        gateway_key_id=entity.gateway_key_id,
        gateway_key_remark=gateway_key_remark or None,
        gateway_has_multiple_keys=gateway_has_multiple_keys,
        reasoning_effort=reasoning_effort,
        status_code=entity.status_code,
        success=bool(entity.success),
        lifecycle_status=(
            RequestLogLifecycleStatus(entity.lifecycle_status)
            if entity.lifecycle_status in RequestLogLifecycleStatus._value2member_map_
            else (
                RequestLogLifecycleStatus.SUCCEEDED
                if entity.success
                else RequestLogLifecycleStatus.FAILED
            )
        ),
        is_stream=bool(entity.is_stream),
        first_token_latency_ms=entity.first_token_latency_ms,
        latency_ms=entity.latency_ms,
        input_tokens=entity.input_tokens,
        cache_read_input_tokens=entity.cache_read_input_tokens,
        cache_write_input_tokens=entity.cache_write_input_tokens,
        output_tokens=entity.output_tokens,
        total_tokens=entity.total_tokens,
        input_cost_usd=entity.input_cost_usd,
        output_cost_usd=entity.output_cost_usd,
        total_cost_usd=entity.total_cost_usd,
        rate_multiplier=entity.rate_multiplier,
        billing_mode=entity.billing_mode,
        billing_units=entity.billing_units,
        attempt_count=len(attempts),
        error_message=entity.error_message,
        created_at=entity.created_at.replace(tzinfo=UTC).isoformat(),
    )


def to_request_log_attempt(
    item: dict[str, Any],
    credential_metadata: dict[tuple[str, str], tuple[str, int]],
    channel_credential_counts: dict[str, int],
) -> RequestLogAttempt:
    payload = dict(item)
    credential_id, credential_name, credential_number = credential_values(
        str(item.get("channel_id") or ""),
        item.get("credential_id"),
        item.get("credential_name"),
        credential_metadata,
    )
    payload["credential_id"] = credential_id
    payload["credential_name"] = credential_name
    payload["credential_number"] = credential_number
    payload["channel_has_multiple_credentials"] = (
        channel_credential_counts.get(str(item.get("channel_id") or ""), 0) > 1
    )
    return RequestLogAttempt(**payload)


def to_request_log_detail(
    entity: RequestLogEntity,
    *,
    gateway_key_remark: str | None = None,
    gateway_has_multiple_keys: bool = False,
    channel_has_multiple_credentials: bool = False,
    credential_metadata: dict[tuple[str, str], tuple[str, int]] | None = None,
    channel_credential_counts: dict[str, int] | None = None,
) -> RequestLogDetail:
    resolved_metadata = credential_metadata or {}
    resolved_counts = channel_credential_counts or {}
    return RequestLogDetail(
        **to_request_log(
            entity,
            gateway_key_remark=gateway_key_remark,
            gateway_has_multiple_keys=gateway_has_multiple_keys,
            channel_has_multiple_credentials=channel_has_multiple_credentials,
            credential_metadata=resolved_metadata,
        ).model_dump(),
        request_content=entity.request_content,
        response_content=entity.response_content,
        attempts=[
            to_request_log_attempt(item, resolved_metadata, resolved_counts)
            for item in parse_attempts_json(entity.attempts_json)
        ],
    )


def parse_attempts_json(raw_value: str | None) -> list[dict[str, Any]]:
    if not raw_value:
        return []
    payload = json.loads(raw_value)
    if not isinstance(payload, list) or not all(
        isinstance(item, dict) for item in payload
    ):
        raise ValueError("Invalid request log attempts JSON")
    return payload


def resolve_request_log_window(
    days: int, *, time_zone: ZoneInfo, offset_days: int = 0
) -> tuple[datetime | None, datetime | None]:
    if days == 0:
        return None, None
    now = datetime.now(time_zone)
    if days == -1:
        start_at = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
            days=offset_days
        )
        end_at = start_at + timedelta(days=1)
    else:
        end_at = now - timedelta(days=offset_days)
        start_at = end_at - timedelta(days=days)
    return (
        start_at.astimezone(UTC).replace(tzinfo=None),
        end_at.astimezone(UTC).replace(tzinfo=None),
    )


def resolve_imported_date_window(
    days: int, *, time_zone: ZoneInfo, offset_days: int = 0
) -> tuple[str | None, str | None]:
    start_at, end_at = resolve_request_log_window(
        days, offset_days=offset_days, time_zone=time_zone
    )
    if start_at is None or end_at is None:
        return None, None
    return (
        start_at.replace(tzinfo=UTC).astimezone(time_zone).strftime("%Y%m%d"),
        end_at.replace(tzinfo=UTC).astimezone(time_zone).strftime("%Y%m%d"),
    )


def apply_request_log_window(
    stmt: Any, *, days: int, time_zone: ZoneInfo, offset_days: int = 0
) -> Any:
    start_at, end_at = resolve_request_log_window(
        days, offset_days=offset_days, time_zone=time_zone
    )
    if start_at is not None:
        stmt = stmt.where(RequestLogEntity.created_at >= start_at)
    if end_at is not None:
        stmt = stmt.where(RequestLogEntity.created_at < end_at)
    return stmt


def prepare_request_log_keyword(keyword: str | None) -> str | None:
    keyword_value = (keyword or "").strip().lower()
    return keyword_value or None


def escape_like_pattern(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def apply_request_log_model_prefix_filter(
    stmt: Any, *, model_prefix: str | None
) -> Any:
    keyword_value = prepare_request_log_keyword(model_prefix)
    if keyword_value is None:
        return stmt
    prefixes = REQUEST_LOG_MODEL_FAMILY_PREFIXES.get(keyword_value, (keyword_value,))
    columns = (
        RequestLogEntity.resolved_group_name,
        RequestLogEntity.requested_group_name,
        RequestLogEntity.upstream_model_name,
    )
    conditions = []
    for prefix in prefixes:
        escaped_prefix = escape_like_pattern(prefix)
        for column in columns:
            lowered_column = func.lower(func.coalesce(column, ""))
            conditions.append(lowered_column.like(f"{escaped_prefix}%", escape="\\"))
            conditions.append(lowered_column.like(f"%/{escaped_prefix}%", escape="\\"))
    return stmt.where(or_(*conditions))


def apply_request_log_keyword_filter(stmt: Any, *, keyword: str | None) -> Any:
    keyword_value = prepare_request_log_keyword(keyword)
    if keyword_value is None:
        return stmt
    pattern = f"%{escape_like_pattern(keyword_value)}%"
    status_code_text = cast(RequestLogEntity.status_code, String)
    search_columns = [
        RequestLogEntity.requested_group_name,
        RequestLogEntity.resolved_group_name,
        RequestLogEntity.upstream_model_name,
        RequestLogEntity.channel_name,
        RequestLogEntity.channel_id,
        RequestLogEntity.gateway_key_id,
        RequestLogEntity.error_message,
        RequestLogEntity.protocol,
        RequestLogEntity.user_agent,
        status_code_text,
        GatewayApiKeyEntity.remark,
    ]
    conditions = [
        func.lower(func.coalesce(column, "")).like(pattern, escape="\\")
        for column in search_columns
    ]
    return stmt.outerjoin(
        GatewayApiKeyEntity,
        GatewayApiKeyEntity.id == RequestLogEntity.gateway_key_id,
    ).where(or_(*conditions))


def prepare_gateway_key_id(gateway_key_id: str | None) -> str | None:
    gateway_key_id_value = (gateway_key_id or "").strip()
    return gateway_key_id_value or None


def apply_gateway_key_filter(stmt: Any, *, gateway_key_id: str | None = None) -> Any:
    gateway_key_id_value = prepare_gateway_key_id(gateway_key_id)
    if gateway_key_id_value is None:
        return stmt
    if gateway_key_id_value == "n/a":
        return stmt.where(RequestLogEntity.gateway_key_id.is_(None))
    return stmt.where(RequestLogEntity.gateway_key_id == gateway_key_id_value)


def apply_request_log_filters(
    stmt: Any,
    *,
    days: int,
    time_zone: ZoneInfo,
    gateway_key_id: str | None = None,
    model_prefix: str | None = None,
    status_filter: RequestLogStatusFilter | None = None,
    protocol: ProtocolKind | None = None,
    channel: str | None = None,
    keyword: str | None = None,
) -> Any:
    stmt = apply_request_log_window(stmt, days=days, time_zone=time_zone)
    stmt = apply_gateway_key_filter(stmt, gateway_key_id=gateway_key_id)
    stmt = apply_request_log_model_prefix_filter(stmt, model_prefix=model_prefix)
    if status_filter == RequestLogStatusFilter.SUCCESS:
        stmt = stmt.where(
            RequestLogEntity.lifecycle_status
            == RequestLogLifecycleStatus.SUCCEEDED.value
        )
    elif status_filter == RequestLogStatusFilter.FAILED:
        stmt = stmt.where(
            RequestLogEntity.lifecycle_status == RequestLogLifecycleStatus.FAILED.value
        )
    elif status_filter == RequestLogStatusFilter.CANCELLED:
        stmt = stmt.where(
            RequestLogEntity.lifecycle_status
            == RequestLogLifecycleStatus.CANCELLED.value
        )
    elif status_filter == RequestLogStatusFilter.RUNNING:
        stmt = stmt.where(
            RequestLogEntity.lifecycle_status.in_(REQUEST_LOG_RUNNING_STATUSES)
        )
    if protocol is not None:
        stmt = stmt.where(RequestLogEntity.protocol == protocol.value)
    trimmed_channel = (channel or "").strip()
    if trimmed_channel == "n/a":
        stmt = stmt.where(RequestLogEntity.channel_id.is_(None))
    elif trimmed_channel:
        stmt = stmt.where(RequestLogEntity.channel_id == trimmed_channel)
    return apply_request_log_keyword_filter(stmt, keyword=keyword)


def apply_request_log_sort(
    stmt: Any, *, sort: RequestLogSortMode = RequestLogSortMode.LATEST
) -> Any:
    if sort == RequestLogSortMode.COST:
        return stmt.order_by(
            RequestLogEntity.total_cost_usd.desc(),
            RequestLogEntity.created_at.desc(),
            RequestLogEntity.id.desc(),
        )
    if sort == RequestLogSortMode.LATENCY:
        return stmt.order_by(
            RequestLogEntity.latency_ms.desc(),
            RequestLogEntity.created_at.desc(),
            RequestLogEntity.id.desc(),
        )
    if sort == RequestLogSortMode.TOKENS:
        return stmt.order_by(
            RequestLogEntity.total_tokens.desc(),
            RequestLogEntity.created_at.desc(),
            RequestLogEntity.id.desc(),
        )
    return stmt.order_by(RequestLogEntity.created_at.desc(), RequestLogEntity.id.desc())


class RequestLogHydrator:
    def __init__(self, gateway_key_repo: GatewayKeyPort) -> None:
        self.gateway_key_repo = gateway_key_repo

    async def hydrate_request_logs(
        self,
        session: AsyncSession,
        entities: list[RequestLogEntity],
        *,
        gateway_has_multiple_keys: bool | None = None,
    ) -> list[RequestLogItem]:
        remarks = await self.gateway_key_repo.remarks_by_id(
            session, [entity.gateway_key_id for entity in entities]
        )
        if gateway_has_multiple_keys is None:
            gateway_has_multiple_keys = (
                await self.gateway_has_multiple_keys(session) if entities else False
            )
        (
            credential_counts,
            credential_metadata,
        ) = await self.request_log_channel_credentials(
            session, [entity.channel_id for entity in entities]
        )
        return [
            to_request_log(
                entity,
                gateway_key_remark=remarks.get(entity.gateway_key_id or ""),
                gateway_has_multiple_keys=gateway_has_multiple_keys,
                channel_has_multiple_credentials=credential_counts.get(
                    entity.channel_id or "", 0
                )
                > 1,
                credential_metadata=credential_metadata,
            )
            for entity in entities
        ]

    @staticmethod
    async def gateway_has_multiple_keys(session: AsyncSession) -> bool:
        rows = (await session.execute(select(GatewayApiKeyEntity.id).limit(2))).all()
        return len(rows) > 1

    async def request_log_channel_credentials(
        self, session: AsyncSession, channel_ids: list[str | None]
    ) -> tuple[dict[str, int], dict[tuple[str, str], tuple[str, int]]]:
        channels_by_protocol_config, _ = group_channel_ids_by_protocol_config(
            channel_ids
        )
        if not channels_by_protocol_config:
            return ({}, {})
        protocol_config_ids = list(channels_by_protocol_config.keys())
        protocol_config_rows = (
            await session.execute(
                select(
                    SiteProtocolConfigEntity.id, SiteProtocolConfigEntity.site_id
                ).where(SiteProtocolConfigEntity.id.in_(protocol_config_ids))
            )
        ).all()
        channels_by_site: dict[str, list[str]] = {}
        for protocol_config_id, site_id in protocol_config_rows:
            channels_by_site.setdefault(str(site_id), []).extend(
                channels_by_protocol_config.get(str(protocol_config_id), [])
            )
        if not channels_by_site:
            return ({}, {})
        protocol_credential_rows = (
            await session.execute(
                select(
                    SiteProtocolConfigCredentialEntity.protocol_config_id,
                    SiteProtocolConfigCredentialEntity.credential_id,
                ).where(
                    SiteProtocolConfigCredentialEntity.protocol_config_id.in_(
                        protocol_config_ids
                    )
                )
            )
        ).all()
        credential_ids_by_config: dict[str, set[str]] = {}
        for protocol_config_id, credential_id in protocol_credential_rows:
            credential_ids_by_config.setdefault(str(protocol_config_id), set()).add(
                str(credential_id)
            )
        credential_rows = (
            await session.execute(
                select(
                    SiteCredentialEntity.id,
                    SiteCredentialEntity.site_id,
                    SiteCredentialEntity.name,
                )
                .where(SiteCredentialEntity.site_id.in_(list(channels_by_site)))
                .order_by(
                    SiteCredentialEntity.site_id.asc(),
                    SiteCredentialEntity.sort_order.asc(),
                    SiteCredentialEntity.id.asc(),
                )
            )
        ).all()
        credentials_by_site: dict[str, dict[str, tuple[str, int]]] = {}
        credential_numbers_by_site: dict[str, int] = {}
        for credential_id, site_id, credential_name in credential_rows:
            site_id_text = str(site_id)
            credential_numbers_by_site[site_id_text] = (
                credential_numbers_by_site.get(site_id_text, 0) + 1
            )
            credentials_by_site.setdefault(site_id_text, {})[str(credential_id)] = (
                str(credential_name or ""),
                credential_numbers_by_site[site_id_text],
            )
        credential_counts: dict[str, int] = {}
        credential_metadata: dict[tuple[str, str], tuple[str, int]] = {}
        for protocol_config_id, site_id in protocol_config_rows:
            site_id_text = str(site_id)
            site_credentials = credentials_by_site.get(site_id_text, {})
            for channel_id in channels_by_protocol_config.get(
                str(protocol_config_id), []
            ):
                bound_credential_ids = {
                    credential_id
                    for credential_id in credential_ids_by_config.get(
                        str(protocol_config_id), set()
                    )
                    if credential_id in site_credentials
                }
                credential_counts[channel_id] = len(bound_credential_ids)
                for credential_id, (
                    credential_name,
                    credential_number,
                ) in site_credentials.items():
                    credential_metadata[channel_id, credential_id] = (
                        credential_name,
                        credential_number,
                    )
        return (credential_counts, credential_metadata)


class RequestLogQueries:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        settings_repo: SettingsPort,
        gateway_key_repo: GatewayKeyPort,
        hydrator: HydratorPort,
        runtime_time_zone: RuntimeTimeZone,
    ) -> None:
        self.session_factory = session_factory
        self.settings_repo = settings_repo
        self.gateway_key_repo = gateway_key_repo
        self.hydrator = hydrator
        self.runtime_time_zone = runtime_time_zone

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
        trimmed_query = query.strip()
        bounded_limit = min(max(limit, 1), 100)
        bounded_offset = max(offset, 0)
        async with self.session_factory() as session:
            if mode == "model":
                item_stmt = select(
                    ModelGroupEntity.name.label("key"),
                    ModelGroupEntity.name.label("name"),
                ).where(ModelGroupEntity.route_group_id == "")
                if trimmed_query:
                    item_stmt = item_stmt.where(
                        ModelGroupEntity.name.ilike(f"%{trimmed_query}%")
                    )
                item_stmt = item_stmt.order_by(
                    func.lower(ModelGroupEntity.name), ModelGroupEntity.name
                )
                item_rows = await session.execute(
                    item_stmt.offset(bounded_offset).limit(bounded_limit + 1)
                )
                request_logs_stmt = select(
                    RequestLogEntity.resolved_group_name.label("key"),
                    RequestLogEntity.lifecycle_status,
                    RequestLogEntity.created_at,
                )
            else:
                item_stmt = select(
                    SiteEntity.id.label("key"), SiteEntity.name.label("name")
                ).where(SiteEntity.enabled == 1)
                if trimmed_query:
                    item_stmt = item_stmt.where(
                        SiteEntity.name.ilike(f"%{trimmed_query}%")
                    )
                item_stmt = item_stmt.order_by(
                    func.lower(SiteEntity.name), SiteEntity.name
                )
                item_rows = await session.execute(
                    item_stmt.offset(bounded_offset).limit(bounded_limit + 1)
                )
                request_logs_stmt = select(
                    SiteProtocolConfigEntity.site_id.label("key"),
                    RequestLogEntity.lifecycle_status,
                    RequestLogEntity.created_at,
                ).join(
                    SiteProtocolConfigEntity,
                    SiteProtocolConfigEntity.id == RequestLogEntity.protocol_config_id,
                )
            rows = item_rows.all()
            has_next_page = len(rows) > bounded_limit
            rows = rows[:bounded_limit]
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
            next_offset=bounded_offset + bounded_limit if has_next_page else None,
            items=[
                HealthItem(
                    name=items_by_key[key],
                    success_count=sum(item["success_count"] for item in counts),
                    total_count=sum(item["total_count"] for item in counts),
                    tier=health_tier(
                        sum(item["total_count"] for item in counts),
                        sum(item["success_count"] for item in counts),
                    ),
                    buckets=[
                        HealthBucket(
                            started_at=start.isoformat(),
                            ended_at=end.isoformat(),
                            success_count=counts[index]["success_count"],
                            total_count=counts[index]["total_count"],
                            tier=health_tier(
                                counts[index]["total_count"],
                                counts[index]["success_count"],
                            ),
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
        time_zone = self.runtime_time_zone(
            await self.settings_repo.get_runtime_settings()
        )
        async with self.session_factory() as session:
            items_stmt = select(RequestLogEntity)
            items_stmt = apply_request_log_filters(
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
            items_stmt = apply_request_log_sort(items_stmt, sort=sort)
            items_stmt = items_stmt.offset(max(offset, 0)).limit(max(limit, 0))
            total_stmt = select(func.count()).select_from(RequestLogEntity)
            total_stmt = apply_request_log_filters(
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
                select(RequestLogEntity.channel_id, channel_label_expr.label("label"))
                .select_from(RequestLogEntity)
                .distinct()
            )
            channel_stmt = apply_request_log_filters(
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
            gateway_key_stmt = apply_request_log_filters(
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
            model_name_stmt = apply_request_log_filters(
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
            gateway_key_remarks = await self.gateway_key_repo.remarks_by_id(
                session, gateway_key_ids
            )
            gateway_has_multiple_keys = await self.hydrator.gateway_has_multiple_keys(
                session
            )
            gateway_keys = [
                RequestLogFilterOption(
                    id=key_id,
                    label="n/a"
                    if key_id == "n/a"
                    else gateway_key_remarks.get(key_id, "") or key_id,
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
                    trimmed_value = str(value).strip()
                    if trimmed_value:
                        model_name_values.add(trimmed_value)
            model_names = sorted(model_name_values)
            return RequestLogPage(
                items=await self.hydrator.hydrate_request_logs(
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
        async with self.session_factory() as session:
            entity = await session.get(RequestLogEntity, log_id)
            if entity is None:
                raise ResourceNotFoundError(log_id)
            remarks = await self.gateway_key_repo.remarks_by_id(
                session, [entity.gateway_key_id]
            )
            gateway_has_multiple_keys = await self.hydrator.gateway_has_multiple_keys(
                session
            )
            channel_ids = [entity.channel_id]
            for attempt in parse_attempts_json(entity.attempts_json):
                attempt_channel_id = attempt.get("channel_id")
                if isinstance(attempt_channel_id, str):
                    channel_ids.append(attempt_channel_id)
            (
                credential_counts,
                credential_metadata,
            ) = await self.hydrator.request_log_channel_credentials(
                session, channel_ids
            )
            return to_request_log_detail(
                entity,
                gateway_key_remark=remarks.get(entity.gateway_key_id or ""),
                gateway_has_multiple_keys=gateway_has_multiple_keys,
                channel_has_multiple_credentials=credential_counts.get(
                    entity.channel_id or "", 0
                )
                > 1,
                credential_metadata=credential_metadata,
                channel_credential_counts=credential_counts,
            )

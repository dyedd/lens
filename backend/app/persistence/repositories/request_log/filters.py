from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import String, cast, func, or_

from app.models.protocols import (
    ProtocolKind,
    RequestLogLifecycleStatus,
    RequestLogSortMode,
    RequestLogStatusFilter,
)
from app.persistence.entities import GatewayApiKeyEntity, RequestLogEntity
from app.persistence.request_log_constants import (
    REQUEST_LOG_MODEL_FAMILY_PREFIXES,
    REQUEST_LOG_RUNNING_STATUSES,
)


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

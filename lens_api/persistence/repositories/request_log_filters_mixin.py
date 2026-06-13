from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..shared import (
    Any,
    GatewayApiKeyEntity,
    ProtocolKind,
    REQUEST_LOG_MODEL_FAMILY_PREFIXES,
    REQUEST_LOG_RUNNING_STATUSES,
    RequestLogEntity,
    RequestLogLifecycleStatus,
    RequestLogSortMode,
    RequestLogStatusFilter,
    String,
    UTC,
    ZoneInfo,
    cast,
    datetime,
    func,
    or_,
    timedelta,
)


class RequestLogFilterMixin:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _resolve_request_log_window(
        days: int, *, time_zone: ZoneInfo, offset_days: int = 0
    ) -> tuple[datetime | None, datetime | None]:
        if days == 0:
            return None, None

        now = datetime.now(time_zone)
        if days == -1:
            start_at = now.replace(
                hour=0, minute=0, second=0, microsecond=0
            ) - timedelta(days=offset_days)
            end_at = start_at + timedelta(days=1)
            return (
                start_at.astimezone(UTC).replace(tzinfo=None),
                end_at.astimezone(UTC).replace(tzinfo=None),
            )

        end_at = now - timedelta(days=offset_days)
        start_at = end_at - timedelta(days=days)
        return (
            start_at.astimezone(UTC).replace(tzinfo=None),
            end_at.astimezone(UTC).replace(tzinfo=None),
        )

    @classmethod
    def _resolve_imported_date_window(
        cls, days: int, *, time_zone: ZoneInfo, offset_days: int = 0
    ) -> tuple[str | None, str | None]:
        start_at, end_at = cls._resolve_request_log_window(
            days, offset_days=offset_days, time_zone=time_zone
        )
        if start_at is None or end_at is None:
            return None, None
        return (
            start_at.replace(tzinfo=UTC).astimezone(time_zone).strftime("%Y%m%d"),
            end_at.replace(tzinfo=UTC).astimezone(time_zone).strftime("%Y%m%d"),
        )

    @classmethod
    def _apply_request_log_window(
        cls, stmt: Any, *, days: int, time_zone: ZoneInfo, offset_days: int = 0
    ) -> Any:
        start_at, end_at = cls._resolve_request_log_window(
            days, offset_days=offset_days, time_zone=time_zone
        )
        if start_at is not None:
            stmt = stmt.where(RequestLogEntity.created_at >= start_at)
        if end_at is not None:
            stmt = stmt.where(RequestLogEntity.created_at < end_at)
        return stmt

    @staticmethod
    def _normalize_request_log_keyword(keyword: str | None) -> str | None:
        normalized = (keyword or "").strip().lower()
        return normalized or None

    @staticmethod
    def _escape_like_pattern(value: str) -> str:
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    @classmethod
    def _apply_request_log_model_prefix_filter(
        cls, stmt: Any, *, model_prefix: str | None
    ) -> Any:
        normalized = cls._normalize_request_log_keyword(model_prefix)
        if normalized is None:
            return stmt
        prefixes = REQUEST_LOG_MODEL_FAMILY_PREFIXES.get(normalized, (normalized,))
        columns = (
            RequestLogEntity.resolved_group_name,
            RequestLogEntity.requested_group_name,
            RequestLogEntity.upstream_model_name,
        )
        conditions = []
        for prefix in prefixes:
            escaped_prefix = cls._escape_like_pattern(prefix)
            for column in columns:
                normalized_column = func.lower(func.coalesce(column, ""))
                conditions.append(
                    normalized_column.like(f"{escaped_prefix}%", escape="\\")
                )
                conditions.append(
                    normalized_column.like(f"%/{escaped_prefix}%", escape="\\")
                )
        return stmt.where(or_(*conditions))

    @classmethod
    def _apply_request_log_keyword_filter(
        cls, stmt: Any, *, keyword: str | None
    ) -> Any:
        normalized = cls._normalize_request_log_keyword(keyword)
        if normalized is None:
            return stmt

        pattern = f"%{cls._escape_like_pattern(normalized)}%"
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

    @classmethod
    def _apply_request_log_filters(
        cls,
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
        stmt = cls._apply_request_log_window(stmt, days=days, time_zone=time_zone)
        stmt = cls._apply_gateway_key_filter(stmt, gateway_key_id=gateway_key_id)
        stmt = cls._apply_request_log_model_prefix_filter(
            stmt, model_prefix=model_prefix
        )

        if status_filter == RequestLogStatusFilter.SUCCESS:
            stmt = stmt.where(
                RequestLogEntity.lifecycle_status
                == RequestLogLifecycleStatus.SUCCEEDED.value
            )
            stmt = stmt.where(RequestLogEntity.success == 1)
        elif status_filter == RequestLogStatusFilter.FAILED:
            stmt = stmt.where(
                RequestLogEntity.lifecycle_status
                == RequestLogLifecycleStatus.FAILED.value
            )
            stmt = stmt.where(RequestLogEntity.success == 0)
        elif status_filter == RequestLogStatusFilter.RUNNING:
            stmt = stmt.where(
                RequestLogEntity.lifecycle_status.in_(REQUEST_LOG_RUNNING_STATUSES)
            )

        if protocol is not None:
            stmt = stmt.where(RequestLogEntity.protocol == protocol.value)

        normalized_channel = (channel or "").strip()
        if normalized_channel:
            if normalized_channel == "n/a":
                stmt = stmt.where(RequestLogEntity.channel_id.is_(None))
            else:
                stmt = stmt.where(RequestLogEntity.channel_id == normalized_channel)

        return cls._apply_request_log_keyword_filter(stmt, keyword=keyword)

    @staticmethod
    def _apply_request_log_sort(
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
        return stmt.order_by(
            RequestLogEntity.created_at.desc(), RequestLogEntity.id.desc()
        )

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..shared import (
    ProtocolKind,
    RequestLogEntity,
    RequestLogFilterOption,
    RequestLogPage,
    RequestLogSortMode,
    RequestLogStatusFilter,
    func,
    literal,
    select,
)


class _RequestLogPageReadMixin:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

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

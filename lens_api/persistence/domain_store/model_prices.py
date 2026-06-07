from __future__ import annotations

from .shared import (
    Any,
    ImportedStatsDailyEntity,
    ImportedStatsTotalEntity,
    ModelGroupEntity,
    ModelPriceEntity,
    ModelPriceItem,
    ModelPriceListResponse,
    ModelPriceUpdate,
    OverviewModelDailyStatsEntity,
    ProtocolKind,
    REQUEST_LOG_RUNNING_STATUSES,
    RequestLogDailyStatsEntity,
    RequestLogEntity,
    RequestLogLifecycleStatus,
    SETTING_MODEL_PRICE_LAST_SYNC_AT,
    SettingEntity,
    UTC,
    ZoneInfo,
    _parse_group_protocols,
    datetime,
    delete,
    normalize_model_key,
    resolve_time_zone,
    select,
    update,
)


class DomainModelPricesMixin:
    async def fail_running_request_logs(
        self, *, interrupted_latency_cap_ms: int | None = None
    ) -> None:
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

    @staticmethod
    def _runtime_time_zone(runtime: dict[str, Any]) -> ZoneInfo:
        return resolve_time_zone(runtime["time_zone"])

    async def replace_imported_stats(
        self,
        *,
        total: dict[str, int | float] | list[dict[str, int | float]] | None,
        daily: list[dict[str, int | float | str]],
        model_prices: list[dict[str, int | float | str]],
    ) -> None:
        async with self._session_factory() as session:
            await session.execute(delete(ImportedStatsDailyEntity))
            await session.execute(delete(ImportedStatsTotalEntity))
            await session.execute(delete(RequestLogDailyStatsEntity))
            await session.execute(delete(OverviewModelDailyStatsEntity))
            await session.execute(delete(ModelPriceEntity))
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

            for item in model_prices:
                key = str(item.get("model_key") or "").strip().lower()
                if not key:
                    continue
                session.add(
                    ModelPriceEntity(
                        model_key=key,
                        display_name=str(item.get("display_name") or key),
                        input_price_per_million=float(
                            item.get("input_price_per_million") or 0.0
                        ),
                        output_price_per_million=float(
                            item.get("output_price_per_million") or 0.0
                        ),
                        cache_read_price_per_million=float(
                            item.get("cache_read_price_per_million") or 0.0
                        ),
                        cache_write_price_per_million=float(
                            item.get("cache_write_price_per_million") or 0.0
                        ),
                    )
                )

            await session.commit()

    async def list_group_names(self, *, include_routed: bool = False) -> list[str]:
        async with self._session_factory() as session:
            query = select(ModelGroupEntity.name).order_by(ModelGroupEntity.name.asc())
            if not include_routed:
                query = query.where(ModelGroupEntity.route_group_id == "")
            rows = await session.execute(query)
            return [str(item) for item in rows.scalars().all() if str(item).strip()]

    async def replace_model_prices(
        self, model_prices: list[dict[str, int | float | str]]
    ) -> None:
        async with self._session_factory() as session:
            await session.execute(delete(ModelPriceEntity))
            for item in model_prices:
                key = normalize_model_key(str(item.get("model_key") or ""))
                if not key:
                    continue
                session.add(
                    ModelPriceEntity(
                        model_key=key,
                        display_name=str(item.get("display_name") or key),
                        input_price_per_million=float(
                            item.get("input_price_per_million") or 0.0
                        ),
                        output_price_per_million=float(
                            item.get("output_price_per_million") or 0.0
                        ),
                        cache_read_price_per_million=float(
                            item.get("cache_read_price_per_million") or 0.0
                        ),
                        cache_write_price_per_million=float(
                            item.get("cache_write_price_per_million") or 0.0
                        ),
                    )
                )
            await session.commit()

    async def sync_model_prices(
        self,
        model_prices: list[dict[str, int | float | str]],
        *,
        overwrite_existing: bool,
        allowed_keys: list[str] | None = None,
    ) -> None:
        async with self._session_factory() as session:
            existing_rows = (
                (await session.execute(select(ModelPriceEntity))).scalars().all()
            )
            entities_by_key = {item.model_key: item for item in existing_rows}

            for item in model_prices:
                key = normalize_model_key(str(item.get("model_key") or ""))
                if not key:
                    continue
                entity = entities_by_key.get(key)
                if entity is None:
                    session.add(
                        ModelPriceEntity(
                            model_key=key,
                            display_name=str(item.get("display_name") or key),
                            input_price_per_million=float(
                                item.get("input_price_per_million") or 0.0
                            ),
                            output_price_per_million=float(
                                item.get("output_price_per_million") or 0.0
                            ),
                            cache_read_price_per_million=float(
                                item.get("cache_read_price_per_million") or 0.0
                            ),
                            cache_write_price_per_million=float(
                                item.get("cache_write_price_per_million") or 0.0
                            ),
                        )
                    )
                    continue
                if overwrite_existing:
                    entity.display_name = str(
                        item.get("display_name") or entity.display_name or key
                    )
                    entity.input_price_per_million = float(
                        item.get("input_price_per_million") or 0.0
                    )
                    entity.output_price_per_million = float(
                        item.get("output_price_per_million") or 0.0
                    )
                    entity.cache_read_price_per_million = float(
                        item.get("cache_read_price_per_million") or 0.0
                    )
                    entity.cache_write_price_per_million = float(
                        item.get("cache_write_price_per_million") or 0.0
                    )

            if allowed_keys is not None:
                normalized_allowed_keys = {
                    normalize_model_key(item)
                    for item in allowed_keys
                    if normalize_model_key(item)
                }
                if normalized_allowed_keys:
                    await session.execute(
                        delete(ModelPriceEntity).where(
                            ModelPriceEntity.model_key.not_in(normalized_allowed_keys)
                        )
                    )
                else:
                    await session.execute(delete(ModelPriceEntity))

            await session.commit()

    async def list_model_prices(self) -> ModelPriceListResponse:
        async with self._session_factory() as session:
            price_rows = (
                (
                    await session.execute(
                        select(ModelPriceEntity).order_by(
                            ModelPriceEntity.display_name.asc(),
                            ModelPriceEntity.model_key.asc(),
                        )
                    )
                )
                .scalars()
                .all()
            )
            group_rows = (
                await session.execute(
                    select(ModelGroupEntity.name, ModelGroupEntity.protocols_json)
                    .where(ModelGroupEntity.route_group_id == "")
                    .order_by(ModelGroupEntity.name.asc())
                )
            ).all()
            last_synced_at = await session.get(
                SettingEntity, SETTING_MODEL_PRICE_LAST_SYNC_AT
            )

        prices_by_key = {item.model_key: item for item in price_rows}
        protocols_by_key: dict[str, set[ProtocolKind]] = {}
        display_names_by_key: dict[str, str] = {}
        for name, protocols_json in group_rows:
            key = normalize_model_key(str(name))
            if not key:
                continue
            protocols_by_key.setdefault(key, set()).update(
                _parse_group_protocols(str(protocols_json or "[]"))
            )
            display_names_by_key.setdefault(key, str(name))

        for key, price_entity in prices_by_key.items():
            if key not in display_names_by_key:
                display_names_by_key[key] = str(price_entity.display_name or key)

        items: list[ModelPriceItem] = []
        for key in sorted(
            display_names_by_key, key=lambda item: display_names_by_key[item].lower()
        ):
            price_entity = prices_by_key.get(key)
            items.append(
                ModelPriceItem(
                    model_key=key,
                    display_name=display_names_by_key[key],
                    protocols=sorted(
                        protocols_by_key.get(key, set()), key=lambda value: value.value
                    ),
                    input_price_per_million=(
                        float(price_entity.input_price_per_million)
                        if price_entity is not None
                        else 0.0
                    ),
                    output_price_per_million=(
                        float(price_entity.output_price_per_million)
                        if price_entity is not None
                        else 0.0
                    ),
                    cache_read_price_per_million=(
                        float(price_entity.cache_read_price_per_million)
                        if price_entity is not None
                        else 0.0
                    ),
                    cache_write_price_per_million=(
                        float(price_entity.cache_write_price_per_million)
                        if price_entity is not None
                        else 0.0
                    ),
                )
            )

        return ModelPriceListResponse(
            items=items,
            last_synced_at=(
                last_synced_at.value
                if last_synced_at is not None and last_synced_at.value.strip()
                else None
            ),
        )

    async def upsert_model_price(self, payload: ModelPriceUpdate) -> ModelPriceItem:
        model_key = normalize_model_key(payload.model_key)
        if not model_key:
            raise ValueError("Model key is required")

        async with self._session_factory() as session:
            group_rows = (
                await session.execute(
                    select(
                        ModelGroupEntity.name,
                        ModelGroupEntity.protocols_json,
                    ).where(ModelGroupEntity.route_group_id == "")
                )
            ).all()
            matched_groups = [
                (
                    str(name),
                    _parse_group_protocols(str(protocols_json or "[]")),
                )
                for name, protocols_json in group_rows
                if normalize_model_key(str(name)) == model_key
            ]
            if not matched_groups:
                raise ValueError(
                    "Model price can only be maintained for existing model groups"
                )

            entity = await session.get(ModelPriceEntity, model_key)
            display_name = payload.display_name.strip() or matched_groups[0][0]
            if entity is None:
                entity = ModelPriceEntity(
                    model_key=model_key,
                    display_name=display_name,
                    input_price_per_million=float(payload.input_price_per_million),
                    output_price_per_million=float(payload.output_price_per_million),
                    cache_read_price_per_million=float(
                        payload.cache_read_price_per_million
                    ),
                    cache_write_price_per_million=float(
                        payload.cache_write_price_per_million
                    ),
                )
                session.add(entity)
            else:
                entity.display_name = display_name
                entity.input_price_per_million = float(payload.input_price_per_million)
                entity.output_price_per_million = float(
                    payload.output_price_per_million
                )
                entity.cache_read_price_per_million = float(
                    payload.cache_read_price_per_million
                )
                entity.cache_write_price_per_million = float(
                    payload.cache_write_price_per_million
                )

            await session.commit()

        protocols = sorted(
            {
                protocol
                for _, group_protocols in matched_groups
                for protocol in group_protocols
            },
            key=lambda value: value.value,
        )

        return ModelPriceItem(
            model_key=model_key,
            display_name=display_name,
            protocols=protocols,
            input_price_per_million=float(payload.input_price_per_million),
            output_price_per_million=float(payload.output_price_per_million),
            cache_read_price_per_million=float(payload.cache_read_price_per_million),
            cache_write_price_per_million=float(payload.cache_write_price_per_million),
        )

    async def set_model_price_sync_time(self, value: str) -> None:
        async with self._session_factory() as session:
            entity = await session.get(SettingEntity, SETTING_MODEL_PRICE_LAST_SYNC_AT)
            if entity is None:
                session.add(
                    SettingEntity(key=SETTING_MODEL_PRICE_LAST_SYNC_AT, value=value)
                )
            else:
                entity.value = value
            await session.commit()

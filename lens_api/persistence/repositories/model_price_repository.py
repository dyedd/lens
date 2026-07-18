from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..shared import (
    ModelGroupEntity,
    ModelPriceEntity,
    ModelPriceItem,
    ModelPriceListResponse,
    ModelPriceUpdate,
    ProtocolKind,
    SETTING_MODEL_PRICE_LAST_SYNC_AT,
    SettingEntity,
    _parse_group_protocols,
    normalize_model_key,
)


def _model_price_entity(
    item: dict[str, int | float | str],
) -> ModelPriceEntity | None:
    key = normalize_model_key(str(item.get("model_key") or ""))
    if not key:
        return None
    return ModelPriceEntity(
        model_key=key,
        display_name=str(item.get("display_name") or key),
        input_price_per_million=float(item.get("input_price_per_million") or 0.0),
        output_price_per_million=float(item.get("output_price_per_million") or 0.0),
        cache_read_price_per_million=float(
            item.get("cache_read_price_per_million") or 0.0
        ),
        cache_write_price_per_million=float(
            item.get("cache_write_price_per_million") or 0.0
        ),
    )


async def _replace_model_prices(
    session_factory: async_sessionmaker[AsyncSession],
    model_prices: list[dict[str, int | float | str]],
) -> None:
    async with session_factory() as session:
        await session.execute(delete(ModelPriceEntity))
        for item in model_prices:
            entity = _model_price_entity(item)
            if entity is not None:
                session.add(entity)
        await session.commit()


async def _sync_model_prices(
    session_factory: async_sessionmaker[AsyncSession],
    model_prices: list[dict[str, int | float | str]],
    *,
    overwrite_existing: bool,
    allowed_keys: list[str] | None,
) -> None:
    async with session_factory() as session:
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
                new_entity = _model_price_entity(item)
                if new_entity is not None:
                    session.add(new_entity)
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


async def _set_model_price_sync_time(
    session_factory: async_sessionmaker[AsyncSession], value: str
) -> None:
    async with session_factory() as session:
        entity = await session.get(SettingEntity, SETTING_MODEL_PRICE_LAST_SYNC_AT)
        if entity is None:
            session.add(
                SettingEntity(key=SETTING_MODEL_PRICE_LAST_SYNC_AT, value=value)
            )
        else:
            entity.value = value
        await session.commit()


class ModelPriceRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def estimate_model_cost(
        self,
        model_name: str | None,
        input_tokens: int,
        output_tokens: int,
        cache_read_input_tokens: int = 0,
        cache_write_input_tokens: int = 0,
    ) -> tuple[float, float, float]:
        """Estimate input, output, and total cost for a priced model."""
        if not model_name:
            return 0.0, 0.0, 0.0

        async with self._session_factory() as session:
            entity = await session.get(
                ModelPriceEntity, normalize_model_key(model_name)
            )
            if entity is None:
                return 0.0, 0.0, 0.0

        total_input_tokens = max(input_tokens, 0)
        cache_read_tokens = max(cache_read_input_tokens, 0)
        cache_write_tokens = max(cache_write_input_tokens, 0)
        regular_input_tokens = max(
            total_input_tokens - cache_read_tokens - cache_write_tokens, 0
        )

        input_cost = (regular_input_tokens / 1_000_000) * float(
            entity.input_price_per_million
        )
        input_cost += (cache_read_tokens / 1_000_000) * float(
            entity.cache_read_price_per_million
        )
        input_cost += (cache_write_tokens / 1_000_000) * float(
            entity.cache_write_price_per_million
        )
        output_cost = (max(output_tokens, 0) / 1_000_000) * float(
            entity.output_price_per_million
        )
        total_cost = input_cost + output_cost
        return round(input_cost, 8), round(output_cost, 8), round(total_cost, 8)

    async def list_model_prices(self) -> ModelPriceListResponse:
        """Return model group prices and the latest synchronization time."""
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
        """Create or update pricing for an existing model group."""
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

    async def replace_model_prices(
        self, model_prices: list[dict[str, int | float | str]]
    ) -> None:
        """Replace all persisted model prices with the supplied entries."""
        await _replace_model_prices(self._session_factory, model_prices)

    async def sync_model_prices(
        self,
        model_prices: list[dict[str, int | float | str]],
        *,
        overwrite_existing: bool,
        allowed_keys: list[str] | None = None,
    ) -> None:
        """Synchronize model prices and optionally remove disallowed entries."""
        await _sync_model_prices(
            self._session_factory,
            model_prices,
            overwrite_existing=overwrite_existing,
            allowed_keys=allowed_keys,
        )

    async def set_model_price_sync_time(self, value: str) -> None:
        """Persist the latest model price synchronization time."""
        await _set_model_price_sync_time(self._session_factory, value)

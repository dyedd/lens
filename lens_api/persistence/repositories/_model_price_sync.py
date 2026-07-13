from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..shared import (
    ModelPriceEntity,
    SETTING_MODEL_PRICE_LAST_SYNC_AT,
    SettingEntity,
    normalize_model_key,
)


def _model_price_entity(item: dict[str, int | float | str]) -> ModelPriceEntity | None:
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

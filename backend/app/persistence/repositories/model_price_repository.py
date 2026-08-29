from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.model_prices import canonical_model_price_key
from app.models.model_prices import (
    ModelPriceItem,
    ModelPriceListResponse,
    ModelPriceUpdate,
)
from app.models.protocols import ProtocolKind
from app.persistence.entities import (
    ModelGroupEntity,
    ModelGroupItemEntity,
    ModelPriceEntity,
    SettingEntity,
)
from app.persistence.settings_keys import SETTING_MODEL_PRICE_LAST_SYNC_AT

from ...core.protocol_reachability import infer_client_protocols
from ...core.runtime_channel_ids import split_runtime_channel_id


@dataclass(frozen=True, slots=True)
class ModelCostEstimate:
    input_cost_usd: float = 0.0
    output_cost_usd: float = 0.0
    total_cost_usd: float = 0.0
    billing_mode: str = "tokens"
    billing_units: int = 0


def _model_price_entity(
    item: dict[str, int | float | str],
) -> ModelPriceEntity | None:
    key = canonical_model_price_key(str(item.get("model_key") or ""))
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
        image_price_per_image=float(item.get("image_price_per_image") or 0.0),
        pricing_mode=str(item.get("pricing_mode") or "tokens"),
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
    synced_at: str,
    allowed_keys: list[str],
) -> None:
    async with session_factory() as session:
        existing_rows = (
            (await session.execute(select(ModelPriceEntity))).scalars().all()
        )
        entities_by_key = {item.model_key: item for item in existing_rows}

        for item in model_prices:
            key = canonical_model_price_key(str(item.get("model_key") or ""))
            if not key:
                continue
            entity = entities_by_key.get(key)
            if entity is None:
                new_entity = _model_price_entity(item)
                if new_entity is not None:
                    session.add(new_entity)
                continue
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
            entity.image_price_per_image = float(
                item.get("image_price_per_image") or 0.0
            )
            entity.pricing_mode = str(item.get("pricing_mode") or "tokens")

        canonical_allowed_keys = {
            canonical_model_price_key(item)
            for item in allowed_keys
            if canonical_model_price_key(item)
        }
        if canonical_allowed_keys:
            await session.execute(
                delete(ModelPriceEntity).where(
                    ModelPriceEntity.model_key.not_in(canonical_allowed_keys)
                )
            )
        else:
            await session.execute(delete(ModelPriceEntity))

        await _set_model_price_sync_time(session, synced_at)
        await session.commit()


async def _set_model_price_sync_time(session: AsyncSession, value: str) -> None:
    entity = await session.get(SettingEntity, SETTING_MODEL_PRICE_LAST_SYNC_AT)
    if entity is None:
        session.add(SettingEntity(key=SETTING_MODEL_PRICE_LAST_SYNC_AT, value=value))
    else:
        entity.value = value


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
        image_count: int = 0,
        rate_multiplier: float | None = None,
    ) -> ModelCostEstimate:
        """Estimate input, output, and total cost for a priced model."""
        if not model_name:
            return ModelCostEstimate()

        async with self._session_factory() as session:
            entity = await session.get(
                ModelPriceEntity, canonical_model_price_key(model_name)
            )
            if entity is None:
                return ModelCostEstimate()

        multiplier = 1.0 if rate_multiplier is None else float(rate_multiplier)

        if entity.pricing_mode == "non_tokens":
            billing_units = max(image_count, 0)
            output_cost = (
                billing_units * float(entity.image_price_per_image or 0.0) * multiplier
            )
            rounded_cost = round(output_cost, 8)
            return ModelCostEstimate(
                output_cost_usd=rounded_cost,
                total_cost_usd=rounded_cost,
                billing_mode="non_tokens",
                billing_units=billing_units,
            )

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
        input_cost *= multiplier
        output_cost *= multiplier
        total_cost = input_cost + output_cost
        return ModelCostEstimate(
            input_cost_usd=round(input_cost, 8),
            output_cost_usd=round(output_cost, 8),
            total_cost_usd=round(total_cost, 8),
        )

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
                    select(ModelGroupEntity.name, ModelGroupItemEntity.channel_id)
                    .outerjoin(
                        ModelGroupItemEntity,
                        ModelGroupItemEntity.group_id == ModelGroupEntity.id,
                    )
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
        for name, channel_id in group_rows:
            key = canonical_model_price_key(str(name))
            if not key:
                continue
            parsed = split_runtime_channel_id(str(channel_id))
            if parsed is not None:
                protocols_by_key.setdefault(key, set()).update(
                    infer_client_protocols([parsed[1]])
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
                    image_price_per_image=(
                        float(price_entity.image_price_per_image)
                        if price_entity is not None
                        else 0.0
                    ),
                    pricing_mode=(
                        price_entity.pricing_mode
                        if price_entity is not None
                        else "tokens"
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
        model_key = canonical_model_price_key(payload.model_key)
        if not model_key:
            raise ValueError("Model key is required")

        async with self._session_factory() as session:
            group_rows = (
                await session.execute(
                    select(
                        ModelGroupEntity.name,
                        ModelGroupItemEntity.channel_id,
                    )
                    .outerjoin(
                        ModelGroupItemEntity,
                        ModelGroupItemEntity.group_id == ModelGroupEntity.id,
                    )
                    .where(ModelGroupEntity.route_group_id == "")
                )
            ).all()
            matched_groups = [
                (
                    str(name),
                    (
                        parsed[1]
                        if (parsed := split_runtime_channel_id(str(channel_id)))
                        is not None
                        else None
                    ),
                )
                for name, channel_id in group_rows
                if canonical_model_price_key(str(name)) == model_key
            ]
            if not matched_groups:
                raise ValueError(
                    "Model price can only be maintained for existing model groups"
                )

            entity = await session.get(ModelPriceEntity, model_key)
            pricing_mode = payload.pricing_mode or (
                entity.pricing_mode if entity is not None else "tokens"
            )
            input_price = float(payload.input_price_per_million)
            output_price = float(payload.output_price_per_million)
            cache_read_price = float(payload.cache_read_price_per_million)
            cache_write_price = float(payload.cache_write_price_per_million)
            unit_price = float(payload.image_price_per_image)
            if pricing_mode == "non_tokens":
                input_price = output_price = cache_read_price = cache_write_price = 0.0
            else:
                unit_price = 0.0
            display_name = payload.display_name.strip() or matched_groups[0][0]
            if entity is None:
                entity = ModelPriceEntity(
                    model_key=model_key,
                    display_name=display_name,
                    input_price_per_million=input_price,
                    output_price_per_million=output_price,
                    cache_read_price_per_million=cache_read_price,
                    cache_write_price_per_million=cache_write_price,
                    image_price_per_image=unit_price,
                    pricing_mode=pricing_mode,
                )
                session.add(entity)
            else:
                entity.display_name = display_name
                entity.input_price_per_million = input_price
                entity.output_price_per_million = output_price
                entity.cache_read_price_per_million = cache_read_price
                entity.cache_write_price_per_million = cache_write_price
                entity.image_price_per_image = unit_price
                entity.pricing_mode = pricing_mode

            await session.commit()

        protocols = sorted(
            {
                protocol
                for _, upstream_protocol in matched_groups
                for protocol in infer_client_protocols(
                    [upstream_protocol] if upstream_protocol is not None else []
                )
            },
            key=lambda value: value.value,
        )

        return ModelPriceItem(
            model_key=model_key,
            display_name=display_name,
            protocols=protocols,
            input_price_per_million=input_price,
            output_price_per_million=output_price,
            cache_read_price_per_million=cache_read_price,
            cache_write_price_per_million=cache_write_price,
            image_price_per_image=unit_price,
            pricing_mode=pricing_mode,
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
        synced_at: str,
        allowed_keys: list[str],
    ) -> None:
        """Synchronize model prices and the source timestamp atomically."""
        await _sync_model_prices(
            self._session_factory,
            model_prices,
            synced_at=synced_at,
            allowed_keys=allowed_keys,
        )

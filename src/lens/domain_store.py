from __future__ import annotations

import json
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .entities import GatewayKeyEntity, ModelGroupEntity, SettingEntity
from .models import GatewayKey, GatewayKeyCreate, GatewayKeyUpdate, ModelGroup, ModelGroupCreate, ModelGroupUpdate, SettingItem


class DomainStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def list_groups(self) -> list[ModelGroup]:
        async with self._session_factory() as session:
            result = await session.execute(select(ModelGroupEntity).order_by(ModelGroupEntity.name))
            return [self._to_group(item) for item in result.scalars().all()]

    async def find_group_by_name(self, protocol: str, name: str | None) -> ModelGroup | None:
        if not name:
            return None

        async with self._session_factory() as session:
            result = await session.execute(
                select(ModelGroupEntity)
                .where(ModelGroupEntity.protocol == protocol)
                .where(ModelGroupEntity.name == name)
                .where(ModelGroupEntity.enabled == 1)
                .limit(1)
            )
            entity = result.scalar_one_or_none()
            if entity is None:
                return None
            return self._to_group(entity)

    async def create_group(self, payload: ModelGroupCreate) -> ModelGroup:
        async with self._session_factory() as session:
            next_id = await self._next_id(session, ModelGroupEntity, payload.protocol.value)
            entity = ModelGroupEntity(
                id=next_id,
                name=payload.name,
                protocol=payload.protocol.value,
                strategy=payload.strategy.value,
                provider_ids_json=json.dumps(payload.provider_ids, ensure_ascii=True),
                enabled=1 if payload.enabled else 0,
            )
            session.add(entity)
            await session.commit()
            return self._to_group(entity)

    async def update_group(self, group_id: str, payload: ModelGroupUpdate) -> ModelGroup:
        async with self._session_factory() as session:
            entity = await session.get(ModelGroupEntity, group_id)
            if entity is None:
                raise KeyError(group_id)

            changes = payload.model_dump(exclude_unset=True)
            for key, value in changes.items():
                if key == "protocol" and value is not None:
                    entity.protocol = value.value
                elif key == "strategy" and value is not None:
                    entity.strategy = value.value
                elif key == "provider_ids" and value is not None:
                    entity.provider_ids_json = json.dumps(value, ensure_ascii=True)
                elif key == "enabled" and value is not None:
                    entity.enabled = 1 if value else 0
                else:
                    setattr(entity, key, value)

            await session.commit()
            await session.refresh(entity)
            return self._to_group(entity)

    async def delete_group(self, group_id: str) -> None:
        async with self._session_factory() as session:
            entity = await session.get(ModelGroupEntity, group_id)
            if entity is None:
                raise KeyError(group_id)
            await session.delete(entity)
            await session.commit()

    async def list_gateway_keys(self) -> list[GatewayKey]:
        async with self._session_factory() as session:
            result = await session.execute(select(GatewayKeyEntity).order_by(GatewayKeyEntity.name))
            return [self._to_gateway_key(item) for item in result.scalars().all()]

    async def get_gateway_key_by_secret(self, secret: str) -> GatewayKey | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(GatewayKeyEntity)
                .where(GatewayKeyEntity.secret == secret)
                .where(GatewayKeyEntity.enabled == 1)
                .limit(1)
            )
            entity = result.scalar_one_or_none()
            if entity is None:
                return None
            return self._to_gateway_key(entity)

    async def create_gateway_key(self, payload: GatewayKeyCreate) -> GatewayKey:
        async with self._session_factory() as session:
            next_id = await self._next_id(session, GatewayKeyEntity, "gk")
            secret = f"sk-lens-{secrets.token_urlsafe(24)}"
            entity = GatewayKeyEntity(
                id=next_id,
                name=payload.name,
                secret=secret,
                enabled=1 if payload.enabled else 0,
            )
            session.add(entity)
            await session.commit()
            return self._to_gateway_key(entity)

    async def update_gateway_key(self, key_id: str, payload: GatewayKeyUpdate) -> GatewayKey:
        async with self._session_factory() as session:
            entity = await session.get(GatewayKeyEntity, key_id)
            if entity is None:
                raise KeyError(key_id)

            changes = payload.model_dump(exclude_unset=True)
            for key, value in changes.items():
                if key == "enabled" and value is not None:
                    entity.enabled = 1 if value else 0
                else:
                    setattr(entity, key, value)

            await session.commit()
            await session.refresh(entity)
            return self._to_gateway_key(entity)

    async def delete_gateway_key(self, key_id: str) -> None:
        async with self._session_factory() as session:
            entity = await session.get(GatewayKeyEntity, key_id)
            if entity is None:
                raise KeyError(key_id)
            await session.delete(entity)
            await session.commit()

    async def list_settings(self) -> list[SettingItem]:
        async with self._session_factory() as session:
            result = await session.execute(select(SettingEntity).order_by(SettingEntity.key))
            return [SettingItem(key=item.key, value=item.value) for item in result.scalars().all()]

    async def upsert_settings(self, items: list[SettingItem]) -> list[SettingItem]:
        async with self._session_factory() as session:
            for item in items:
                entity = await session.get(SettingEntity, item.key)
                if entity is None:
                    session.add(SettingEntity(key=item.key, value=item.value))
                else:
                    entity.value = item.value
            await session.commit()
            result = await session.execute(select(SettingEntity).order_by(SettingEntity.key))
            return [SettingItem(key=item.key, value=item.value) for item in result.scalars().all()]

    async def _next_id(self, session: AsyncSession, entity_type, prefix: str) -> str:
        result = await session.execute(select(entity_type.id))
        existing_ids = set(result.scalars().all())
        next_number = len(existing_ids) + 1
        next_id = f"{prefix}-{next_number}"
        while next_id in existing_ids:
            next_number += 1
            next_id = f"{prefix}-{next_number}"
        return next_id

    @staticmethod
    def _to_group(entity: ModelGroupEntity) -> ModelGroup:
        return ModelGroup(
            id=entity.id,
            name=entity.name,
            protocol=entity.protocol,
            strategy=entity.strategy,
            provider_ids=json.loads(entity.provider_ids_json),
            enabled=bool(entity.enabled),
        )

    @staticmethod
    def _to_gateway_key(entity: GatewayKeyEntity) -> GatewayKey:
        return GatewayKey(
            id=entity.id,
            name=entity.name,
            secret=entity.secret,
            enabled=bool(entity.enabled),
        )

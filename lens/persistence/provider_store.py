from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..models import ProviderConfig, ProviderCreate, ProviderStatus, ProviderUpdate
from .entities import ProviderEntity


class ProviderStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def list(self) -> list[ProviderConfig]:
        async with self._session_factory() as session:
            result = await session.execute(select(ProviderEntity).order_by(ProviderEntity.priority, ProviderEntity.name))
            entities = result.scalars().all()
            return [self._to_model(entity) for entity in entities]

    async def create(self, payload: ProviderCreate) -> ProviderConfig:
        async with self._session_factory() as session:
            next_id = await self._next_provider_id(session, payload.protocol.value)
            entity = ProviderEntity(
                id=next_id,
                name=payload.name,
                protocol=payload.protocol.value,
                base_url=str(payload.base_url),
                api_key=payload.api_key,
                model_name=payload.model_name,
                status=payload.status.value,
                weight=payload.weight,
                priority=payload.priority,
                headers_json=json.dumps(payload.headers, ensure_ascii=True),
                model_patterns_json=json.dumps(payload.model_patterns, ensure_ascii=True),
            )
            session.add(entity)
            await session.commit()
            return self._to_model(entity)

    async def update(self, provider_id: str, payload: ProviderUpdate) -> ProviderConfig:
        async with self._session_factory() as session:
            entity = await session.get(ProviderEntity, provider_id)
            if entity is None:
                raise KeyError(provider_id)

            changes = payload.model_dump(exclude_unset=True)
            for key, value in changes.items():
                if key == "base_url" and value is not None:
                    entity.base_url = str(value)
                elif key == "status" and value is not None:
                    entity.status = value.value
                elif key == "headers" and value is not None:
                    entity.headers_json = json.dumps(value, ensure_ascii=True)
                elif key == "model_patterns" and value is not None:
                    entity.model_patterns_json = json.dumps(value, ensure_ascii=True)
                else:
                    setattr(entity, key, value)

            await session.commit()
            await session.refresh(entity)
            return self._to_model(entity)

    async def delete(self, provider_id: str) -> None:
        async with self._session_factory() as session:
            entity = await session.get(ProviderEntity, provider_id)
            if entity is None:
                raise KeyError(provider_id)

            await session.delete(entity)
            await session.commit()

    async def _next_provider_id(self, session: AsyncSession, protocol: str) -> str:
        result = await session.execute(select(ProviderEntity.id))
        existing_ids = set(result.scalars().all())

        next_number = len(existing_ids) + 1
        next_id = f"{protocol}-{next_number}"
        while next_id in existing_ids:
            next_number += 1
            next_id = f"{protocol}-{next_number}"
        return next_id

    @staticmethod
    def _to_model(entity: ProviderEntity) -> ProviderConfig:
        return ProviderConfig(
            id=entity.id,
            name=entity.name,
            protocol=entity.protocol,
            base_url=entity.base_url,
            api_key=entity.api_key,
            model_name=entity.model_name,
            status=ProviderStatus(entity.status),
            weight=entity.weight,
            priority=entity.priority,
            headers=json.loads(entity.headers_json),
            model_patterns=json.loads(entity.model_patterns_json),
        )

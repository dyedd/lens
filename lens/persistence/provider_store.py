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
            result = await session.execute(select(ProviderEntity).order_by(ProviderEntity.name))
            entities = result.scalars().all()
            return [self._to_model(entity) for entity in entities]

    async def create(self, payload: ProviderCreate) -> ProviderConfig:
        async with self._session_factory() as session:
            next_id = await self._next_provider_id(session, payload.protocol.value)
            entity = ProviderEntity(
                id=next_id,
                name=payload.name,
                protocol=payload.protocol.value,
                base_url=str(self._first_base_url(payload.base_urls, payload.base_url)),
                api_key=self._first_api_key(payload.keys, payload.api_key),
                status=payload.status.value,
                headers_json=json.dumps(payload.headers, ensure_ascii=True),
                model_patterns_json=json.dumps(payload.model_patterns, ensure_ascii=True),
                base_urls_json=json.dumps([item.model_dump(mode="json") for item in self._normalize_base_urls(payload.base_urls, payload.base_url)], ensure_ascii=True),
                keys_json=json.dumps([item.model_dump(mode="json") for item in self._normalize_keys(payload.keys, payload.api_key)], ensure_ascii=True),
                proxy=1 if payload.proxy else 0,
                channel_proxy=payload.channel_proxy,
                param_override=payload.param_override,
                match_regex=payload.match_regex,
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
                if key == "protocol" and value is not None:
                    entity.protocol = value.value
                elif key == "base_url" and value is not None:
                    entity.base_url = str(value)
                elif key == "status" and value is not None:
                    entity.status = value.value
                elif key == "headers" and value is not None:
                    entity.headers_json = json.dumps(value, ensure_ascii=True)
                elif key == "model_patterns" and value is not None:
                    entity.model_patterns_json = json.dumps(value, ensure_ascii=True)
                elif key == "base_urls" and value is not None:
                    entity.base_urls_json = json.dumps([item.model_dump(mode="json") for item in value], ensure_ascii=True)
                    entity.base_url = str(value[0].url) if value else entity.base_url
                elif key == "keys" and value is not None:
                    entity.keys_json = json.dumps([item.model_dump(mode="json") for item in value], ensure_ascii=True)
                    enabled_key = next((item.key for item in value if item.enabled), value[0].key if value else None)
                    if enabled_key:
                        entity.api_key = enabled_key
                elif key == "proxy" and value is not None:
                    entity.proxy = 1 if value else 0
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
        base_urls = json.loads(entity.base_urls_json or "[]")
        keys = json.loads(entity.keys_json or "[]")
        if not base_urls and entity.base_url:
            base_urls = [{"url": entity.base_url, "delay": 0}]
        if not keys and entity.api_key:
            keys = [{"key": entity.api_key, "remark": "", "enabled": True}]
        return ProviderConfig(
            id=entity.id,
            name=entity.name,
            protocol=entity.protocol,
            base_url=entity.base_url,
            api_key=entity.api_key,
            status=ProviderStatus(entity.status),
            headers=json.loads(entity.headers_json),
            model_patterns=json.loads(entity.model_patterns_json),
            base_urls=base_urls,
            keys=keys,
            proxy=bool(entity.proxy),
            channel_proxy=entity.channel_proxy,
            param_override=entity.param_override,
            match_regex=entity.match_regex,
        )

    @staticmethod
    def _normalize_base_urls(base_urls, fallback_base_url):
        if base_urls:
            return base_urls
        return [{"url": str(fallback_base_url), "delay": 0}]

    @staticmethod
    def _normalize_keys(keys, fallback_api_key):
        if keys:
            return keys
        return [{"key": fallback_api_key, "remark": "", "enabled": True}]

    @staticmethod
    def _first_base_url(base_urls, fallback_base_url):
        if base_urls:
            return base_urls[0].url
        return fallback_base_url

    @staticmethod
    def _first_api_key(keys, fallback_api_key):
        if keys:
            for item in keys:
                if item.enabled:
                    return item.key
            return keys[0].key
        return fallback_api_key

from __future__ import annotations

import json
import uuid
from collections import defaultdict

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..models import (
    ChannelConfig,
    ChannelDiscoveredModel,
    ChannelKeyItem,
    ChannelStatus,
    SiteBaseUrl,
    SiteBaseUrlInput,
    SiteConfig,
    SiteCreate,
    SiteCredential,
    SiteCredentialInput,
    SiteModel,
    SiteModelFetchRequest,
    SiteProtocolConfig,
    SiteProtocolConfigInput,
    SiteProtocolCredentialBinding,
    SiteProtocolCredentialBindingInput,
    SiteUpdate,
)
from .entities import (
    ModelGroupItemEntity,
    SiteBaseUrlEntity,
    SiteCredentialEntity,
    SiteDiscoveredModelEntity,
    SiteEntity,
    SiteProtocolConfigEntity,
    SiteProtocolCredentialBindingEntity,
)


class ChannelStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def list(self) -> list[ChannelConfig]:
        sites = await self.list_sites()
        items: list[ChannelConfig] = []
        for site in sites:
            items.extend(self._flatten_site(site))
        return sorted(items, key=lambda item: (item.name.lower(), item.id))

    async def list_sites(self) -> list[SiteConfig]:
        async with self._session_factory() as session:
            return await self._load_sites(session)

    async def get_site(self, site_id: str) -> SiteConfig:
        async with self._session_factory() as session:
            sites = await self._load_sites(session, site_ids=[site_id])
            if not sites:
                raise KeyError(site_id)
            return sites[0]

    async def create_site(self, payload: SiteCreate) -> SiteConfig:
        async with self._session_factory() as session:
            await self._ensure_site_name_unique(session, payload.name)
            site_id = str(uuid.uuid4())
            await self._upsert_site_payload(session, site_id, payload.name, payload.base_urls, payload.credentials, payload.protocols)
            await session.commit()
        return await self.get_site(site_id)

    async def update_site(self, site_id: str, payload: SiteUpdate) -> SiteConfig:
        async with self._session_factory() as session:
            site = await self._get_site_entity(session, site_id)
            if site is None:
                raise KeyError(site_id)
            await self._ensure_site_name_unique(session, payload.name, exclude_site_id=site_id)
            await self._upsert_site_payload(session, site_id, payload.name, payload.base_urls, payload.credentials, payload.protocols)
            await session.commit()
        return await self.get_site(site_id)

    async def delete_site(self, site_id: str) -> None:
        async with self._session_factory() as session:
            site = await self._get_site_entity(session, site_id)
            if site is None:
                raise KeyError(site_id)

            protocol_ids = await self._site_protocol_ids(session, site_id)
            credential_ids = await self._site_credential_ids(session, site_id)
            if protocol_ids:
                await session.execute(delete(ModelGroupItemEntity).where(ModelGroupItemEntity.channel_id.in_(protocol_ids)))
                await session.execute(delete(SiteDiscoveredModelEntity).where(SiteDiscoveredModelEntity.protocol_config_id.in_(protocol_ids)))
                await session.execute(delete(SiteProtocolCredentialBindingEntity).where(SiteProtocolCredentialBindingEntity.protocol_config_id.in_(protocol_ids)))
                await session.execute(delete(SiteProtocolConfigEntity).where(SiteProtocolConfigEntity.id.in_(protocol_ids)))
            if credential_ids:
                await session.execute(delete(SiteCredentialEntity).where(SiteCredentialEntity.id.in_(credential_ids)))
            await session.execute(delete(SiteBaseUrlEntity).where(SiteBaseUrlEntity.site_id == site_id))
            await session.delete(site)
            await session.commit()

    async def fetch_models_preview(self, payload: SiteModelFetchRequest) -> list[dict[str, str]]:
        credentials = [
            SiteCredential(
                id=item.id or str(uuid.uuid4()),
                name=item.name.strip(),
                api_key=item.api_key,
                enabled=item.enabled,
                sort_order=index,
            )
            for index, item in enumerate(payload.credentials)
            if item.name.strip() and item.api_key.strip()
        ]
        credential_map = {item.id: item for item in credentials}
        binding_ids = [item.credential_id for item in payload.bindings if item.enabled and item.credential_id in credential_map]
        if not binding_ids:
            binding_ids = [item.id for item in credentials if item.enabled]
        return [{"credential_id": item_id, "credential_name": credential_map[item_id].name} for item_id in binding_ids]
    async def _load_sites(self, session: AsyncSession, site_ids: list[str] | None = None) -> list[SiteConfig]:
        site_query = select(SiteEntity).order_by(SiteEntity.name.asc())
        if site_ids is not None:
            site_query = site_query.where(SiteEntity.id.in_(site_ids))
        site_rows = (await session.execute(site_query)).scalars().all()
        if not site_rows:
            return []

        ids = [item.id for item in site_rows]
        base_url_rows = (
            await session.execute(
                select(SiteBaseUrlEntity)
                .where(SiteBaseUrlEntity.site_id.in_(ids))
                .order_by(SiteBaseUrlEntity.site_id.asc(), SiteBaseUrlEntity.sort_order.asc(), SiteBaseUrlEntity.id.asc())
            )
        ).scalars().all()
        credential_rows = (
            await session.execute(
                select(SiteCredentialEntity)
                .where(SiteCredentialEntity.site_id.in_(ids))
                .order_by(SiteCredentialEntity.site_id.asc(), SiteCredentialEntity.sort_order.asc(), SiteCredentialEntity.id.asc())
            )
        ).scalars().all()
        protocol_rows = (
            await session.execute(
                select(SiteProtocolConfigEntity)
                .where(SiteProtocolConfigEntity.site_id.in_(ids))
                .order_by(SiteProtocolConfigEntity.site_id.asc(), SiteProtocolConfigEntity.protocol.asc(), SiteProtocolConfigEntity.id.asc())
            )
        ).scalars().all()
        protocol_ids = [item.id for item in protocol_rows]
        binding_rows = []
        model_rows = []
        if protocol_ids:
            binding_rows = (
                await session.execute(
                    select(SiteProtocolCredentialBindingEntity)
                    .where(SiteProtocolCredentialBindingEntity.protocol_config_id.in_(protocol_ids))
                    .order_by(SiteProtocolCredentialBindingEntity.protocol_config_id.asc(), SiteProtocolCredentialBindingEntity.sort_order.asc(), SiteProtocolCredentialBindingEntity.id.asc())
                )
            ).scalars().all()
            model_rows = (
                await session.execute(
                    select(SiteDiscoveredModelEntity)
                    .where(SiteDiscoveredModelEntity.protocol_config_id.in_(protocol_ids))
                    .order_by(SiteDiscoveredModelEntity.protocol_config_id.asc(), SiteDiscoveredModelEntity.sort_order.asc(), SiteDiscoveredModelEntity.id.asc())
                )
            ).scalars().all()

        credentials_by_site: dict[str, list[SiteCredential]] = defaultdict(list)
        credentials_by_id: dict[str, SiteCredential] = {}

        base_urls_by_site: dict[str, list[SiteBaseUrl]] = defaultdict(list)
        for row in base_url_rows:
            base_urls_by_site[row.site_id].append(
                SiteBaseUrl(
                    id=row.id,
                    url=row.url,
                    name=row.name,
                    enabled=bool(row.enabled),
                    sort_order=row.sort_order,
                )
            )

        for row in credential_rows:
            item = SiteCredential(
                id=row.id,
                name=row.name,
                api_key=row.api_key,
                enabled=bool(row.enabled),
                sort_order=row.sort_order,
            )
            credentials_by_site[row.site_id].append(item)
            credentials_by_id[row.id] = item

        bindings_by_protocol: dict[str, list[SiteProtocolCredentialBinding]] = defaultdict(list)
        for row in binding_rows:
            credential = credentials_by_id.get(row.credential_id)
            bindings_by_protocol[row.protocol_config_id].append(
                SiteProtocolCredentialBinding(
                    credential_id=row.credential_id,
                    credential_name=credential.name if credential else '',
                    enabled=bool(row.enabled),
                    sort_order=row.sort_order,
                )
            )

        models_by_protocol: dict[str, list[SiteModel]] = defaultdict(list)
        for row in model_rows:
            credential = credentials_by_id.get(row.credential_id)
            models_by_protocol[row.protocol_config_id].append(
                SiteModel(
                    id=row.id,
                    credential_id=row.credential_id,
                    credential_name=credential.name if credential else '',
                    model_name=row.model_name,
                    enabled=bool(row.enabled),
                    sort_order=row.sort_order,
                )
            )

        protocols_by_site: dict[str, list[SiteProtocolConfig]] = defaultdict(list)
        for row in protocol_rows:
            protocols_by_site[row.site_id].append(
                SiteProtocolConfig(
                    id=row.id,
                    protocol=row.protocol,
                    enabled=bool(row.enabled),
                    headers=json.loads(row.headers_json or '{}'),
                    channel_proxy=row.channel_proxy,
                    param_override=row.param_override,
                    match_regex=row.match_regex,
                    base_url_id=row.base_url_id,
                    bindings=bindings_by_protocol.get(row.id, []),
                    models=models_by_protocol.get(row.id, []),
                )
            )

        return [
            SiteConfig(
                id=row.id,
                name=row.name,
                base_urls=base_urls_by_site.get(row.id, []),
                credentials=credentials_by_site.get(row.id, []),
                protocols=protocols_by_site.get(row.id, []),
            )
            for row in site_rows
        ]

    async def _upsert_site_payload(
        self,
        session: AsyncSession,
        site_id: str,
        name: str,
        base_urls: list[SiteBaseUrlInput],
        credentials: list[SiteCredentialInput],
        protocols: list[SiteProtocolConfigInput],
    ) -> None:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError('Site name is required')
        if not base_urls:
            raise ValueError('At least one base URL is required')
        if not protocols:
            raise ValueError('At least one protocol config is required')

        normalized_base_urls = self._normalize_base_urls(base_urls)
        normalized_credentials = self._normalize_credentials(credentials)
        credential_ids = {item.id for item in normalized_credentials}

        site = await self._get_site_entity(session, site_id)
        if site is None:
            session.add(SiteEntity(id=site_id, name=normalized_name))
        else:
            site.name = normalized_name

        await session.execute(delete(SiteBaseUrlEntity).where(SiteBaseUrlEntity.site_id == site_id))
        for index, item in enumerate(normalized_base_urls):
            session.add(
                SiteBaseUrlEntity(
                    id=item.id,
                    site_id=site_id,
                    url=str(item.url),
                    name=item.name,
                    enabled=1 if item.enabled else 0,
                    sort_order=index,
                )
            )

        current_protocol_ids = set(await self._site_protocol_ids(session, site_id))
        current_credential_ids = set(await self._site_credential_ids(session, site_id))
        next_protocol_ids: set[str] = set()
        next_credential_ids = {item.id for item in normalized_credentials}

        await session.execute(delete(SiteCredentialEntity).where(SiteCredentialEntity.site_id == site_id))
        for index, item in enumerate(normalized_credentials):
            session.add(
                SiteCredentialEntity(
                    id=item.id,
                    site_id=site_id,
                    name=item.name,
                    api_key=item.api_key,
                    enabled=1 if item.enabled else 0,
                    sort_order=index,
                )
            )

        protocol_keys: set[str] = set()
        for protocol in protocols:
            protocol_id = protocol.id or str(uuid.uuid4())
            next_protocol_ids.add(protocol_id)
            protocol_key = protocol.protocol.value
            if protocol_key in protocol_keys:
                raise ValueError(f'Duplicate protocol config for protocol={protocol.protocol.value}')
            protocol_keys.add(protocol_key)

            existing_protocol = await session.get(SiteProtocolConfigEntity, protocol_id)
            if existing_protocol is None:
                existing_protocol = SiteProtocolConfigEntity(
                    id=protocol_id,
                    site_id=site_id,
                    protocol=protocol.protocol.value,
                    enabled=1 if protocol.enabled else 0,
                    headers_json=json.dumps(protocol.headers, ensure_ascii=True),
                    channel_proxy=protocol.channel_proxy,
                    param_override=protocol.param_override,
                    match_regex=protocol.match_regex,
                    base_url_id=protocol.base_url_id,
                )
                session.add(existing_protocol)
            else:
                existing_protocol.site_id = site_id
                existing_protocol.protocol = protocol.protocol.value
                existing_protocol.enabled = 1 if protocol.enabled else 0
                existing_protocol.headers_json = json.dumps(protocol.headers, ensure_ascii=True)
                existing_protocol.channel_proxy = protocol.channel_proxy
                existing_protocol.param_override = protocol.param_override
                existing_protocol.match_regex = protocol.match_regex
                existing_protocol.base_url_id = protocol.base_url_id

            await session.execute(delete(SiteProtocolCredentialBindingEntity).where(SiteProtocolCredentialBindingEntity.protocol_config_id == protocol_id))
            bindings = protocol.bindings or [
                SiteProtocolCredentialBindingInput(credential_id=item.id, enabled=item.enabled)
                for item in normalized_credentials
            ]
            seen_binding_ids: set[str] = set()
            for binding_index, binding in enumerate(bindings):
                if binding.credential_id not in credential_ids:
                    raise ValueError(f'Credential not found for protocol config {protocol.protocol.value}: {binding.credential_id}')
                if binding.credential_id in seen_binding_ids:
                    raise ValueError(f'Duplicate credential binding in protocol config {protocol.protocol.value}: {binding.credential_id}')
                seen_binding_ids.add(binding.credential_id)
                session.add(
                    SiteProtocolCredentialBindingEntity(
                        id=str(uuid.uuid4()),
                        protocol_config_id=protocol_id,
                        credential_id=binding.credential_id,
                        enabled=1 if binding.enabled else 0,
                        sort_order=binding_index,
                    )
                )

            await session.execute(delete(SiteDiscoveredModelEntity).where(SiteDiscoveredModelEntity.protocol_config_id == protocol_id))
            seen_models: set[tuple[str, str]] = set()
            for model_index, model in enumerate(protocol.models):
                model_name = model.model_name.strip()
                if not model_name:
                    raise ValueError(f'Model name is required in protocol config {protocol.protocol.value}')
                if model.credential_id not in credential_ids:
                    raise ValueError(f'Model credential not found in protocol config {protocol.protocol.value}: {model.credential_id}')
                model_key = (model.credential_id, model_name)
                if model_key in seen_models:
                    raise ValueError(f'Duplicate model in protocol config {protocol.protocol.value}: {model_name}')
                seen_models.add(model_key)
                session.add(
                    SiteDiscoveredModelEntity(
                        id=model.id or str(uuid.uuid4()),
                        protocol_config_id=protocol_id,
                        credential_id=model.credential_id,
                        model_name=model_name,
                        enabled=1 if model.enabled else 0,
                        sort_order=model_index,
                    )
                )

        deleted_protocol_ids = current_protocol_ids - next_protocol_ids
        if deleted_protocol_ids:
            await session.execute(delete(ModelGroupItemEntity).where(ModelGroupItemEntity.channel_id.in_(deleted_protocol_ids)))
            await session.execute(delete(SiteDiscoveredModelEntity).where(SiteDiscoveredModelEntity.protocol_config_id.in_(deleted_protocol_ids)))
            await session.execute(delete(SiteProtocolCredentialBindingEntity).where(SiteProtocolCredentialBindingEntity.protocol_config_id.in_(deleted_protocol_ids)))
            await session.execute(delete(SiteProtocolConfigEntity).where(SiteProtocolConfigEntity.id.in_(deleted_protocol_ids)))

        deleted_credential_ids = current_credential_ids - next_credential_ids
        if deleted_credential_ids:
            await session.execute(delete(SiteCredentialEntity).where(SiteCredentialEntity.id.in_(deleted_credential_ids)))

    def _flatten_site(self, site: SiteConfig) -> list[ChannelConfig]:
        credentials_by_id = {item.id: item for item in site.credentials}
        base_urls_by_id = {item.id: item for item in site.base_urls}
        default_base_url = next((item.url for item in site.base_urls if item.enabled), site.base_urls[0].url if site.base_urls else 'http://localhost')
        items: list[ChannelConfig] = []
        for protocol in site.protocols:
            bound_base_url = base_urls_by_id.get(protocol.base_url_id)
            active_base_url = bound_base_url.url if bound_base_url else default_base_url
            binding_credentials = [
                credentials_by_id[binding.credential_id]
                for binding in protocol.bindings
                if binding.credential_id in credentials_by_id
            ]
            keys = [
                ChannelKeyItem(
                    id=item.id,
                    key=item.api_key,
                    remark=item.name,
                    enabled=item.enabled,
                )
                for item in binding_credentials
            ]
            models = [
                ChannelDiscoveredModel(
                    id=item.id,
                    credential_id=item.credential_id,
                    credential_name=credentials_by_id[item.credential_id].name if item.credential_id in credentials_by_id else '',
                    model_name=item.model_name,
                    enabled=item.enabled,
                    sort_order=item.sort_order,
                )
                for item in protocol.models
            ]
            active_key = next((item for item in keys if item.enabled), keys[0] if keys else None)
            items.append(
                ChannelConfig(
                    id=protocol.id,
                    name=site.name,
                    protocol=protocol.protocol,
                    base_url=active_base_url,
                    api_key=active_key.key if active_key else 'placeholder-key',
                    status=ChannelStatus.ENABLED if protocol.enabled else ChannelStatus.DISABLED,
                    headers=protocol.headers,
                    model_patterns=[item.model_name for item in models if item.enabled],
                    keys=keys,
                    models=models,
                    channel_proxy=protocol.channel_proxy,
                    param_override=protocol.param_override,
                    match_regex=protocol.match_regex,
                )
            )
        return items

    def _normalize_credentials(self, items: list[SiteCredentialInput]) -> list[SiteCredential]:
        normalized: list[SiteCredential] = []
        seen_names: set[str] = set()
        for index, item in enumerate(items):
            name = item.name.strip()
            if not name:
                raise ValueError('Credential name is required')
            if name.lower() in seen_names:
                raise ValueError(f'Duplicate credential name: {name}')
            seen_names.add(name.lower())
            normalized.append(
                SiteCredential(
                    id=item.id or str(uuid.uuid4()),
                    name=name,
                    api_key=item.api_key,
                    enabled=item.enabled,
                    sort_order=index,
                )
            )
        if not normalized:
            raise ValueError('At least one credential is required')
        return normalized

    def _normalize_base_urls(self, items: list[SiteBaseUrlInput]) -> list[SiteBaseUrl]:
        normalized: list[SiteBaseUrl] = []
        for index, item in enumerate(items):
            url_str = str(item.url).strip()
            if not url_str:
                raise ValueError('Base URL is required')
            normalized.append(
                SiteBaseUrl(
                    id=item.id or str(uuid.uuid4()),
                    url=item.url,
                    name=item.name.strip(),
                    enabled=item.enabled,
                    sort_order=index,
                )
            )
        if not normalized:
            raise ValueError('At least one base URL is required')
        return normalized

    async def _ensure_site_name_unique(self, session: AsyncSession, name: str, exclude_site_id: str | None = None) -> None:
        normalized_name = name.strip()
        result = await session.execute(select(SiteEntity).where(SiteEntity.name == normalized_name).limit(1))
        row = result.scalar_one_or_none()
        if row is not None and row.id != exclude_site_id:
            raise ValueError(f'Site already exists: {normalized_name}')

    async def _site_protocol_ids(self, session: AsyncSession, site_id: str) -> list[str]:
        return list((await session.execute(select(SiteProtocolConfigEntity.id).where(SiteProtocolConfigEntity.site_id == site_id))).scalars().all())

    async def _site_credential_ids(self, session: AsyncSession, site_id: str) -> list[str]:
        return list((await session.execute(select(SiteCredentialEntity.id).where(SiteCredentialEntity.site_id == site_id))).scalars().all())

    async def _get_site_entity(self, session: AsyncSession, site_id: str) -> SiteEntity | None:
        return await session.get(SiteEntity, site_id)

from __future__ import annotations

import json
import uuid
from collections import defaultdict

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..models import (
    ChannelConfig,
    ChannelDiscoveredModel,
    ChannelKeyItem,
    ChannelStatus,
    ProtocolKind,
    SiteBaseUrl,
    SiteBaseUrlInput,
    SiteBatchImportError,
    SiteBatchImportRequest,
    SiteBatchImportResult,
    SiteBatchImportSkipped,
    SiteConfig,
    SiteCreate,
    SiteCredential,
    SiteCredentialInput,
    SiteImportItem,
    SiteImportModelInput,
    SiteModel,
    SiteModelInput,
    SiteModelFetchRequest,
    SiteModelInput,
    SiteProtocolConfig,
    SiteProtocolConfigInput,
    SiteUpdate,
)
from .entities import (
    ModelGroupItemEntity,
    SiteBaseUrlEntity,
    SiteCredentialEntity,
    SiteDiscoveredModelEntity,
    SiteEntity,
    SiteProtocolConfigEntity,
)


def _combo_model_key(model: SiteModelInput) -> tuple[str, str]:
    return (model.credential_id, model.model_name.strip())


def _composite_id_like(column, combo_id: str):
    """构造匹配复合 channel_id（{combo_id}_{protocol}）的 LIKE 条件。

    combo_id 可能来自客户端输入，其中的 LIKE 元字符（_ / %）必须转义，
    否则 'a_b' 这样的 id 会把 '_' 当通配符误匹配无关条目。分隔符与尾部
    通配符（\\_%）保持字面/通配语义，用显式 ESCAPE 区分。
    """
    escaped = combo_id.replace("\\", "\\\\").replace("_", "\\_").replace("%", "\\%")
    return column.like(f"{escaped}\\_%", escape="\\")



def _deduplicate_combo_models(models: list[SiteModelInput]) -> list[SiteModelInput]:
    deduplicated: list[SiteModelInput] = []
    indexes: dict[tuple[str, str, ProtocolKind | None], int] = {}
    none_indexes: dict[tuple[str, str], int] = {}
    model_keys_with_specific_protocols: set[tuple[str, str]] = set()
    discarded_indexes: set[int] = set()

    for model in models:
        model_key = _combo_model_key(model)
        protocol = model.protocol

        if protocol is None:
            if model_key in model_keys_with_specific_protocols:
                continue

            row_key = (*model_key, None)
            existing_index = indexes.get(row_key)
            if existing_index is None:
                indexes[row_key] = len(deduplicated)
                none_indexes[model_key] = len(deduplicated)
                deduplicated.append(model)
                continue

            existing = deduplicated[existing_index]
            deduplicated[existing_index] = existing.model_copy(
                update={
                    "id": existing.id or model.id,
                    "enabled": existing.enabled or model.enabled,
                    "protocol": None,
                }
            )
            continue

        model_keys_with_specific_protocols.add(model_key)
        none_index = none_indexes.pop(model_key, None)
        if none_index is not None:
            discarded_indexes.add(none_index)
            indexes.pop((*model_key, None), None)

        row_key = (*model_key, protocol)
        existing_index = indexes.get(row_key)
        if existing_index is None:
            indexes[row_key] = len(deduplicated)
            deduplicated.append(model)
            continue

        existing = deduplicated[existing_index]
        deduplicated[existing_index] = existing.model_copy(
            update={
                "id": existing.id or model.id,
                "enabled": existing.enabled or model.enabled,
                "protocol": protocol,
            }
        )

    return [
        model
        for index, model in enumerate(deduplicated)
        if index not in discarded_indexes
    ]


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
            await self._upsert_site_payload(
                session,
                site_id,
                payload.name,
                payload.base_urls,
                payload.credentials,
                payload.protocols,
            )
            await session.commit()
        return await self.get_site(site_id)

    async def update_site(self, site_id: str, payload: SiteUpdate) -> SiteConfig:
        async with self._session_factory() as session:
            site = await session.get(SiteEntity, site_id)
            if site is None:
                raise KeyError(site_id)
            await self._ensure_site_name_unique(
                session, payload.name, exclude_site_id=site_id
            )
            await self._upsert_site_payload(
                session,
                site_id,
                payload.name,
                payload.base_urls,
                payload.credentials,
                payload.protocols,
            )
            await session.commit()
        return await self.get_site(site_id)

    async def import_sites(
        self, payload: SiteBatchImportRequest
    ) -> SiteBatchImportResult:
        skipped: list[SiteBatchImportSkipped] = []
        errors: list[SiteBatchImportError] = []
        prepared: list[SiteCreate] = []

        if not payload.sites:
            errors.append(
                SiteBatchImportError(
                    index=0,
                    field="sites",
                    message="At least one site is required",
                )
            )
            return self._batch_import_result(
                committed=False,
                created=[],
                skipped=skipped,
                errors=errors,
            )

        async with self._session_factory() as session:
            existing_names = await self._site_name_keys(session)
            seen_names: set[str] = set()

            for index, item in enumerate(payload.sites):
                name = item.name.strip()
                if not name:
                    errors.append(
                        SiteBatchImportError(
                            index=index,
                            field="name",
                            message="Site name is required",
                        )
                    )
                    continue

                name_key = name.lower()
                if name_key in existing_names:
                    skipped.append(
                        SiteBatchImportSkipped(
                            index=index,
                            name=name,
                            reason="duplicate_name",
                        )
                    )
                    continue
                if name_key in seen_names:
                    skipped.append(
                        SiteBatchImportSkipped(
                            index=index,
                            name=name,
                            reason="duplicate_in_file",
                        )
                    )
                    continue

                site_payload, site_errors = self._import_item_to_site_create(
                    index, item
                )
                if site_errors:
                    errors.extend(site_errors)
                    continue

                if site_payload is not None:
                    prepared.append(site_payload)
                    seen_names.add(name_key)

            if errors or not prepared:
                return self._batch_import_result(
                    committed=False,
                    created=[],
                    skipped=skipped,
                    errors=errors,
                )

            site_ids: list[str] = []
            for site_payload in prepared:
                site_id = str(uuid.uuid4())
                await self._upsert_site_payload(
                    session,
                    site_id,
                    site_payload.name,
                    site_payload.base_urls,
                    site_payload.credentials,
                    site_payload.protocols,
                )
                site_ids.append(site_id)

            await session.commit()

        created = await self._load_sites_by_ids(site_ids)
        return self._batch_import_result(
            committed=bool(created),
            created=created,
            skipped=skipped,
            errors=errors,
        )

    async def delete_site(self, site_id: str) -> None:
        async with self._session_factory() as session:
            site = await session.get(SiteEntity, site_id)
            if site is None:
                raise KeyError(site_id)

            protocol_ids = await self._site_protocol_ids(session, site_id)
            credential_ids = await self._site_credential_ids(session, site_id)
            if protocol_ids:
                await session.execute(
                    delete(ModelGroupItemEntity).where(
                        or_(
                            *[
                                _composite_id_like(
                                    ModelGroupItemEntity.channel_id, pid
                                )
                                for pid in protocol_ids
                            ]
                        )
                    )
                )
                await session.execute(
                    delete(SiteDiscoveredModelEntity).where(
                        SiteDiscoveredModelEntity.protocol_config_id.in_(protocol_ids)
                    )
                )
                await session.execute(
                    delete(SiteProtocolConfigEntity).where(
                        SiteProtocolConfigEntity.id.in_(protocol_ids)
                    )
                )
            if credential_ids:
                await session.execute(
                    delete(SiteCredentialEntity).where(
                        SiteCredentialEntity.id.in_(credential_ids)
                    )
                )
            await session.execute(
                delete(SiteBaseUrlEntity).where(SiteBaseUrlEntity.site_id == site_id)
            )
            await session.delete(site)
            await session.commit()

    async def fetch_models_preview(
        self, payload: SiteModelFetchRequest
    ) -> list[dict[str, str]]:
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
        if payload.credential_id not in credential_map:
            raise ValueError(
                f"Credential not found for model discovery: {payload.credential_id}"
            )
        credential = credential_map[payload.credential_id]
        if not credential.enabled:
            raise ValueError(
                f"Credential is disabled for model discovery: {payload.credential_id}"
            )
        return [
            {
                "credential_id": credential.id,
                "credential_name": credential.name,
            }
        ]

    async def _load_sites(
        self, session: AsyncSession, site_ids: list[str] | None = None
    ) -> list[SiteConfig]:
        site_query = select(SiteEntity).order_by(SiteEntity.name.asc())
        if site_ids is not None:
            site_query = site_query.where(SiteEntity.id.in_(site_ids))
        site_rows = (await session.execute(site_query)).scalars().all()
        if not site_rows:
            return []

        ids = [item.id for item in site_rows]
        base_url_rows = (
            (
                await session.execute(
                    select(SiteBaseUrlEntity)
                    .where(SiteBaseUrlEntity.site_id.in_(ids))
                    .order_by(
                        SiteBaseUrlEntity.site_id.asc(),
                        SiteBaseUrlEntity.sort_order.asc(),
                        SiteBaseUrlEntity.id.asc(),
                    )
                )
            )
            .scalars()
            .all()
        )
        credential_rows = (
            (
                await session.execute(
                    select(SiteCredentialEntity)
                    .where(SiteCredentialEntity.site_id.in_(ids))
                    .order_by(
                        SiteCredentialEntity.site_id.asc(),
                        SiteCredentialEntity.sort_order.asc(),
                        SiteCredentialEntity.id.asc(),
                    )
                )
            )
            .scalars()
            .all()
        )
        protocol_rows = (
            (
                await session.execute(
                    select(SiteProtocolConfigEntity)
                    .where(SiteProtocolConfigEntity.site_id.in_(ids))
                    .order_by(
                        SiteProtocolConfigEntity.site_id.asc(),
                        SiteProtocolConfigEntity.id.asc(),
                    )
                )
            )
            .scalars()
            .all()
        )
        protocol_ids = [item.id for item in protocol_rows]
        model_rows = []
        if protocol_ids:
            model_rows = (
                (
                    await session.execute(
                        select(SiteDiscoveredModelEntity)
                        .where(
                            SiteDiscoveredModelEntity.protocol_config_id.in_(
                                protocol_ids
                            )
                        )
                        .order_by(
                            SiteDiscoveredModelEntity.protocol_config_id.asc(),
                            SiteDiscoveredModelEntity.sort_order.asc(),
                            SiteDiscoveredModelEntity.id.asc(),
                        )
                    )
                )
                .scalars()
                .all()
            )

        base_urls_by_site = self._group_base_urls(base_url_rows)
        credentials_by_site, credentials_by_id = self._group_credentials(
            credential_rows
        )
        models_by_protocol = self._group_models(model_rows, credentials_by_id)
        protocols_by_site = self._group_protocols(protocol_rows, models_by_protocol)

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

    async def _load_sites_by_ids(self, site_ids: list[str]) -> list[SiteConfig]:
        if not site_ids:
            return []
        async with self._session_factory() as session:
            sites = await self._load_sites(session, site_ids=site_ids)
        order = {site_id: index for index, site_id in enumerate(site_ids)}
        return sorted(sites, key=lambda item: order.get(item.id, len(order)))

    async def _site_name_keys(self, session: AsyncSession) -> set[str]:
        rows = (await session.execute(select(SiteEntity.name))).scalars().all()
        return {row.strip().lower() for row in rows if row.strip()}

    def _batch_import_result(
        self,
        *,
        committed: bool,
        created: list[SiteConfig],
        skipped: list[SiteBatchImportSkipped],
        errors: list[SiteBatchImportError],
    ) -> SiteBatchImportResult:
        return SiteBatchImportResult(
            committed=committed,
            created_count=len(created),
            skipped_count=len(skipped),
            error_count=len(errors),
            created=created,
            skipped=skipped,
            errors=errors,
        )

    def _import_item_to_site_create(
        self, index: int, item: SiteImportItem
    ) -> tuple[SiteCreate | None, list[SiteBatchImportError]]:
        errors: list[SiteBatchImportError] = []

        base_urls, base_url_refs = self._import_base_urls(index, item, errors)
        credentials, credential_refs = self._import_credentials(index, item, errors)
        protocols = self._import_protocols(
            index,
            item,
            base_url_refs,
            credential_refs,
            errors,
        )

        if errors:
            return None, errors

        return (
            SiteCreate(
                name=item.name.strip(),
                base_urls=base_urls,
                credentials=credentials,
                protocols=protocols,
            ),
            [],
        )

    def _import_base_urls(
        self,
        index: int,
        item: SiteImportItem,
        errors: list[SiteBatchImportError],
    ) -> tuple[list[SiteBaseUrlInput], dict[str, str]]:
        base_urls: list[SiteBaseUrlInput] = []
        refs: dict[str, str] = {}
        if not item.base_urls:
            errors.append(
                SiteBatchImportError(
                    index=index,
                    field="base_urls",
                    message="At least one base URL is required",
                )
            )
            return base_urls, refs

        for base_url_index, base_url in enumerate(item.base_urls):
            ref = self._import_ref(base_url.ref, "base_url", base_url_index)
            if ref in refs:
                errors.append(
                    SiteBatchImportError(
                        index=index,
                        field=f"base_urls.{base_url_index}.ref",
                        message=f"Duplicate base URL ref: {ref}",
                    )
                )
                continue
            base_url_id = str(uuid.uuid4())
            refs[ref] = base_url_id
            base_urls.append(
                SiteBaseUrlInput(
                    id=base_url_id,
                    url=base_url.url,
                    name=base_url.name.strip(),
                    enabled=base_url.enabled,
                )
            )
        return base_urls, refs

    def _import_credentials(
        self,
        index: int,
        item: SiteImportItem,
        errors: list[SiteBatchImportError],
    ) -> tuple[list[SiteCredentialInput], dict[str, str]]:
        credentials: list[SiteCredentialInput] = []
        refs: dict[str, str] = {}
        names: set[str] = set()
        if not item.credentials:
            errors.append(
                SiteBatchImportError(
                    index=index,
                    field="credentials",
                    message="At least one credential is required",
                )
            )
            return credentials, refs

        for credential_index, credential in enumerate(item.credentials):
            ref = self._import_ref(credential.ref, "credential", credential_index)
            if ref in refs:
                errors.append(
                    SiteBatchImportError(
                        index=index,
                        field=f"credentials.{credential_index}.ref",
                        message=f"Duplicate credential ref: {ref}",
                    )
                )
                continue

            api_key = credential.api_key.strip()
            if not api_key:
                errors.append(
                    SiteBatchImportError(
                        index=index,
                        field=f"credentials.{credential_index}.api_key",
                        message="Credential API key is required",
                    )
                )
                continue

            name = credential.name.strip() or f"Key {credential_index + 1}"
            name_key = name.lower()
            if name_key in names:
                errors.append(
                    SiteBatchImportError(
                        index=index,
                        field=f"credentials.{credential_index}.name",
                        message=f"Duplicate credential name: {name}",
                    )
                )
                continue
            names.add(name_key)

            credential_id = str(uuid.uuid4())
            refs[ref] = credential_id
            credentials.append(
                SiteCredentialInput(
                    id=credential_id,
                    name=name,
                    api_key=api_key,
                    enabled=credential.enabled,
                )
            )
        return credentials, refs

    def _import_protocols(
        self,
        index: int,
        item: SiteImportItem,
        base_url_refs: dict[str, str],
        credential_refs: dict[str, str],
        errors: list[SiteBatchImportError],
    ) -> list[SiteProtocolConfigInput]:
        protocols: list[SiteProtocolConfigInput] = []
        protocol_keys: set[tuple[str, str, str]] = set()
        if not item.protocols:
            errors.append(
                SiteBatchImportError(
                    index=index,
                    field="protocols",
                    message="At least one protocol config is required",
                )
            )
            return protocols

        for protocol_index, protocol in enumerate(item.protocols):
            base_url_id = self._resolve_import_ref(
                index,
                f"protocols.{protocol_index}.base_url_ref",
                protocol.base_url_ref,
                base_url_refs,
                "Base URL",
                errors,
            )
            credential_id = self._resolve_import_ref(
                index,
                f"protocols.{protocol_index}.credential_ref",
                protocol.credential_ref,
                credential_refs,
                "Credential",
                errors,
            )
            if not base_url_id or not credential_id:
                continue

            protocol_key = (protocol.protocol.value, base_url_id, credential_id)
            if protocol_key in protocol_keys:
                errors.append(
                    SiteBatchImportError(
                        index=index,
                        field=f"protocols.{protocol_index}",
                        message=(
                            "Duplicate protocol config for protocol="
                            f"{protocol.protocol.value}"
                        ),
                    )
                )
                continue
            protocol_keys.add(protocol_key)

            protocols.append(
                SiteProtocolConfigInput(
                    id=str(uuid.uuid4()),
                    protocol=protocol.protocol,
                    enabled=protocol.enabled,
                    headers={
                        key.strip(): value
                        for key, value in protocol.headers.items()
                        if key.strip()
                    },
                    channel_proxy=protocol.channel_proxy.strip(),
                    param_override=protocol.param_override.strip(),
                    match_regex=protocol.match_regex.strip(),
                    base_url_id=base_url_id,
                    credential_id=credential_id,
                    models=self._import_protocol_models(
                        index,
                        protocol_index,
                        protocol.models,
                        credential_id,
                        credential_refs,
                        errors,
                    ),
                )
            )
        return protocols

    def _import_protocol_models(
        self,
        index: int,
        protocol_index: int,
        models: list[SiteImportModelInput],
        protocol_credential_id: str,
        credential_refs: dict[str, str],
        errors: list[SiteBatchImportError],
    ) -> list[SiteModelInput]:
        model_inputs: list[SiteModelInput] = []
        seen_models: set[tuple[str, str]] = set()
        for model_index, model in enumerate(models):
            model_name = model.model_name.strip()
            if not model_name:
                errors.append(
                    SiteBatchImportError(
                        index=index,
                        field=f"protocols.{protocol_index}.models.{model_index}",
                        message="Model name is required",
                    )
                )
                continue

            credential_id = protocol_credential_id
            if model.credential_ref.strip():
                credential_id = self._resolve_import_ref(
                    index,
                    (
                        f"protocols.{protocol_index}.models."
                        f"{model_index}.credential_ref"
                    ),
                    model.credential_ref,
                    credential_refs,
                    "Credential",
                    errors,
                )
            if not credential_id:
                continue

            model_key = (credential_id, model_name)
            if model_key in seen_models:
                errors.append(
                    SiteBatchImportError(
                        index=index,
                        field=f"protocols.{protocol_index}.models.{model_index}",
                        message=f"Duplicate model in protocol config: {model_name}",
                    )
                )
                continue
            seen_models.add(model_key)
            model_inputs.append(
                SiteModelInput(
                    id=str(uuid.uuid4()),
                    credential_id=credential_id,
                    model_name=model_name,
                    enabled=model.enabled,
                )
            )
        return model_inputs

    def _resolve_import_ref(
        self,
        index: int,
        field: str,
        ref: str,
        refs: dict[str, str],
        label: str,
        errors: list[SiteBatchImportError],
    ) -> str:
        normalized_ref = ref.strip()
        if normalized_ref:
            value = refs.get(normalized_ref)
            if value:
                return value
            errors.append(
                SiteBatchImportError(
                    index=index,
                    field=field,
                    message=f"{label} ref not found: {normalized_ref}",
                )
            )
            return ""

        if len(refs) == 1:
            return next(iter(refs.values()))

        errors.append(
            SiteBatchImportError(
                index=index,
                field=field,
                message=f"{label} ref is required",
            )
        )
        return ""

    @staticmethod
    def _import_ref(value: str, prefix: str, index: int) -> str:
        return value.strip() or f"{prefix}:{index}"

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
            raise ValueError("Site name is required")
        if not base_urls:
            raise ValueError("At least one base URL is required")

        normalized_base_urls = self._normalize_base_urls(base_urls)
        normalized_credentials = self._normalize_credentials(credentials)
        credential_ids = {item.id for item in normalized_credentials}
        base_url_ids = {item.id for item in normalized_base_urls}

        site = await session.get(SiteEntity, site_id)
        if site is None:
            session.add(SiteEntity(id=site_id, name=normalized_name))
        else:
            site.name = normalized_name

        await self._upsert_base_urls(session, site_id, normalized_base_urls)
        current_protocol_ids = set(await self._site_protocol_ids(session, site_id))
        current_credential_ids = set(await self._site_credential_ids(session, site_id))
        next_credential_ids = {item.id for item in normalized_credentials}
        await self._upsert_credentials(session, site_id, normalized_credentials)

        next_protocol_ids = await self._upsert_protocols(
            session,
            site_id,
            protocols,
            credential_ids,
            base_url_ids,
        )

        await self._cleanup_deleted_protocols(
            session, current_protocol_ids - next_protocol_ids
        )
        await self._cleanup_deleted_credentials(
            session, current_credential_ids - next_credential_ids
        )
        await self._cleanup_invalid_group_items(session, next_protocol_ids)

    def _flatten_site(self, site: SiteConfig) -> list[ChannelConfig]:
        credentials_by_id = {item.id: item for item in site.credentials}
        base_urls_by_id = {item.id: item for item in site.base_urls}
        items: list[ChannelConfig] = []
        for combo in site.protocols:
            bound_base_url = base_urls_by_id.get(combo.base_url_id)
            if bound_base_url is None:
                raise ValueError(
                    f"Base URL not found for combo {combo.id}: {combo.base_url_id}"
                )
            protocols = bound_base_url.compatible_protocols
            if not protocols:
                continue
            keys = self._build_channel_keys(combo, credentials_by_id)
            if not keys:
                continue
            active_key = next((k for k in keys if k.enabled), keys[0])
            for protocol in protocols:
                protocol_models = [
                    m for m in combo.models
                    if m.protocol == protocol or m.protocol is None
                ]
                items.append(
                    ChannelConfig(
                        id=f"{combo.id}_{protocol.value}",
                        name=site.name,
                        protocol=protocol,
                        base_url=bound_base_url.url,
                        api_key=active_key.key,
                        status=(
                            ChannelStatus.ENABLED
                            if combo.enabled
                            else ChannelStatus.DISABLED
                        ),
                        headers=combo.headers,
                        model_patterns=[
                            m.model_name for m in protocol_models if m.enabled
                        ],
                        keys=keys,
                        models=self._build_channel_models(combo, credentials_by_id, protocol),
                        channel_proxy=combo.channel_proxy,
                        param_override=combo.param_override,
                        match_regex=combo.match_regex,
                    )
                )
        return items

    def _build_channel_keys(
        self,
        protocol: SiteProtocolConfig,
        credentials_by_id: dict[str, SiteCredential],
    ) -> list[ChannelKeyItem]:
        credential_ids = list(
            dict.fromkeys(
                [protocol.credential_id]
                + [item.credential_id for item in protocol.models]
            )
        )
        return [
            ChannelKeyItem(
                id=credential.id,
                key=credential.api_key,
                remark=credential.name,
                enabled=credential.enabled,
            )
            for credential_id in credential_ids
            if credential_id and (credential := credentials_by_id.get(credential_id))
        ]

    def _build_channel_models(
        self,
        combo: SiteProtocolConfig,
        credentials_by_id: dict[str, SiteCredential],
        protocol: ProtocolKind,
    ) -> list[ChannelDiscoveredModel]:
        return [
            ChannelDiscoveredModel(
                id=item.id,
                credential_id=item.credential_id,
                credential_name=credentials_by_id[item.credential_id].name,
                model_name=item.model_name,
                enabled=item.enabled,
                sort_order=item.sort_order,
            )
            for item in combo.models
            if item.protocol == protocol or item.protocol is None
        ]

    def _normalize_credentials(
        self, items: list[SiteCredentialInput]
    ) -> list[SiteCredential]:
        normalized: list[SiteCredential] = []
        seen_names: set[str] = set()
        for index, item in enumerate(items):
            name = item.name.strip()
            if not name:
                raise ValueError("Credential name is required")
            name_key = name.lower()
            if name_key in seen_names:
                raise ValueError(f"Duplicate credential name: {name}")
            seen_names.add(name_key)
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
            raise ValueError("At least one credential is required")
        return normalized

    def _normalize_base_urls(self, items: list[SiteBaseUrlInput]) -> list[SiteBaseUrl]:
        normalized: list[SiteBaseUrl] = []
        for index, item in enumerate(items):
            url_str = str(item.url).strip()
            if not url_str:
                raise ValueError("Base URL is required")
            normalized.append(
                SiteBaseUrl(
                    id=item.id or str(uuid.uuid4()),
                    url=item.url,
                    name=item.name.strip(),
                    enabled=item.enabled,
                    sort_order=index,
                    compatible_protocols=list(dict.fromkeys(item.compatible_protocols)),
                )
            )
        return normalized

    async def _ensure_site_name_unique(
        self, session: AsyncSession, name: str, exclude_site_id: str | None = None
    ) -> None:
        normalized_name = name.strip()
        result = await session.execute(
            select(SiteEntity).where(SiteEntity.name == normalized_name).limit(1)
        )
        row = result.scalar_one_or_none()
        if row is not None and row.id != exclude_site_id:
            raise ValueError(f"Site already exists: {normalized_name}")

    async def _site_protocol_ids(
        self, session: AsyncSession, site_id: str
    ) -> list[str]:
        return list(
            (
                await session.execute(
                    select(SiteProtocolConfigEntity.id).where(
                        SiteProtocolConfigEntity.site_id == site_id
                    )
                )
            )
            .scalars()
            .all()
        )

    async def _site_credential_ids(
        self, session: AsyncSession, site_id: str
    ) -> list[str]:
        return list(
            (
                await session.execute(
                    select(SiteCredentialEntity.id).where(
                        SiteCredentialEntity.site_id == site_id
                    )
                )
            )
            .scalars()
            .all()
        )

    def _group_base_urls(
        self, rows: list[SiteBaseUrlEntity]
    ) -> dict[str, list[SiteBaseUrl]]:
        result: dict[str, list[SiteBaseUrl]] = defaultdict(list)
        valid_protocol_values = {pk.value for pk in ProtocolKind}
        for row in rows:
            result[row.site_id].append(
                SiteBaseUrl(
                    id=row.id,
                    url=row.url,
                    name=row.name,
                    enabled=bool(row.enabled),
                    sort_order=row.sort_order,
                    compatible_protocols=[
                        ProtocolKind(p)
                        for p in json.loads(row.compatible_protocols_json or "[]")
                        if p in valid_protocol_values
                    ],
                )
            )
        return result

    def _group_credentials(
        self, rows: list[SiteCredentialEntity]
    ) -> tuple[dict[str, list[SiteCredential]], dict[str, SiteCredential]]:
        by_site: dict[str, list[SiteCredential]] = defaultdict(list)
        by_id: dict[str, SiteCredential] = {}
        for row in rows:
            item = SiteCredential(
                id=row.id,
                name=row.name,
                api_key=row.api_key,
                enabled=bool(row.enabled),
                sort_order=row.sort_order,
            )
            by_site[row.site_id].append(item)
            by_id[row.id] = item
        return by_site, by_id

    def _group_models(
        self,
        rows: list[SiteDiscoveredModelEntity],
        credentials_by_id: dict[str, SiteCredential],
    ) -> dict[str, list[SiteModel]]:
        result: dict[str, list[SiteModel]] = defaultdict(list)
        valid_protocol_values = {pk.value for pk in ProtocolKind}
        for row in rows:
            credential = credentials_by_id.get(row.credential_id)
            result[row.protocol_config_id].append(
                SiteModel(
                    id=row.id,
                    credential_id=row.credential_id,
                    credential_name=credential.name if credential else "",
                    model_name=row.model_name,
                    enabled=bool(row.enabled),
                    sort_order=row.sort_order,
                    protocol=(
                        ProtocolKind(row.protocol)
                        if row.protocol in valid_protocol_values
                        else None
                    ),
                )
            )
        return result

    def _group_protocols(
        self,
        rows: list[SiteProtocolConfigEntity],
        models_by_protocol: dict[str, list[SiteModel]],
    ) -> dict[str, list[SiteProtocolConfig]]:
        result: dict[str, list[SiteProtocolConfig]] = defaultdict(list)
        for row in rows:
            result[row.site_id].append(
                SiteProtocolConfig(
                    id=row.id,
                    name=row.name,
                    enabled=bool(row.enabled),
                    headers=json.loads(row.headers_json),
                    channel_proxy=row.channel_proxy,
                    param_override=row.param_override,
                    match_regex=row.match_regex,
                    base_url_id=row.base_url_id,
                    credential_id=row.credential_id,
                    models=models_by_protocol.get(row.id, []),
                )
            )
        return result

    async def _upsert_base_urls(
        self, session: AsyncSession, site_id: str, items: list[SiteBaseUrl]
    ) -> None:
        await session.execute(
            delete(SiteBaseUrlEntity).where(SiteBaseUrlEntity.site_id == site_id)
        )
        for index, item in enumerate(items):
            session.add(
                SiteBaseUrlEntity(
                    id=item.id,
                    site_id=site_id,
                    url=str(item.url),
                    name=item.name,
                    enabled=int(item.enabled),
                    sort_order=index,
                    compatible_protocols_json=json.dumps(
                        [p.value for p in item.compatible_protocols], ensure_ascii=True
                    ),
                )
            )

    async def _upsert_credentials(
        self, session: AsyncSession, site_id: str, items: list[SiteCredential]
    ) -> None:
        await session.execute(
            delete(SiteCredentialEntity).where(SiteCredentialEntity.site_id == site_id)
        )
        for index, item in enumerate(items):
            session.add(
                SiteCredentialEntity(
                    id=item.id,
                    site_id=site_id,
                    name=item.name,
                    api_key=item.api_key,
                    enabled=int(item.enabled),
                    sort_order=index,
                )
            )

    async def _upsert_protocols(
        self,
        session: AsyncSession,
        site_id: str,
        protocols: list[SiteProtocolConfigInput],
        credential_ids: set[str],
        base_url_ids: set[str],
    ) -> set[str]:
        protocol_ids: set[str] = set()
        protocol_keys: set[tuple[str, str]] = set()
        for protocol in protocols:
            protocol_id = protocol.id or str(uuid.uuid4())
            protocol_ids.add(protocol_id)
            if protocol.base_url_id not in base_url_ids:
                raise ValueError(
                    f"Base URL not found for combo {protocol_id}: {protocol.base_url_id}"
                )
            if protocol.credential_id and protocol.credential_id not in credential_ids:
                raise ValueError(
                    f"Credential not found for combo {protocol_id}: {protocol.credential_id}"
                )
            protocol_key = (protocol.base_url_id, protocol.credential_id)
            if protocol_key in protocol_keys:
                raise ValueError(
                    f"Duplicate combo for base_url_id={protocol.base_url_id} credential_id={protocol.credential_id}"
                )
            protocol_keys.add(protocol_key)

            existing_protocol = await session.get(SiteProtocolConfigEntity, protocol_id)
            if existing_protocol is None:
                existing_protocol = SiteProtocolConfigEntity(id=protocol_id)
                session.add(existing_protocol)
            existing_protocol.site_id = site_id
            existing_protocol.name = protocol.name.strip()
            existing_protocol.enabled = int(protocol.enabled)
            existing_protocol.headers_json = json.dumps(
                protocol.headers, ensure_ascii=True
            )
            existing_protocol.channel_proxy = protocol.channel_proxy
            existing_protocol.param_override = protocol.param_override
            existing_protocol.match_regex = protocol.match_regex
            existing_protocol.base_url_id = protocol.base_url_id
            existing_protocol.credential_id = protocol.credential_id

            await self._upsert_protocol_models(
                session,
                protocol_id,
                protocol,
                credential_ids,
            )
        return protocol_ids

    async def _upsert_protocol_models(
        self,
        session: AsyncSession,
        protocol_id: str,
        protocol: SiteProtocolConfigInput,
        credential_ids: set[str],
    ) -> None:
        await session.execute(
            delete(SiteDiscoveredModelEntity).where(
                SiteDiscoveredModelEntity.protocol_config_id == protocol_id
            )
        )
        seen_models: set[tuple[str, str, str | None]] = set()
        seen_row_ids: set[str] = set()

        for model_index, model in enumerate(
            _deduplicate_combo_models(protocol.models)
        ):
            model_name = model.model_name.strip()
            if not model_name:
                raise ValueError(
                    f"Model name is required in combo {protocol_id}"
                )
            if model.credential_id not in credential_ids:
                raise ValueError(
                    f"Model credential not found in combo {protocol_id}: {model.credential_id}"
                )

            protocol_value = model.protocol.value if model.protocol else None
            model_key = (model.credential_id, model_name, protocol_value)
            if model_key in seen_models:
                raise ValueError(
                    f"Duplicate model in combo {protocol_id}: {model_name}"
                )
            seen_models.add(model_key)

            model_id = model.id
            if not model_id or model_id in seen_row_ids:
                model_id = str(uuid.uuid4())
            seen_row_ids.add(model_id)

            session.add(
                SiteDiscoveredModelEntity(
                    id=model_id,
                    protocol_config_id=protocol_id,
                    credential_id=model.credential_id,
                    model_name=model_name,
                    enabled=int(model.enabled),
                    sort_order=model_index,
                    protocol=protocol_value,
                )
            )

    async def _cleanup_deleted_protocols(
        self, session: AsyncSession, protocol_ids: set[str]
    ) -> None:
        if not protocol_ids:
            return
        await session.execute(
            delete(ModelGroupItemEntity).where(
                or_(
                    *[
                        _composite_id_like(ModelGroupItemEntity.channel_id, pid)
                        for pid in protocol_ids
                    ]
                )
            )
        )
        await session.execute(
            delete(SiteDiscoveredModelEntity).where(
                SiteDiscoveredModelEntity.protocol_config_id.in_(protocol_ids)
            )
        )
        await session.execute(
            delete(SiteProtocolConfigEntity).where(
                SiteProtocolConfigEntity.id.in_(protocol_ids)
            )
        )

    async def _cleanup_deleted_credentials(
        self, session: AsyncSession, credential_ids: set[str]
    ) -> None:
        if not credential_ids:
            return
        await session.execute(
            delete(SiteCredentialEntity).where(
                SiteCredentialEntity.id.in_(credential_ids)
            )
        )

    async def _cleanup_invalid_group_items(
        self, session: AsyncSession, protocol_ids: set[str]
    ) -> None:
        if not protocol_ids:
            return
        # 复合 channel_id 形如 {protocol_config_id}_{protocol}。一个 group item 有效，
        # 要求存在一个 enabled 模型行，且该行服务于 channel_id 所声明的具体协议：
        #   - model.protocol 为具体值 → channel_id 必须精确等于 {pid}_{model.protocol}
        #   - model.protocol 为 NULL（继承地址全部协议）→ channel_id 以 {pid}_ 开头即可
        # 仅判断 {pid}_% 而忽略协议，会让模型从 chat 移到 responses 后残留旧的
        # {pid}_openai_chat 条目。
        matching_model = (
            select(SiteDiscoveredModelEntity.id)
            .where(
                or_(
                    ModelGroupItemEntity.channel_id
                    == SiteDiscoveredModelEntity.protocol_config_id.concat("_").concat(
                        SiteDiscoveredModelEntity.protocol
                    ),
                    SiteDiscoveredModelEntity.protocol.is_(None)
                    & ModelGroupItemEntity.channel_id.like(
                        SiteDiscoveredModelEntity.protocol_config_id.concat("_%")
                    ),
                )
            )
            .where(
                SiteDiscoveredModelEntity.credential_id
                == ModelGroupItemEntity.credential_id
            )
            .where(
                SiteDiscoveredModelEntity.model_name == ModelGroupItemEntity.model_name
            )
            .where(SiteDiscoveredModelEntity.enabled == 1)
            .exists()
        )
        await session.execute(
            delete(ModelGroupItemEntity)
            .where(
                or_(
                    *[
                        _composite_id_like(ModelGroupItemEntity.channel_id, pid)
                        for pid in protocol_ids
                    ]
                )
            )
            .where(~matching_model)
        )

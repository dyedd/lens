from __future__ import annotations

from .shared import (
    AsyncSession,
    ChannelConfig,
    ModelGroupItemEntity,
    SiteBaseUrlEntity,
    SiteBatchImportError,
    SiteBatchImportRequest,
    SiteBatchImportResult,
    SiteBatchImportSkipped,
    SiteConfig,
    SiteCreate,
    SiteCredential,
    SiteCredentialEntity,
    SiteDiscoveredModelEntity,
    SiteEntity,
    SiteModelFetchRequest,
    SiteProtocolConfigEntity,
    SiteUpdate,
    _channel_id_matches_protocol_config,
    async_sessionmaker,
    delete,
    or_,
    uuid,
)
from .loaders import ChannelLoadersMixin
from .normalization import ChannelNormalizationMixin
from .site_import_normalization import ChannelSiteImportNormalizationMixin
from .upserts import ChannelUpsertsMixin


class ChannelStore(
    ChannelLoadersMixin,
    ChannelSiteImportNormalizationMixin,
    ChannelNormalizationMixin,
    ChannelUpsertsMixin,
):
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

            protocol_config_ids = await self._site_protocol_config_ids(session, site_id)
            credential_ids = await self._site_credential_ids(session, site_id)
            if protocol_config_ids:
                await session.execute(
                    delete(ModelGroupItemEntity).where(
                        or_(
                            *[
                                _channel_id_matches_protocol_config(
                                    ModelGroupItemEntity.channel_id, pid
                                )
                                for pid in protocol_config_ids
                            ]
                        )
                    )
                )
                await session.execute(
                    delete(SiteDiscoveredModelEntity).where(
                        SiteDiscoveredModelEntity.protocol_config_id.in_(
                            protocol_config_ids
                        )
                    )
                )
                await session.execute(
                    delete(SiteProtocolConfigEntity).where(
                        SiteProtocolConfigEntity.id.in_(protocol_config_ids)
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

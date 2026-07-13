from __future__ import annotations

from .shared import (
    SiteBatchImportError,
    SiteBatchImportRequest,
    SiteBatchImportResult,
    SiteBatchImportSkipped,
    SiteCreate,
    uuid,
)


class ChannelSiteBatchImportMixin:
    async def import_sites(
        self, payload: SiteBatchImportRequest
    ) -> SiteBatchImportResult:
        """Validate and atomically import a batch of site configurations."""
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

from __future__ import annotations

from .shared import (
    SiteBaseUrlInput,
    SiteBatchImportError,
    SiteBatchImportResult,
    SiteBatchImportSkipped,
    SiteConfig,
    SiteCreate,
    SiteCredentialInput,
    SiteImportItem,
    SiteImportModelInput,
    SiteModelInput,
    SiteProtocolConfigInput,
    ProtocolKind,
    uuid,
)
from .site_import_protocols import ChannelSiteImportProtocolsMixin


class ChannelSiteImportNormalizationMixin(ChannelSiteImportProtocolsMixin):
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

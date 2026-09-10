from __future__ import annotations

import uuid
from dataclasses import dataclass

from ...models.protocols import ProtocolKind
from ...models.site_import import (
    SiteBatchImportFieldError,
    SiteBatchImportItemResult,
    SiteBatchImportResult,
    SiteImportItem,
    SiteImportModelInput,
)
from ...models.sites import (
    SiteBaseUrlInput,
    SiteCreate,
    SiteCredentialInput,
    SiteModelInput,
    SiteProtocolConfigInput,
)


@dataclass(frozen=True)
class PreparedSiteImport:
    enabled: bool
    payload: SiteCreate


def prepare_site_import(
    item: SiteImportItem,
) -> tuple[PreparedSiteImport | None, list[SiteBatchImportFieldError]]:
    errors: list[SiteBatchImportFieldError] = []
    base_urls, base_url_refs = _import_base_urls(item, errors)
    credentials, credential_refs = _import_credentials(item, errors)
    if not item.protocols:
        errors.append(
            SiteBatchImportFieldError(
                field="protocols",
                message="At least one protocol config is required",
            )
        )
    if errors:
        return None, errors

    protocols = _import_protocols(
        item,
        base_url_refs,
        credential_refs,
        errors,
    )
    if errors:
        return None, errors

    return (
        PreparedSiteImport(
            enabled=item.enabled,
            payload=SiteCreate(
                name=item.name.strip(),
                tags=item.tags,
                base_urls=base_urls,
                credentials=credentials,
                protocols=protocols,
            ),
        ),
        [],
    )


def _import_base_urls(
    item: SiteImportItem,
    errors: list[SiteBatchImportFieldError],
) -> tuple[list[SiteBaseUrlInput], dict[str, str]]:
    base_urls: list[SiteBaseUrlInput] = []
    refs: dict[str, str] = {}
    if not item.base_urls:
        errors.append(
            SiteBatchImportFieldError(
                field="base_urls",
                message="At least one base URL is required",
            )
        )
        return base_urls, refs

    for base_url_index, base_url in enumerate(item.base_urls):
        ref = base_url.ref
        if ref in refs:
            errors.append(
                SiteBatchImportFieldError(
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
    item: SiteImportItem,
    errors: list[SiteBatchImportFieldError],
) -> tuple[list[SiteCredentialInput], dict[str, str]]:
    credentials: list[SiteCredentialInput] = []
    refs: dict[str, str] = {}
    names: set[str] = set()
    if not item.credentials:
        errors.append(
            SiteBatchImportFieldError(
                field="credentials",
                message="At least one credential is required",
            )
        )
        return credentials, refs

    for credential_index, credential in enumerate(item.credentials):
        ref = credential.ref
        if ref in refs:
            errors.append(
                SiteBatchImportFieldError(
                    field=f"credentials.{credential_index}.ref",
                    message=f"Duplicate credential ref: {ref}",
                )
            )
            continue

        api_key = credential.api_key.strip()
        if not api_key:
            errors.append(
                SiteBatchImportFieldError(
                    field=f"credentials.{credential_index}.api_key",
                    message="Credential API key is required",
                )
            )
            continue

        name = credential.name.strip() or f"Key {credential_index + 1}"
        name_key = name.lower()
        if name_key in names:
            errors.append(
                SiteBatchImportFieldError(
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
    item: SiteImportItem,
    base_url_refs: dict[str, str],
    credential_refs: dict[str, str],
    errors: list[SiteBatchImportFieldError],
) -> list[SiteProtocolConfigInput]:
    protocols: list[SiteProtocolConfigInput] = []
    protocol_keys: set[tuple[str, str, str]] = set()
    for protocol_index, protocol in enumerate(item.protocols):
        base_url_id = _resolve_import_ref(
            f"protocols.{protocol_index}.base_url_ref",
            protocol.base_url_ref,
            base_url_refs,
            "Base URL",
            errors,
        )
        credential_ids = [
            credential_id
            for credential_ref_index, credential_ref in enumerate(
                protocol.credential_refs
            )
            if (
                credential_id := _resolve_import_ref(
                    "protocols."
                    f"{protocol_index}.credential_refs.{credential_ref_index}",
                    credential_ref,
                    credential_refs,
                    "Credential",
                    errors,
                )
            )
            is not None
        ]
        if base_url_id is None or len(credential_ids) != len(protocol.credential_refs):
            continue

        has_duplicate = False
        for credential_id in credential_ids:
            protocol_key = (protocol.protocol.value, base_url_id, credential_id)
            if protocol_key in protocol_keys:
                errors.append(
                    SiteBatchImportFieldError(
                        field=f"protocols.{protocol_index}",
                        message=(
                            "Duplicate protocol config for protocol="
                            f"{protocol.protocol.value}"
                        ),
                    )
                )
                has_duplicate = True
            protocol_keys.add(protocol_key)
        if has_duplicate:
            continue

        models = _import_protocol_models(
            protocol_index,
            protocol.models,
            protocol.protocol,
            set(credential_ids),
            credential_refs,
            errors,
        )
        protocols.append(
            SiteProtocolConfigInput(
                id=str(uuid.uuid4()),
                name=protocol.name,
                protocols=[protocol.protocol],
                enabled=protocol.enabled,
                headers=protocol.headers,
                proxy_mode=protocol.proxy_mode,
                channel_proxy=protocol.channel_proxy.strip(),
                param_override=protocol.param_override,
                base_url_id=base_url_id,
                credential_ids=credential_ids,
                models=models,
                sync_targets=[
                    {
                        "credential_id": model.credential_id,
                        "model_name": model.model_name,
                        "protocol": model.protocol,
                    }
                    for model in models
                    if model.source.value == "synced"
                ],
            )
        )
    return protocols


def _import_protocol_models(
    protocol_index: int,
    models: list[SiteImportModelInput],
    protocol: ProtocolKind,
    protocol_credential_ids: set[str],
    credential_refs: dict[str, str],
    errors: list[SiteBatchImportFieldError],
) -> list[SiteModelInput]:
    model_inputs: list[SiteModelInput] = []
    seen_models: set[tuple[str, str]] = set()
    for model_index, model in enumerate(models):
        model_name = model.model_name.strip()
        if not model_name:
            errors.append(
                SiteBatchImportFieldError(
                    field=f"protocols.{protocol_index}.models.{model_index}",
                    message="Model name is required",
                )
            )
            continue

        credential_ref = model.credential_ref.strip()
        credential_id = _resolve_import_ref(
            f"protocols.{protocol_index}.models.{model_index}.credential_ref",
            credential_ref,
            credential_refs,
            "Credential",
            errors,
        )
        if credential_id is None:
            continue
        if credential_id not in protocol_credential_ids:
            errors.append(
                SiteBatchImportFieldError(
                    field=f"protocols.{protocol_index}.models.{model_index}.credential_ref",
                    message="Model credential is not selected by protocol config",
                )
            )
            continue

        model_key = (credential_id, model_name)
        if model_key in seen_models:
            errors.append(
                SiteBatchImportFieldError(
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
                protocol=protocol,
                source=model.source,
            )
        )
    return model_inputs


def _resolve_import_ref(
    field: str,
    ref: str,
    refs: dict[str, str],
    label: str,
    errors: list[SiteBatchImportFieldError],
) -> str | None:
    value = refs.get(ref)
    if value is not None:
        return value
    errors.append(
        SiteBatchImportFieldError(
            field=field,
            message=f"{label} ref not found: {ref}",
        )
    )
    return None


@dataclass
class PreparedSiteBatch:
    sites: dict[int, PreparedSiteImport]
    item_results: dict[int, SiteBatchImportItemResult]


def prepare_site_batch(
    sites: list[SiteImportItem],
    existing_names: set[str],
) -> PreparedSiteBatch:
    prepared_sites: dict[int, PreparedSiteImport] = {}
    item_results: dict[int, SiteBatchImportItemResult] = {}
    seen_names: set[str] = set()

    for index, site in enumerate(sites):
        name = site.name.strip()
        if not name:
            item_results[index] = SiteBatchImportItemResult(
                index=index,
                name=name,
                status="error",
                reason="",
                site=None,
                errors=[
                    SiteBatchImportFieldError(
                        field="name",
                        message="Site name is required",
                    )
                ],
            )
            continue

        name_key = name.lower()
        if name_key in existing_names:
            item_results[index] = SiteBatchImportItemResult(
                index=index,
                name=name,
                status="skipped",
                reason="duplicate_name",
                site=None,
                errors=[],
            )
            continue
        if name_key in seen_names:
            item_results[index] = SiteBatchImportItemResult(
                index=index,
                name=name,
                status="skipped",
                reason="duplicate_in_file",
                site=None,
                errors=[],
            )
            continue
        seen_names.add(name_key)

        prepared_site, errors = prepare_site_import(site)
        if errors:
            item_results[index] = SiteBatchImportItemResult(
                index=index,
                name=name,
                status="error",
                reason="",
                site=None,
                errors=errors,
            )
            continue
        assert prepared_site is not None
        prepared_sites[index] = prepared_site

    if any(result.status == "error" for result in item_results.values()):
        for index, prepared_site in prepared_sites.items():
            item_results[index] = SiteBatchImportItemResult(
                index=index,
                name=prepared_site.payload.name,
                status="not_committed",
                reason="batch_validation_failed",
                site=None,
                errors=[],
            )
        prepared_sites = {}

    return PreparedSiteBatch(sites=prepared_sites, item_results=item_results)


def build_site_batch_import_result(
    item_results: dict[int, SiteBatchImportItemResult],
) -> SiteBatchImportResult:
    items = [item_results[index] for index in sorted(item_results)]
    return SiteBatchImportResult(
        committed=any(item.status == "created" for item in items),
        created_count=sum(item.status == "created" for item in items),
        skipped_count=sum(item.status == "skipped" for item in items),
        error_count=sum(item.status == "error" for item in items),
        not_committed_count=sum(item.status == "not_committed" for item in items),
        items=items,
    )

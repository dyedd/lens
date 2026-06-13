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


class ChannelSiteImportNormalizationMixin:
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
                    protocols=[protocol.protocol],
                    enabled=protocol.enabled,
                    headers={
                        key.strip(): value
                        for key, value in protocol.headers.items()
                        if key.strip()
                    },
                    proxy_mode=protocol.proxy_mode,
                    channel_proxy=protocol.channel_proxy.strip(),
                    param_override=protocol.param_override.strip(),
                    match_regex=protocol.match_regex.strip(),
                    base_url_id=base_url_id,
                    credential_id=credential_id,
                    models=self._import_protocol_models(
                        index,
                        protocol_index,
                        protocol.models,
                        protocol.protocol,
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
        protocol: ProtocolKind,
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
                    protocol=protocol,
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

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.runtime_channel_ids import compose_runtime_channel_id
from app.models.sites import SiteConfig, SiteCredentialInput
from app.persistence.channel_store.endpoint_credentials import credential_ids_for_url
from app.persistence.entities import (
    SiteBaseUrlEntity,
    SiteCredentialEntity,
    SiteCredentialRateEntity,
    SiteDiscoveredModelEntity,
    SiteEntity,
    SiteProtocolConfigEntity,
)

from ..site_loader import build_site_configs, fetch_site_rows
from .serialize import parse_optional_datetime


async def load_sites(session: AsyncSession) -> list[SiteConfig]:
    return build_site_configs(await fetch_site_rows(session))


async def replace_sites(
    session: AsyncSession, sites: list[SiteConfig]
) -> tuple[set[str], set[tuple[str, str, str]]]:
    await session.execute(delete(SiteCredentialRateEntity))
    await session.execute(delete(SiteDiscoveredModelEntity))
    await session.execute(delete(SiteProtocolConfigEntity))
    await session.execute(delete(SiteCredentialEntity))
    await session.execute(delete(SiteBaseUrlEntity))
    await session.execute(delete(SiteEntity))

    site_ids: set[str] = set()
    site_names: set[str] = set()
    protocol_config_ids: set[str] = set()
    credential_ids: set[str] = set()
    model_keys: set[tuple[str, str, str]] = set()
    base_url_ids: set[str] = set()
    model_ids: set[str] = set()

    for site in sites:
        if site.id in site_ids:
            raise ValueError(f"Duplicate site id in backup: {site.id}")
        if site.name in site_names:
            raise ValueError(f"Duplicate site name in backup: {site.name}")
        site_ids.add(site.id)
        site_names.add(site.name)
        session.add(
            SiteEntity(
                id=site.id,
                name=site.name,
                enabled=int(site.enabled),
                tags_json=json.dumps(site.tags, ensure_ascii=True),
                updated_at=parse_optional_datetime(site.updated_at)
                or datetime.now(UTC).replace(tzinfo=None),
                headers_json=json.dumps(
                    [rule.model_dump(mode="json") for rule in site.headers],
                    ensure_ascii=True,
                ),
                proxy_mode=site.proxy_mode.value,
                channel_proxy=site.channel_proxy,
                param_override=json.dumps(
                    [rule.model_dump(mode="json") for rule in site.param_override],
                    ensure_ascii=True,
                ),
            )
        )
        site_base_url_ids: set[str] = set()
        site_base_url_kinds: set[str] = set()
        site_credential_ids: set[str] = set()
        rate_configs: dict[str, SiteCredentialInput] = {}

        for base_url in site.base_urls:
            if base_url.id in base_url_ids:
                raise ValueError(f"Duplicate base url id in backup: {base_url.id}")
            base_url_ids.add(base_url.id)
            site_base_url_ids.add(base_url.id)
            if base_url.kind in site_base_url_kinds:
                raise ValueError(
                    f"Duplicate endpoint purpose in backup site {site.name}: {base_url.kind}"
                )
            site_base_url_kinds.add(base_url.kind)
            session.add(
                SiteBaseUrlEntity(
                    id=base_url.id,
                    site_id=site.id,
                    url=str(base_url.url),
                    sort_order=base_url.sort_order,
                    kind=base_url.kind,
                )
            )

        for credential in site.credentials:
            if credential.id in credential_ids:
                raise ValueError(f"Duplicate credential id in backup: {credential.id}")
            rate_config = SiteCredentialInput.model_validate(
                {
                    "id": credential.id,
                    "name": credential.name,
                    "api_key": credential.api_key,
                    "base_url_id": credential.base_url_id,
                    "rate_source": credential.rate_source,
                    "rate_protocol_config_id": credential.rate_protocol_config_id,
                    "rate_group": credential.rate_group,
                }
            )
            rate_configs[credential.id] = rate_config
            if (
                credential.base_url_id
                and credential.base_url_id not in site_base_url_ids
            ):
                raise ValueError(
                    "Credential base URL not found in backup site "
                    f"{site.name}: {credential.base_url_id}"
                )
            credential_ids.add(credential.id)
            site_credential_ids.add(credential.id)
            session.add(
                SiteCredentialEntity(
                    id=credential.id,
                    site_id=site.id,
                    name=credential.name,
                    api_key=credential.api_key,
                    sort_order=credential.sort_order,
                    base_url_id=credential.base_url_id,
                    model_pattern=credential.model_pattern,
                )
            )

        seen_url_ids: set[str] = set()
        for protocol_config in site.protocols:
            if protocol_config.id in protocol_config_ids:
                raise ValueError(
                    f"Duplicate protocol config id in backup: {protocol_config.id}"
                )
            protocol_config_ids.add(protocol_config.id)
            if protocol_config.base_url_id not in site_base_url_ids:
                raise ValueError(
                    "Protocol config base URL not found in backup site "
                    f"{site.name}: {protocol_config.base_url_id}"
                )
            if protocol_config.base_url_id in seen_url_ids:
                raise ValueError(
                    "Duplicate protocol config for backup base URL "
                    f"{protocol_config.base_url_id}"
                )
            seen_url_ids.add(protocol_config.base_url_id)
            bound_credential_ids = set(
                credential_ids_for_url(
                    [(item.id, item.base_url_id) for item in site.credentials],
                    protocol_config.base_url_id,
                )
            )
            session.add(
                SiteProtocolConfigEntity(
                    id=protocol_config.id,
                    site_id=site.id,
                    base_url_id=protocol_config.base_url_id,
                    protocols_json=json.dumps(
                        [protocol.value for protocol in protocol_config.protocols],
                        ensure_ascii=True,
                    ),
                )
            )

            for model in protocol_config.models:
                if model.id in model_ids:
                    raise ValueError(
                        f"Duplicate discovered model id in backup: {model.id}"
                    )
                model_ids.add(model.id)
                if (
                    not model.credential_id
                    or model.credential_id not in bound_credential_ids
                ):
                    raise ValueError(
                        "Discovered model credential not found in backup site "
                        f"{site.name}: {model.credential_id}"
                    )
                if model.protocol is None:
                    raise ValueError(
                        "Discovered model protocol not found in backup site "
                        f"{site.name}: {model.model_name}"
                    )
                model_keys.add(
                    (
                        compose_runtime_channel_id(protocol_config.id, model.protocol),
                        model.credential_id,
                        model.model_name,
                    )
                )
                session.add(
                    SiteDiscoveredModelEntity(
                        id=model.id,
                        protocol_config_id=protocol_config.id,
                        credential_id=model.credential_id,
                        model_name=model.model_name,
                        enabled=1 if model.enabled else 0,
                        sort_order=model.sort_order,
                        protocol=model.protocol.value,
                        context_window=model.context_window,
                        upstream_context_window=model.upstream_context_window,
                    )
                )
        protocol_by_id = {protocol.id: protocol for protocol in site.protocols}
        for credential in site.credentials:
            rate_config = rate_configs[credential.id]
            if rate_config.rate_source == "none":
                continue
            protocol = protocol_by_id.get(rate_config.rate_protocol_config_id)
            if protocol is None:
                raise ValueError(
                    "Credential rate protocol config not found in backup site "
                    f"{site.name}: {rate_config.rate_protocol_config_id}"
                )
            bound_ids = set(
                credential_ids_for_url(
                    [(item.id, item.base_url_id) for item in site.credentials],
                    protocol.base_url_id,
                )
            )
            if credential.id not in bound_ids:
                raise ValueError(
                    "Credential rate protocol config not found in backup site "
                    f"{site.name}: {rate_config.rate_protocol_config_id}"
                )
            session.add(
                SiteCredentialRateEntity(
                    credential_id=credential.id,
                    protocol_config_id=rate_config.rate_protocol_config_id,
                    source=rate_config.rate_source,
                    group_name=rate_config.rate_group,
                    multiplier=None,
                    observed_at=None,
                    last_synced_at=None,
                    last_error="",
                )
            )

    return protocol_config_ids, model_keys

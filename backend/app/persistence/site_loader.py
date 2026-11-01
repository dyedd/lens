from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.protocols import ChannelProxyMode, ProtocolKind
from app.models.sites import (
    SiteBaseUrl,
    SiteConfig,
    SiteCredential,
    SiteModel,
    SiteProtocolConfig,
)
from app.models.upstream_rules import HeaderRule, ParamOverrideRule
from app.persistence.channel_store.endpoint_credentials import credential_ids_for_url
from app.persistence.entities import (
    SiteBaseUrlEntity,
    SiteCredentialEntity,
    SiteCredentialRateEntity,
    SiteDiscoveredModelEntity,
    SiteEntity,
    SiteProtocolConfigEntity,
)

from ..core.context_windows import coerce_context_window


@dataclass(frozen=True, slots=True)
class SiteRows:
    sites: list[SiteEntity]
    base_urls: list[SiteBaseUrlEntity]
    credentials: list[SiteCredentialEntity]
    credential_rates: list[SiteCredentialRateEntity]
    protocol_configs: list[SiteProtocolConfigEntity]
    discovered_models: list[SiteDiscoveredModelEntity]


def format_site_updated_at(value: datetime | None) -> str | None:
    """Format a site timestamp as UTC ISO-8601."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC).isoformat()
    return value.astimezone(UTC).isoformat()


def load_header_rules(raw: str | None) -> list[HeaderRule]:
    return [HeaderRule.model_validate(item) for item in json.loads(raw or "[]")]


def load_param_rules(raw: str | None) -> list[ParamOverrideRule]:
    return [ParamOverrideRule.model_validate(item) for item in json.loads(raw or "[]")]


def protocols_from_bindings(
    models: list[SiteModel],
    configured_protocols: list[ProtocolKind] | None = None,
) -> list[ProtocolKind]:
    protocols: list[ProtocolKind] = list(configured_protocols or [])
    for model in models:
        if model.protocol is not None and model.protocol not in protocols:
            protocols.append(model.protocol)
    return protocols


def credential_pairs(
    credentials: list[SiteCredential],
) -> list[tuple[str, str]]:
    return [(item.id, item.base_url_id) for item in credentials]


def build_site_configs(rows: SiteRows) -> list[SiteConfig]:
    """Map persisted site rows to the shared site configuration model."""
    if not rows.sites:
        return []

    base_urls_by_site: dict[str, list[SiteBaseUrl]] = defaultdict(list)
    for row in rows.base_urls:
        base_urls_by_site[row.site_id].append(
            SiteBaseUrl(
                id=row.id,
                url=row.url,
                sort_order=row.sort_order,
                kind=row.kind or "default",
            )
        )

    credentials_by_site: dict[str, list[SiteCredential]] = defaultdict(list)
    credentials_by_id: dict[str, SiteCredential] = {}
    rates_by_credential = {row.credential_id: row for row in rows.credential_rates}
    for row in rows.credentials:
        rate = rates_by_credential.get(row.id)
        item = SiteCredential(
            id=row.id,
            name=row.name,
            api_key=row.api_key,
            sort_order=row.sort_order,
            base_url_id=row.base_url_id,
            model_pattern=row.model_pattern,
            rate_source=rate.source if rate is not None else "none",
            rate_protocol_config_id=(
                rate.protocol_config_id if rate is not None else ""
            ),
            rate_group=rate.group_name if rate is not None else "",
            rate_multiplier=rate.multiplier if rate is not None else None,
            rate_observed_at=rate.observed_at if rate is not None else None,
            rate_last_synced_at=rate.last_synced_at if rate is not None else None,
            rate_last_error=rate.last_error if rate is not None else "",
        )
        credentials_by_site[row.site_id].append(item)
        credentials_by_id[row.id] = item

    models_by_protocol_config: dict[str, list[SiteModel]] = defaultdict(list)
    valid_protocol_values = {protocol_kind.value for protocol_kind in ProtocolKind}
    for row in rows.discovered_models:
        credential = credentials_by_id.get(row.credential_id)
        models_by_protocol_config[row.protocol_config_id].append(
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
                context_window=coerce_context_window(row.context_window),
                upstream_context_window=coerce_context_window(
                    row.upstream_context_window
                ),
            )
        )

    protocols_by_site: dict[str, list[SiteProtocolConfig]] = defaultdict(list)
    for row in rows.protocol_configs:
        models = models_by_protocol_config.get(row.id, [])
        try:
            configured_protocols = [
                ProtocolKind(value) for value in json.loads(row.protocols_json)
            ]
        except (TypeError, ValueError, json.JSONDecodeError):
            configured_protocols = []
        protocols_by_site[row.site_id].append(
            SiteProtocolConfig(
                id=row.id,
                base_url_id=row.base_url_id,
                protocols=protocols_from_bindings(models, configured_protocols),
                credential_ids=credential_ids_for_url(
                    [
                        (item.id, item.base_url_id)
                        for item in credentials_by_site.get(row.site_id, [])
                    ],
                    row.base_url_id,
                ),
                models=models,
            )
        )

    return [
        SiteConfig(
            id=row.id,
            name=row.name,
            enabled=bool(row.enabled),
            tags=json.loads(row.tags_json),
            updated_at=format_site_updated_at(row.updated_at),
            proxy_mode=ChannelProxyMode(row.proxy_mode),
            channel_proxy=row.channel_proxy,
            headers=load_header_rules(row.headers_json),
            param_override=load_param_rules(row.param_override),
            base_urls=base_urls_by_site.get(row.id, []),
            credentials=credentials_by_site.get(row.id, []),
            protocols=protocols_by_site.get(row.id, []),
        )
        for row in rows.sites
    ]


async def fetch_site_rows(
    session: AsyncSession, site_ids: list[str] | None = None
) -> SiteRows:
    """Load sites and their related configuration rows in stable order."""
    site_query = select(SiteEntity).order_by(SiteEntity.name.asc())
    if site_ids is not None:
        site_query = site_query.where(SiteEntity.id.in_(site_ids))
    site_rows = (await session.execute(site_query)).scalars().all()
    if not site_rows:
        return SiteRows([], [], [], [], [], [])

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
    credential_ids = [item.id for item in credential_rows]
    credential_rate_rows: list[SiteCredentialRateEntity] = []
    if credential_ids:
        credential_rate_rows = (
            (
                await session.execute(
                    select(SiteCredentialRateEntity).where(
                        SiteCredentialRateEntity.credential_id.in_(credential_ids)
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
    protocol_config_ids = [item.id for item in protocol_rows]
    model_rows: list[SiteDiscoveredModelEntity] = []
    if protocol_config_ids:
        model_rows = (
            (
                await session.execute(
                    select(SiteDiscoveredModelEntity)
                    .where(
                        SiteDiscoveredModelEntity.protocol_config_id.in_(
                            protocol_config_ids
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

    return SiteRows(
        sites=site_rows,
        base_urls=base_url_rows,
        credentials=credential_rows,
        credential_rates=credential_rate_rows,
        protocol_configs=protocol_rows,
        discovered_models=model_rows,
    )

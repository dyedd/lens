from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ..shared import (
    AsyncSession,
    ModelGroupEnsureModelInput,
    ModelGroupEnsureResultItem,
    ModelGroupEntity,
    ModelGroupItemInput,
    ProtocolKind,
    SiteBaseUrlEntity,
    SiteCredentialEntity,
    SiteDiscoveredModelEntity,
    SiteProtocolConfigEntity,
    _parse_supported_protocols_json,
    _runtime_channel_id,
    select,
)

_EnsureStatus = Literal["create", "update", "unchanged", "skipped"]


_EnsureStatus = Literal["create", "update", "unchanged", "skipped"]


@dataclass
class _EnsurePreparedItem:
    group_name: str
    protocol_config_id: str
    credential_id: str
    model_name: str
    protocols: list[ProtocolKind]
    items: list[ModelGroupItemInput]


@dataclass
class _EnsureGroupOperation:
    group_name: str
    entity: ModelGroupEntity | None = None
    items: list[_EnsurePreparedItem] = field(default_factory=list)


@dataclass
class _EnsureSiteLookups:
    protocol_configs: dict[str, SiteProtocolConfigEntity]
    base_url_enabled: dict[str, bool]
    credential_enabled: dict[str, bool]
    model_enabled: dict[tuple[str, str, str, ProtocolKind], bool]


class _GroupEnsurePreparationMixin:
    async def _load_ensure_site_lookups(
        self, session: AsyncSession, site_id: str
    ) -> _EnsureSiteLookups:
        protocol_rows = (
            (
                await session.execute(
                    select(SiteProtocolConfigEntity).where(
                        SiteProtocolConfigEntity.site_id == site_id
                    )
                )
            )
            .scalars()
            .all()
        )
        base_url_rows = (
            (
                await session.execute(
                    select(SiteBaseUrlEntity).where(
                        SiteBaseUrlEntity.site_id == site_id
                    )
                )
            )
            .scalars()
            .all()
        )
        credential_rows = (
            (
                await session.execute(
                    select(SiteCredentialEntity).where(
                        SiteCredentialEntity.site_id == site_id
                    )
                )
            )
            .scalars()
            .all()
        )

        protocol_config_ids = [row.id for row in protocol_rows]
        model_rows: list[SiteDiscoveredModelEntity] = []
        if protocol_config_ids:
            model_rows = (
                (
                    await session.execute(
                        select(SiteDiscoveredModelEntity).where(
                            SiteDiscoveredModelEntity.protocol_config_id.in_(
                                protocol_config_ids
                            )
                        )
                    )
                )
                .scalars()
                .all()
            )

        model_enabled: dict[tuple[str, str, str, ProtocolKind], bool] = {}
        for row in model_rows:
            if not row.protocol:
                continue
            try:
                protocol = ProtocolKind(row.protocol)
            except ValueError:
                continue
            model_enabled[
                (row.protocol_config_id, row.credential_id, row.model_name, protocol)
            ] = bool(row.enabled)

        return _EnsureSiteLookups(
            protocol_configs={row.id: row for row in protocol_rows},
            base_url_enabled={row.id: bool(row.enabled) for row in base_url_rows},
            credential_enabled={row.id: bool(row.enabled) for row in credential_rows},
            model_enabled=model_enabled,
        )

    def _prepare_ensure_model_item(
        self,
        item: ModelGroupEnsureModelInput,
        lookups: _EnsureSiteLookups,
    ) -> tuple[_EnsurePreparedItem, None] | tuple[None, ModelGroupEnsureResultItem]:
        model_name = item.model_name.strip()
        group_name = item.group_name.strip() or model_name
        protocols = list(dict.fromkeys(item.protocols))
        prepared = _EnsurePreparedItem(
            group_name=group_name,
            protocol_config_id=item.protocol_config_id,
            credential_id=item.credential_id,
            model_name=model_name,
            protocols=protocols,
            items=[],
        )
        if not model_name:
            return None, self._ensure_result_item(
                prepared, status="skipped", skipped_reason="model_name_required"
            )

        protocol_config = lookups.protocol_configs.get(item.protocol_config_id)
        if protocol_config is None:
            return None, self._ensure_result_item(
                prepared,
                status="skipped",
                skipped_reason="protocol_config_not_found",
            )
        if not protocol_config.enabled or not lookups.base_url_enabled.get(
            protocol_config.base_url_id, False
        ):
            return None, self._ensure_result_item(
                prepared, status="skipped", skipped_reason="channel_disabled"
            )

        credential_enabled = lookups.credential_enabled.get(item.credential_id)
        if credential_enabled is None:
            return None, self._ensure_result_item(
                prepared, status="skipped", skipped_reason="credential_not_found"
            )
        if not credential_enabled:
            return None, self._ensure_result_item(
                prepared, status="skipped", skipped_reason="credential_disabled"
            )

        configured_protocols = set(
            _parse_supported_protocols_json(protocol_config.protocols_json)
        )
        valid_protocols: list[ProtocolKind] = []
        members: list[ModelGroupItemInput] = []
        for protocol in protocols:
            if protocol not in configured_protocols:
                continue
            model_key = (
                item.protocol_config_id,
                item.credential_id,
                model_name,
                protocol,
            )
            if lookups.model_enabled.get(model_key) is not True:
                continue
            valid_protocols.append(protocol)
            members.append(
                ModelGroupItemInput(
                    channel_id=_runtime_channel_id(item.protocol_config_id, protocol),
                    credential_id=item.credential_id,
                    model_name=model_name,
                    enabled=True,
                )
            )

        if not members:
            return None, self._ensure_result_item(
                prepared, status="skipped", skipped_reason="model_not_available"
            )

        prepared.protocols = valid_protocols
        prepared.items = members
        return prepared, None

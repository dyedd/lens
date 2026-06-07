from __future__ import annotations

import json
import uuid
from collections import defaultdict

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...models import (
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
    SiteProtocolConfig,
    SiteProtocolConfigInput,
    SiteUpdate,
)
from ..entities import (
    ModelGroupItemEntity,
    SiteBaseUrlEntity,
    SiteCredentialEntity,
    SiteDiscoveredModelEntity,
    SiteEntity,
    SiteProtocolConfigEntity,
)


def _deduplicate_protocols(protocols: list[ProtocolKind]) -> list[ProtocolKind]:
    return list(dict.fromkeys(protocols))


def _parse_protocols_json(raw: str | None) -> list[ProtocolKind]:
    valid_protocol_values = {pk.value for pk in ProtocolKind}
    try:
        values = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    if not isinstance(values, list):
        return []
    return [
        ProtocolKind(value)
        for value in values
        if isinstance(value, str) and value in valid_protocol_values
    ]


def _dump_protocols_json(protocols: list[ProtocolKind]) -> str:
    return json.dumps(
        [p.value for p in _deduplicate_protocols(protocols)],
        ensure_ascii=True,
    )


def _input_protocols(protocol_config: SiteProtocolConfigInput) -> list[ProtocolKind]:
    return _deduplicate_protocols(protocol_config.protocols)


def _protocol_config_model_key(model: SiteModelInput) -> tuple[str, str]:
    return (model.credential_id, model.model_name.strip())


def _channel_id_matches_protocol_config(column, protocol_config_id: str):
    escaped = (
        protocol_config_id.replace("\\", "\\\\").replace("_", "\\_").replace("%", "\\%")
    )
    return column.like(f"{escaped}\\_%", escape="\\")


def _deduplicate_protocol_config_models(
    models: list[SiteModelInput],
) -> list[SiteModelInput]:
    deduplicated: list[SiteModelInput] = []
    indexes: dict[tuple[str, str, ProtocolKind | None], int] = {}

    for model in models:
        row_key = (*_protocol_config_model_key(model), model.protocol)
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
                "protocol": model.protocol,
            }
        )

    return deduplicated

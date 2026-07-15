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
    ModelGroupEntity,
    ModelGroupItemEntity,
    SiteBaseUrlEntity,
    SiteCredentialEntity,
    SiteDiscoveredModelEntity,
    SiteEntity,
    SiteProtocolConfigEntity,
)


def _deduplicate_protocols(protocols: list[ProtocolKind]) -> list[ProtocolKind]:
    return list(dict.fromkeys(protocols))


def _dump_protocols_json(protocols: list[ProtocolKind]) -> str:
    return json.dumps(
        [p.value for p in _deduplicate_protocols(protocols)],
        ensure_ascii=True,
    )


def _deduplicate_protocol_config_models(
    models: list[SiteModelInput],
) -> list[SiteModelInput]:
    deduplicated: list[SiteModelInput] = []
    indexes: dict[tuple[str, str, ProtocolKind | None], int] = {}

    for model in models:
        row_key = (model.credential_id, model.model_name.strip(), model.protocol)
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

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
    ModelSource,
    ProtocolKind,
    SiteBaseUrl,
    SiteBaseUrlInput,
    SiteBatchImportItemResult,
    SiteBatchImportRequest,
    SiteBatchImportResult,
    SiteConfig,
    SiteCreate,
    SiteCredential,
    SiteCredentialInput,
    SiteEnabledUpdate,
    SiteImportItem,
    SiteImportModelInput,
    SiteModel,
    SiteModelInput,
    SiteModelFetchRequest,
    SiteProtocolConfig,
    SiteProtocolConfigInput,
    SiteSyncTarget,
    SiteUpdate,
)
from ..entities import (
    ModelGroupEntity,
    ModelGroupItemEntity,
    SiteBaseUrlEntity,
    SiteCredentialEntity,
    SiteCredentialRateEntity,
    SiteDiscoveredModelEntity,
    SiteEntity,
    SiteProtocolConfigEntity,
    SiteProtocolConfigCredentialEntity,
    SiteProtocolConfigSyncTargetEntity,
)


def _deduplicate_protocols(protocols: list[ProtocolKind]) -> list[ProtocolKind]:
    return list(dict.fromkeys(protocols))


def _dump_protocols_json(protocols: list[ProtocolKind]) -> str:
    return json.dumps(
        [p.value for p in _deduplicate_protocols(protocols)],
        ensure_ascii=True,
    )

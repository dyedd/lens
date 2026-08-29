from __future__ import annotations

import asyncio
import json
import sys
import uuid
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.core.db import create_engine, create_session_factory
from app.core.runtime_channel_ids import compose_runtime_channel_id
from app.models.model_groups import ModelGroupCreate, ModelGroupItemInput
from app.models.protocols import ProtocolKind, RoutingStrategy
from app.models.sites import (
    SiteBaseUrlInput,
    SiteCreate,
    SiteCredentialInput,
    SiteModelInput,
    SiteProtocolConfigInput,
)
from app.persistence.channel_store import ChannelStore
from app.persistence.entities import (
    ModelGroupEntity,
    ModelGroupItemEntity,
    RequestLogEntity,
    SiteBaseUrlEntity,
    SiteCredentialEntity,
    SiteCredentialRateEntity,
    SiteDiscoveredModelEntity,
    SiteEntity,
    SiteProtocolConfigCredentialEntity,
    SiteProtocolConfigEntity,
    SiteProtocolConfigSyncTargetEntity,
)
from app.persistence.repositories import GroupRepository, ModelPriceRepository
from app.persistence.stats_entities import (
    ImportedStatsDailyEntity,
    ImportedStatsTotalEntity,
    OverviewModelDailyStatsEntity,
    RequestLogDailyStatsEntity,
)
from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

OCTOPUS_TYPE_TO_PROTOCOL = {
    0: ProtocolKind.OPENAI_CHAT,
    1: ProtocolKind.OPENAI_RESPONSES,
    2: ProtocolKind.ANTHROPIC,
    3: ProtocolKind.GEMINI,
}

PROTOCOL_GROUP_SUFFIXES = {
    ProtocolKind.OPENAI_CHAT: "",
    ProtocolKind.OPENAI_RESPONSES: " (Responses)",
    ProtocolKind.ANTHROPIC: " (Anthropic)",
    ProtocolKind.GEMINI: " (Gemini)",
}

OCTOPUS_DEFAULT_GROUP_MODE = 0
OCTOPUS_WEIGHTED_GROUP_MODE = 2
OCTOPUS_ROUND_ROBIN_GROUP_MODE = 3


@dataclass(frozen=True)
class ImportedChannelRef:
    runtime_channel_id: str
    credential_id: str
    is_enabled: bool


def parse_model_names(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def validate_octopus_groups(payload: dict) -> None:
    """Reject Octopus group settings that Lens cannot preserve."""
    for octopus_group in payload.get("groups", []):
        group_name = str(
            octopus_group.get("name") or octopus_group.get("id") or "<unknown>"
        )
        octopus_mode = int(octopus_group.get("mode") or OCTOPUS_DEFAULT_GROUP_MODE)
        if octopus_mode == OCTOPUS_WEIGHTED_GROUP_MODE:
            raise ValueError(
                f"Group '{group_name}' uses weighted routing, which Lens does not support"
            )
        if str(octopus_group.get("match_regex") or "").strip():
            raise ValueError(
                f"Group '{group_name}' has match_regex, which has no Lens equivalent"
            )


async def replace_imported_statistics(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    total: dict | list[dict] | None,
    daily: list[dict],
) -> None:
    """Replace imported Octopus totals and daily statistics."""
    async with session_factory() as session:
        await session.execute(delete(ImportedStatsDailyEntity))
        await session.execute(delete(ImportedStatsTotalEntity))
        await session.execute(delete(RequestLogDailyStatsEntity))
        await session.execute(delete(OverviewModelDailyStatsEntity))
        await session.execute(update(RequestLogEntity).values(stats_archived=0))

        if isinstance(total, list):
            total_item = total[0] if total else None
        else:
            total_item = total
        if total_item is not None:
            session.add(
                ImportedStatsTotalEntity(
                    id=1,
                    input_token=int(total_item.get("input_token") or 0),
                    output_token=int(total_item.get("output_token") or 0),
                    input_cost=float(total_item.get("input_cost") or 0.0),
                    output_cost=float(total_item.get("output_cost") or 0.0),
                    wait_time=int(total_item.get("wait_time") or 0),
                    request_success=int(total_item.get("request_success") or 0),
                    request_failed=int(total_item.get("request_failed") or 0),
                )
            )

        for item in daily:
            date_value = str(item.get("date") or "")
            if len(date_value) != 8:
                continue
            session.add(
                ImportedStatsDailyEntity(
                    date=date_value,
                    input_token=int(item.get("input_token") or 0),
                    output_token=int(item.get("output_token") or 0),
                    input_cost=float(item.get("input_cost") or 0.0),
                    output_cost=float(item.get("output_cost") or 0.0),
                    wait_time=int(item.get("wait_time") or 0),
                    request_success=int(item.get("request_success") or 0),
                    request_failed=int(item.get("request_failed") or 0),
                )
            )

        await session.commit()


async def run_import(export_path: str) -> None:
    """Import a supported Octopus export into the configured Lens database."""
    payload = json.loads(Path(export_path).read_text(encoding="utf-8"))
    validate_octopus_groups(payload)

    channels_by_octopus_id = {
        int(item["id"]): item
        for item in payload.get("channels", [])
        if item.get("id") is not None
    }
    group_items_by_group_id: dict[int, list[dict]] = defaultdict(list)
    group_model_names_by_channel_id: dict[int, list[str]] = defaultdict(list)
    for item in payload.get("group_items", []):
        group_id = item.get("group_id")
        channel_id = item.get("channel_id")
        model_name = str(item.get("model_name") or "").strip()
        if group_id is not None:
            group_items_by_group_id[int(group_id)].append(item)
        if channel_id is not None and model_name:
            group_model_names_by_channel_id[int(channel_id)].append(model_name)

    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    channel_store = ChannelStore(session_factory)
    group_repository = GroupRepository(session_factory)
    model_price_repository = ModelPriceRepository(session_factory)

    try:
        await replace_imported_statistics(
            session_factory,
            total=payload.get("stats_total"),
            daily=payload.get("stats_daily", []),
        )
        await model_price_repository.replace_model_prices(
            [
                {
                    "model_key": item.get("name"),
                    "display_name": item.get("name"),
                    "input_price_per_million": item.get("input"),
                    "output_price_per_million": item.get("output"),
                }
                for item in payload.get("llm_infos", [])
                if item.get("name")
            ]
        )

        channel_keys_by_channel: dict[int, list[dict]] = defaultdict(list)
        for item in payload.get("channel_keys", []):
            channel_id = item.get("channel_id")
            if channel_id is None:
                continue
            channel_keys_by_channel[int(channel_id)].append(item)

        async with session_factory() as session:
            await session.execute(delete(ModelGroupItemEntity))
            await session.execute(delete(ModelGroupEntity))
            await session.execute(delete(SiteProtocolConfigSyncTargetEntity))
            await session.execute(delete(SiteProtocolConfigCredentialEntity))
            await session.execute(delete(SiteCredentialRateEntity))
            await session.execute(delete(SiteDiscoveredModelEntity))
            await session.execute(delete(SiteProtocolConfigEntity))
            await session.execute(delete(SiteCredentialEntity))
            await session.execute(delete(SiteBaseUrlEntity))
            await session.execute(delete(SiteEntity))
            await session.commit()

        imported_channels: dict[int, ImportedChannelRef] = {}

        for channel in payload.get("channels", []):
            channel_id = channel.get("id")
            if channel_id is None:
                continue
            octopus_channel_id = int(channel_id)
            protocol = OCTOPUS_TYPE_TO_PROTOCOL.get(channel.get("type"))
            base_url = str(channel.get("base_url") or "").strip()
            channel_key_records = [
                item
                for item in channel_keys_by_channel.get(octopus_channel_id, [])
                if item.get("channel_key")
            ]

            if protocol is None or not base_url or not channel_key_records:
                continue

            credentials: list[SiteCredentialInput] = []
            for index, key_info in enumerate(channel_key_records):
                credentials.append(
                    SiteCredentialInput(
                        id=str(uuid.uuid4()),
                        name=str(key_info.get("remark") or f"Key {index + 1}"),
                        api_key=str(key_info.get("channel_key")),
                        enabled=bool(key_info.get("enabled", True)),
                    )
                )

            default_credential = next(
                (credential for credential in credentials if credential.enabled),
                credentials[0],
            )
            default_credential_id = str(default_credential.id)
            direct_models = parse_model_names(channel.get("model"))
            custom_models = parse_model_names(channel.get("custom_model"))
            group_models = group_model_names_by_channel_id.get(octopus_channel_id, [])
            model_names = list(
                dict.fromkeys([*direct_models, *custom_models, *group_models])
            )
            base_url_id = str(uuid.uuid4())
            protocol_config_id = str(uuid.uuid4())
            channel_enabled = bool(channel.get("enabled", True))

            site = await channel_store.create_site(
                SiteCreate(
                    name=channel.get("name") or f"channel-{channel_id}",
                    base_urls=[
                        SiteBaseUrlInput(
                            id=base_url_id,
                            url=base_url,
                            supported_protocols=[protocol],
                        )
                    ],
                    credentials=credentials,
                    protocols=[
                        SiteProtocolConfigInput(
                            id=protocol_config_id,
                            protocols=[protocol],
                            enabled=channel_enabled,
                            base_url_id=base_url_id,
                            headers={},
                            channel_proxy=channel.get("channel_proxy") or "",
                            param_override=channel.get("param_override") or "",
                            credential_ids=[default_credential_id],
                            models=[
                                SiteModelInput(
                                    id=str(uuid.uuid4()),
                                    credential_id=default_credential_id,
                                    model_name=model_name,
                                    enabled=True,
                                    protocol=protocol,
                                )
                                for model_name in model_names
                            ],
                        )
                    ],
                )
            )
            created_protocol_config = site.protocols[0]
            imported_channels[octopus_channel_id] = ImportedChannelRef(
                runtime_channel_id=compose_runtime_channel_id(
                    created_protocol_config.id,
                    protocol,
                ),
                credential_id=default_credential_id,
                is_enabled=channel_enabled and default_credential.enabled,
            )

        created_group_count = 0
        for octopus_group in payload.get("groups", []):
            items = sorted(
                group_items_by_group_id.get(int(octopus_group["id"]), []),
                key=lambda entry: entry.get("priority", 9999),
            )
            grouped_members: dict[ProtocolKind, list[ModelGroupItemInput]] = (
                defaultdict(list)
            )

            for item in items:
                channel_id = item.get("channel_id")
                imported = (
                    imported_channels.get(int(channel_id))
                    if channel_id is not None
                    else None
                )
                model_name = str(item.get("model_name") or "").strip()
                if imported is None or not model_name:
                    continue
                channel_payload = channels_by_octopus_id.get(int(channel_id))
                protocol = (
                    OCTOPUS_TYPE_TO_PROTOCOL.get(channel_payload.get("type"))
                    if channel_payload
                    else None
                )
                if protocol is None:
                    continue
                grouped_members[protocol].append(
                    ModelGroupItemInput(
                        channel_id=imported.runtime_channel_id,
                        credential_id=imported.credential_id,
                        model_name=model_name,
                        enabled=imported.is_enabled,
                    )
                )

            if not grouped_members:
                continue

            strategy = (
                RoutingStrategy.ROUND_ROBIN
                if int(octopus_group.get("mode") or OCTOPUS_DEFAULT_GROUP_MODE)
                == OCTOPUS_ROUND_ROBIN_GROUP_MODE
                else RoutingStrategy.FAILOVER
            )

            for protocol, group_members in grouped_members.items():
                group_name = str(octopus_group["name"])
                if len(grouped_members) > 1:
                    group_name = f"{group_name}{PROTOCOL_GROUP_SUFFIXES[protocol]}"
                await group_repository.create_group(
                    ModelGroupCreate(
                        name=group_name,
                        strategy=strategy,
                        items=group_members,
                    )
                )
                created_group_count += 1

        print(f"Imported sites={len(imported_channels)} groups={created_group_count}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/import_octopus_export.py <export.json>")
    asyncio.run(
        run_import(sys.argv[1]),
        loop_factory=(asyncio.SelectorEventLoop if sys.platform == "win32" else None),
    )

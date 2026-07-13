from __future__ import annotations

import asyncio
import json
import sys
import uuid
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete

from lens_api.core.config import settings
from lens_api.core.db import create_engine, create_session_factory
from lens_api.core.runtime_channel_ids import compose_runtime_channel_id
from lens_api.models import (
    ModelGroupCreate,
    ModelGroupItemInput,
    ProtocolKind,
    RoutingStrategy,
    SiteBaseUrlInput,
    SiteCreate,
    SiteCredentialInput,
    SiteModelInput,
    SiteProtocolConfigInput,
)
from lens_api.persistence.channel_store import ChannelStore
from lens_api.persistence.entities import (
    ModelGroupEntity,
    ModelGroupItemEntity,
    SiteBaseUrlEntity,
    SiteCredentialEntity,
    SiteDiscoveredModelEntity,
    SiteEntity,
    SiteProtocolConfigEntity,
)
from lens_api.persistence.repositories import GroupRepository, ModelPriceRepository
from octopus_import_support import replace_imported_stats, validate_supported_groups

TYPE_TO_PROTOCOL = {
    0: ProtocolKind.OPENAI_CHAT,
    1: ProtocolKind.OPENAI_RESPONSES,
    2: ProtocolKind.ANTHROPIC,
    3: ProtocolKind.GEMINI,
}

PROTOCOL_SUFFIX = {
    ProtocolKind.OPENAI_CHAT: "",
    ProtocolKind.OPENAI_RESPONSES: " (Responses)",
    ProtocolKind.ANTHROPIC: " (Anthropic)",
    ProtocolKind.GEMINI: " (Gemini)",
}


@dataclass(frozen=True)
class _ImportedChannel:
    runtime_channel_id: str
    credential_id: str
    is_enabled: bool


def _normalize_model_names(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


async def main(export_path: str) -> None:
    """Import a supported Octopus export into the configured Lens database."""
    payload = json.loads(Path(export_path).read_text(encoding="utf-8"))
    validate_supported_groups(payload)

    channels_by_id = {
        int(item["id"]): item
        for item in payload.get("channels", [])
        if item.get("id") is not None
    }
    group_items_by_group: dict[int, list[dict]] = defaultdict(list)
    group_model_names_by_channel: dict[int, list[str]] = defaultdict(list)
    for item in payload.get("group_items", []):
        group_id = item.get("group_id")
        channel_id = item.get("channel_id")
        model_name = str(item.get("model_name") or "").strip()
        if group_id is not None:
            group_items_by_group[int(group_id)].append(item)
        if channel_id is not None and model_name:
            group_model_names_by_channel[int(channel_id)].append(model_name)

    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    channel_store = ChannelStore(session_factory)
    group_repository = GroupRepository(session_factory)
    model_price_repository = ModelPriceRepository(session_factory)

    try:
        await replace_imported_stats(
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
            await session.execute(delete(SiteDiscoveredModelEntity))
            await session.execute(delete(SiteProtocolConfigEntity))
            await session.execute(delete(SiteCredentialEntity))
            await session.execute(delete(SiteBaseUrlEntity))
            await session.execute(delete(SiteEntity))
            await session.commit()

        imported_channels: dict[int, _ImportedChannel] = {}

        for channel in payload.get("channels", []):
            channel_id = channel.get("id")
            if channel_id is None:
                continue
            normalized_channel_id = int(channel_id)
            protocol = TYPE_TO_PROTOCOL.get(channel.get("type"))
            base_url = str(channel.get("base_url") or "").strip()
            key_infos = [
                item
                for item in channel_keys_by_channel.get(normalized_channel_id, [])
                if item.get("channel_key")
            ]

            if protocol is None or not base_url or not key_infos:
                continue

            credentials: list[SiteCredentialInput] = []
            for index, key_info in enumerate(key_infos):
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
            direct_models = _normalize_model_names(channel.get("model"))
            custom_models = _normalize_model_names(channel.get("custom_model"))
            group_models = group_model_names_by_channel.get(normalized_channel_id, [])
            all_models = list(
                dict.fromkeys([*direct_models, *custom_models, *group_models])
            )
            base_url_id = str(uuid.uuid4())
            protocol_config_id = str(uuid.uuid4())
            is_channel_enabled = bool(channel.get("enabled", True))

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
                            enabled=is_channel_enabled,
                            base_url_id=base_url_id,
                            headers={},
                            channel_proxy=channel.get("channel_proxy") or "",
                            param_override=channel.get("param_override") or "",
                            match_regex=channel.get("match_regex") or "",
                            credential_id=default_credential_id,
                            models=[
                                SiteModelInput(
                                    id=str(uuid.uuid4()),
                                    credential_id=default_credential_id,
                                    model_name=model_name,
                                    enabled=True,
                                    protocol=protocol,
                                )
                                for model_name in all_models
                            ],
                        )
                    ],
                )
            )
            imported_protocol_config = site.protocols[0]
            imported_channels[normalized_channel_id] = _ImportedChannel(
                runtime_channel_id=compose_runtime_channel_id(
                    imported_protocol_config.id,
                    protocol,
                ),
                credential_id=default_credential_id,
                is_enabled=is_channel_enabled and default_credential.enabled,
            )

        imported_group_count = 0
        for group in payload.get("groups", []):
            items = sorted(
                group_items_by_group.get(int(group["id"]), []),
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
                channel_payload = channels_by_id.get(int(channel_id))
                protocol = (
                    TYPE_TO_PROTOCOL.get(channel_payload.get("type"))
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
                if int(group.get("mode") or 0) == 3
                else RoutingStrategy.FAILOVER
            )

            for protocol, group_members in grouped_members.items():
                group_name = str(group["name"])
                if len(grouped_members) > 1:
                    group_name = f"{group_name}{PROTOCOL_SUFFIX[protocol]}"
                await group_repository.create_group(
                    ModelGroupCreate(
                        name=group_name,
                        protocols=[protocol],
                        strategy=strategy,
                        items=group_members,
                    )
                )
                imported_group_count += 1

        print(f"Imported sites={len(imported_channels)} groups={imported_group_count}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/import_octopus_export.py <export.json>")
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main(sys.argv[1]))

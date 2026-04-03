from __future__ import annotations

import asyncio
import json
import sys
import uuid
from collections import defaultdict
from pathlib import Path

from sqlalchemy import delete

from lens.core.config import settings
from lens.core.db import create_engine, create_session_factory
from lens.models import (
    ModelGroupCreate,
    ModelGroupItemInput,
    ProtocolKind,
    RoutingStrategy,
    SiteCreate,
    SiteCredentialInput,
    SiteModel,
    SiteProtocolConfigInput,
    SiteProtocolCredentialBindingInput,
)
from lens.persistence.domain_store import DomainStore
from lens.persistence.entities import (
    ModelGroupEntity,
    ModelGroupItemEntity,
    ProviderEntity,
    SiteCredentialEntity,
    SiteDiscoveredModelEntity,
    SiteEntity,
    SiteProtocolConfigEntity,
    SiteProtocolCredentialBindingEntity,
)
from lens.persistence.provider_store import ProviderStore


TYPE_TO_PROTOCOL = {
    0: ProtocolKind.OPENAI_CHAT,
    1: ProtocolKind.OPENAI_RESPONSES,
    2: ProtocolKind.ANTHROPIC,
    3: ProtocolKind.GEMINI,
}

PROTOCOL_SUFFIX = {
    ProtocolKind.OPENAI_CHAT: '',
    ProtocolKind.OPENAI_RESPONSES: ' (Responses)',
    ProtocolKind.ANTHROPIC: ' (Anthropic)',
    ProtocolKind.GEMINI: ' (Gemini)',
}


def normalize_model_names(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(',') if item.strip()]


async def main(export_path: str) -> None:
    payload = json.loads(Path(export_path).read_text(encoding='utf-8'))
    channels_by_id = {item['id']: item for item in payload.get('channels', []) if item.get('id') is not None}

    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    provider_store = ProviderStore(session_factory)
    domain_store = DomainStore(session_factory)

    stats_total = payload.get('stats_total')
    await domain_store.replace_imported_stats(
        total=stats_total[0] if isinstance(stats_total, list) and stats_total else stats_total,
        daily=payload.get('stats_daily', []),
        model_prices=[
            {
                'model_key': item.get('name'),
                'display_name': item.get('name'),
                'input_price_per_million': item.get('input'),
                'output_price_per_million': item.get('output'),
            }
            for item in payload.get('llm_infos', [])
            if item.get('name')
        ],
    )

    channel_keys_by_channel: dict[int, list[dict]] = defaultdict(list)
    for item in payload.get('channel_keys', []):
        channel_id = item.get('channel_id')
        if channel_id is None:
            continue
        channel_keys_by_channel[int(channel_id)].append(item)

    async with session_factory() as session:
        await session.execute(delete(ModelGroupItemEntity))
        await session.execute(delete(ModelGroupEntity))
        await session.execute(delete(SiteDiscoveredModelEntity))
        await session.execute(delete(SiteProtocolCredentialBindingEntity))
        await session.execute(delete(SiteProtocolConfigEntity))
        await session.execute(delete(SiteCredentialEntity))
        await session.execute(delete(SiteEntity))
        await session.execute(delete(ProviderEntity))
        await session.commit()

    imported_channels: dict[int, tuple[str, str]] = {}

    for channel in payload.get('channels', []):
        channel_id = channel.get('id')
        protocol = TYPE_TO_PROTOCOL.get(channel.get('type'))
        base_url = str(channel.get('base_url') or '').strip()
        key_infos = [item for item in channel_keys_by_channel.get(int(channel_id), []) if item.get('channel_key')]

        if protocol is None or not base_url or not key_infos:
            continue

        credentials: list[SiteCredentialInput] = []
        credential_id_by_value: dict[str, str] = {}
        for index, key_info in enumerate(key_infos):
            credential_id = str(uuid.uuid4())
            api_key = str(key_info.get('channel_key'))
            credential_id_by_value[api_key] = credential_id
            credentials.append(
                SiteCredentialInput(
                    id=credential_id,
                    name=str(key_info.get('remark') or f'Key {index + 1}'),
                    api_key=api_key,
                    enabled=bool(key_info.get('enabled', True)),
                )
            )

        default_credential_id = credentials[0].id or ''
        direct_models = normalize_model_names(channel.get('model'))
        custom_models = normalize_model_names(channel.get('custom_model'))
        all_models = list(dict.fromkeys([*direct_models, *custom_models]))
        protocol_id = str(uuid.uuid4())

        site = await provider_store.create_site(
            SiteCreate(
                name=channel.get('name') or f'channel-{channel_id}',
                credentials=credentials,
                protocols=[
                    SiteProtocolConfigInput(
                        id=protocol_id,
                        protocol=protocol,
                        enabled=bool(channel.get('enabled', True)),
                        base_url=base_url,
                        headers={},
                        proxy=bool(channel.get('proxy')),
                        channel_proxy=channel.get('channel_proxy') or '',
                        param_override=channel.get('param_override') or '',
                        match_regex=channel.get('match_regex') or '',
                        bindings=[
                            SiteProtocolCredentialBindingInput(credential_id=item.id or '', enabled=item.enabled)
                            for item in credentials
                        ],
                        models=[
                            SiteModel(
                                id=str(uuid.uuid4()),
                                credential_id=default_credential_id,
                                credential_name='',
                                model_name=model_name,
                                enabled=True,
                                sort_order=index,
                            )
                            for index, model_name in enumerate(all_models)
                        ],
                    )
                ],
            )
        )
        imported_channels[int(channel_id)] = (site.id, site.protocols[0].id)

    group_items_by_group: dict[int, list[dict]] = defaultdict(list)
    for item in payload.get('group_items', []):
        group_id = item.get('group_id')
        if group_id is None:
            continue
        group_items_by_group[int(group_id)].append(item)

    for group in payload.get('groups', []):
        items = sorted(group_items_by_group.get(int(group['id']), []), key=lambda entry: entry.get('priority', 9999))
        grouped_members: dict[ProtocolKind, list[ModelGroupItemInput]] = defaultdict(list)

        for item in items:
            channel_id = item.get('channel_id')
            imported = imported_channels.get(int(channel_id)) if channel_id is not None else None
            model_name = str(item.get('model_name') or '').strip()
            if not imported or not model_name:
                continue
            _, provider_id = imported
            channel_payload = channels_by_id.get(channel_id)
            protocol = TYPE_TO_PROTOCOL.get(channel_payload.get('type')) if channel_payload else None
            if protocol is None:
                continue
            grouped_members[protocol].append(
                ModelGroupItemInput(provider_id=provider_id, credential_id='', model_name=model_name, enabled=True)
            )

        if not grouped_members:
            continue

        strategy = RoutingStrategy.FAILOVER
        if int(group.get('mode') or 0) == 3:
            strategy = RoutingStrategy.ROUND_ROBIN
        elif int(group.get('mode') or 0) == 2:
            strategy = RoutingStrategy.WEIGHTED

        for protocol, group_members in grouped_members.items():
            if not group_members:
                continue
            group_name = str(group['name'])
            if len(grouped_members) > 1:
                group_name = f'{group_name}{PROTOCOL_SUFFIX[protocol]}'
            try:
                await domain_store.create_group(
                    ModelGroupCreate(
                        name=group_name,
                        protocol=protocol,
                        strategy=strategy,
                        match_regex=group.get('match_regex') or '',
                        items=group_members,
                    )
                )
            except Exception as exc:
                raise RuntimeError(
                    f'Failed to import group={group_name} protocol={protocol.value} members={len(group_members)}'
                ) from exc

    print(f"Imported sites={len(imported_channels)} groups={len(payload.get('groups', []))}")
    await engine.dispose()


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python scripts/import_octopus_export.py <export.json>')
    asyncio.run(main(sys.argv[1]))

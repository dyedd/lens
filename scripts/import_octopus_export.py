from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import delete, select

from lens.db import Base, create_engine, create_session_factory
from lens.domain_store import DomainStore
from lens.entities import GatewayKeyEntity, ModelGroupEntity, ProviderEntity
from lens.models import ModelGroupCreate, ProtocolKind, ProviderCreate, ProviderStatus, RoutingStrategy
from lens.store import ProviderStore


TYPE_TO_PROTOCOL = {
    0: ProtocolKind.OPENAI_CHAT,
    1: ProtocolKind.OPENAI_RESPONSES,
    2: ProtocolKind.ANTHROPIC,
    3: ProtocolKind.GEMINI,
}


def normalize_model_names(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(',') if item.strip()]


async def main(export_path: str) -> None:
    payload = json.loads(Path(export_path).read_text(encoding='utf-8'))

    engine = create_engine('sqlite+aiosqlite:///data/lens.db')
    session_factory = create_session_factory(engine)
    provider_store = ProviderStore(session_factory)
    domain_store = DomainStore(session_factory)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    await domain_store.ensure_schema()

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

    channel_keys_by_channel = {
        item['channel_id']: item
        for item in payload.get('channel_keys', [])
        if item.get('enabled')
    }

    async with session_factory() as session:
        await session.execute(delete(ModelGroupEntity))
        await session.execute(delete(GatewayKeyEntity))
        await session.execute(delete(ProviderEntity))
        await session.commit()

    imported_channels: dict[int, str] = {}

    for channel in payload.get('channels', []):
        protocol = TYPE_TO_PROTOCOL.get(channel.get('type'))
        base_urls = channel.get('base_urls') or []
        first_url = (base_urls[0] or {}).get('url') if base_urls else None
        key_info = channel_keys_by_channel.get(channel.get('id'))

        if protocol is None or not first_url or not key_info or not key_info.get('channel_key'):
            continue

        direct_models = normalize_model_names(channel.get('model'))
        custom_models = normalize_model_names(channel.get('custom_model'))
        all_models = [*direct_models, *custom_models]

        provider = await provider_store.create(
            ProviderCreate(
                name=channel.get('name') or f"channel-{channel['id']}",
                protocol=protocol,
                base_url=first_url,
                api_key=key_info['channel_key'],
                model_name=all_models[0] if len(all_models) == 1 else None,
                status=ProviderStatus.ENABLED if channel.get('enabled') else ProviderStatus.DISABLED,
                weight=1,
                priority=max(int((base_urls[0] or {}).get('delay') or 0), 1),
                headers={},
                model_patterns=all_models if len(all_models) > 1 else [],
            )
        )
        imported_channels[channel['id']] = provider.id

    for item in payload.get('channel_keys', []):
        if not item.get('enabled'):
            continue
        channel = next((entry for entry in payload.get('channels', []) if entry.get('id') == item.get('channel_id')), None)
        key_name = (channel or {}).get('name') or f"channel-{item.get('channel_id')}"
        await domain_store.create_gateway_key_from_secret(
            name=key_name,
            secret=item['channel_key'],
            enabled=True,
        )

    group_items_by_group: dict[int, list[dict]] = {}
    for item in payload.get('group_items', []):
        group_items_by_group.setdefault(item['group_id'], []).append(item)

    for group in payload.get('groups', []):
        items = sorted(group_items_by_group.get(group['id'], []), key=lambda entry: entry.get('priority', 9999))
        provider_ids = [imported_channels[item['channel_id']] for item in items if item.get('channel_id') in imported_channels]
        if not provider_ids:
            continue

        strategy = RoutingStrategy.FAILOVER
        if int(group.get('mode') or 0) == 3:
            strategy = RoutingStrategy.ROUND_ROBIN
        elif int(group.get('mode') or 0) == 2:
            strategy = RoutingStrategy.WEIGHTED

        sample_model = (items[0] or {}).get('model_name', '') if items else ''
        protocol = guess_group_protocol(group.get('name', ''), sample_model)

        await domain_store.create_group(
            ModelGroupCreate(
                name=group['name'],
                protocol=protocol,
                strategy=strategy,
                provider_ids=provider_ids,
                enabled=True,
            )
        )

    print(f"Imported providers={len(imported_channels)} groups={len(payload.get('groups', []))}")

    await engine.dispose()


def guess_group_protocol(group_name: str, sample_model: str) -> ProtocolKind:
    value = f"{group_name} {sample_model}".lower()
    if 'gemini' in value:
        return ProtocolKind.GEMINI
    if 'gpt-' in value:
        return ProtocolKind.OPENAI_RESPONSES
    if 'claude' in value or 'anthropic' in value:
        return ProtocolKind.ANTHROPIC
    return ProtocolKind.OPENAI_CHAT


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python scripts/import_octopus_export.py <export.json>')
    asyncio.run(main(sys.argv[1]))

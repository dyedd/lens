from __future__ import annotations

import asyncio

from lens.core.db import Base, create_engine, create_session_factory
from lens.models import ModelGroupCandidatesRequest, ModelGroupCreate, ModelGroupItemInput, ProtocolKind, RoutingStrategy, SiteCreate
from lens.persistence.domain_store import DomainStore
from lens.persistence.channel_store import ChannelStore


def test_create_group_persists_ordered_model_items(tmp_path):
    asyncio.run(_run_group_store_test(tmp_path))


async def _run_group_store_test(tmp_path):
    database_path = tmp_path / "group-store.db"
    engine = create_engine(f"sqlite+aiosqlite:///{database_path.resolve().as_posix()}")
    session_factory = create_session_factory(engine)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    channel_store = ChannelStore(session_factory)
    domain_store = DomainStore(session_factory)

    site_one = await channel_store.create_site(
        SiteCreate(
            name="Anthropic A",
            base_url="https://a.example.com",
            credentials=[{"name": "Key 1", "api_key": "sk-a", "enabled": True}],
            protocols=[{
                "protocol": ProtocolKind.ANTHROPIC,
                "enabled": True,
                "headers": {},
                "channel_proxy": "",
                "param_override": "",
                "match_regex": "",
                "bindings": [],
                "models": [],
            }],
        )
    )
    credential_one = site_one.credentials[0]
    provider_one = site_one.protocols[0]
    site_one = await channel_store.update_site(
        site_one.id,
        SiteCreate(
            name=site_one.name,
            base_url=site_one.base_url,
            credentials=[{"id": credential_one.id, "name": credential_one.name, "api_key": credential_one.api_key, "enabled": True}],
            protocols=[{
                "id": provider_one.id,
                "protocol": provider_one.protocol,
                "enabled": True,
                "headers": {},
                "channel_proxy": "",
                "param_override": "",
                "match_regex": "",
                "bindings": [{"credential_id": credential_one.id, "enabled": True}],
                "models": [
                    {"credential_id": credential_one.id, "model_name": "anthropic/claude-sonnet-4-6", "enabled": True},
                    {"credential_id": credential_one.id, "model_name": "anthropic/claude-opus-4-6", "enabled": True},
                ],
            }],
        ),
    )
    provider_one = site_one.protocols[0]

    site_two = await channel_store.create_site(
        SiteCreate(
            name="Anthropic B",
            base_url="https://b.example.com",
            credentials=[{"name": "Key 1", "api_key": "sk-b", "enabled": True}],
            protocols=[{
                "protocol": ProtocolKind.ANTHROPIC,
                "enabled": True,
                "headers": {},
                "channel_proxy": "",
                "param_override": "",
                "match_regex": "",
                "bindings": [],
                "models": [],
            }],
        )
    )
    credential_two = site_two.credentials[0]
    provider_two = site_two.protocols[0]
    site_two = await channel_store.update_site(
        site_two.id,
        SiteCreate(
            name=site_two.name,
            base_url=site_two.base_url,
            credentials=[{"id": credential_two.id, "name": credential_two.name, "api_key": credential_two.api_key, "enabled": True}],
            protocols=[{
                "id": provider_two.id,
                "protocol": provider_two.protocol,
                "enabled": True,
                "headers": {},
                "channel_proxy": "",
                "param_override": "",
                "match_regex": "",
                "bindings": [{"credential_id": credential_two.id, "enabled": True}],
                "models": [
                    {"credential_id": credential_two.id, "model_name": "claude-sonnet-4-5", "enabled": True},
                    {"credential_id": credential_two.id, "model_name": "claude-haiku-4-5", "enabled": True},
                ],
            }],
        ),
    )
    provider_two = site_two.protocols[0]

    group = await domain_store.create_group(
        ModelGroupCreate(
            name="claude-sonnet",
            protocol=ProtocolKind.ANTHROPIC,
            strategy=RoutingStrategy.ROUND_ROBIN,
            items=[
                ModelGroupItemInput(channel_id=provider_one.id, model_name="anthropic/claude-sonnet-4-6", enabled=True),
                ModelGroupItemInput(channel_id=provider_two.id, model_name="claude-sonnet-4-5", enabled=False),
            ],
        )
    )

    assert [item.channel_id for item in group.items] == [provider_one.id, provider_two.id]
    assert [item.model_name for item in group.items] == ["anthropic/claude-sonnet-4-6", "claude-sonnet-4-5"]
    assert [item.enabled for item in group.items] == [True, False]

    groups = await domain_store.list_groups()
    persisted = next(item for item in groups if item.id == group.id)
    assert [item.channel_id for item in persisted.items] == [provider_one.id, provider_two.id]
    assert [item.sort_order for item in persisted.items] == [0, 1]
    assert [item.enabled for item in persisted.items] == [True, False]

    candidates = await domain_store.list_group_candidates(
        ModelGroupCandidatesRequest(
            protocol=ProtocolKind.ANTHROPIC,
            exclude_items=[ModelGroupItemInput(channel_id=provider_one.id, model_name="anthropic/claude-sonnet-4-6")],
        )
    )
    candidate_keys = {(item.channel_id, item.model_name) for item in candidates.candidates}
    assert (provider_one.id, "anthropic/claude-sonnet-4-6") not in candidate_keys
    assert (provider_two.id, "claude-sonnet-4-5") in candidate_keys

    openai_site = await channel_store.create_site(
        SiteCreate(
            name="OpenAI A",
            base_url="https://openai.example.com",
            credentials=[{"name": "Key 1", "api_key": "sk-openai", "enabled": True}],
            protocols=[{
                "protocol": ProtocolKind.OPENAI_CHAT,
                "enabled": True,
                "headers": {},
                "channel_proxy": "",
                "param_override": "",
                "match_regex": "",
                "bindings": [],
                "models": [],
            }],
        )
    )
    openai_credential = openai_site.credentials[0]
    openai_channel = openai_site.protocols[0]
    openai_site = await channel_store.update_site(
        openai_site.id,
        SiteCreate(
            name=openai_site.name,
            base_url=openai_site.base_url,
            credentials=[{"id": openai_credential.id, "name": openai_credential.name, "api_key": openai_credential.api_key, "enabled": True}],
            protocols=[{
                "id": openai_channel.id,
                "protocol": openai_channel.protocol,
                "enabled": True,
                "headers": {},
                "channel_proxy": "",
                "param_override": "",
                "match_regex": "",
                "bindings": [{"credential_id": openai_credential.id, "enabled": True}],
                "models": [{"credential_id": openai_credential.id, "model_name": "claude-sonnet", "enabled": True}],
            }],
        ),
    )
    openai_channel = openai_site.protocols[0]
    duplicate_name_group = await domain_store.create_group(
        ModelGroupCreate(
            name="claude-sonnet",
            protocol=ProtocolKind.OPENAI_CHAT,
            strategy=RoutingStrategy.ROUND_ROBIN,
            items=[ModelGroupItemInput(channel_id=openai_channel.id, model_name="claude-sonnet", enabled=True)],
        )
    )

    assert duplicate_name_group.name == group.name
    assert duplicate_name_group.protocol == ProtocolKind.OPENAI_CHAT
    assert duplicate_name_group.id != group.id

    await engine.dispose()


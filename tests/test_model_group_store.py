from __future__ import annotations

import asyncio

from lens.core.db import Base, create_engine, create_session_factory
from lens.models import ModelGroupCandidatesRequest, ModelGroupCreate, ModelGroupItemInput, ProtocolKind, ProviderCreate, RoutingStrategy
from lens.persistence.domain_store import DomainStore
from lens.persistence.provider_store import ProviderStore


def test_create_group_persists_ordered_model_items(tmp_path):
    asyncio.run(_run_group_store_test(tmp_path))


async def _run_group_store_test(tmp_path):
    database_path = tmp_path / "group-store.db"
    engine = create_engine(f"sqlite+aiosqlite:///{database_path.resolve().as_posix()}")
    session_factory = create_session_factory(engine)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    provider_store = ProviderStore(session_factory)
    domain_store = DomainStore(session_factory)

    provider_one = await provider_store.create(
        ProviderCreate(
            name="Anthropic A",
            protocol=ProtocolKind.ANTHROPIC,
            base_url="https://a.example.com",
            api_key="sk-a",
            model_patterns=["anthropic/claude-sonnet-4-6", "anthropic/claude-opus-4-6"],
        )
    )
    provider_two = await provider_store.create(
        ProviderCreate(
            name="Anthropic B",
            protocol=ProtocolKind.ANTHROPIC,
            base_url="https://b.example.com",
            api_key="sk-b",
            model_patterns=["claude-sonnet-4-5", "claude-haiku-4-5"],
        )
    )

    group = await domain_store.create_group(
        ModelGroupCreate(
            name="claude-sonnet",
            protocol=ProtocolKind.ANTHROPIC,
            strategy=RoutingStrategy.ROUND_ROBIN,
            match_regex="",
            first_token_timeout=12,
            session_keep_time=34,
            items=[
                ModelGroupItemInput(provider_id=provider_one.id, model_name="anthropic/claude-sonnet-4-6", enabled=True),
                ModelGroupItemInput(provider_id=provider_two.id, model_name="claude-sonnet-4-5", enabled=False),
            ],
        )
    )

    assert [item.provider_id for item in group.items] == [provider_one.id, provider_two.id]
    assert [item.model_name for item in group.items] == ["anthropic/claude-sonnet-4-6", "claude-sonnet-4-5"]
    assert [item.enabled for item in group.items] == [True, False]
    assert group.first_token_timeout == 12
    assert group.session_keep_time == 34

    groups = await domain_store.list_groups()
    persisted = next(item for item in groups if item.id == group.id)
    assert [item.provider_id for item in persisted.items] == [provider_one.id, provider_two.id]
    assert [item.sort_order for item in persisted.items] == [0, 1]
    assert [item.enabled for item in persisted.items] == [True, False]
    assert persisted.first_token_timeout == 12
    assert persisted.session_keep_time == 34

    candidates = await domain_store.list_group_candidates(
        ModelGroupCandidatesRequest(
            protocol=ProtocolKind.ANTHROPIC,
            name="claude-sonnet",
            match_regex="",
            exclude_items=[ModelGroupItemInput(provider_id=provider_one.id, model_name="anthropic/claude-sonnet-4-6")],
        )
    )
    matched_keys = {(item.provider_id, item.model_name) for item in candidates.matched_items}
    assert (provider_one.id, "anthropic/claude-sonnet-4-6") not in matched_keys
    assert (provider_two.id, "claude-sonnet-4-5") in matched_keys

    openai_provider = await provider_store.create(
        ProviderCreate(
            name="OpenAI A",
            protocol=ProtocolKind.OPENAI_CHAT,
            base_url="https://openai.example.com",
            api_key="sk-openai",
            model_patterns=["claude-sonnet"],
        )
    )
    duplicate_name_group = await domain_store.create_group(
        ModelGroupCreate(
            name="claude-sonnet",
            protocol=ProtocolKind.OPENAI_CHAT,
            strategy=RoutingStrategy.ROUND_ROBIN,
            match_regex="",
            items=[ModelGroupItemInput(provider_id=openai_provider.id, model_name="claude-sonnet", enabled=True)],
        )
    )

    assert duplicate_name_group.name == group.name
    assert duplicate_name_group.protocol == ProtocolKind.OPENAI_CHAT
    assert duplicate_name_group.id != group.id

    await engine.dispose()

from types import SimpleNamespace

import pytest
import pytest_asyncio

from lens_api.core.db import Base, create_engine, create_session_factory
from lens_api.gateway import service
from lens_api.models import (
    ModelGroupCreate,
    ModelGroupItemInput,
    ProtocolKind,
    SiteBaseUrlInput,
    SiteCreate,
    SiteCredentialInput,
    SiteModelInput,
    SiteProtocolConfigInput,
)
from lens_api.persistence.channel_store import ChannelStore
from lens_api.persistence.domain_store import DomainStore


@pytest_asyncio.fixture
async def session_factory(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'lens.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    try:
        yield factory
    finally:
        await engine.dispose()


async def _seed_channel(
    session_factory,
    *,
    combo_id: str,
    protocol: ProtocolKind,
    model_name: str,
) -> tuple[str, str]:
    credential_id = f"{combo_id}-credential"
    await ChannelStore(session_factory).create_site(
        SiteCreate(
            name=f"Site {combo_id}",
            base_urls=[
                SiteBaseUrlInput(
                    id=f"{combo_id}-base",
                    url="https://api.example.com",
                    compatible_protocols=[protocol],
                )
            ],
            credentials=[
                SiteCredentialInput(
                    id=credential_id,
                    name="Primary",
                    api_key="sk-test",
                )
            ],
            protocols=[
                SiteProtocolConfigInput(
                    id=combo_id,
                    name=f"Combo {combo_id}",
                    base_url_id=f"{combo_id}-base",
                    credential_id=credential_id,
                    models=[
                        SiteModelInput(
                            id=f"{combo_id}-model",
                            credential_id=credential_id,
                            model_name=model_name,
                        )
                    ],
                )
            ],
        )
    )
    return f"{combo_id}_{protocol.value}", credential_id


def _install_app_state(monkeypatch, session_factory) -> DomainStore:
    domain_store = DomainStore(session_factory)
    monkeypatch.setattr(
        service,
        "app_state",
        SimpleNamespace(
            domain_store=domain_store,
            store=ChannelStore(session_factory),
        ),
    )
    return domain_store


async def _create_multi_protocol_group(
    session_factory,
    monkeypatch,
    *,
    name: str = "Shared Group",
) -> None:
    channel_id, credential_id = await _seed_channel(
        session_factory,
        combo_id="chat-combo",
        protocol=ProtocolKind.OPENAI_CHAT,
        model_name="gpt-5-mini",
    )
    domain_store = _install_app_state(monkeypatch, session_factory)
    await domain_store.create_group(
        ModelGroupCreate(
            name=name,
            protocols=[
                ProtocolKind.OPENAI_CHAT,
                ProtocolKind.OPENAI_RESPONSES,
                ProtocolKind.ANTHROPIC,
            ],
            items=[
                ModelGroupItemInput(
                    channel_id=channel_id,
                    credential_id=credential_id,
                    model_name="gpt-5-mini",
                )
            ],
        )
    )


@pytest.mark.asyncio
async def test_resolve_group_by_name_and_openai_chat_protocol(
    session_factory, monkeypatch
) -> None:
    await _create_multi_protocol_group(session_factory, monkeypatch)

    plan = await service._resolve_routing_plan(
        ProtocolKind.OPENAI_CHAT, "Shared Group"
    )

    assert plan.requested_group_name == "Shared Group"
    assert plan.resolved_group_name == "Shared Group"
    assert plan.route_targets is not None
    assert plan.route_targets[0].channel.protocol == ProtocolKind.OPENAI_CHAT


@pytest.mark.asyncio
async def test_resolve_group_by_name_and_responses_protocol(
    session_factory, monkeypatch
) -> None:
    await _create_multi_protocol_group(session_factory, monkeypatch)

    plan = await service._resolve_routing_plan(
        ProtocolKind.OPENAI_RESPONSES, "Shared Group"
    )

    assert plan.requested_group_name == "Shared Group"
    assert plan.resolved_group_name == "Shared Group"
    assert plan.route_targets is not None
    assert plan.route_targets[0].channel.protocol == ProtocolKind.OPENAI_CHAT


@pytest.mark.asyncio
async def test_resolve_group_by_name_and_anthropic_protocol(
    session_factory, monkeypatch
) -> None:
    await _create_multi_protocol_group(session_factory, monkeypatch)

    plan = await service._resolve_routing_plan(
        ProtocolKind.ANTHROPIC, "Shared Group"
    )

    assert plan.requested_group_name == "Shared Group"
    assert plan.resolved_group_name == "Shared Group"
    assert plan.route_targets is not None
    assert plan.route_targets[0].channel.protocol == ProtocolKind.OPENAI_CHAT


@pytest.mark.asyncio
async def test_resolve_group_rejects_unsupported_protocol(
    session_factory, monkeypatch
) -> None:
    channel_id, credential_id = await _seed_channel(
        session_factory,
        combo_id="chat-only",
        protocol=ProtocolKind.OPENAI_CHAT,
        model_name="gpt-5-mini",
    )
    domain_store = _install_app_state(monkeypatch, session_factory)
    await domain_store.create_group(
        ModelGroupCreate(
            name="Chat Only",
            protocols=[ProtocolKind.OPENAI_CHAT],
            items=[
                ModelGroupItemInput(
                    channel_id=channel_id,
                    credential_id=credential_id,
                    model_name="gpt-5-mini",
                )
            ],
        )
    )

    assert (
        await domain_store.find_group_by_name(
            ProtocolKind.OPENAI_EMBEDDING.value, "Chat Only"
        )
        is None
    )
    with pytest.raises(LookupError, match="No model group matched Chat Only"):
        await service._resolve_routing_plan(
            ProtocolKind.OPENAI_EMBEDDING, "Chat Only"
        )


@pytest.mark.asyncio
async def test_route_targets_filtered_by_request_protocol(
    session_factory, monkeypatch
) -> None:
    chat_channel_id, chat_credential_id = await _seed_channel(
        session_factory,
        combo_id="chat-target",
        protocol=ProtocolKind.OPENAI_CHAT,
        model_name="gpt-5-mini",
    )
    embedding_channel_id, embedding_credential_id = await _seed_channel(
        session_factory,
        combo_id="embedding-target",
        protocol=ProtocolKind.OPENAI_EMBEDDING,
        model_name="text-embedding-3-large",
    )
    domain_store = _install_app_state(monkeypatch, session_factory)
    await domain_store.create_group(
        ModelGroupCreate(
            name="Mixed Group",
            protocols=[ProtocolKind.OPENAI_CHAT, ProtocolKind.OPENAI_EMBEDDING],
            items=[
                ModelGroupItemInput(
                    channel_id=chat_channel_id,
                    credential_id=chat_credential_id,
                    model_name="gpt-5-mini",
                ),
                ModelGroupItemInput(
                    channel_id=embedding_channel_id,
                    credential_id=embedding_credential_id,
                    model_name="text-embedding-3-large",
                ),
            ],
        )
    )

    plan = await service._resolve_routing_plan(
        ProtocolKind.OPENAI_CHAT, "Mixed Group"
    )

    assert plan.route_targets is not None
    assert [target.channel.protocol for target in plan.route_targets] == [
        ProtocolKind.OPENAI_CHAT
    ]


@pytest.mark.asyncio
async def test_openai_chat_channel_can_serve_anthropic_group_request(
    session_factory, monkeypatch
) -> None:
    channel_id, credential_id = await _seed_channel(
        session_factory,
        combo_id="anthropic-via-chat",
        protocol=ProtocolKind.OPENAI_CHAT,
        model_name="gpt-5-mini",
    )
    domain_store = _install_app_state(monkeypatch, session_factory)
    await domain_store.create_group(
        ModelGroupCreate(
            name="Anthropic Alias",
            protocols=[ProtocolKind.ANTHROPIC],
            items=[
                ModelGroupItemInput(
                    channel_id=channel_id,
                    credential_id=credential_id,
                    model_name="gpt-5-mini",
                )
            ],
        )
    )

    plan = await service._resolve_routing_plan(
        ProtocolKind.ANTHROPIC, "Anthropic Alias"
    )

    assert plan.route_targets is not None
    assert [target.channel.protocol for target in plan.route_targets] == [
        ProtocolKind.OPENAI_CHAT
    ]

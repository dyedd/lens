import pytest
import pytest_asyncio
from pydantic import ValidationError

from lens_api.core.db import Base, create_engine, create_session_factory
from lens_api.models import (
    ModelGroupCandidatesRequest,
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
from lens_api.persistence.entities import SiteDiscoveredModelEntity


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
    protocols: list[ProtocolKind],
    model_name: str,
    model_protocol: ProtocolKind | None = None,
) -> tuple[str, str]:
    credential_id = f"{combo_id}-credential"
    base_url_id = f"{combo_id}-base"
    await ChannelStore(session_factory).create_site(
        SiteCreate(
            name=f"Site {combo_id}",
            base_urls=[
                SiteBaseUrlInput(
                    id=base_url_id,
                    url="https://api.example.com",
                    compatible_protocols=protocols,
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
                    base_url_id=base_url_id,
                    credential_id=credential_id,
                    models=[
                        SiteModelInput(
                            id=f"{combo_id}-model",
                            credential_id=credential_id,
                            model_name=model_name,
                            protocol=model_protocol,
                        )
                    ],
                )
            ],
        )
    )
    return f"{combo_id}_{protocols[0].value}", credential_id


def test_create_group_requires_protocols() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ModelGroupCreate(name="Missing protocols")

    assert "protocols" in str(exc_info.value)


@pytest.mark.asyncio
async def test_create_group_rejects_duplicate_name(session_factory) -> None:
    store = DomainStore(session_factory)
    await store.create_group(
        ModelGroupCreate(name="GPT-5", protocols=[ProtocolKind.OPENAI_CHAT])
    )

    with pytest.raises(ValueError, match="Model group already exists: GPT-5"):
        await store.create_group(
            ModelGroupCreate(name="GPT-5", protocols=[ProtocolKind.ANTHROPIC])
        )


@pytest.mark.asyncio
async def test_group_candidates_match_any_selected_protocol(session_factory) -> None:
    await _seed_channel(
        session_factory,
        combo_id="chat-combo",
        protocols=[ProtocolKind.OPENAI_CHAT],
        model_name="gpt-5-mini",
    )
    await _seed_channel(
        session_factory,
        combo_id="embedding-combo",
        protocols=[ProtocolKind.OPENAI_EMBEDDING],
        model_name="text-embedding-3-large",
    )

    result = await DomainStore(session_factory).list_group_candidates(
        ModelGroupCandidatesRequest(
            protocols=[ProtocolKind.OPENAI_CHAT, ProtocolKind.ANTHROPIC]
        )
    )

    candidate_ids = {item.channel_id for item in result.candidates}
    assert "chat-combo_openai_chat" in candidate_ids
    assert "embedding-combo_openai_embedding" not in candidate_ids

    anthropic_result = await DomainStore(session_factory).list_group_candidates(
        ModelGroupCandidatesRequest(protocols=[ProtocolKind.ANTHROPIC])
    )
    assert "chat-combo_openai_chat" in {
        item.channel_id for item in anthropic_result.candidates
    }


@pytest.mark.asyncio
async def test_group_candidates_deduplicate(session_factory) -> None:
    channel_id, credential_id = await _seed_channel(
        session_factory,
        combo_id="dedupe-combo",
        protocols=[ProtocolKind.OPENAI_CHAT],
        model_name="gpt-5-mini",
    )
    async with session_factory() as session:
        session.add(
            SiteDiscoveredModelEntity(
                id="dedupe-combo-model-duplicate",
                protocol_config_id="dedupe-combo",
                credential_id=credential_id,
                model_name="gpt-5-mini",
                enabled=1,
                sort_order=1,
                protocol=None,
            )
        )
        await session.commit()

    result = await DomainStore(session_factory).list_group_candidates(
        ModelGroupCandidatesRequest(protocols=[ProtocolKind.OPENAI_CHAT])
    )

    matches = [
        item
        for item in result.candidates
        if (
            item.channel_id,
            item.credential_id,
            item.model_name,
        )
        == (channel_id, credential_id, "gpt-5-mini")
    ]
    assert len(matches) == 1


@pytest.mark.asyncio
async def test_group_item_must_reach_at_least_one_group_protocol(
    session_factory,
) -> None:
    channel_id, credential_id = await _seed_channel(
        session_factory,
        combo_id="embedding-only",
        protocols=[ProtocolKind.OPENAI_EMBEDDING],
        model_name="text-embedding-3-large",
    )

    with pytest.raises(
        ValueError,
        match="Channels cannot reach any selected protocol: embedding-only_openai_embedding",
    ):
        await DomainStore(session_factory).create_group(
            ModelGroupCreate(
                name="Chat Group",
                protocols=[ProtocolKind.OPENAI_CHAT],
                items=[
                    ModelGroupItemInput(
                        channel_id=channel_id,
                        credential_id=credential_id,
                        model_name="text-embedding-3-large",
                    )
                ],
            )
        )


@pytest.mark.asyncio
async def test_route_group_target_must_cover_all_protocols(session_factory) -> None:
    store = DomainStore(session_factory)
    target = await store.create_group(
        ModelGroupCreate(name="Target", protocols=[ProtocolKind.OPENAI_CHAT])
    )

    with pytest.raises(
        ValueError,
        match="Route target protocols must cover source protocols: anthropic",
    ):
        await store.create_group(
            ModelGroupCreate(
                name="Source",
                protocols=[ProtocolKind.OPENAI_CHAT, ProtocolKind.ANTHROPIC],
                route_group_id=target.id,
            )
        )


@pytest.mark.asyncio
async def test_to_group_returns_protocols(session_factory) -> None:
    store = DomainStore(session_factory)
    await store.create_group(
        ModelGroupCreate(
            name="Visible Protocols",
            protocols=[ProtocolKind.OPENAI_CHAT, ProtocolKind.ANTHROPIC],
        )
    )

    groups = await store.list_groups()

    assert groups[0].protocols == [ProtocolKind.OPENAI_CHAT, ProtocolKind.ANTHROPIC]

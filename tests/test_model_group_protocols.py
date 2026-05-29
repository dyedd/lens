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
async def test_group_items_must_cover_every_declared_protocol(session_factory) -> None:
    channel_id, credential_id = await _seed_channel(
        session_factory,
        combo_id="chat-only",
        protocols=[ProtocolKind.OPENAI_CHAT],
        model_name="gpt-5-mini",
    )

    with pytest.raises(
        ValueError,
        match="Protocol openai_embedding has no reachable channel in group items",
    ):
        await DomainStore(session_factory).create_group(
            ModelGroupCreate(
                name="Mixed Group",
                protocols=[ProtocolKind.OPENAI_CHAT, ProtocolKind.OPENAI_EMBEDDING],
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


# ---------------------------------------------------------------------------
# 新增：候选聚合与校验硬化测试
# ---------------------------------------------------------------------------


async def _seed_multi_protocol_channel(
    session_factory,
    *,
    combo_id: str,
    protocols: list[ProtocolKind],
    model_name: str,
    credential_enabled: bool = True,
) -> tuple[str, str]:
    """在多协议 base_url 下创建一个 combo，返回 (代表性 channel_id, credential_id)。"""
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
                    enabled=credential_enabled,
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
                        )
                    ],
                )
            ],
        )
    )
    return f"{combo_id}_{protocols[0].value}", credential_id


@pytest.mark.asyncio
async def test_candidates_multi_protocol_same_combo_aggregates(session_factory) -> None:
    """同 combo + credential + model，chat + responses → 候选仅 1 条，protocols 含两者。"""
    _, credential_id = await _seed_multi_protocol_channel(
        session_factory,
        combo_id="agg-combo",
        protocols=[ProtocolKind.OPENAI_CHAT, ProtocolKind.OPENAI_RESPONSES],
        model_name="gpt-4o",
    )

    result = await DomainStore(session_factory).list_group_candidates(
        ModelGroupCandidatesRequest(
            protocols=[ProtocolKind.OPENAI_CHAT, ProtocolKind.OPENAI_RESPONSES]
        )
    )

    matches = [
        c for c in result.candidates
        if c.combo_id == "agg-combo"
        and c.credential_id == credential_id
        and c.model_name == "gpt-4o"
    ]
    assert len(matches) == 1
    assert ProtocolKind.OPENAI_CHAT in matches[0].protocols
    assert ProtocolKind.OPENAI_RESPONSES in matches[0].protocols


@pytest.mark.asyncio
async def test_candidates_same_model_different_credentials(session_factory) -> None:
    """同名 model 不同 credential → 2 条候选。"""
    combo_id = "diff-cred-combo"
    base_url_id = f"{combo_id}-base"
    cred_a = f"{combo_id}-cred-a"
    cred_b = f"{combo_id}-cred-b"

    await ChannelStore(session_factory).create_site(
        SiteCreate(
            name=f"Site {combo_id}",
            base_urls=[
                SiteBaseUrlInput(
                    id=base_url_id,
                    url="https://api.example.com",
                    compatible_protocols=[ProtocolKind.OPENAI_CHAT],
                )
            ],
            credentials=[
                SiteCredentialInput(id=cred_a, name="CredA", api_key="sk-a"),
                SiteCredentialInput(id=cred_b, name="CredB", api_key="sk-b"),
            ],
            protocols=[
                SiteProtocolConfigInput(
                    id=combo_id,
                    name=f"Combo {combo_id}",
                    base_url_id=base_url_id,
                    credential_id=cred_a,
                    models=[
                        SiteModelInput(
                            id=f"{combo_id}-model-a",
                            credential_id=cred_a,
                            model_name="shared-model",
                        ),
                        SiteModelInput(
                            id=f"{combo_id}-model-b",
                            credential_id=cred_b,
                            model_name="shared-model",
                        ),
                    ],
                )
            ],
        )
    )

    result = await DomainStore(session_factory).list_group_candidates(
        ModelGroupCandidatesRequest(protocols=[ProtocolKind.OPENAI_CHAT])
    )

    matches = [
        c for c in result.candidates
        if c.combo_id == combo_id and c.model_name == "shared-model"
    ]
    assert len(matches) == 2
    cred_ids = {c.credential_id for c in matches}
    assert cred_a in cred_ids
    assert cred_b in cred_ids


@pytest.mark.asyncio
async def test_candidates_chat_only_with_responses_group(session_factory) -> None:
    """chat-only 模型 + 组[responses] → 可选，items 落 chat 通道（转换兜底）。"""
    _, credential_id = await _seed_multi_protocol_channel(
        session_factory,
        combo_id="chat-resp-combo",
        protocols=[ProtocolKind.OPENAI_CHAT],
        model_name="gpt-4o",
    )

    result = await DomainStore(session_factory).list_group_candidates(
        ModelGroupCandidatesRequest(protocols=[ProtocolKind.OPENAI_RESPONSES])
    )

    matches = [
        c for c in result.candidates
        if c.combo_id == "chat-resp-combo" and c.credential_id == credential_id
    ]
    assert len(matches) == 1
    # items 应落在 chat 通道（openai_chat 可转换到 openai_responses）
    assert len(matches[0].items) == 1
    assert matches[0].items[0].channel_id == f"chat-resp-combo_openai_chat"


@pytest.mark.asyncio
async def test_candidates_chat_only_with_chat_and_responses_group(session_factory) -> None:
    """chat-only + 组[chat, responses] → items 仅 1 条 chat（同通道兜底多协议只一条）。"""
    _, credential_id = await _seed_multi_protocol_channel(
        session_factory,
        combo_id="chat-cr-combo",
        protocols=[ProtocolKind.OPENAI_CHAT],
        model_name="gpt-4o",
    )

    result = await DomainStore(session_factory).list_group_candidates(
        ModelGroupCandidatesRequest(
            protocols=[ProtocolKind.OPENAI_CHAT, ProtocolKind.OPENAI_RESPONSES]
        )
    )

    matches = [
        c for c in result.candidates
        if c.combo_id == "chat-cr-combo" and c.credential_id == credential_id
    ]
    assert len(matches) == 1
    # chat 原生覆盖 OPENAI_CHAT，又兜底 OPENAI_RESPONSES → 同一 chat 通道，共 1 条 item
    assert len(matches[0].items) == 1
    assert matches[0].items[0].channel_id == f"chat-cr-combo_openai_chat"


@pytest.mark.asyncio
async def test_candidates_chat_only_not_cover_embedding(session_factory) -> None:
    """chat-only + 组[chat, embedding] → 不在候选（覆盖不足）。"""
    await _seed_multi_protocol_channel(
        session_factory,
        combo_id="no-emb-combo",
        protocols=[ProtocolKind.OPENAI_CHAT],
        model_name="gpt-4o",
    )

    result = await DomainStore(session_factory).list_group_candidates(
        ModelGroupCandidatesRequest(
            protocols=[ProtocolKind.OPENAI_CHAT, ProtocolKind.OPENAI_EMBEDDING]
        )
    )

    combo_ids = {c.combo_id for c in result.candidates}
    assert "no-emb-combo" not in combo_ids


@pytest.mark.asyncio
async def test_candidates_disabled_credential_excluded(session_factory) -> None:
    """credential disabled → 不出现在候选。"""
    await _seed_multi_protocol_channel(
        session_factory,
        combo_id="dis-cred-combo",
        protocols=[ProtocolKind.OPENAI_CHAT],
        model_name="gpt-4o",
        credential_enabled=False,
    )

    result = await DomainStore(session_factory).list_group_candidates(
        ModelGroupCandidatesRequest(protocols=[ProtocolKind.OPENAI_CHAT])
    )

    combo_ids = {c.combo_id for c in result.candidates}
    assert "dis-cred-combo" not in combo_ids


@pytest.mark.asyncio
async def test_validate_group_rejects_disabled_credential(session_factory) -> None:
    """_validate_group_payload 拒绝 disabled credential。"""
    channel_id, credential_id = await _seed_multi_protocol_channel(
        session_factory,
        combo_id="val-dis-cred",
        protocols=[ProtocolKind.OPENAI_CHAT],
        model_name="gpt-4o",
        credential_enabled=False,
    )

    with pytest.raises(ValueError, match="Credential is disabled or not found"):
        await DomainStore(session_factory).create_group(
            ModelGroupCreate(
                name="DisabledCredGroup",
                protocols=[ProtocolKind.OPENAI_CHAT],
                items=[
                    ModelGroupItemInput(
                        channel_id=channel_id,
                        credential_id=credential_id,
                        model_name="gpt-4o",
                    )
                ],
            )
        )


@pytest.mark.asyncio
async def test_candidates_model_protocol_none_protocols_deduplicated(
    session_factory,
) -> None:
    """model.protocol is None 多协议展开 → protocols 去重，候选仅 1 条。"""
    _, credential_id = await _seed_multi_protocol_channel(
        session_factory,
        combo_id="dedup-proto-combo",
        protocols=[ProtocolKind.OPENAI_CHAT, ProtocolKind.ANTHROPIC],
        model_name="gpt-4o",
    )

    result = await DomainStore(session_factory).list_group_candidates(
        ModelGroupCandidatesRequest(
            protocols=[ProtocolKind.OPENAI_CHAT, ProtocolKind.ANTHROPIC]
        )
    )

    matches = [
        c for c in result.candidates
        if c.combo_id == "dedup-proto-combo" and c.credential_id == credential_id
    ]
    # 同 combo + credential + model → 聚合为 1 条
    assert len(matches) == 1
    # protocols 去重，两个协议均在
    assert len(set(matches[0].protocols)) == len(matches[0].protocols)
    assert ProtocolKind.OPENAI_CHAT in matches[0].protocols
    assert ProtocolKind.ANTHROPIC in matches[0].protocols


@pytest.mark.asyncio
async def test_candidates_exclude_items_removes_model(session_factory) -> None:
    """exclude_items 命中模型身份 → 该模型不再出现在候选。"""
    channel_id, credential_id = await _seed_multi_protocol_channel(
        session_factory,
        combo_id="excl-combo",
        protocols=[ProtocolKind.OPENAI_CHAT],
        model_name="gpt-4o",
    )

    # 不排除时，候选包含该模型
    result_all = await DomainStore(session_factory).list_group_candidates(
        ModelGroupCandidatesRequest(protocols=[ProtocolKind.OPENAI_CHAT])
    )
    assert any(c.combo_id == "excl-combo" for c in result_all.candidates)

    # 排除后，候选不包含该模型
    result_excl = await DomainStore(session_factory).list_group_candidates(
        ModelGroupCandidatesRequest(
            protocols=[ProtocolKind.OPENAI_CHAT],
            exclude_items=[
                ModelGroupItemInput(
                    channel_id=channel_id,
                    credential_id=credential_id,
                    model_name="gpt-4o",
                )
            ],
        )
    )
    assert not any(c.combo_id == "excl-combo" for c in result_excl.candidates)

from time import monotonic
from types import SimpleNamespace

import pytest
import pytest_asyncio

from lens_api.core.db import Base, create_engine, create_session_factory
from lens_api.gateway import service
from lens_api.gateway.router import RoundRobinRouter, RouteTarget
from lens_api.models import (
    ChannelConfig,
    ChannelKeyItem,
    ChannelStatus,
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


# ---------------------------------------------------------------------------
# 辅助：快速构造 ChannelConfig + RouteTarget
# ---------------------------------------------------------------------------


def _make_channel(
    channel_id: str,
    protocol: ProtocolKind,
    *,
    keys: list[ChannelKeyItem] | None = None,
) -> ChannelConfig:
    return ChannelConfig(
        id=channel_id,
        name=channel_id,
        protocol=protocol,
        base_url="https://api.example.com",
        api_key="sk-test",
        status=ChannelStatus.ENABLED,
        keys=keys or [],
    )


def _make_target(
    channel: ChannelConfig,
    model_name: str = "gpt-4o",
    credential_id: str | None = None,
) -> RouteTarget:
    return RouteTarget(
        channel=channel,
        model_name=model_name,
        credential_id=credential_id,
    )


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


# ---------------------------------------------------------------------------
# 单元测试：_prefer_native_targets（原生优先去重）
# ---------------------------------------------------------------------------


def test_prefer_native_drops_converted_when_native_available() -> None:
    """同 combo/credential/model 同时有原生 responses 和 chat 转换目标时，选中原生。"""
    combo = "site-abc"
    cred = "cred-1"
    model = "gpt-4o"

    native_ch = _make_channel(f"{combo}_openai_responses", ProtocolKind.OPENAI_RESPONSES)
    converted_ch = _make_channel(f"{combo}_openai_chat", ProtocolKind.OPENAI_CHAT)

    native_target = _make_target(native_ch, model, cred)
    converted_target = _make_target(converted_ch, model, cred)

    router = RoundRobinRouter()
    result = router._prefer_native_targets(
        [native_target, converted_target], ProtocolKind.OPENAI_RESPONSES
    )

    assert len(result) == 1
    assert result[0].channel.protocol == ProtocolKind.OPENAI_RESPONSES


def test_prefer_native_falls_back_to_converted_when_native_cooled() -> None:
    """原生 responses 目标处于冷却状态被移除后，转换目标作为兜底仍能被选中。"""
    combo = "site-def"
    cred = "cred-2"
    model = "gpt-4o"

    native_ch = _make_channel(f"{combo}_openai_responses", ProtocolKind.OPENAI_RESPONSES)
    converted_ch = _make_channel(f"{combo}_openai_chat", ProtocolKind.OPENAI_CHAT)

    native_target = _make_target(native_ch, model, cred)
    converted_target = _make_target(converted_ch, model, cred)

    router = RoundRobinRouter()
    # 模拟冷却：将原生 channel 的 health 状态设置为未来时间
    router._health[native_ch.id].opened_until = monotonic() + 9999

    # 可用性过滤后，原生目标被移除，只剩转换目标
    now = monotonic()
    available = [t for t in [native_target, converted_target]
                 if router._target_is_available(t, now=now)]

    # 此时 available 只含 converted_target（原生被冷却过滤掉了）
    # _prefer_native_targets 应保留转换目标（原组无原生可用，不去重）
    result = router._prefer_native_targets(available, ProtocolKind.OPENAI_RESPONSES)

    assert len(result) == 1
    assert result[0].channel.protocol == ProtocolKind.OPENAI_CHAT


def test_prefer_native_does_not_deduplicate_different_credentials() -> None:
    """不同 credential 的同名模型不互相去重，各自保留。"""
    combo = "site-ghi"
    model = "gpt-4o"

    # cred-A 有原生 responses
    native_ch_a = _make_channel(f"{combo}_openai_responses", ProtocolKind.OPENAI_RESPONSES)
    native_a = _make_target(native_ch_a, model, "cred-A")

    # cred-A 同时有 chat 转换目标（应被去重）
    converted_ch_a = _make_channel(f"{combo}_openai_chat", ProtocolKind.OPENAI_CHAT)
    converted_a = _make_target(converted_ch_a, model, "cred-A")

    # cred-B 只有 chat 转换目标（无原生，应保留）
    converted_b = _make_target(converted_ch_a, model, "cred-B")

    router = RoundRobinRouter()
    result = router._prefer_native_targets(
        [native_a, converted_a, converted_b], ProtocolKind.OPENAI_RESPONSES
    )

    protocols = [(t.credential_id, t.channel.protocol) for t in result]
    # cred-A 的转换目标应被去重，cred-B 的转换目标应保留
    assert ("cred-A", ProtocolKind.OPENAI_RESPONSES) in protocols
    assert ("cred-A", ProtocolKind.OPENAI_CHAT) not in protocols
    assert ("cred-B", ProtocolKind.OPENAI_CHAT) in protocols
    assert len(result) == 2

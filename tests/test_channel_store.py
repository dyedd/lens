import pytest
import pytest_asyncio
from sqlalchemy import select

from lens_api.core.db import Base, create_engine, create_session_factory
from lens_api.models import (
    ProtocolKind,
    SiteBaseUrl,
    SiteBaseUrlInput,
    SiteConfig,
    SiteCreate,
    SiteCredential,
    SiteCredentialInput,
    SiteModel,
    SiteModelInput,
    SiteProtocolConfig,
    SiteProtocolConfigInput,
    SiteUpdate,
)
from lens_api.persistence.channel_store import ChannelStore, _deduplicate_combo_models
from lens_api.persistence.entities import ModelGroupItemEntity, SiteDiscoveredModelEntity


def _model(
    model_name: str,
    protocol: ProtocolKind | None,
    credential_id: str = "key-1",
    enabled: bool = True,
    id: str | None = None,
) -> SiteModelInput:
    return SiteModelInput(
        id=id,
        credential_id=credential_id,
        model_name=model_name,
        protocol=protocol,
        enabled=enabled,
    )


def test_deduplicate_combo_models_keeps_same_name_across_protocols() -> None:
    models = _deduplicate_combo_models(
        [
            _model("kimi-k2.6", ProtocolKind.OPENAI_CHAT),
            _model("kimi-k2.6", ProtocolKind.OPENAI_RESPONSES),
        ]
    )

    assert len(models) == 2
    assert [model.model_name for model in models] == ["kimi-k2.6", "kimi-k2.6"]
    assert [model.protocol for model in models] == [
        ProtocolKind.OPENAI_CHAT,
        ProtocolKind.OPENAI_RESPONSES,
    ]


def test_deduplicate_combo_models_keeps_distinct_credentials() -> None:
    models = _deduplicate_combo_models(
        [
            _model("kimi-k2.6", ProtocolKind.OPENAI_CHAT, credential_id="key-1"),
            _model("kimi-k2.6", ProtocolKind.OPENAI_CHAT, credential_id="key-2"),
        ]
    )

    assert len(models) == 2


def test_deduplicate_combo_models_merges_exact_duplicates_without_widening_protocol() -> None:
    models = _deduplicate_combo_models(
        [
            _model("kimi-k2.6", ProtocolKind.OPENAI_CHAT, enabled=False),
            _model("kimi-k2.6", ProtocolKind.OPENAI_CHAT, enabled=True),
        ]
    )

    assert len(models) == 1
    assert models[0].protocol == ProtocolKind.OPENAI_CHAT
    assert models[0].enabled is True


def test_deduplicate_combo_models_drops_none_when_specific_protocol_exists() -> None:
    models = _deduplicate_combo_models(
        [
            _model("gpt-5.5", None),
            _model("gpt-5.5", ProtocolKind.OPENAI_CHAT),
            _model("gpt-5.5", ProtocolKind.OPENAI_RESPONSES),
        ]
    )

    assert len(models) == 2
    assert [model.protocol for model in models] == [
        ProtocolKind.OPENAI_CHAT,
        ProtocolKind.OPENAI_RESPONSES,
    ]


def test_deduplicate_combo_models_drops_none_when_specific_protocol_first() -> None:
    models = _deduplicate_combo_models(
        [
            _model("gpt-5.5", ProtocolKind.OPENAI_CHAT),
            _model("gpt-5.5", ProtocolKind.OPENAI_RESPONSES),
            _model("gpt-5.5", None),
        ]
    )

    assert len(models) == 2
    assert [item.protocol for item in models] == [
        ProtocolKind.OPENAI_CHAT,
        ProtocolKind.OPENAI_RESPONSES,
    ]


def test_deduplicate_combo_models_keeps_single_none_when_no_specific_protocol() -> None:
    models = _deduplicate_combo_models(
        [
            _model("gpt-5.5", None, enabled=False),
            _model("gpt-5.5", None, enabled=True),
        ]
    )

    assert len(models) == 1
    assert models[0].protocol is None
    assert models[0].enabled is True


def test_deduplicate_combo_models_merges_exact_duplicate_preserves_first_id() -> None:
    models = _deduplicate_combo_models(
        [
            _model("gpt-5.5", ProtocolKind.OPENAI_CHAT, enabled=False, id="model-1"),
            _model("gpt-5.5", ProtocolKind.OPENAI_CHAT, enabled=True, id="model-2"),
        ]
    )

    assert len(models) == 1
    assert models[0].id == "model-1"
    assert models[0].protocol == ProtocolKind.OPENAI_CHAT
    assert models[0].enabled is True


def test_flatten_site_uses_site_name_for_channel_display() -> None:
    site = SiteConfig(
        id="site-1",
        name="Actual Channel",
        base_urls=[
            SiteBaseUrl(
                id="base-1",
                url="https://api.example.com",
                compatible_protocols=[ProtocolKind.OPENAI_CHAT],
            )
        ],
        credentials=[
            SiteCredential(id="key-1", name="Primary", api_key="sk-test")
        ],
        protocols=[
            SiteProtocolConfig(
                id="combo-1",
                name="组合 1",
                base_url_id="base-1",
                credential_id="key-1",
                models=[
                    SiteModel(
                        id="model-1",
                        credential_id="key-1",
                        credential_name="Primary",
                        model_name="gpt-5-mini",
                        protocol=ProtocolKind.OPENAI_CHAT,
                    )
                ],
            )
        ],
    )

    channels = ChannelStore(None)._flatten_site(site)  # type: ignore[arg-type]

    assert len(channels) == 1
    assert channels[0].name == "Actual Channel"


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


@pytest.mark.asyncio
async def test_channel_store_persists_same_model_across_protocols(
    session_factory,
) -> None:
    await ChannelStore(session_factory).create_site(
        SiteCreate(
            name="Multi Protocol Site",
            base_urls=[
                SiteBaseUrlInput(
                    id="base-1",
                    url="https://api.example.com",
                    compatible_protocols=[
                        ProtocolKind.OPENAI_CHAT,
                        ProtocolKind.OPENAI_RESPONSES,
                    ],
                )
            ],
            credentials=[
                SiteCredentialInput(
                    id="key-1",
                    name="Primary",
                    api_key="sk-test",
                )
            ],
            protocols=[
                SiteProtocolConfigInput(
                    id="combo-1",
                    name="Combo",
                    base_url_id="base-1",
                    credential_id="key-1",
                    models=[
                        SiteModelInput(
                            id="shared-id",
                            credential_id="key-1",
                            model_name="gpt-5.5",
                            protocol=ProtocolKind.OPENAI_CHAT,
                        ),
                        SiteModelInput(
                            id="shared-id",
                            credential_id="key-1",
                            model_name="gpt-5.5",
                            protocol=ProtocolKind.OPENAI_RESPONSES,
                        ),
                    ],
                )
            ],
        )
    )

    async with session_factory() as session:
        rows = (
            await session.execute(
                select(SiteDiscoveredModelEntity)
                .where(SiteDiscoveredModelEntity.protocol_config_id == "combo-1")
                .order_by(SiteDiscoveredModelEntity.sort_order)
            )
        ).scalars().all()

    assert len(rows) == 2
    assert [row.model_name for row in rows] == ["gpt-5.5", "gpt-5.5"]
    assert [row.protocol for row in rows] == [
        ProtocolKind.OPENAI_CHAT.value,
        ProtocolKind.OPENAI_RESPONSES.value,
    ]
    assert rows[0].id != rows[1].id


@pytest.mark.asyncio
async def test_flatten_excludes_unselected_protocol_channel(
    session_factory,
) -> None:
    store = ChannelStore(session_factory)
    await store.create_site(
        SiteCreate(
            name="Selective Protocol Site",
            base_urls=[
                SiteBaseUrlInput(
                    id="base-1",
                    url="https://api.example.com",
                    compatible_protocols=[
                        ProtocolKind.OPENAI_CHAT,
                        ProtocolKind.OPENAI_RESPONSES,
                        ProtocolKind.ANTHROPIC,
                    ],
                )
            ],
            credentials=[
                SiteCredentialInput(
                    id="key-1",
                    name="Primary",
                    api_key="sk-test",
                )
            ],
            protocols=[
                SiteProtocolConfigInput(
                    id="combo-1",
                    name="Combo",
                    base_url_id="base-1",
                    credential_id="key-1",
                    models=[
                        SiteModelInput(
                            id="model-chat",
                            credential_id="key-1",
                            model_name="gpt-5.5",
                            protocol=ProtocolKind.OPENAI_CHAT,
                        ),
                        SiteModelInput(
                            id="model-responses",
                            credential_id="key-1",
                            model_name="gpt-5.5",
                            protocol=ProtocolKind.OPENAI_RESPONSES,
                        ),
                    ],
                )
            ],
        )
    )

    channels = await store.list()

    anthropic_channels = [
        c for c in channels if c.protocol == ProtocolKind.ANTHROPIC
    ]
    assert anthropic_channels
    for ch in anthropic_channels:
        assert "gpt-5.5" not in ch.model_patterns
        assert all(m.model_name != "gpt-5.5" for m in ch.models)

    chat_channels = [
        c for c in channels if c.protocol == ProtocolKind.OPENAI_CHAT
    ]
    assert any("gpt-5.5" in c.model_patterns for c in chat_channels)


@pytest.mark.asyncio
async def test_cleanup_removes_stale_item_when_model_moves_protocol(
    session_factory,
) -> None:
    """模型从 openai_chat 移到 openai_responses 后，指向旧 combo_openai_chat 的
    group item 必须被清理（回归：旧实现只按 combo 前缀匹配，忽略协议后缀，
    会让失效条目残留）。"""
    store = ChannelStore(session_factory)
    await store.create_site(
        SiteCreate(
            name="Site",
            base_urls=[
                SiteBaseUrlInput(
                    id="base-1",
                    url="https://api.example.com",
                    compatible_protocols=[
                        ProtocolKind.OPENAI_CHAT,
                        ProtocolKind.OPENAI_RESPONSES,
                    ],
                )
            ],
            credentials=[
                SiteCredentialInput(id="key-1", name="Primary", api_key="sk-test")
            ],
            protocols=[
                SiteProtocolConfigInput(
                    id="combo-1",
                    name="Combo",
                    base_url_id="base-1",
                    credential_id="key-1",
                    models=[_model("gpt-5.5", ProtocolKind.OPENAI_CHAT)],
                )
            ],
        )
    )

    # 手动放入一个指向 combo-1_openai_chat 的 group item
    async with session_factory() as session:
        session.add(
            ModelGroupItemEntity(
                group_id="group-1",
                channel_id="combo-1_openai_chat",
                credential_id="key-1",
                model_name="gpt-5.5",
                sort_order=0,
            )
        )
        await session.commit()

    # 更新站点：该模型改为只服务 openai_responses
    site_id = (await store.list_sites())[0].id
    await store.update_site(
        site_id,
        SiteUpdate(
            name="Site",
            base_urls=[
                SiteBaseUrlInput(
                    id="base-1",
                    url="https://api.example.com",
                    compatible_protocols=[
                        ProtocolKind.OPENAI_CHAT,
                        ProtocolKind.OPENAI_RESPONSES,
                    ],
                )
            ],
            credentials=[
                SiteCredentialInput(id="key-1", name="Primary", api_key="sk-test")
            ],
            protocols=[
                SiteProtocolConfigInput(
                    id="combo-1",
                    name="Combo",
                    base_url_id="base-1",
                    credential_id="key-1",
                    models=[_model("gpt-5.5", ProtocolKind.OPENAI_RESPONSES)],
                )
            ],
        ),
    )

    async with session_factory() as session:
        remaining = (
            (await session.execute(select(ModelGroupItemEntity.channel_id)))
            .scalars()
            .all()
        )
    # 指向 combo-1_openai_chat 的失效条目应被清理
    assert "combo-1_openai_chat" not in remaining


@pytest.mark.asyncio
async def test_cleanup_keeps_item_when_model_inherits_all_protocols(
    session_factory,
) -> None:
    """模型 protocol=None（继承地址全部协议）时，combo 各协议的 group item 都有效，
    不应被误删。"""
    store = ChannelStore(session_factory)
    await store.create_site(
        SiteCreate(
            name="Site",
            base_urls=[
                SiteBaseUrlInput(
                    id="base-1",
                    url="https://api.example.com",
                    compatible_protocols=[
                        ProtocolKind.OPENAI_CHAT,
                        ProtocolKind.OPENAI_RESPONSES,
                    ],
                )
            ],
            credentials=[
                SiteCredentialInput(id="key-1", name="Primary", api_key="sk-test")
            ],
            protocols=[
                SiteProtocolConfigInput(
                    id="combo-1",
                    name="Combo",
                    base_url_id="base-1",
                    credential_id="key-1",
                    models=[_model("gpt-5.5", None)],
                )
            ],
        )
    )

    async with session_factory() as session:
        session.add(
            ModelGroupItemEntity(
                group_id="group-1",
                channel_id="combo-1_openai_responses",
                credential_id="key-1",
                model_name="gpt-5.5",
                sort_order=0,
            )
        )
        await session.commit()

    site_id = (await store.list_sites())[0].id
    await store.update_site(
        site_id,
        SiteUpdate(
            name="Site",
            base_urls=[
                SiteBaseUrlInput(
                    id="base-1",
                    url="https://api.example.com",
                    compatible_protocols=[
                        ProtocolKind.OPENAI_CHAT,
                        ProtocolKind.OPENAI_RESPONSES,
                    ],
                )
            ],
            credentials=[
                SiteCredentialInput(id="key-1", name="Primary", api_key="sk-test")
            ],
            protocols=[
                SiteProtocolConfigInput(
                    id="combo-1",
                    name="Combo",
                    base_url_id="base-1",
                    credential_id="key-1",
                    models=[_model("gpt-5.5", None)],
                )
            ],
        ),
    )

    async with session_factory() as session:
        remaining = (
            (await session.execute(select(ModelGroupItemEntity.channel_id)))
            .scalars()
            .all()
        )
    assert "combo-1_openai_responses" in remaining

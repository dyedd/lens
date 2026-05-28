import asyncio
import json
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from lens_api.core.db import Base, create_engine, create_session_factory
from lens_api.persistence.backup_store import BACKUP_DUMP_VERSION, BackupStore
from lens_api.persistence.entities import ModelGroupEntity, ModelGroupItemEntity


def _backup_payload(
    groups: list[dict[str, object]],
    sites: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "version": BACKUP_DUMP_VERSION,
        "exported_at": "2026-05-28T00:00:00+00:00",
        "lens_version": "test",
        "include_request_logs": False,
        "include_gateway_api_keys": False,
        "sites": sites or [],
        "groups": groups,
    }


def _group(
    *,
    group_id: str = "group-1",
    name: str = "Chat",
    **fields: object,
) -> dict[str, object]:
    data: dict[str, object] = {
        "id": group_id,
        "name": name,
        "strategy": "round_robin",
        "route_group_id": "",
        "sync_filter_mode": "",
        "sync_filter_query": "",
        "items": [],
    }
    data.update(fields)
    return data


def _site(
    *,
    combo_id: str = "combo-1",
    protocols: list[str] | None = None,
    model_protocol: str | None = None,
    model_name: str = "gpt-5-mini",
) -> dict[str, object]:
    protocols = protocols or ["openai_chat"]
    return {
        "id": f"{combo_id}-site",
        "name": f"Site {combo_id}",
        "base_urls": [
            {
                "id": f"{combo_id}-base",
                "url": "https://api.example.com",
                "compatible_protocols": protocols,
            }
        ],
        "credentials": [
            {
                "id": f"{combo_id}-credential",
                "name": "Primary",
                "api_key": "sk-test",
            }
        ],
        "protocols": [
            {
                "id": combo_id,
                "name": f"Combo {combo_id}",
                "base_url_id": f"{combo_id}-base",
                "credential_id": f"{combo_id}-credential",
                "models": [
                    {
                        "id": f"{combo_id}-model",
                        "credential_id": f"{combo_id}-credential",
                        "model_name": model_name,
                        "protocol": model_protocol,
                    }
                ],
            }
        ],
    }


def _parse_groups(
    groups: list[dict[str, object]],
    sites: list[dict[str, object]] | None = None,
):
    return BackupStore.parse_dump(json.dumps(_backup_payload(groups, sites)).encode())


async def _create_store(
    tmp_path: Path,
) -> tuple[AsyncEngine, async_sessionmaker, BackupStore]:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'backup.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = create_session_factory(engine)
    return engine, session_factory, BackupStore(session_factory)


async def _import_groups(
    tmp_path: Path, groups: list[dict[str, object]]
) -> ModelGroupEntity:
    engine, session_factory, store = await _create_store(tmp_path)
    try:
        await store.import_dump(_parse_groups(groups))
        async with session_factory() as session:
            entity = await session.get(ModelGroupEntity, "group-1")
            assert entity is not None
            return entity
    finally:
        await engine.dispose()


def test_export_uses_protocols(tmp_path: Path) -> None:
    async def run() -> None:
        engine, session_factory, store = await _create_store(tmp_path)
        try:
            async with session_factory() as session:
                session.add(
                    ModelGroupEntity(
                        id="group-1",
                        name="Chat",
                        protocols_json=json.dumps(
                            ["openai_chat", "openai_responses"]
                        ),
                        strategy="round_robin",
                    )
                )
                await session.commit()

            dump = await store.export_dump(
                lens_version="test",
                include_request_logs=False,
                include_gateway_api_keys=False,
            )
            group = dump.model_dump(mode="json")["groups"][0]

            assert group["protocols"] == ["openai_chat", "openai_responses"]
            assert "protocol" not in group
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_import_old_protocol_field_as_single_protocol_list(tmp_path: Path) -> None:
    entity = asyncio.run(
        _import_groups(
            tmp_path,
            [_group(protocol="openai_chat")],
        )
    )

    assert json.loads(entity.protocols_json) == ["openai_chat"]


def test_import_new_protocols_field(tmp_path: Path) -> None:
    entity = asyncio.run(
        _import_groups(
            tmp_path,
            [_group(protocols=["openai_chat", "openai_responses"])],
        )
    )

    assert json.loads(entity.protocols_json) == [
        "openai_chat",
        "openai_responses",
    ]


def test_import_rejects_duplicate_group_names(tmp_path: Path) -> None:
    async def run() -> None:
        engine, _, store = await _create_store(tmp_path)
        try:
            await store.import_dump(
                _parse_groups(
                    [
                        _group(
                            group_id="group-1",
                            name="Duplicate",
                            protocols=["openai_chat"],
                        ),
                        _group(
                            group_id="group-2",
                            name="Duplicate",
                            protocols=["openai_responses"],
                        ),
                    ]
                )
            )
        finally:
            await engine.dispose()

    with pytest.raises(
        ValueError, match="Duplicate model group name in backup: Duplicate"
    ):
        asyncio.run(run())


def test_import_rejects_empty_protocols() -> None:
    with pytest.raises(
        ValueError, match="Backup model group missing protocols: Empty"
    ):
        _parse_groups([_group(name="Empty", protocols=[])])


def test_import_rewrites_bare_combo_id_to_composite_channel_id(tmp_path: Path) -> None:
    async def run() -> str:
        engine, session_factory, store = await _create_store(tmp_path)
        try:
            await store.import_dump(
                _parse_groups(
                    [
                        _group(
                            protocols=["openai_chat"],
                            items=[
                                {
                                    "channel_id": "combo-1",
                                    "credential_id": "combo-1-credential",
                                    "model_name": "gpt-5-mini",
                                }
                            ],
                        )
                    ],
                    [_site(combo_id="combo-1", protocols=["openai_chat", "anthropic"])],
                )
            )
            async with session_factory() as session:
                item = (
                    await session.execute(select(ModelGroupItemEntity))
                ).scalar_one()
                return item.channel_id
        finally:
            await engine.dispose()

    assert asyncio.run(run()) == "combo-1_openai_chat"


def test_import_rejects_route_group_target_missing_protocol(tmp_path: Path) -> None:
    async def run() -> None:
        engine, _, store = await _create_store(tmp_path)
        try:
            await store.import_dump(
                _parse_groups(
                    [
                        _group(
                            group_id="target",
                            name="Target",
                            protocols=["openai_chat"],
                        ),
                        _group(
                            group_id="source",
                            name="Source",
                            protocols=["openai_chat", "anthropic"],
                            route_group_id="target",
                        ),
                    ]
                )
            )
        finally:
            await engine.dispose()

    with pytest.raises(
        ValueError,
        match="Route target protocols must cover source protocols: anthropic",
    ):
        asyncio.run(run())


def test_import_rejects_group_with_unreachable_declared_protocol(tmp_path: Path) -> None:
    async def run() -> None:
        engine, _, store = await _create_store(tmp_path)
        try:
            await store.import_dump(
                _parse_groups(
                    [
                        _group(
                            protocols=["openai_chat"],
                            items=[
                                {
                                    "channel_id": "embed-combo",
                                    "credential_id": "embed-combo-credential",
                                    "model_name": "text-embedding-3-large",
                                }
                            ],
                        )
                    ],
                    [
                        _site(
                            combo_id="embed-combo",
                            protocols=["openai_embedding"],
                            model_name="text-embedding-3-large",
                        )
                    ],
                )
            )
        finally:
            await engine.dispose()

    with pytest.raises(
        ValueError,
        match="Protocol openai_chat has no reachable channel in group items",
    ):
        asyncio.run(run())

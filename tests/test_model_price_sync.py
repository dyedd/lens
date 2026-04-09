from __future__ import annotations

import asyncio

from lens_api.core.db import Base, create_engine, create_session_factory
from lens_api.core.model_prices import build_group_price_payloads, build_models_dev_price_index
from lens_api.models import ModelGroupCreate, ProtocolKind, RoutingStrategy
from lens_api.persistence.domain_store import DomainStore


def test_build_group_price_payloads_matches_group_name():
    index = build_models_dev_price_index(
        {
            'openai': {
                'models': {
                    'gpt-5.4': {
                        'cost': {
                            'input': 1.25,
                            'output': 10.0,
                        }
                    },
                    'gpt-5.4-mini': {
                        'cost': {
                            'input': 0.25,
                            'output': 2.0,
                        }
                    },
                }
            }
        }
    )

    payloads = build_group_price_payloads(['gpt-5.4', 'missing-model'], index)

    assert payloads == [
        {
            'model_key': 'gpt-5.4',
            'display_name': 'gpt-5.4',
            'input_price_per_million': 1.25,
            'output_price_per_million': 10.0,
            'cache_read_price_per_million': 0.0,
            'cache_write_price_per_million': 0.0,
        }
    ]


def test_sync_model_prices_can_preserve_manual_values(tmp_path):
    asyncio.run(_run_sync_model_prices_can_preserve_manual_values(tmp_path))


async def _run_sync_model_prices_can_preserve_manual_values(tmp_path):
    database_path = tmp_path / 'model-price-sync.db'
    engine = create_engine(f"sqlite+aiosqlite:///{database_path.resolve().as_posix()}")
    session_factory = create_session_factory(engine)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    store = DomainStore(session_factory)
    await store.replace_model_prices([
        {
            'model_key': 'gpt-5.4',
            'display_name': 'gpt-5.4',
            'input_price_per_million': 9.0,
            'output_price_per_million': 19.0,
            'cache_read_price_per_million': 0.9,
            'cache_write_price_per_million': 1.9,
        }
    ])

    await store.sync_model_prices([
        {
            'model_key': 'gpt-5.4',
            'display_name': 'gpt-5.4',
            'input_price_per_million': 1.0,
            'output_price_per_million': 2.0,
            'cache_read_price_per_million': 0.1,
            'cache_write_price_per_million': 0.2,
        }
    ], overwrite_existing=False, allowed_keys=['gpt-5.4'])

    response = await store.list_model_prices()
    assert response.items[0].input_price_per_million == 9.0
    assert response.items[0].output_price_per_million == 19.0
    assert response.items[0].cache_read_price_per_million == 0.9
    assert response.items[0].cache_write_price_per_million == 1.9

    await store.sync_model_prices([
        {
            'model_key': 'gpt-5.4',
            'display_name': 'gpt-5.4',
            'input_price_per_million': 1.0,
            'output_price_per_million': 2.0,
            'cache_read_price_per_million': 0.1,
            'cache_write_price_per_million': 0.2,
        }
    ], overwrite_existing=True, allowed_keys=['gpt-5.4'])

    response = await store.list_model_prices()
    assert response.items[0].input_price_per_million == 1.0
    assert response.items[0].output_price_per_million == 2.0
    assert response.items[0].cache_read_price_per_million == 0.1
    assert response.items[0].cache_write_price_per_million == 0.2

    await engine.dispose()


def test_list_model_prices_returns_all_group_rows(tmp_path):
    asyncio.run(_run_list_model_prices_returns_all_group_rows(tmp_path))


async def _run_list_model_prices_returns_all_group_rows(tmp_path):
    database_path = tmp_path / 'model-price-groups.db'
    engine = create_engine(f"sqlite+aiosqlite:///{database_path.resolve().as_posix()}")
    session_factory = create_session_factory(engine)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    store = DomainStore(session_factory)
    await store.create_group(
        ModelGroupCreate(name='gpt-5.4', protocol=ProtocolKind.OPENAI_CHAT, strategy=RoutingStrategy.ROUND_ROBIN, items=[])
    )
    await store.create_group(
        ModelGroupCreate(name='claude-opus-4-6', protocol=ProtocolKind.ANTHROPIC, strategy=RoutingStrategy.ROUND_ROBIN, items=[])
    )
    await store.replace_model_prices([
        {
            'model_key': 'gpt-5.4',
            'display_name': 'gpt-5.4',
            'input_price_per_million': 1.0,
            'output_price_per_million': 2.0,
            'cache_read_price_per_million': 0.1,
            'cache_write_price_per_million': 0.2,
        }
    ])

    response = await store.list_model_prices()
    items = {item.model_key: item for item in response.items}
    assert set(items) == {'claude-opus-4-6', 'gpt-5.4'}
    assert items['claude-opus-4-6'].input_price_per_million == 0.0
    assert [item.value for item in items['claude-opus-4-6'].protocols] == ['anthropic']
    assert items['gpt-5.4'].cache_read_price_per_million == 0.1

    await engine.dispose()

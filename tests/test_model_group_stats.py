from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from lens_api.core.db import Base, create_engine, create_session_factory
from lens_api.models import ModelGroupCreate, ModelGroupItemInput, ProtocolKind, RoutingStrategy, SiteCreate, SiteUpdate
from lens_api.persistence.domain_store import DomainStore
from lens_api.persistence.channel_store import ChannelStore
from lens_api.persistence.entities import RequestLogEntity
from lens_api.models import SettingItem


def _base_urls(url: str) -> list[dict[str, object]]:
    return [{"url": url, "name": "", "enabled": True}]


def _site_base_urls(site) -> list[dict[str, object]]:
    return [
        {
            "id": item.id,
            "url": str(item.url),
            "name": item.name,
            "enabled": item.enabled,
        }
        for item in site.base_urls
    ]


def test_list_group_stats_returns_aggregated_metrics(tmp_path):
    asyncio.run(_run_group_stats_test(tmp_path))


def test_overview_metrics_merge_imported_stats_with_request_logs(tmp_path):
    asyncio.run(_run_overview_metrics_merge_test(tmp_path))


def test_overview_today_range_filters_current_day(tmp_path):
    asyncio.run(_run_overview_today_range_test(tmp_path))


def test_clear_request_logs_keeps_archived_overview_stats(tmp_path):
    asyncio.run(_run_clear_request_logs_keeps_archived_stats_test(tmp_path))


async def _run_group_stats_test(tmp_path):
    database_path = tmp_path / "group-stats.db"
    database_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite+aiosqlite:///{database_path.resolve().as_posix()}")
    session_factory = create_session_factory(engine)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    channel_store = ChannelStore(session_factory)
    domain_store = DomainStore(session_factory)

    primary_site = await channel_store.create_site(
        SiteCreate(
            name="Primary Claude",
            base_urls=_base_urls("https://primary.example.com"),
            credentials=[{"name": "Key 1", "api_key": "sk-primary", "enabled": True}],
            protocols=[{"protocol": ProtocolKind.OPENAI_CHAT, "enabled": True, "headers": {}, "channel_proxy": "", "param_override": "", "match_regex": "", "bindings": [], "models": []}],
        )
    )
    primary_credential = primary_site.credentials[0]
    primary_protocol = primary_site.protocols[0]
    primary_site = await channel_store.update_site(
        primary_site.id,
        SiteUpdate(
            name=primary_site.name,
            base_urls=_site_base_urls(primary_site),
            credentials=[{"id": primary_credential.id, "name": primary_credential.name, "api_key": primary_credential.api_key, "enabled": True}],
            protocols=[{"id": primary_protocol.id, "protocol": primary_protocol.protocol, "enabled": True, "headers": {}, "channel_proxy": "", "param_override": "", "match_regex": "", "bindings": [{"credential_id": primary_credential.id, "enabled": True}], "models": [{"credential_id": primary_credential.id, "model_name": "claude-opus-4-6-2026-03-31", "enabled": True}, {"credential_id": primary_credential.id, "model_name": "gpt-4.1-2026-03-30", "enabled": True}]}],
        ),
    )
    primary_channel = primary_site.protocols[0]

    fallback_site = await channel_store.create_site(
        SiteCreate(
            name="Fallback Claude",
            base_urls=_base_urls("https://fallback.example.com"),
            credentials=[{"name": "Key 1", "api_key": "sk-fallback", "enabled": True}],
            protocols=[{"protocol": ProtocolKind.OPENAI_CHAT, "enabled": True, "headers": {}, "channel_proxy": "", "param_override": "", "match_regex": "", "bindings": [], "models": []}],
        )
    )
    fallback_credential = fallback_site.credentials[0]
    fallback_protocol = fallback_site.protocols[0]
    fallback_site = await channel_store.update_site(
        fallback_site.id,
        SiteUpdate(
            name=fallback_site.name,
            base_urls=_site_base_urls(fallback_site),
            credentials=[{"id": fallback_credential.id, "name": fallback_credential.name, "api_key": fallback_credential.api_key, "enabled": True}],
            protocols=[{"id": fallback_protocol.id, "protocol": fallback_protocol.protocol, "enabled": True, "headers": {}, "channel_proxy": "", "param_override": "", "match_regex": "", "bindings": [{"credential_id": fallback_credential.id, "enabled": True}], "models": [{"credential_id": fallback_credential.id, "model_name": "claude-opus-4-6-2026-03-31", "enabled": True}]}],
        ),
    )
    fallback_channel = fallback_site.protocols[0]

    primary_group = await domain_store.create_group(
        ModelGroupCreate(
            name="claude-opus-4-6",
            protocol=ProtocolKind.OPENAI_CHAT,
            strategy=RoutingStrategy.ROUND_ROBIN,
            items=[
                ModelGroupItemInput(channel_id=primary_channel.id, model_name="claude-opus-4-6-2026-03-31"),
                ModelGroupItemInput(channel_id=fallback_channel.id, model_name="claude-opus-4-6-2026-03-31"),
            ],
        )
    )
    await domain_store.create_group(
        ModelGroupCreate(
            name="gpt-4.1",
            protocol=ProtocolKind.OPENAI_CHAT,
            strategy=RoutingStrategy.FAILOVER,
            items=[
                ModelGroupItemInput(channel_id=primary_channel.id, model_name="gpt-4.1-2026-03-30"),
            ],
        )
    )

    await domain_store.create_request_log(
        protocol=ProtocolKind.OPENAI_CHAT.value,
        requested_model=primary_group.name,
        matched_group_name=primary_group.name,
        channel_id=primary_channel.id,
        channel_name=primary_channel.id,
        gateway_key_id="gw-a",
        status_code=200,
        success=True,
        is_stream=False,
        first_token_latency_ms=0,
        latency_ms=180,
        resolved_model="claude-opus-4-6-2026-03-31",
        input_tokens=1000,
        output_tokens=500,
        total_tokens=1500,
        input_cost_usd=0.003,
        output_cost_usd=0.006,
        total_cost_usd=0.009,
        request_content='{"model":"claude-opus-4-6"}',
        response_content='{"model":"claude-opus-4-6-2026-03-31"}',
        attempts=[],
        error_message=None,
    )
    await domain_store.create_request_log(
        protocol=ProtocolKind.OPENAI_CHAT.value,
        requested_model=primary_group.name,
        matched_group_name=primary_group.name,
        channel_id=fallback_channel.id,
        channel_name=fallback_channel.id,
        gateway_key_id="gw-a",
        status_code=429,
        success=False,
        is_stream=False,
        first_token_latency_ms=0,
        latency_ms=220,
        resolved_model=None,
        input_tokens=200,
        output_tokens=0,
        total_tokens=200,
        input_cost_usd=0.0,
        output_cost_usd=0.0,
        total_cost_usd=0.0,
        request_content='{"model":"claude-opus-4-6"}',
        response_content=None,
        attempts=[],
        error_message="rate limited",
    )
    await domain_store.create_request_log(
        protocol=ProtocolKind.OPENAI_CHAT.value,
        requested_model="gpt-4.1",
        matched_group_name="gpt-4.1",
        channel_id=primary_channel.id,
        channel_name=primary_channel.id,
        gateway_key_id="gw-b",
        status_code=200,
        success=True,
        is_stream=False,
        first_token_latency_ms=0,
        latency_ms=90,
        resolved_model="gpt-4.1-2026-03-30",
        input_tokens=120,
        output_tokens=80,
        total_tokens=200,
        input_cost_usd=0.001,
        output_cost_usd=0.002,
        total_cost_usd=0.003,
        request_content='{"model":"gpt-4.1"}',
        response_content='{"model":"gpt-4.1-2026-03-30"}',
        attempts=[],
        error_message=None,
    )

    stats = await domain_store.list_group_stats()
    stats_by_group = {item.name: item for item in stats}

    primary_stats = stats_by_group[primary_group.name]
    assert primary_stats.request_count == 2
    assert primary_stats.success_count == 1
    assert primary_stats.failed_count == 1
    assert primary_stats.total_tokens == 1700
    assert primary_stats.avg_latency_ms == 200
    assert primary_stats.total_cost_usd == 0.009
    assert primary_stats.last_resolved_model == "claude-opus-4-6-2026-03-31"

    secondary_stats = stats_by_group["gpt-4.1"]
    assert secondary_stats.request_count == 1
    assert secondary_stats.success_count == 1
    assert secondary_stats.failed_count == 0
    assert secondary_stats.total_tokens == 200
    assert secondary_stats.avg_latency_ms == 90
    assert secondary_stats.total_cost_usd == 0.003
    assert secondary_stats.last_resolved_model == "gpt-4.1-2026-03-30"

    await engine.dispose()


def test_estimate_model_cost_uses_group_name_key(tmp_path):
    asyncio.run(_run_group_name_price_test(tmp_path))


async def _run_group_name_price_test(tmp_path):
    database_path = tmp_path / 'group-price.db'
    engine = create_engine(f"sqlite+aiosqlite:///{database_path.resolve().as_posix()}")
    session_factory = create_session_factory(engine)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    domain_store = DomainStore(session_factory)
    await domain_store.replace_model_prices([
        {
            'model_key': 'gpt-5.4',
            'display_name': 'gpt-5.4',
            'input_price_per_million': 2.0,
            'output_price_per_million': 8.0,
            'cache_read_price_per_million': 0.5,
            'cache_write_price_per_million': 1.0,
        }
    ])

    input_cost, output_cost, total_cost = await domain_store.estimate_model_cost('gpt-5.4', 1000, 500)
    assert input_cost == 0.002
    assert output_cost == 0.004
    assert total_cost == 0.006

    await engine.dispose()


async def _run_overview_metrics_merge_test(tmp_path):
    database_path = tmp_path / 'overview-merge.db'
    engine = create_engine(f"sqlite+aiosqlite:///{database_path.resolve().as_posix()}")
    session_factory = create_session_factory(engine)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    domain_store = DomainStore(session_factory)
    await domain_store.replace_imported_stats(
        total={
            'input_token': 100,
            'output_token': 50,
            'input_cost': 1.5,
            'output_cost': 2.5,
            'wait_time': 900,
            'request_success': 2,
            'request_failed': 1,
        },
        daily=[
            {
                'date': '20250101',
                'input_token': 100,
                'output_token': 50,
                'input_cost': 1.5,
                'output_cost': 2.5,
                'wait_time': 900,
                'request_success': 2,
                'request_failed': 1,
            }
        ],
        model_prices=[],
    )
    await domain_store.create_request_log(
        protocol=ProtocolKind.OPENAI_CHAT.value,
        requested_model='gpt-4.1',
        matched_group_name='gpt-4.1',
        channel_id='channel-a',
        channel_name='Channel A',
        gateway_key_id='gw-a',
        status_code=200,
        success=True,
        is_stream=False,
        first_token_latency_ms=0,
        latency_ms=100,
        resolved_model='gpt-4.1',
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
        input_cost_usd=0.1,
        output_cost_usd=0.2,
        total_cost_usd=0.3,
        request_content='{"model":"gpt-4.1"}',
        response_content='{"model":"gpt-4.1"}',
        attempts=[],
        error_message=None,
    )

    metrics = await domain_store.get_overview_metrics()
    assert metrics.total_requests == 4
    assert metrics.successful_requests == 3
    assert metrics.failed_requests == 1
    assert metrics.avg_latency_ms == 250

    summary = await domain_store.get_overview_summary(days=0)
    assert summary.request_count.value == 4
    assert summary.wait_time_ms.value == 1000
    assert summary.total_tokens.value == 165
    assert summary.total_cost_usd.value == 4.3

    daily_points = await domain_store.list_overview_daily(days=0)
    assert any(item.date == '20250101' and item.request_count == 3 for item in daily_points)
    assert any(item.date != '20250101' and item.request_count == 1 and item.successful_requests == 1 for item in daily_points)

    await engine.dispose()


async def _run_overview_today_range_test(tmp_path):
    database_path = tmp_path / "overview-today.db"
    engine = create_engine(f"sqlite+aiosqlite:///{database_path.resolve().as_posix()}")
    session_factory = create_session_factory(engine)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    domain_store = DomainStore(session_factory)
    now = datetime.now(UTC).replace(tzinfo=None, hour=12, minute=0, second=0, microsecond=0)
    today = now.strftime("%Y%m%d")
    yesterday = (now - timedelta(days=1)).strftime("%Y%m%d")

    await domain_store.replace_imported_stats(
        total=None,
        daily=[
            {
                "date": yesterday,
                "input_token": 100,
                "output_token": 50,
                "input_cost": 0.4,
                "output_cost": 0.6,
                "wait_time": 400,
                "request_success": 3,
                "request_failed": 1,
            }
        ],
        model_prices=[],
    )

    today_success = await domain_store.create_request_log(
        protocol=ProtocolKind.OPENAI_CHAT.value,
        requested_model="gpt-4.1",
        matched_group_name="gpt-4.1",
        channel_id="channel-today-success",
        channel_name="Today Success",
        gateway_key_id="gw-today",
        status_code=200,
        success=True,
        is_stream=False,
        first_token_latency_ms=0,
        latency_ms=120,
        resolved_model="gpt-4.1",
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
        input_cost_usd=0.1,
        output_cost_usd=0.2,
        total_cost_usd=0.3,
        request_content='{"model":"gpt-4.1"}',
        response_content='{"model":"gpt-4.1"}',
        attempts=[],
        error_message=None,
    )
    today_failed = await domain_store.create_request_log(
        protocol=ProtocolKind.OPENAI_CHAT.value,
        requested_model="gpt-4.1",
        matched_group_name="gpt-4.1",
        channel_id="channel-today-failed",
        channel_name="Today Failed",
        gateway_key_id="gw-today",
        status_code=500,
        success=False,
        is_stream=False,
        first_token_latency_ms=0,
        latency_ms=60,
        resolved_model=None,
        input_tokens=5,
        output_tokens=0,
        total_tokens=5,
        input_cost_usd=0.0,
        output_cost_usd=0.0,
        total_cost_usd=0.0,
        request_content='{"model":"gpt-4.1"}',
        response_content=None,
        attempts=[],
        error_message="boom",
    )
    yesterday_log = await domain_store.create_request_log(
        protocol=ProtocolKind.OPENAI_CHAT.value,
        requested_model="claude-3-7-sonnet",
        matched_group_name="claude-3-7-sonnet",
        channel_id="channel-yesterday",
        channel_name="Yesterday",
        gateway_key_id="gw-yesterday",
        status_code=200,
        success=True,
        is_stream=False,
        first_token_latency_ms=0,
        latency_ms=200,
        resolved_model="claude-3-7-sonnet",
        input_tokens=20,
        output_tokens=10,
        total_tokens=30,
        input_cost_usd=0.2,
        output_cost_usd=0.3,
        total_cost_usd=0.5,
        request_content='{"model":"claude-3-7-sonnet"}',
        response_content='{"model":"claude-3-7-sonnet"}',
        attempts=[],
        error_message=None,
    )

    async with session_factory() as session:
        today_success_entity = await session.get(RequestLogEntity, today_success.id)
        today_failed_entity = await session.get(RequestLogEntity, today_failed.id)
        yesterday_entity = await session.get(RequestLogEntity, yesterday_log.id)
        assert today_success_entity is not None
        assert today_failed_entity is not None
        assert yesterday_entity is not None
        today_success_entity.created_at = now
        today_failed_entity.created_at = now - timedelta(hours=1)
        yesterday_entity.created_at = now - timedelta(days=1)
        await session.commit()

    summary = await domain_store.get_overview_summary(days=-1)
    assert summary.request_count.value == 2
    assert summary.request_count.delta == -50.0
    assert summary.wait_time_ms.value == 180
    assert summary.total_tokens.value == 20
    assert summary.total_cost_usd.value == 0.3

    daily_points = await domain_store.list_overview_daily(days=-1)
    assert len(daily_points) == 1
    assert daily_points[0].date == today
    assert daily_points[0].request_count == 2
    assert daily_points[0].successful_requests == 1
    assert daily_points[0].failed_requests == 1

    model_analytics = await domain_store.get_model_analytics(days=-1)
    assert model_analytics.available_models == ["gpt-4.1"]
    assert len(model_analytics.distribution) == 1
    assert model_analytics.distribution[0].model == "gpt-4.1"
    assert model_analytics.distribution[0].requests == 1
    assert all(point.date == today for point in model_analytics.trend)

    logs = await domain_store.list_request_logs(days=-1)
    assert [item.id for item in logs] == [today_success.id, today_failed.id]

    await engine.dispose()


async def _run_clear_request_logs_keeps_archived_stats_test(tmp_path):
    database_path = tmp_path / 'clear-logs-keeps-stats.db'
    engine = create_engine(f"sqlite+aiosqlite:///{database_path.resolve().as_posix()}")
    session_factory = create_session_factory(engine)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    domain_store = DomainStore(session_factory)
    await domain_store.upsert_settings([
        SettingItem(key='stats_save_interval', value='999999'),
    ])

    await domain_store.create_request_log(
        protocol=ProtocolKind.OPENAI_CHAT.value,
        requested_model='gpt-4.1',
        matched_group_name='gpt-4.1',
        channel_id='channel-a',
        channel_name='Channel A',
        gateway_key_id='gw-a',
        status_code=200,
        success=True,
        is_stream=False,
        first_token_latency_ms=0,
        latency_ms=120,
        resolved_model='gpt-4.1',
        input_tokens=20,
        output_tokens=10,
        total_tokens=30,
        input_cost_usd=0.2,
        output_cost_usd=0.3,
        total_cost_usd=0.5,
        request_content='{"model":"gpt-4.1"}',
        response_content='{"model":"gpt-4.1"}',
        attempts=[],
        error_message=None,
    )
    await domain_store.create_request_log(
        protocol=ProtocolKind.OPENAI_CHAT.value,
        requested_model='gpt-4.1',
        matched_group_name='gpt-4.1',
        channel_id='channel-a',
        channel_name='Channel A',
        gateway_key_id='gw-a',
        status_code=500,
        success=False,
        is_stream=False,
        first_token_latency_ms=0,
        latency_ms=80,
        resolved_model=None,
        input_tokens=5,
        output_tokens=0,
        total_tokens=5,
        input_cost_usd=0.0,
        output_cost_usd=0.0,
        total_cost_usd=0.0,
        request_content='{"model":"gpt-4.1"}',
        response_content=None,
        attempts=[],
        error_message='boom',
    )

    before_clear = await domain_store.get_overview_summary(days=0)
    assert before_clear.request_count.value == 2
    assert before_clear.total_tokens.value == 35
    assert before_clear.total_cost_usd.value == 0.5

    await domain_store.clear_request_logs()

    logs = await domain_store.list_request_logs()
    assert logs == []

    after_clear = await domain_store.get_overview_summary(days=0)
    assert after_clear.request_count.value == 2
    assert after_clear.wait_time_ms.value == 200
    assert after_clear.total_tokens.value == 35
    assert after_clear.total_cost_usd.value == 0.5

    metrics = await domain_store.get_overview_metrics()
    assert metrics.total_requests == 2
    assert metrics.successful_requests == 1
    assert metrics.failed_requests == 1
    assert metrics.avg_latency_ms == 100

    analytics = await domain_store.get_model_analytics(days=0)
    assert analytics.available_models == ['gpt-4.1']
    assert analytics.distribution[0].requests == 1
    assert analytics.distribution[0].total_tokens == 30
    assert analytics.distribution[0].total_cost_usd == 0.5

    await engine.dispose()


def test_model_analytics_merges_same_model_across_days(tmp_path):
    asyncio.run(_run_model_analytics_merge_same_model_test(tmp_path))


async def _run_model_analytics_merge_same_model_test(tmp_path):
    database_path = tmp_path / 'model-analytics-merge.db'
    engine = create_engine(f"sqlite+aiosqlite:///{database_path.resolve().as_posix()}")
    session_factory = create_session_factory(engine)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    domain_store = DomainStore(session_factory)
    await domain_store.upsert_settings([
        SettingItem(key='stats_save_interval', value='999999'),
    ])

    first = await domain_store.create_request_log(
        protocol=ProtocolKind.OPENAI_CHAT.value,
        requested_model='gpt-5.4',
        matched_group_name='gpt-5.4',
        channel_id='channel-a',
        channel_name='Channel A',
        gateway_key_id='gw-a',
        status_code=200,
        success=True,
        is_stream=False,
        first_token_latency_ms=0,
        latency_ms=100,
        resolved_model='gpt-5.4',
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        input_cost_usd=0.1,
        output_cost_usd=0.2,
        total_cost_usd=0.3,
        request_content='{"model":"gpt-5.4"}',
        response_content='{"model":"gpt-5.4"}',
        attempts=[],
        error_message=None,
    )
    second = await domain_store.create_request_log(
        protocol=ProtocolKind.OPENAI_CHAT.value,
        requested_model='gpt-5.4',
        matched_group_name='gpt-5.4',
        channel_id='channel-a',
        channel_name='Channel A',
        gateway_key_id='gw-a',
        status_code=200,
        success=True,
        is_stream=False,
        first_token_latency_ms=0,
        latency_ms=110,
        resolved_model='gpt-5.4',
        input_tokens=120,
        output_tokens=60,
        total_tokens=180,
        input_cost_usd=0.2,
        output_cost_usd=0.3,
        total_cost_usd=0.5,
        request_content='{"model":"gpt-5.4"}',
        response_content='{"model":"gpt-5.4"}',
        attempts=[],
        error_message=None,
    )

    now = datetime.now(UTC).replace(tzinfo=None, hour=12, minute=0, second=0, microsecond=0)
    async with session_factory() as session:
        first_entity = await session.get(RequestLogEntity, first.id)
        second_entity = await session.get(RequestLogEntity, second.id)
        assert first_entity is not None
        assert second_entity is not None
        first_entity.created_at = now - timedelta(days=1)
        second_entity.created_at = now
        await session.commit()

    analytics = await domain_store.get_model_analytics(days=7)
    assert analytics.available_models == ['gpt-5.4']
    assert len(analytics.distribution) == 1
    assert len(analytics.request_ranking) == 1
    assert analytics.distribution[0].model == 'gpt-5.4'
    assert analytics.distribution[0].requests == 2
    assert analytics.distribution[0].total_tokens == 330
    assert analytics.distribution[0].total_cost_usd == 0.8
    assert len(analytics.trend) == 2

    await engine.dispose()


from __future__ import annotations

import asyncio

from lens_api.core.db import Base, create_engine, create_session_factory
from lens_api.models import ModelGroupCreate, ModelGroupItemInput, ProtocolKind, RoutingStrategy, SiteCreate, SiteUpdate
from lens_api.persistence.domain_store import DomainStore
from lens_api.persistence.channel_store import ChannelStore


def test_list_group_stats_returns_aggregated_metrics(tmp_path):
    asyncio.run(_run_group_stats_test(tmp_path))


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
            base_url="https://primary.example.com",
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
            base_url=primary_site.base_url,
            credentials=[{"id": primary_credential.id, "name": primary_credential.name, "api_key": primary_credential.api_key, "enabled": True}],
            protocols=[{"id": primary_protocol.id, "protocol": primary_protocol.protocol, "enabled": True, "headers": {}, "channel_proxy": "", "param_override": "", "match_regex": "", "bindings": [{"credential_id": primary_credential.id, "enabled": True}], "models": [{"credential_id": primary_credential.id, "model_name": "claude-opus-4-6-2026-03-31", "enabled": True}, {"credential_id": primary_credential.id, "model_name": "gpt-4.1-2026-03-30", "enabled": True}]}],
        ),
    )
    primary_channel = primary_site.protocols[0]

    fallback_site = await channel_store.create_site(
        SiteCreate(
            name="Fallback Claude",
            base_url="https://fallback.example.com",
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
            base_url=fallback_site.base_url,
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


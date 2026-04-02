from __future__ import annotations

import asyncio

from lens.core.db import Base, create_engine, create_session_factory
from lens.models import ModelGroupCreate, ModelGroupItemInput, ProtocolKind, ProviderCreate, RoutingStrategy
from lens.persistence.domain_store import DomainStore
from lens.persistence.provider_store import ProviderStore


def test_list_group_stats_returns_aggregated_metrics(tmp_path):
    asyncio.run(_run_group_stats_test(tmp_path))


async def _run_group_stats_test(tmp_path):
    database_path = tmp_path / "group-stats.db"
    database_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite+aiosqlite:///{database_path.resolve().as_posix()}")
    session_factory = create_session_factory(engine)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    provider_store = ProviderStore(session_factory)
    domain_store = DomainStore(session_factory)

    primary_provider = await provider_store.create(
        ProviderCreate(
            name="Primary Claude",
            protocol=ProtocolKind.OPENAI_CHAT,
            base_url="https://primary.example.com/v1",
            api_key="sk-primary",
            model_patterns=["claude-opus-4-6-2026-03-31", "gpt-4.1-2026-03-30"],
        )
    )
    fallback_provider = await provider_store.create(
        ProviderCreate(
            name="Fallback Claude",
            protocol=ProtocolKind.OPENAI_CHAT,
            base_url="https://fallback.example.com/v1",
            api_key="sk-fallback",
            model_patterns=["claude-opus-4-6-2026-03-31"],
        )
    )

    primary_group = await domain_store.create_group(
        ModelGroupCreate(
            name="claude-opus-4-6",
            protocol=ProtocolKind.OPENAI_CHAT,
            strategy=RoutingStrategy.ROUND_ROBIN,
            items=[
                ModelGroupItemInput(provider_id=primary_provider.id, model_name="claude-opus-4-6-2026-03-31"),
                ModelGroupItemInput(provider_id=fallback_provider.id, model_name="claude-opus-4-6-2026-03-31"),
            ],
        )
    )
    await domain_store.create_group(
        ModelGroupCreate(
            name="gpt-4.1",
            protocol=ProtocolKind.OPENAI_CHAT,
            strategy=RoutingStrategy.FAILOVER,
            items=[
                ModelGroupItemInput(provider_id=primary_provider.id, model_name="gpt-4.1-2026-03-30"),
            ],
        )
    )

    await domain_store.create_request_log(
        protocol=ProtocolKind.OPENAI_CHAT.value,
        requested_model=primary_group.name,
        matched_group_name=primary_group.name,
        provider_id=primary_provider.id,
        gateway_key_id="gw-a",
        status_code=200,
        success=True,
        latency_ms=180,
        resolved_model="claude-opus-4-6-2026-03-31",
        input_tokens=1000,
        output_tokens=500,
        total_tokens=1500,
        input_cost_usd=0.003,
        output_cost_usd=0.006,
        total_cost_usd=0.009,
        error_message=None,
    )
    await domain_store.create_request_log(
        protocol=ProtocolKind.OPENAI_CHAT.value,
        requested_model=primary_group.name,
        matched_group_name=primary_group.name,
        provider_id=fallback_provider.id,
        gateway_key_id="gw-a",
        status_code=429,
        success=False,
        latency_ms=220,
        resolved_model=None,
        input_tokens=200,
        output_tokens=0,
        total_tokens=200,
        input_cost_usd=0.0,
        output_cost_usd=0.0,
        total_cost_usd=0.0,
        error_message="rate limited",
    )
    await domain_store.create_request_log(
        protocol=ProtocolKind.OPENAI_CHAT.value,
        requested_model="gpt-4.1",
        matched_group_name="gpt-4.1",
        provider_id=primary_provider.id,
        gateway_key_id="gw-b",
        status_code=200,
        success=True,
        latency_ms=90,
        resolved_model="gpt-4.1-2026-03-30",
        input_tokens=120,
        output_tokens=80,
        total_tokens=200,
        input_cost_usd=0.001,
        output_cost_usd=0.002,
        total_cost_usd=0.003,
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

from __future__ import annotations

import pytest

from lens_api.core.db import Base, create_engine, create_session_factory
from lens_api.models import GatewayApiKeyCreate, RequestLogLifecycleStatus
from lens_api.persistence.domain_store import DomainStore


async def _store(tmp_path):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return DomainStore(create_session_factory(engine)), engine


async def _create_key(store: DomainStore, remark: str = "Key"):
    return await store.create_gateway_api_key(
        GatewayApiKeyCreate(
            remark=remark,
            enabled=True,
            allowed_models=[],
            max_cost_usd=0,
            expires_at=None,
        )
    )


async def _spent(store: DomainStore, key_id: str) -> float:
    keys = await store.list_gateway_api_keys()
    return next(item.spent_cost_usd for item in keys if item.id == key_id)


async def _create_terminal_log(
    store: DomainStore,
    *,
    key_id: str,
    total_cost_usd: float,
):
    return await store.create_request_log(
        protocol="openai_chat",
        user_agent="",
        requested_group_name="gpt-test",
        resolved_group_name="gpt-test",
        upstream_model_name="gpt-test",
        channel_id="channel-1",
        channel_name="Channel",
        gateway_key_id=key_id,
        status_code=200,
        success=True,
        lifecycle_status=RequestLogLifecycleStatus.SUCCEEDED,
        is_stream=False,
        first_token_latency_ms=0,
        latency_ms=10,
        input_tokens=1,
        output_tokens=1,
        total_tokens=2,
        input_cost_usd=0.0,
        output_cost_usd=total_cost_usd,
        total_cost_usd=total_cost_usd,
    )


async def _finish_log(
    store: DomainStore,
    log_id: int,
    *,
    key_id: str,
    total_cost_usd: float,
):
    return await store.update_request_log(
        log_id,
        protocol="openai_chat",
        user_agent="",
        requested_group_name="gpt-test",
        resolved_group_name="gpt-test",
        upstream_model_name="gpt-test",
        channel_id="channel-1",
        channel_name="Channel",
        gateway_key_id=key_id,
        status_code=200,
        success=True,
        lifecycle_status=RequestLogLifecycleStatus.SUCCEEDED,
        is_stream=False,
        first_token_latency_ms=0,
        latency_ms=10,
        input_tokens=1,
        output_tokens=1,
        total_tokens=2,
        input_cost_usd=0.0,
        output_cost_usd=total_cost_usd,
        total_cost_usd=total_cost_usd,
    )


@pytest.mark.asyncio
async def test_gateway_key_spend_accumulates_from_terminal_logs(tmp_path) -> None:
    store, engine = await _store(tmp_path)
    try:
        key = await _create_key(store)

        await _create_terminal_log(store, key_id=key.id, total_cost_usd=1.25)
        await _create_terminal_log(store, key_id=key.id, total_cost_usd=2.75)

        assert await _spent(store, key.id) == pytest.approx(4.0)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_gateway_key_spend_updates_by_delta(tmp_path) -> None:
    store, engine = await _store(tmp_path)
    try:
        key = await _create_key(store)
        pending = await store.create_pending_request_log(
            protocol="openai_chat",
            user_agent="",
            requested_group_name="gpt-test",
            resolved_group_name="gpt-test",
            upstream_model_name="gpt-test",
            channel_id="channel-1",
            channel_name="Channel",
            gateway_key_id=key.id,
            is_stream=False,
        )

        assert await _spent(store, key.id) == pytest.approx(0.0)

        await _finish_log(store, pending.id, key_id=key.id, total_cost_usd=2.0)
        assert await _spent(store, key.id) == pytest.approx(2.0)

        await _finish_log(store, pending.id, key_id=key.id, total_cost_usd=3.5)
        assert await _spent(store, key.id) == pytest.approx(3.5)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_gateway_key_spend_moves_when_log_key_changes(tmp_path) -> None:
    store, engine = await _store(tmp_path)
    try:
        first_key = await _create_key(store, "First")
        second_key = await _create_key(store, "Second")
        log = await _create_terminal_log(
            store, key_id=first_key.id, total_cost_usd=4.0
        )

        await _finish_log(store, log.id, key_id=second_key.id, total_cost_usd=4.5)

        assert await _spent(store, first_key.id) == pytest.approx(0.0)
        assert await _spent(store, second_key.id) == pytest.approx(4.5)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_gateway_key_spend_survives_request_log_clear(tmp_path) -> None:
    store, engine = await _store(tmp_path)
    try:
        key = await _create_key(store)
        await _create_terminal_log(store, key_id=key.id, total_cost_usd=1.5)

        await store.clear_request_logs()

        assert await _spent(store, key.id) == pytest.approx(1.5)
    finally:
        await engine.dispose()

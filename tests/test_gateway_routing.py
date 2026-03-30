from __future__ import annotations

import secrets

import anyio
from fastapi.testclient import TestClient

from lens.models import GatewayKeyCreate, ModelGroupCreate, ProtocolKind, ProviderCreate, RoutingStrategy
from lens.service import app, app_state, _resolve_routing_plan


def test_gateway_routes_require_valid_key() -> None:
    with TestClient(app) as client:
        missing = client.post("/v1/chat/completions", json={"model": "gpt-4o-mini", "messages": []})
        assert missing.status_code == 401
        assert missing.json()["detail"] == "Missing gateway API key"

        invalid = client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o-mini", "messages": []},
            headers={"Authorization": "Bearer not-a-real-key"},
        )
        assert invalid.status_code == 401
        assert invalid.json()["detail"] == "Invalid gateway API key"


def test_model_group_name_routes_by_group_providers() -> None:
    group_name = f"claude-opus-4-6-{secrets.token_hex(4)}"

    with TestClient(app) as client:
        gateway_key = run_async(app_state.domain_store.create_gateway_key(GatewayKeyCreate(name="default")))
        provider_a = run_async(
            app_state.store.create(
                ProviderCreate(
                    name="OpenAI A",
                    protocol=ProtocolKind.OPENAI_CHAT,
                    base_url="https://example-a.com",
                    api_key="sk-a",
                    model_patterns=["^gpt-4o-mini$"],
                    priority=10,
                )
            )
        )
        provider_b = run_async(
            app_state.store.create(
                ProviderCreate(
                    name="OpenAI B",
                    protocol=ProtocolKind.OPENAI_CHAT,
                    base_url="https://example-b.com",
                    api_key="sk-b",
                    model_patterns=["^other-model$"],
                    priority=20,
                )
            )
        )
        run_async(
            app_state.domain_store.create_group(
                ModelGroupCreate(
                    name=group_name,
                    protocol=ProtocolKind.OPENAI_CHAT,
                    strategy=RoutingStrategy.FAILOVER,
                    provider_ids=[provider_b.id],
                    enabled=True,
                )
            )
        )

        plan = run_async(_resolve_routing_plan(ProtocolKind.OPENAI_CHAT, group_name))
        providers = run_async(app_state.store.list())
        preview = app_state.router.preview(
            providers,
            ProtocolKind.OPENAI_CHAT,
            group_name,
            strategy=plan.strategy,
            allowed_provider_ids=plan.allowed_provider_ids,
            use_model_matching=plan.use_model_matching,
            matched_group_name=plan.matched_group.name if plan.matched_group else None,
        )

        assert plan.matched_group is not None
        assert plan.matched_group.name == group_name
        assert plan.allowed_provider_ids == {provider_b.id}
        assert plan.use_model_matching is False
        assert preview.matched_group_name == group_name
        assert preview.strategy == RoutingStrategy.FAILOVER
        assert preview.matched_provider_ids == [provider_b.id]

        fallback_plan = run_async(_resolve_routing_plan(ProtocolKind.OPENAI_CHAT, "gpt-4o-mini"))
        fallback_preview = app_state.router.preview(
            providers,
            ProtocolKind.OPENAI_CHAT,
            "gpt-4o-mini",
            strategy=fallback_plan.strategy,
            allowed_provider_ids=fallback_plan.allowed_provider_ids,
            use_model_matching=fallback_plan.use_model_matching,
        )
        assert provider_a.id in fallback_preview.matched_provider_ids

        response = client.post(
            "/v1/chat/completions",
            json={"model": group_name, "messages": []},
            headers={"Authorization": f"Bearer {gateway_key.secret}"},
        )
        assert response.status_code in {502, 503}


def test_request_logs_and_overview_metrics_are_exposed() -> None:
    with TestClient(app) as client:
        login = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
        assert login.status_code == 200
        token = login.json()["access_token"]

        overview = client.get("/api/overview", headers={"Authorization": f"Bearer {token}"})
        assert overview.status_code == 200
        overview_payload = overview.json()
        assert "total_requests" in overview_payload
        assert "enabled_providers" in overview_payload

        logs = client.get("/api/request-logs", headers={"Authorization": f"Bearer {token}"})
        assert logs.status_code == 200
        logs_payload = logs.json()
        assert isinstance(logs_payload, list)
        assert len(logs_payload) >= 1
        assert "status_code" in logs_payload[0]
        assert "latency_ms" in logs_payload[0]


def run_async(awaitable):
    return anyio.run(_await_value, awaitable)


async def _await_value(awaitable):
    return await awaitable

from __future__ import annotations

from typing import Any

import httpx
from conftest import assert_error, gateway_headers, valid_site_payload

from lens_api.core.runtime_channel_ids import compose_runtime_channel_id
from lens_api.models import ProtocolKind


def test_anthropic_route_prefers_native_channel_over_earlier_chat_member(
    client,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    from lens_api.gateway.service import proxy_upstream

    create_site(
        valid_site_payload(
            protocols=["openai_chat", "anthropic"],
            model_name="upstream-model",
        )
    )
    create_model_group(
        name="client-model",
        protocols=["anthropic"],
        items=[
            {
                "channel_id": compose_runtime_channel_id(
                    "pc-1", ProtocolKind.OPENAI_CHAT
                ),
                "credential_id": "cred-1",
                "model_name": "upstream-model",
                "enabled": True,
            },
            {
                "channel_id": compose_runtime_channel_id(
                    "pc-1", ProtocolKind.ANTHROPIC
                ),
                "credential_id": "cred-1",
                "model_name": "upstream-model",
                "enabled": True,
            },
        ],
    )
    attempted_urls: list[str] = []

    async def fake_send_upstream(
        _client: httpx.AsyncClient,
        upstream: Any,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        assert not stream
        attempted_urls.append(upstream.url)
        return httpx.Response(
            400,
            json={"error": {"message": "stop after capturing primary"}},
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send_upstream)
    key = create_gateway_key()

    response = client.post(
        "/v1/messages",
        headers=gateway_headers(key),
        json={
            "model": "client-model",
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 16,
        },
    )

    assert response.status_code == 400, response.text
    assert len(attempted_urls) == 1
    assert attempted_urls[0].endswith("/v1/messages")


def test_model_group_sync_filter_is_normalized_and_validated(
    client,
    admin_headers,
) -> None:
    created = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={
            "name": "filtered",
            "protocols": ["openai_chat"],
            "sync_filter_mode": "contains",
            "sync_filter_query": "  gpt  ",
        },
    )
    invalid = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={
            "name": "invalid-filter",
            "protocols": ["openai_chat"],
            "sync_filter_mode": "regex",
            "sync_filter_query": "[",
        },
    )

    assert created.status_code == 201
    assert created.json()["sync_filter_mode"] == "contains"
    assert created.json()["sync_filter_query"] == "gpt"
    assert_error(invalid, 422, "Request validation failed")


def test_create_route_group_rejects_invalid_route_targets(
    client,
    admin_headers,
    create_model_group,
) -> None:
    target = create_model_group(name="target", protocols=["openai_chat"])
    route = create_model_group(
        name="route",
        protocols=["openai_chat"],
        route_group_id=target["id"],
    )

    missing = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={
            "name": "missing-target",
            "protocols": ["openai_chat"],
            "route_group_id": "missing",
        },
    )
    missing_protocol = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={
            "name": "missing-protocol",
            "protocols": ["openai_chat", "gemini"],
            "route_group_id": target["id"],
        },
    )
    chained = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={
            "name": "chained",
            "protocols": ["openai_chat"],
            "route_group_id": route["id"],
        },
    )

    assert_error(missing, 400, "Route target model group not found")
    assert_error(missing_protocol, 400, "Route target protocols must cover")
    assert_error(chained, 400, "Route target must be an execution group")


def test_update_model_group_rejects_self_route(
    client, admin_headers, create_model_group
) -> None:
    group = create_model_group(name="self-route")

    response = client.put(
        f"/api/admin/model-groups/{group['id']}",
        headers=admin_headers,
        json={"route_group_id": group["id"]},
    )

    assert_error(response, 400, "cannot route to itself")


def test_update_referenced_execution_group_preserves_route_group_contracts(
    client,
    admin_headers,
    create_model_group,
) -> None:
    execution = create_model_group(
        name="execution",
        protocols=["openai_chat", "gemini"],
    )
    create_model_group(
        name="route",
        protocols=["openai_chat"],
        route_group_id=execution["id"],
    )
    target = create_model_group(name="target", protocols=["openai_chat", "gemini"])

    remove_protocol = client.put(
        f"/api/admin/model-groups/{execution['id']}",
        headers=admin_headers,
        json={"protocols": ["openai_chat"]},
    )
    become_route = client.put(
        f"/api/admin/model-groups/{execution['id']}",
        headers=admin_headers,
        json={"route_group_id": target["id"]},
    )

    assert_error(remove_protocol, 400, "cannot remove protocols")
    assert_error(become_route, 400, "cannot become route groups")


def test_update_route_group_clears_sync_filter(
    client,
    admin_headers,
    create_model_group,
) -> None:
    target = create_model_group(name="target")
    source = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={
            "name": "source",
            "protocols": ["openai_chat"],
            "sync_filter_mode": "contains",
            "sync_filter_query": "gpt",
        },
    ).json()

    response = client.put(
        f"/api/admin/model-groups/{source['id']}",
        headers=admin_headers,
        json={"route_group_id": target["id"]},
    )

    assert response.status_code == 200
    assert response.json()["route_group_id"] == target["id"]
    assert response.json()["sync_filter_mode"] == ""
    assert response.json()["sync_filter_query"] == ""


def test_delete_model_group_rejects_referenced_execution_group(
    client,
    admin_headers,
    create_model_group,
) -> None:
    execution_group = create_model_group(name="gpt-4o")
    create_model_group(
        name="public-gpt-4o",
        route_group_id=execution_group["id"],
    )

    response = client.delete(
        f"/api/admin/model-groups/{execution_group['id']}",
        headers=admin_headers,
    )

    assert_error(response, 400, "still referenced")

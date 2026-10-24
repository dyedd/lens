from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from conftest import (
    assert_error,
    gateway_headers,
    openai_chat_channel_id,
    valid_site_payload,
)

from app.persistence.settings_keys import SETTING_CORS_ALLOW_ORIGINS


def test_router_snapshot_is_empty_without_channels(client, admin_headers) -> None:
    response = client.get("/api/admin/routes", headers=admin_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["health"] == []
    assert payload["routes"]
    assert all(route["channel_ids"] == [] for route in payload["routes"])
    assert all(route["next_channel_id"] is None for route in payload["routes"])


def test_cors_preflight_allows_any_origin_by_default(client) -> None:
    response = client.options(
        "/anything",
        headers={
            "Origin": "https://app.example",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert response.status_code == 204
    assert response.headers["access-control-allow-origin"] == "*"
    assert response.headers["access-control-allow-headers"] == "authorization"


def test_cors_preflight_respects_configured_origins(client, admin_headers) -> None:
    settings_response = client.put(
        "/api/admin/settings",
        headers=admin_headers,
        json={
            "items": [
                {
                    "key": SETTING_CORS_ALLOW_ORIGINS,
                    "value": "https://allowed.example",
                }
            ]
        },
    )
    assert settings_response.status_code == 200

    allowed = client.options(
        "/anything",
        headers={"Origin": "https://allowed.example"},
    )
    blocked = client.options(
        "/anything",
        headers={"Origin": "https://blocked.example"},
    )

    assert allowed.status_code == 204
    assert allowed.headers["access-control-allow-origin"] == "https://allowed.example"
    assert allowed.headers["vary"] == "Origin"
    assert "access-control-allow-origin" not in blocked.headers


def _site_with_key(name: str, prefix: str, **model_fields: Any) -> dict[str, Any]:
    payload = valid_site_payload(
        name=name,
        base_id=f"{prefix}-base",
        credential_id=f"{prefix}-cred",
        protocol_config_id=f"{prefix}-pc",
        model_name="gpt-4o",
    )
    payload["credentials"][0]["api_key"] = f"{prefix}-secret"
    payload["protocols"][0]["models"][0].update(model_fields)
    return payload


def _capture_upstream_keys(monkeypatch) -> list[str]:
    import app.gateway.service.proxy_upstream as proxy_upstream

    used_keys: list[str] = []

    async def fake_send_upstream(
        _client: httpx.AsyncClient,
        upstream: Any,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        used_keys.append(httpx.Headers(upstream.headers)["authorization"])
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-1",
                "object": "chat.completion",
                "model": json.loads(body_bytes)["model"],
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "ok"},
                        "finish_reason": "stop",
                    }
                ],
            },
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send_upstream)
    return used_keys


def _chat(client, key: dict[str, Any]) -> Any:
    return client.post(
        "/v1/chat/completions",
        headers=gateway_headers(key),
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]},
    )


def _group_named(client, admin_headers, name: str) -> dict[str, Any]:
    groups = client.get("/api/admin/model-groups", headers=admin_headers).json()
    return next(group for group in groups if group["name"] == name)


def test_site_save_places_channel_model_into_routable_failover_group(
    client,
    admin_headers,
    monkeypatch,
    create_site,
    create_gateway_key,
) -> None:
    created_group = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={"name": "gpt-4o"},
    )
    assert created_group.status_code == 201, created_group.text
    create_site(_site_with_key("Placed", "placed"))
    used_keys = _capture_upstream_keys(monkeypatch)

    response = _chat(client, create_gateway_key())
    group = _group_named(client, admin_headers, "gpt-4o")

    assert response.status_code == 200, response.text
    assert used_keys == ["Bearer placed-secret"]
    assert group["strategy"] == "failover"
    assert [(item["model_name"], item["source"]) for item in group["items"]] == [
        ("gpt-4o", "placement")
    ]


@pytest.mark.parametrize(
    "model_fields",
    [
        pytest.param({"enabled": False}, id="disabled"),
        pytest.param({"upstream_missing": True}, id="missing"),
    ],
)
def test_model_without_group_is_not_routed(
    client,
    monkeypatch,
    create_site,
    create_gateway_key,
    model_fields: dict[str, Any],
) -> None:
    create_site(_site_with_key("Unavailable", "unavailable", **model_fields))
    used_keys = _capture_upstream_keys(monkeypatch)

    response = _chat(client, create_gateway_key())

    assert_error(response, 503)
    assert used_keys == []


def test_model_group_joins_same_named_channel_model(
    client,
    admin_headers,
    monkeypatch,
    create_site,
    create_gateway_key,
) -> None:
    group_response = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={"name": "gpt-4o"},
    )
    assert group_response.status_code == 201, group_response.text
    create_site(_site_with_key("Added Later", "later"))
    used_keys = _capture_upstream_keys(monkeypatch)

    response = _chat(client, create_gateway_key())
    group = client.get(
        f"/api/admin/model-groups/{group_response.json()['id']}",
        headers=admin_headers,
    ).json()

    assert response.status_code == 200, response.text
    assert used_keys == ["Bearer later-secret"]
    assert [(item["model_name"], item["source"]) for item in group["items"]] == [
        ("gpt-4o", "placement")
    ]


def test_disabled_saved_member_keeps_rule_from_routing_to_it(
    client,
    admin_headers,
    monkeypatch,
    create_site,
    create_gateway_key,
) -> None:
    created_group = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={"name": "gpt-4o"},
    )
    assert created_group.status_code == 201, created_group.text
    create_site(_site_with_key("Excluded", "excluded"))
    group = _group_named(client, admin_headers, "gpt-4o")
    update_response = client.put(
        f"/api/admin/model-groups/{group['id']}",
        headers=admin_headers,
        json={
            "items": [
                {
                    "channel_id": openai_chat_channel_id("excluded-pc"),
                    "credential_id": "excluded-cred",
                    "model_name": "gpt-4o",
                    "enabled": False,
                }
            ],
        },
    )
    assert update_response.status_code == 200, update_response.text
    used_keys = _capture_upstream_keys(monkeypatch)

    response = _chat(client, create_gateway_key())

    assert response.status_code == 503, response.text
    assert used_keys == []


def test_removed_rule_member_stays_excluded_until_restored(
    client,
    admin_headers,
    monkeypatch,
    create_site,
    create_gateway_key,
) -> None:
    created_group = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={"name": "gpt-4o"},
    )
    assert created_group.status_code == 201, created_group.text
    create_site(_site_with_key("First", "first"))
    group = _group_named(client, admin_headers, "gpt-4o")
    excluded = client.put(
        f"/api/admin/model-groups/{group['id']}",
        headers=admin_headers,
        json={"items": []},
    )
    create_site(_site_with_key("Second", "second"))
    used_keys = _capture_upstream_keys(monkeypatch)

    response = _chat(client, create_gateway_key())
    restored = client.put(
        f"/api/admin/model-groups/{group['id']}",
        headers=admin_headers,
        json={"excluded_items": []},
    )

    assert excluded.status_code == 200, excluded.text
    assert [item["credential_id"] for item in excluded.json()["excluded_items"]] == [
        "first-cred"
    ]
    assert response.status_code == 200, response.text
    assert used_keys == ["Bearer second-secret"]
    assert restored.status_code == 200, restored.text
    assert sorted(item["credential_id"] for item in restored.json()["items"]) == [
        "first-cred",
        "second-cred",
    ]
    assert restored.json()["excluded_items"] == []


def test_editor_save_keeps_rule_members_added_while_it_was_open(
    client,
    admin_headers,
    create_site,
) -> None:
    created_group = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={"name": "gpt-4o"},
    )
    assert created_group.status_code == 201, created_group.text
    create_site(_site_with_key("First", "first"))
    group = _group_named(client, admin_headers, "gpt-4o")
    create_site(_site_with_key("Second", "second"))

    # The editor still holds the members it loaded and sends its exclusions.
    saved = client.put(
        f"/api/admin/model-groups/{group['id']}",
        headers=admin_headers,
        json={
            "items": [
                {
                    "channel_id": item["channel_id"],
                    "credential_id": item["credential_id"],
                    "model_name": item["model_name"],
                    "enabled": item["enabled"],
                    "source": item["source"],
                }
                for item in group["items"]
            ],
            "excluded_items": [],
        },
    )

    assert saved.status_code == 200, saved.text
    assert sorted(item["credential_id"] for item in saved.json()["items"]) == [
        "first-cred",
        "second-cred",
    ]
    assert saved.json()["excluded_items"] == []


def _site_with_two_credentials(name: str, prefix: str) -> dict[str, Any]:
    """Build a site whose single model is served by two credentials."""
    payload = valid_site_payload(
        name=name,
        base_id=f"{prefix}-base",
        credential_id=f"{prefix}-c1",
        protocol_config_id=f"{prefix}-pc",
        model_name="gpt-4o",
    )
    payload["credentials"][0]["api_key"] = f"{prefix}-secret-1"
    payload["credentials"].append(
        {
            "id": f"{prefix}-c2",
            "name": "secondary-key",
            "api_key": f"{prefix}-secret-2",
        }
    )
    payload["protocols"][0]["models"].append(
        {
            "credential_id": f"{prefix}-c2",
            "model_name": "gpt-4o",
            "enabled": True,
            "protocol": "openai_chat",
        }
    )
    return payload


def _chat_group(client, key: dict[str, Any], model: str) -> Any:
    return client.post(
        "/v1/chat/completions",
        headers=gateway_headers(key),
        json={"model": model, "messages": [{"role": "user", "content": "hi"}]},
    )


def test_rate_limited_credential_fails_over_to_sibling_key(
    client,
    admin_headers,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    """一把 Key 限流只冷却它自己，同渠道其它 Key 仍可承接请求。"""
    import app.gateway.service.proxy_upstream as proxy_upstream

    create_site(_site_with_two_credentials("Multi", "multi"))
    group = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={"name": "key-group"},
    )
    assert group.status_code == 201, group.text
    channel_id = openai_chat_channel_id("multi-pc")
    update = client.put(
        f"/api/admin/model-groups/{group.json()['id']}",
        headers=admin_headers,
        json={
            "strategy": "failover",
            "items": [
                {
                    "channel_id": channel_id,
                    "credential_id": "multi-c1",
                    "model_name": "gpt-4o",
                    "enabled": True,
                },
                {
                    "channel_id": channel_id,
                    "credential_id": "multi-c2",
                    "model_name": "gpt-4o",
                    "enabled": True,
                },
            ],
        },
    )
    assert update.status_code == 200, update.text

    used_keys: list[str] = []

    async def fake_send_upstream(
        _client: httpx.AsyncClient,
        upstream: Any,
        *,
        stream: bool,
        body_bytes: bytes,
    ) -> httpx.Response:
        authorization = httpx.Headers(upstream.headers)["authorization"]
        used_keys.append(authorization)
        if authorization.endswith("multi-secret-1"):
            return httpx.Response(
                429,
                json={"error": {"message": "rate limited"}},
                request=httpx.Request("POST", upstream.url),
            )
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-1",
                "object": "chat.completion",
                "model": json.loads(body_bytes)["model"],
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "ok"},
                        "finish_reason": "stop",
                    }
                ],
            },
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", fake_send_upstream)
    key = create_gateway_key()

    first = _chat_group(client, key, "key-group")

    assert first.status_code == 200, first.text
    assert used_keys == ["Bearer multi-secret-1", "Bearer multi-secret-2"]

    second = _chat_group(client, key, "key-group")

    assert second.status_code == 200, second.text
    assert used_keys[-1] == "Bearer multi-secret-2"
    assert len(used_keys) == 3

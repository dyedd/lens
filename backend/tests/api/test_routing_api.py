from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from conftest import gateway_headers, openai_chat_channel_id, valid_site_payload

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


def test_ungrouped_channel_model_is_routed_directly(
    client,
    monkeypatch,
    create_site,
    create_gateway_key,
) -> None:
    create_site(_site_with_key("Direct", "direct"))
    used_keys = _capture_upstream_keys(monkeypatch)

    response = _chat(client, create_gateway_key())

    assert response.status_code == 200, response.text
    assert used_keys == ["Bearer direct-secret"]


def test_model_group_takes_precedence_over_same_named_channel_models(
    client,
    monkeypatch,
    create_site,
    create_model_group,
    create_gateway_key,
) -> None:
    create_site(_site_with_key("Direct", "direct"))
    create_site(_site_with_key("Grouped", "grouped"))
    create_model_group(
        name="gpt-4o",
        items=[
            {
                "channel_id": openai_chat_channel_id("grouped-pc"),
                "credential_id": "grouped-cred",
                "model_name": "gpt-4o",
                "enabled": True,
            }
        ],
    )
    used_keys = _capture_upstream_keys(monkeypatch)

    response = _chat(client, create_gateway_key())

    assert response.status_code == 200, response.text
    assert used_keys == ["Bearer grouped-secret"]


@pytest.mark.parametrize(
    "model_fields",
    [
        pytest.param({"enabled": False}, id="disabled"),
        pytest.param({"source": "synced", "upstream_missing": True}, id="missing"),
    ],
)
def test_direct_routing_skips_unavailable_channel_models(
    client,
    monkeypatch,
    create_site,
    create_gateway_key,
    model_fields: dict[str, Any],
) -> None:
    create_site(_site_with_key("Direct", "direct", **model_fields))
    used_keys = _capture_upstream_keys(monkeypatch)

    response = _chat(client, create_gateway_key())

    assert response.status_code == 503, response.text
    assert used_keys == []


def test_model_group_rule_routes_to_live_matching_channel_models(
    client,
    admin_headers,
    monkeypatch,
    create_site,
    create_gateway_key,
) -> None:
    group_response = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={
            "name": "gpt-4o",
            "sync_filter_mode": "contains",
            "sync_filter_query": "gpt-4o",
        },
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
    assert [
        (item["model_name"], item["matched_by_rule"]) for item in group["items"]
    ] == [("gpt-4o", True)]


def test_disabled_saved_member_keeps_rule_from_routing_to_it(
    client,
    admin_headers,
    monkeypatch,
    create_site,
    create_gateway_key,
) -> None:
    create_site(_site_with_key("Excluded", "excluded"))
    group_response = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={
            "name": "gpt-4o",
            "sync_filter_mode": "exact",
            "sync_filter_query": "gpt-4o",
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
    assert group_response.status_code == 201, group_response.text
    used_keys = _capture_upstream_keys(monkeypatch)

    response = _chat(client, create_gateway_key())

    assert response.status_code == 503, response.text
    assert used_keys == []

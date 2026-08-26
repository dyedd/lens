from __future__ import annotations

from typing import Any

import httpx
import pytest

from conftest import (
    assert_error,
    openai_chat_channel_id,
    run_async,
    valid_site_payload,
)
from lens_api.models import SiteUpdate


def _rate_site_payload(source: str, *, group: str = "") -> dict[str, Any]:
    payload = valid_site_payload()
    payload["credentials"][0].update(
        {
            "rate_source": source,
            "rate_protocol_config_id": "pc-1",
            "rate_group": group,
        }
    )
    return payload


@pytest.mark.parametrize(
    ("source", "group", "expected_path", "upstream_payload", "expected_rate"),
    [
        (
            "sub2api",
            "",
            "/v1/sub2api/billing",
            {
                "object": "sub2api.key_billing",
                "schema_version": 1,
                "billing_scope": "token",
                "group_rate_multiplier": 0.8,
                "user_rate_multiplier": 0.6,
                "resolved_rate_multiplier": 0.6,
                "peak_rate_enabled": True,
                "peak_rate_multiplier": 1.5,
                "applied_peak_multiplier": 1.5,
                "effective_rate_multiplier": 0.9,
                "observed_at": "2026-08-17T00:00:00Z",
            },
            0.9,
        ),
        (
            "newapi",
            "vip",
            "/api/pricing",
            {"success": True, "group_ratio": {"default": 1, "vip": 0.75}},
            0.75,
        ),
    ],
)
def test_sync_credential_rate_persists_upstream_multiplier(
    client,
    app_state,
    admin_headers,
    create_site,
    monkeypatch,
    source,
    group,
    expected_path,
    upstream_payload,
    expected_rate,
) -> None:
    site = create_site(_rate_site_payload(source, group=group))

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == expected_path
        if source == "sub2api":
            assert request.headers["authorization"] == "Bearer upstream-secret"
            assert request.headers["x-api-key"] == "upstream-secret"
        else:
            assert "authorization" not in request.headers
        return httpx.Response(200, json=upstream_payload, request=request)

    upstream_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(
        app_state, "get_http_client", lambda _proxy_url: upstream_client
    )
    try:
        response = client.post(
            f"/api/admin/sites/{site['id']}/credentials/cred-1/rate-sync",
            headers=admin_headers,
        )
    finally:
        run_async(upstream_client.aclose())

    assert response.status_code == 200, response.text
    credential = response.json()
    assert credential["rate_multiplier"] == expected_rate
    assert credential["rate_observed_at"]
    assert credential["rate_last_synced_at"]
    stored = client.get("/api/admin/sites", headers=admin_headers).json()[0]
    assert stored["credentials"][0]["rate_multiplier"] == expected_rate


def test_failed_credential_rate_sync_preserves_cached_multiplier(
    client,
    app_state,
    admin_headers,
    create_site,
    monkeypatch,
) -> None:
    site = create_site(_rate_site_payload("sub2api"))
    should_fail = False

    async def handler(request: httpx.Request) -> httpx.Response:
        if should_fail:
            return httpx.Response(
                503,
                json={"error": {"message": "temporarily unavailable"}},
                request=request,
            )
        return httpx.Response(
            200,
            json={
                "object": "sub2api.key_billing",
                "schema_version": 1,
                "billing_scope": "token",
                "group_rate_multiplier": 0.8,
                "user_rate_multiplier": None,
                "resolved_rate_multiplier": 0.8,
                "peak_rate_enabled": False,
                "peak_rate_multiplier": None,
                "applied_peak_multiplier": None,
                "effective_rate_multiplier": 0.8,
                "observed_at": "2026-08-17T00:00:00Z",
            },
            request=request,
        )

    upstream_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(
        app_state, "get_http_client", lambda _proxy_url: upstream_client
    )
    try:
        first = client.post(
            f"/api/admin/sites/{site['id']}/credentials/cred-1/rate-sync",
            headers=admin_headers,
        )
        should_fail = True
        failed = client.post(
            f"/api/admin/sites/{site['id']}/credentials/cred-1/rate-sync",
            headers=admin_headers,
        )
    finally:
        run_async(upstream_client.aclose())

    assert first.status_code == 200, first.text
    assert_error(failed, 502, "temporarily unavailable")
    stored = client.get("/api/admin/sites", headers=admin_headers).json()[0]
    credential = stored["credentials"][0]
    assert credential["rate_multiplier"] == 0.8
    assert "temporarily unavailable" in credential["rate_last_error"]


def test_credential_rate_sync_rejects_stale_configuration(
    client,
    app_state,
    admin_headers,
    create_site,
    monkeypatch,
) -> None:
    site = create_site(_rate_site_payload("sub2api"))

    async def handler(request: httpx.Request) -> httpx.Response:
        await app_state.channel_store.update_site(
            site["id"],
            SiteUpdate.model_validate(_rate_site_payload("newapi", group="vip")),
        )
        return httpx.Response(
            200,
            json={
                "object": "sub2api.key_billing",
                "schema_version": 1,
                "billing_scope": "token",
                "group_rate_multiplier": 0.8,
                "user_rate_multiplier": None,
                "resolved_rate_multiplier": 0.8,
                "peak_rate_enabled": False,
                "peak_rate_multiplier": None,
                "applied_peak_multiplier": None,
                "effective_rate_multiplier": 0.8,
                "observed_at": "2026-08-17T00:00:00Z",
            },
            request=request,
        )

    upstream_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(
        app_state, "get_http_client", lambda _proxy_url: upstream_client
    )
    try:
        response = client.post(
            f"/api/admin/sites/{site['id']}/credentials/cred-1/rate-sync",
            headers=admin_headers,
        )
    finally:
        run_async(upstream_client.aclose())

    assert_error(response, 409, "configuration changed during sync")
    stored = client.get("/api/admin/sites", headers=admin_headers).json()[0]
    credential = stored["credentials"][0]
    assert credential["rate_source"] == "newapi"
    assert credential["rate_group"] == "vip"
    assert credential["rate_multiplier"] is None


def test_site_crud_round_trip(client, admin_headers, create_site) -> None:
    assert client.get("/api/admin/sites", headers=admin_headers).json() == []

    create_payload = valid_site_payload(tags=[" primary ", "production", "primary"])
    site = create_site(create_payload)
    assert site["name"] == "OpenAI Site"
    assert site["tags"] == ["primary", "production"]
    assert "priority" not in site
    assert site["base_urls"][0]["url"] == "https://upstream.example/"
    assert site["protocols"][0]["models"][0]["model_name"] == "gpt-4o"

    update_payload = valid_site_payload(
        name="Renamed Site", model_name="gpt-4.1", tags=["backup"]
    )
    update_response = client.put(
        f"/api/admin/sites/{site['id']}",
        headers=admin_headers,
        json=update_payload,
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Renamed Site"
    assert update_response.json()["tags"] == ["backup"]
    assert "priority" not in update_response.json()

    delete_response = client.delete(
        f"/api/admin/sites/{site['id']}", headers=admin_headers
    )
    assert delete_response.status_code == 204
    assert client.get("/api/admin/sites", headers=admin_headers).json() == []


def test_list_sites_filters_by_exact_tag(client, admin_headers, create_site) -> None:
    create_site(valid_site_payload(tags=["production", "OpenAI"]))
    create_site(
        valid_site_payload(
            name="Backup Site",
            base_id="base-backup",
            credential_id="cred-backup",
            protocol_config_id="pc-backup",
            tags=["backup"],
        )
    )

    response = client.get(
        "/api/admin/sites", headers=admin_headers, params={"tag": "production"}
    )

    assert response.status_code == 200
    assert [site["name"] for site in response.json()] == ["OpenAI Site"]

    prefix_response = client.get(
        "/api/admin/sites", headers=admin_headers, params={"tag": "prod"}
    )
    assert prefix_response.status_code == 200
    assert prefix_response.json() == []


def test_toggle_site_preserves_configured_states_and_restores_group_member(
    client,
    admin_headers,
    create_site,
) -> None:
    payload = valid_site_payload()
    payload["protocols"][0]["models"].append(
        {
            "credential_id": "cred-1",
            "model_name": "manually-disabled",
            "enabled": True,
            "protocol": "openai_chat",
        }
    )
    payload["protocols"].append(
        {
            "id": "pc-disabled",
            "name": "disabled",
            "protocols": ["openai_embedding"],
            "enabled": False,
            "base_url_id": "base-1",
            "credential_ids": ["cred-1"],
            "models": [
                {
                    "credential_id": "cred-1",
                    "model_name": "text-embedding-3-small",
                    "enabled": False,
                    "protocol": "openai_embedding",
                }
            ],
        }
    )
    site = create_site(payload)
    group_response = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={
            "name": "gpt-4o",
            "items": [
                {
                    "channel_id": openai_chat_channel_id(),
                    "credential_id": "cred-1",
                    "model_name": "gpt-4o",
                    "enabled": True,
                },
                {
                    "channel_id": openai_chat_channel_id(),
                    "credential_id": "cred-1",
                    "model_name": "manually-disabled",
                    "enabled": False,
                },
            ],
        },
    )
    assert group_response.status_code == 201

    disabled_response = client.put(
        f"/api/admin/sites/{site['id']}/enabled",
        headers=admin_headers,
        json={"enabled": False},
    )

    assert disabled_response.status_code == 200
    disabled_site = disabled_response.json()
    assert disabled_site["enabled"] is False
    assert [item["enabled"] for item in disabled_site["protocols"]] == [True, False]
    assert [item["models"][0]["enabled"] for item in disabled_site["protocols"]] == [
        True,
        False,
    ]
    disabled_group = client.get(
        "/api/admin/model-groups", headers=admin_headers
    ).json()[0]
    assert [item["enabled"] for item in disabled_group["items"]] == [True, False]
    assert [item["state"] for item in disabled_group["items"]] == [
        "unavailable",
        "unavailable",
    ]
    assert disabled_group["items"][1]["reasons"] == [
        "manual_disabled",
        "channel_disabled",
    ]

    enabled_response = client.put(
        f"/api/admin/sites/{site['id']}/enabled",
        headers=admin_headers,
        json={"enabled": True},
    )

    assert enabled_response.status_code == 200
    enabled_site = enabled_response.json()
    assert enabled_site["enabled"] is True
    assert [item["enabled"] for item in enabled_site["protocols"]] == [True, False]
    assert [item["models"][0]["enabled"] for item in enabled_site["protocols"]] == [
        True,
        False,
    ]
    enabled_group = client.get("/api/admin/model-groups", headers=admin_headers).json()[
        0
    ]
    assert [item["enabled"] for item in enabled_group["items"]] == [True, False]
    assert [item["state"] for item in enabled_group["items"]] == [
        "ready",
        "disabled",
    ]
    assert enabled_group["items"][1]["reasons"] == ["manual_disabled"]


def test_site_dependency_changes_update_members_but_keep_group_shells(
    client,
    admin_headers,
    create_site,
    create_model_group,
) -> None:
    site = create_site(valid_site_payload())
    execution_group = create_model_group(
        items=[
            {
                "channel_id": openai_chat_channel_id(),
                "credential_id": "cred-1",
                "model_name": "gpt-4o",
                "enabled": True,
            }
        ]
    )
    routed_group = create_model_group(
        name="routed", route_group_id=execution_group["id"]
    )
    disabled_payload = valid_site_payload(credential_enabled=False)
    disabled_response = client.put(
        f"/api/admin/sites/{site['id']}",
        headers=admin_headers,
        json=disabled_payload,
    )
    assert disabled_response.status_code == 200, disabled_response.text
    disabled_item = client.get(
        f"/api/admin/model-groups/{execution_group['id']}", headers=admin_headers
    ).json()["items"][0]
    assert disabled_item["enabled"] is True
    assert disabled_item["state"] == "unavailable"
    assert disabled_item["reasons"] == ["credential_disabled"]

    enabled_response = client.put(
        f"/api/admin/sites/{site['id']}",
        headers=admin_headers,
        json=valid_site_payload(),
    )
    assert enabled_response.status_code == 200, enabled_response.text
    enabled_item = client.get(
        f"/api/admin/model-groups/{execution_group['id']}", headers=admin_headers
    ).json()["items"][0]
    assert enabled_item["enabled"] is True
    assert enabled_item["state"] == "ready"

    delete_response = client.delete(
        f"/api/admin/sites/{site['id']}", headers=admin_headers
    )
    assert delete_response.status_code == 204
    groups = client.get("/api/admin/model-groups", headers=admin_headers).json()
    assert {group["id"] for group in groups} == {
        execution_group["id"],
        routed_group["id"],
    }
    assert (
        next(group for group in groups if group["id"] == execution_group["id"])["items"]
        == []
    )


def test_removing_credential_cleans_group_members_but_keeps_group_shell(
    client,
    admin_headers,
    create_site,
    create_model_group,
) -> None:
    payload = valid_site_payload(model_name="gpt-4o")
    payload["credentials"].append(
        {
            "id": "cred-2",
            "name": "secondary-key",
            "api_key": "secondary-secret",
            "enabled": True,
        }
    )
    payload["protocols"][0]["credential_ids"].append("cred-2")
    payload["protocols"][0]["models"].append(
        {
            "credential_id": "cred-2",
            "model_name": "gpt-4o-secondary",
            "enabled": True,
            "protocol": "openai_chat",
        }
    )
    site = create_site(payload)
    group = create_model_group(
        name="deleted-key-group",
        items=[
            {
                "channel_id": openai_chat_channel_id(),
                "credential_id": "cred-2",
                "model_name": "gpt-4o-secondary",
                "enabled": True,
            }
        ],
    )

    retained_payload = valid_site_payload(model_name="gpt-4o")
    response = client.put(
        f"/api/admin/sites/{site['id']}",
        headers=admin_headers,
        json=retained_payload,
    )
    assert response.status_code == 200, response.text
    remaining = client.get(
        f"/api/admin/model-groups/{group['id']}", headers=admin_headers
    )
    assert remaining.status_code == 200
    assert remaining.json()["items"] == []


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("base_urls", "At least one base URL is required"),
        ("credentials", "At least one credential is required"),
    ],
)
def test_create_site_rejects_missing_required_resources(
    client, admin_headers, field, message
) -> None:
    payload = valid_site_payload()
    payload[field] = []
    if field == "credentials":
        payload["protocols"] = []

    response = client.post("/api/admin/sites", headers=admin_headers, json=payload)

    assert_error(response, 400, message)


def test_create_site_rejects_duplicate_site_name(
    client,
    admin_headers,
    create_site,
) -> None:
    create_site(valid_site_payload(name="Duplicate Site"))

    response = client.post(
        "/api/admin/sites",
        headers=admin_headers,
        json=valid_site_payload(name="Duplicate Site"),
    )

    assert_error(response, 400, "Site already exists")


def test_update_site_rejects_duplicate_site_name(
    client,
    admin_headers,
    create_site,
) -> None:
    first = create_site(
        valid_site_payload(
            name="First Site",
            base_id="base-first",
            credential_id="cred-first",
            protocol_config_id="pc-first",
        )
    )
    create_site(
        valid_site_payload(
            name="Second Site",
            base_id="base-second",
            credential_id="cred-second",
            protocol_config_id="pc-second",
        )
    )

    response = client.put(
        f"/api/admin/sites/{first['id']}",
        headers=admin_headers,
        json=valid_site_payload(
            name="Second Site",
            base_id="base-first",
            credential_id="cred-first",
            protocol_config_id="pc-first",
        ),
    )

    assert_error(response, 400, "Site already exists")


def test_create_site_rejects_duplicate_credential_name(client, admin_headers) -> None:
    payload = valid_site_payload()
    payload["credentials"] = [
        {"id": "cred-1", "name": "dup", "api_key": "one"},
        {"id": "cred-2", "name": "dup", "api_key": "two"},
    ]

    response = client.post("/api/admin/sites", headers=admin_headers, json=payload)

    assert_error(response, 400, "Duplicate credential name")


@pytest.mark.parametrize(
    ("target", "field", "value", "message"),
    [
        (
            "protocol",
            "base_url_id",
            "missing",
            "Base URL not found for protocol config",
        ),
        (
            "protocol",
            "credential_ids",
            ["missing"],
            "Credential not found for protocol config",
        ),
        ("model", "credential_id", "missing", "Model credential not found"),
        ("model", "protocol", "gemini", "Model protocol is not enabled"),
    ],
)
def test_create_site_rejects_invalid_resource_refs(
    client, admin_headers, target, field, value, message
) -> None:
    payload = valid_site_payload()
    item = payload["protocols"][0]
    if target == "model":
        item = item["models"][0]
    item[field] = value

    response = client.post("/api/admin/sites", headers=admin_headers, json=payload)

    assert_error(response, 400, message)


def test_create_site_rejects_duplicate_protocol_config(client, admin_headers) -> None:
    payload = valid_site_payload()
    duplicate = dict(payload["protocols"][0])
    duplicate["id"] = "pc-2"
    payload["protocols"].append(duplicate)

    response = client.post("/api/admin/sites", headers=admin_headers, json=payload)

    assert_error(response, 400, "Duplicate protocol config")


def test_update_delete_and_toggle_missing_site_return_not_found(
    client, admin_headers
) -> None:
    update_response = client.put(
        "/api/admin/sites/missing",
        headers=admin_headers,
        json=valid_site_payload(name="Missing"),
    )
    delete_response = client.delete("/api/admin/sites/missing", headers=admin_headers)
    enabled_response = client.put(
        "/api/admin/sites/missing/enabled",
        headers=admin_headers,
        json={"enabled": False},
    )

    assert_error(update_response, 404, "missing")
    assert_error(delete_response, 404, "missing")
    assert_error(enabled_response, 404, "missing")

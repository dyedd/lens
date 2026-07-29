from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException

from conftest import assert_error, openai_chat_channel_id, seed_request_log
from conftest import valid_site_payload
from lens_api.models import ChannelModelSyncResponse, SiteModelTestResult


def test_list_sites_requires_admin(client) -> None:
    response = client.get("/api/admin/sites")

    assert_error(response, 401, "Not authenticated")


def test_update_site_enabled_requires_admin(client) -> None:
    response = client.put("/api/admin/sites/missing/enabled", json={"enabled": False})

    assert_error(response, 401, "Not authenticated")


def test_site_crud_round_trip(client, admin_headers, create_site) -> None:
    assert client.get("/api/admin/sites", headers=admin_headers).json() == []

    create_payload = valid_site_payload()
    create_payload["priority"] = 7
    site = create_site(create_payload)
    assert site["name"] == "OpenAI Site"
    assert site["priority"] == 7
    assert site["base_urls"][0]["url"] == "https://upstream.example/"
    assert site["protocols"][0]["models"][0]["model_name"] == "gpt-4o"

    update_payload = valid_site_payload(name="Renamed Site", model_name="gpt-4.1")
    update_payload["priority"] = 3
    update_response = client.put(
        f"/api/admin/sites/{site['id']}",
        headers=admin_headers,
        json=update_payload,
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Renamed Site"
    assert update_response.json()["priority"] == 3

    delete_response = client.delete(
        f"/api/admin/sites/{site['id']}", headers=admin_headers
    )
    assert delete_response.status_code == 204
    assert client.get("/api/admin/sites", headers=admin_headers).json() == []


def test_create_site_rejects_negative_priority(client, admin_headers) -> None:
    payload = valid_site_payload()
    payload["priority"] = -1

    response = client.post("/api/admin/sites", headers=admin_headers, json=payload)

    assert response.status_code == 422


def test_toggle_site_preserves_configured_states_and_restores_group_member(
    client,
    admin_headers,
    create_site,
) -> None:
    payload = valid_site_payload()
    payload["protocols"].append(
        {
            "id": "pc-disabled",
            "name": "disabled",
            "protocols": ["openai_embedding"],
            "enabled": False,
            "base_url_id": "base-1",
            "credential_id": "cred-1",
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
            "protocols": ["openai_chat"],
            "items": [
                {
                    "channel_id": openai_chat_channel_id(),
                    "credential_id": "cred-1",
                    "model_name": "gpt-4o",
                    "enabled": True,
                }
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
    assert disabled_group["items"][0]["enabled"] is True
    assert disabled_group["items"][0]["state"] == "unavailable"
    assert disabled_group["items"][0]["reasons"] == ["channel_disabled"]

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
    assert enabled_group["items"][0]["enabled"] is True
    assert enabled_group["items"][0]["state"] == "ready"
    assert enabled_group["items"][0]["reasons"] == []


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
            "credential_id",
            "missing",
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

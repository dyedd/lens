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


def test_site_crud_round_trip(client, admin_headers, create_site) -> None:
    assert client.get("/api/admin/sites", headers=admin_headers).json() == []

    site = create_site()
    assert site["name"] == "OpenAI Site"
    assert site["base_urls"][0]["url"] == "https://upstream.example/"
    assert site["protocols"][0]["models"][0]["model_name"] == "gpt-4o"

    update_response = client.put(
        f"/api/admin/sites/{site['id']}",
        headers=admin_headers,
        json=valid_site_payload(name="Renamed Site", model_name="gpt-4.1"),
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "Renamed Site"

    delete_response = client.delete(
        f"/api/admin/sites/{site['id']}", headers=admin_headers
    )
    assert delete_response.status_code == 204
    assert client.get("/api/admin/sites", headers=admin_headers).json() == []


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


def test_update_and_delete_missing_site_return_not_found(client, admin_headers) -> None:
    update_response = client.put(
        "/api/admin/sites/missing",
        headers=admin_headers,
        json=valid_site_payload(name="Missing"),
    )
    delete_response = client.delete("/api/admin/sites/missing", headers=admin_headers)

    assert_error(update_response, 404, "missing")
    assert_error(delete_response, 404, "missing")

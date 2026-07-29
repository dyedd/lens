from __future__ import annotations

from copy import deepcopy

import pytest

from conftest import valid_site_payload


def valid_import_site(
    *,
    name: str = "Imported Site",
    enabled: bool = True,
    priority: int = 0,
    protocol_name: str = "primary",
    auto_sync_enabled: bool = False,
    match_regex: str = "",
) -> dict:
    return {
        "name": name,
        "enabled": enabled,
        "priority": priority,
        "base_urls": [
            {
                "ref": "base",
                "url": "https://imported.example/v1",
                "name": "base",
            }
        ],
        "credentials": [
            {
                "ref": "cred",
                "name": "cred",
                "api_key": "import-secret",
            }
        ],
        "protocols": [
            {
                "name": protocol_name,
                "protocol": "openai_chat",
                "auto_sync_enabled": auto_sync_enabled,
                "match_regex": match_regex,
                "base_url_ref": "base",
                "credential_ref": "cred",
                "models": [
                    {
                        "credential_ref": "cred",
                        "model_name": "gpt-4o-mini",
                    }
                ],
            }
        ],
    }


def test_import_sites_rejects_empty_batch(client, admin_headers) -> None:
    response = client.post(
        "/api/admin/sites/import",
        headers=admin_headers,
        json={"sites": []},
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("target", "field"),
    [
        ("site", "enabled"),
        ("site", "priority"),
        ("protocol", "name"),
        ("protocol", "auto_sync_enabled"),
    ],
)
def test_import_sites_requires_strict_import_fields(
    client,
    admin_headers,
    target,
    field,
) -> None:
    site = valid_import_site()
    item = site if target == "site" else site["protocols"][0]
    del item[field]

    response = client.post(
        "/api/admin/sites/import",
        headers=admin_headers,
        json={"sites": [site]},
    )

    assert response.status_code == 422
    assert client.get("/api/admin/sites", headers=admin_headers).json() == []


@pytest.mark.parametrize(
    ("target", "field"),
    [
        ("base_url", "ref"),
        ("credential", "ref"),
        ("protocol", "base_url_ref"),
        ("protocol", "credential_ref"),
    ],
)
def test_import_sites_requires_explicit_resource_refs(
    client,
    admin_headers,
    target,
    field,
) -> None:
    site = valid_import_site()
    items = {
        "base_url": site["base_urls"][0],
        "credential": site["credentials"][0],
        "protocol": site["protocols"][0],
    }
    del items[target][field]

    response = client.post(
        "/api/admin/sites/import",
        headers=admin_headers,
        json={"sites": [site]},
    )

    assert response.status_code == 422
    assert client.get("/api/admin/sites", headers=admin_headers).json() == []


@pytest.mark.parametrize(
    ("target", "field"),
    [
        ("base_url", "ref"),
        ("credential", "ref"),
        ("protocol", "name"),
        ("protocol", "base_url_ref"),
        ("protocol", "credential_ref"),
    ],
)
def test_import_sites_rejects_blank_identifiers(
    client,
    admin_headers,
    target,
    field,
) -> None:
    site = valid_import_site()
    items = {
        "base_url": site["base_urls"][0],
        "credential": site["credentials"][0],
        "protocol": site["protocols"][0],
    }
    items[target][field] = "   "

    response = client.post(
        "/api/admin/sites/import",
        headers=admin_headers,
        json={"sites": [site]},
    )

    assert response.status_code == 422
    assert client.get("/api/admin/sites", headers=admin_headers).json() == []


def test_import_sites_skips_existing_site_names(
    client,
    admin_headers,
    create_site,
) -> None:
    create_site(valid_site_payload(name="Imported Site"))

    response = client.post(
        "/api/admin/sites/import",
        headers=admin_headers,
        json={"sites": [valid_import_site()]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["committed"] is False
    assert payload["skipped_count"] == 1
    assert payload["items"] == [
        {
            "index": 0,
            "name": "Imported Site",
            "status": "skipped",
            "reason": "duplicate_name",
            "site": None,
            "errors": [],
        }
    ]


def test_import_sites_reports_not_committed_items_without_cascading_errors(
    client,
    admin_headers,
) -> None:
    broken = valid_import_site(name="Broken Import")
    broken["base_urls"] = []

    response = client.post(
        "/api/admin/sites/import",
        headers=admin_headers,
        json={"sites": [valid_import_site(), broken]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["committed"] is False
    assert payload["created_count"] == 0
    assert payload["error_count"] == 1
    assert payload["not_committed_count"] == 1
    assert payload["items"][0] == {
        "index": 0,
        "name": "Imported Site",
        "status": "not_committed",
        "reason": "batch_validation_failed",
        "site": None,
        "errors": [],
    }
    assert payload["items"][1] == {
        "index": 1,
        "name": "Broken Import",
        "status": "error",
        "reason": "",
        "site": None,
        "errors": [
            {
                "field": "base_urls",
                "message": "At least one base URL is required",
            }
        ],
    }
    assert client.get("/api/admin/sites", headers=admin_headers).json() == []


def test_import_sites_reserves_duplicate_name_before_item_validation(
    client,
    admin_headers,
) -> None:
    broken = valid_import_site(name="Repeated Site")
    broken["base_urls"] = []

    response = client.post(
        "/api/admin/sites/import",
        headers=admin_headers,
        json={
            "sites": [
                broken,
                valid_import_site(name="Repeated Site"),
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["committed"] is False
    assert payload["error_count"] == 1
    assert payload["skipped_count"] == 1
    assert [item["status"] for item in payload["items"]] == ["error", "skipped"]
    assert payload["items"][1]["reason"] == "duplicate_in_file"
    assert client.get("/api/admin/sites", headers=admin_headers).json() == []


def test_import_sites_preserves_input_order_when_skipping_before_creation(
    client,
    admin_headers,
    create_site,
) -> None:
    create_site(valid_site_payload(name="Existing Site"))

    response = client.post(
        "/api/admin/sites/import",
        headers=admin_headers,
        json={
            "sites": [
                valid_import_site(name="Existing Site"),
                valid_import_site(name="Created Site"),
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "committed",
        "created_count",
        "skipped_count",
        "error_count",
        "not_committed_count",
        "items",
    }
    assert payload["committed"] is True
    assert payload["created_count"] == 1
    assert payload["skipped_count"] == 1
    assert [
        (item["index"], item["name"], item["status"]) for item in payload["items"]
    ] == [
        (0, "Existing Site", "skipped"),
        (1, "Created Site", "created"),
    ]
    assert payload["items"][1]["site"]["name"] == "Created Site"


def test_import_sites_persists_master_state_protocol_name_and_auto_sync(
    client,
    admin_headers,
) -> None:
    response = client.post(
        "/api/admin/sites/import",
        headers=admin_headers,
        json={
            "sites": [
                valid_import_site(
                    enabled=False,
                    priority=8,
                    protocol_name="  Chat primary  ",
                    auto_sync_enabled=True,
                    match_regex="^gpt-",
                )
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["committed"] is True
    assert payload["items"][0]["status"] == "created"
    created = payload["items"][0]["site"]
    assert created["enabled"] is False
    assert created["priority"] == 8
    assert created["protocols"][0]["name"] == "Chat primary"
    assert created["protocols"][0]["auto_sync_enabled"] is True

    stored = client.get("/api/admin/sites", headers=admin_headers).json()[0]
    assert stored["enabled"] is False
    assert stored["priority"] == 8
    assert stored["protocols"][0]["name"] == "Chat primary"
    assert stored["protocols"][0]["auto_sync_enabled"] is True


@pytest.mark.parametrize(
    "param_override",
    ["not-json", "[]", '{"model":"forbidden"}'],
)
def test_import_sites_rejects_invalid_param_override(
    client,
    admin_headers,
    param_override,
) -> None:
    site = valid_import_site()
    site["protocols"][0]["param_override"] = param_override

    response = client.post(
        "/api/admin/sites/import",
        headers=admin_headers,
        json={"sites": [site]},
    )

    assert response.status_code == 422
    assert client.get("/api/admin/sites", headers=admin_headers).json() == []


def test_import_sites_rejects_auto_sync_without_match_regex(
    client,
    admin_headers,
) -> None:
    site = deepcopy(valid_import_site())
    site["protocols"][0]["auto_sync_enabled"] = True

    response = client.post(
        "/api/admin/sites/import",
        headers=admin_headers,
        json={"sites": [site]},
    )

    assert response.status_code == 422
    assert client.get("/api/admin/sites", headers=admin_headers).json() == []

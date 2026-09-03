from __future__ import annotations

import json

import pytest
from conftest import assert_error


def _json_file(payload: dict) -> dict:
    return {
        "file": (
            "backup.json",
            json.dumps(payload).encode(),
            "application/json",
        )
    }


def _metapi_file() -> dict:
    return _json_file(
        {
            "version": "2.1",
            "timestamp": 1735689600000,
            "accounts": {
                "sites": [
                    {
                        "id": 1,
                        "name": "metapi-site",
                        "url": "https://metapi.example.com",
                        "platform": "new-api",
                        "status": "active",
                        "apiKey": "sk-site",
                    }
                ],
                "accounts": [
                    {"id": 11, "siteId": 1, "username": "user", "status": "active"}
                ],
                "accountTokens": [
                    {"id": 21, "accountId": 11, "name": "default", "token": "sk-tok"}
                ],
            },
        }
    )


def _sub2api_file() -> dict:
    return _json_file(
        {
            "exported_at": "2026-09-03T08:15:42Z",
            "proxies": [],
            "accounts": [
                {
                    "name": "sub2api-upstream",
                    "platform": "anthropic",
                    "type": "upstream",
                    "credentials": {
                        "api_key": "sk-ant",
                        "base_url": "https://relay.example.com",
                    },
                },
                {
                    "name": "sub2api-oauth",
                    "platform": "anthropic",
                    "type": "oauth",
                    "credentials": {"token": "session"},
                },
            ],
        }
    )


def _ccload_file() -> dict:
    csv_text = (
        "id,name,api_key,api_key_allowed_models,api_key_cost_multipliers,"
        "api_key_model_scope_empty,urls,priority,models,enabled,auth_type\n"
        '1,ccload-channel,"sk-a,sk-b",[],[],[],'
        '"[{""url"":""https://api.example.com"",""protocols"":[""anthropic""]}]",'
        "10,claude-sonnet-4,true,api_key\n"
    )
    return {"file": ("channels.csv", csv_text.encode(), "text/csv")}


def _all_api_hub_file() -> dict:
    return _json_file(
        {
            "version": "4.0",
            "timestamp": 1756857600000,
            "accounts": {"accounts": [{"id": "a1"}]},
            "apiCredentialProfiles": {
                "version": 6,
                "profiles": [
                    {
                        "id": "p1",
                        "name": "hub-profile",
                        "apiType": "anthropic",
                        "baseUrl": "https://api.anthropic.com",
                        "apiKey": "sk-hub",
                    }
                ],
            },
        }
    )


def _octopus_file() -> dict:
    return _json_file(
        {
            "version": 5,
            "exported_at": "2026-09-03T08:15:42Z",
            "channels": [
                {
                    "id": 1,
                    "name": "octopus-channel",
                    "enabled": True,
                    "base_url": "https://relay.example.com",
                }
            ],
            "channel_keys": [
                {
                    "id": 5,
                    "channel_id": 1,
                    "name": "default",
                    "key": "sk-oct",
                    "enabled": True,
                }
            ],
            "channel_models": [
                {"id": 9, "channel_id": 1, "name": "gpt-5"},
                {"id": 10, "channel_id": 1, "name": "claude-sonnet-4"},
            ],
            "channel_grants": [
                {
                    "id": 20,
                    "channel_model_id": 9,
                    "channel_key_id": 5,
                    "protocols": 2,
                },
                {
                    "id": 21,
                    "channel_model_id": 10,
                    "channel_key_id": 5,
                    "protocols": 8,
                },
            ],
        }
    )


@pytest.mark.parametrize(
    ("file_part", "expected_format", "expected_names"),
    [
        pytest.param(_metapi_file(), "metapi", ["metapi-site"], id="metapi"),
        pytest.param(_sub2api_file(), "sub2api", ["sub2api-upstream"], id="sub2api"),
        pytest.param(_ccload_file(), "ccload", ["ccload-channel"], id="ccload"),
        pytest.param(
            _all_api_hub_file(), "all_api_hub", ["hub-profile"], id="all-api-hub"
        ),
        pytest.param(_octopus_file(), "octopus", ["octopus-channel"], id="octopus"),
    ],
)
def test_preview_foreign_backup_detects_format(
    client, admin_headers, file_part, expected_format, expected_names
) -> None:
    response = client.post(
        "/api/admin/sites/import/preview", headers=admin_headers, files=file_part
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["format"] == expected_format
    assert [site["name"] for site in payload["sites"]] == expected_names
    assert payload["payload"] is not None
    for site in payload["sites"]:
        assert site["credential_count"] >= 1
        assert len(site["base_urls"]) >= 1


def test_preview_then_import_creates_sites(client, admin_headers) -> None:
    preview = client.post(
        "/api/admin/sites/import/preview",
        headers=admin_headers,
        files=_sub2api_file(),
    ).json()

    assert preview["warnings"], "the skipped OAuth account should be reported"
    import_response = client.post(
        "/api/admin/sites/import", headers=admin_headers, json=preview["payload"]
    )

    assert import_response.status_code == 200
    assert import_response.json()["created_count"] == 1
    sites = client.get("/api/admin/sites", headers=admin_headers).json()
    assert [site["name"] for site in sites] == ["sub2api-upstream"]
    assert sites[0]["credentials"][0]["api_key"] == "sk-ant"


def test_preview_flags_lens_backup_file(client, admin_headers) -> None:
    response = client.post(
        "/api/admin/sites/import/preview",
        headers=admin_headers,
        files=_json_file({"lens_version": "1.0.0", "sites": [], "exported_at": "x"}),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["format"] == "lens"
    assert payload["sites"] == []
    assert payload["payload"] is None
    assert payload["warnings"]


def test_preview_rejects_unrecognized_file(client, admin_headers) -> None:
    response = client.post(
        "/api/admin/sites/import/preview",
        headers=admin_headers,
        files={"file": ("notes.txt", b"not a backup", "text/plain")},
    )

    assert_error(response, 422)

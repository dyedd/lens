from __future__ import annotations

import json

import pytest


@pytest.mark.parametrize(
    ("format_id", "content", "protocol", "model_names"),
    [
        (
            "metapi",
            {
                "accounts": {
                    "sites": [
                        {
                            "id": 1,
                            "name": "metapi",
                            "url": "https://provider.example/v1",
                            "apiKey": "import-secret",
                            "platform": "claude",
                            "customHeaders": '{"X-Provider":"metapi"}',
                        }
                    ],
                    "accounts": [{"id": 2, "siteId": 1}],
                    "manualModels": [{"accountId": 2, "modelName": "claude-test"}],
                }
            },
            "anthropic",
            {"claude-test"},
        ),
        (
            "sub2api",
            {
                "type": "sub2api-data",
                "accounts": [
                    {
                        "name": "sub2api",
                        "platform": "gemini",
                        "type": "apikey",
                        "credentials": {
                            "api_key": "import-secret",
                            "base_url": "https://provider.example/v1",
                        },
                    }
                ],
            },
            "gemini",
            set(),
        ),
        (
            "octopus",
            {
                "version": 5,
                "exported_at": "2026-11-07T00:00:00Z",
                "channels": [
                    {
                        "id": 1,
                        "name": "octopus",
                        "base_url": "https://provider.example/v1",
                        "enabled": True,
                    }
                ],
                "channel_keys": [{"id": 2, "channel_id": 1, "key": "import-secret"}],
                "channel_models": [{"id": 3, "channel_id": 1, "name": "claude-test"}],
                "channel_grants": [{"channel_model_id": 3, "protocols": 8}],
            },
            "anthropic",
            {"claude-test"},
        ),
        (
            "all_api_hub",
            {
                "version": "2",
                "timestamp": 1,
                "apiCredentialProfiles": {
                    "profiles": [
                        {
                            "name": "all_api_hub",
                            "baseUrl": "https://provider.example/v1",
                            "apiKey": "import-secret",
                            "apiType": "google",
                            "tagIds": ["tag-1"],
                        }
                    ]
                },
                "tagStore": {"tagsById": {"tag-1": {"name": "Imported"}}},
            },
            "gemini",
            set(),
        ),
        (
            "ccload",
            "name,urls,models,api_key,enabled\n"
            'ccload,"[{""url"":""https://provider.example/v1"",'
            '""protocols"":[""openai""]}]",gpt-4o,import-secret,true\n',
            "openai_chat",
            {"gpt-4o"},
        ),
        (
            "cli_proxy_api",
            "openai-compatibility:\n"
            "  - name: cli_proxy_api\n"
            "    base-url: https://provider.example/v1\n"
            "    api-key-entries:\n"
            "      - api-key: import-secret\n"
            "    models:\n"
            "      - name: gpt-4o\n",
            "openai_chat",
            {"gpt-4o"},
        ),
    ],
    ids=["metapi", "sub2api", "octopus", "all-api-hub", "ccload", "cli-proxy-api"],
)
def test_foreign_export_preview_imports_a_site(
    client, admin_headers, format_id, content, protocol, model_names
) -> None:
    raw = content if isinstance(content, str) else json.dumps(content)
    response = client.post(
        "/api/admin/sites/import/preview",
        headers=admin_headers,
        files={"file": ("export.txt", raw.encode(), "application/octet-stream")},
    )
    assert response.status_code == 200, response.text
    preview = response.json()
    assert preview["format"] == format_id
    assert len(preview["sites"]) == 1
    assert preview["sites"][0]["name"] == format_id
    assert preview["sites"][0]["credential_count"] == 1
    assert preview["sites"][0]["protocols"] == [protocol]
    assert preview["sites"][0]["model_count"] == len(model_names)

    response = client.post(
        "/api/admin/sites/import", headers=admin_headers, json=preview["payload"]
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["committed"] is True
    assert result["created_count"] == 1
    assert result["error_count"] == 0
    assert result["items"][0]["status"] == "created"

    response = client.get("/api/admin/sites", headers=admin_headers)
    assert response.status_code == 200
    [site] = response.json()
    assert site["id"] == result["items"][0]["site"]["id"]
    assert site["name"] == format_id
    assert site["base_urls"][0]["url"] == "https://provider.example/"
    assert site["credentials"][0]["api_key"] == "import-secret"
    source = preview["payload"]["sites"][0]
    assert site["enabled"] == source["enabled"]
    assert site["tags"] == source["tags"]
    assert site["headers"] == source["headers"]
    models = [model for config in site["protocols"] for model in config["models"]]
    assert {model["model_name"] for model in models} == model_names
    assert {model["protocol"] for model in models} == (
        {protocol} if model_names else set()
    )
    assert {model["credential_id"] for model in models} <= {
        site["credentials"][0]["id"]
    }

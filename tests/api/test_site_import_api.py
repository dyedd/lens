from __future__ import annotations

from conftest import valid_site_payload


def test_import_sites_reports_empty_file_errors(client, admin_headers) -> None:
    response = client.post(
        "/api/admin/sites/import",
        headers=admin_headers,
        json={"sites": []},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["committed"] is False
    assert payload["error_count"] == 1
    assert payload["errors"][0]["field"] == "sites"


def test_import_sites_skips_existing_site_names(
    client,
    admin_headers,
    create_site,
) -> None:
    create_site(valid_site_payload(name="Imported Site"))

    response = client.post(
        "/api/admin/sites/import",
        headers=admin_headers,
        json={
            "sites": [
                {
                    "name": "Imported Site",
                    "base_urls": [{"url": "https://imported.example/v1"}],
                    "credentials": [{"name": "cred", "api_key": "secret"}],
                    "protocols": [{"protocol": "openai_chat"}],
                }
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["committed"] is False
    assert payload["skipped_count"] == 1
    assert payload["skipped"][0]["reason"] == "duplicate_name"


def test_import_sites_reports_validation_errors_without_commit(
    client,
    admin_headers,
) -> None:
    response = client.post(
        "/api/admin/sites/import",
        headers=admin_headers,
        json={
            "sites": [
                {
                    "name": "Broken Import",
                    "base_urls": [],
                    "credentials": [{"name": "cred", "api_key": "secret"}],
                    "protocols": [{"protocol": "openai_chat"}],
                }
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["committed"] is False
    assert payload["error_count"] >= 1
    assert client.get("/api/admin/sites", headers=admin_headers).json() == []


def test_import_sites_creates_sites_and_skips_duplicates(client, admin_headers) -> None:
    payload = {
        "sites": [
            {
                "name": "Imported Site",
                "base_urls": [
                    {
                        "ref": "base",
                        "url": "https://imported.example/v1",
                        "name": "base",
                    }
                ],
                "credentials": [
                    {"ref": "cred", "name": "cred", "api_key": "import-secret"}
                ],
                "protocols": [
                    {
                        "protocol": "openai_chat",
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
            },
            {"name": "Imported Site", "base_urls": [], "credentials": []},
        ]
    }

    response = client.post(
        "/api/admin/sites/import", headers=admin_headers, json=payload
    )

    assert response.status_code == 200
    result = response.json()
    assert result["committed"] is True
    assert result["created_count"] == 1
    assert result["skipped_count"] == 1
    assert result["skipped"][0]["reason"] == "duplicate_in_file"

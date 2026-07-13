from __future__ import annotations

from conftest import assert_error, seed_request_log, valid_site_payload


def test_export_backup_requires_admin(client) -> None:
    response = client.get("/api/admin/backups/export")

    assert_error(response, 401, "Not authenticated")


def test_export_backup_returns_json_attachment(
    client,
    admin_headers,
    create_gateway_key,
    create_site,
) -> None:
    create_gateway_key(remark="backup-key")
    create_site(valid_site_payload())

    response = client.get(
        "/api/admin/backups/export",
        headers=admin_headers,
        params={"include_gateway_api_keys": "true"},
    )

    assert response.status_code == 200
    assert "lens-backup-" in response.headers["content-disposition"]
    payload = response.json()
    assert payload["version"] == 2
    assert payload["include_gateway_api_keys"] is True
    assert len(payload["sites"]) == 1
    assert len(payload["gateway_api_keys"]) == 1


def test_export_backup_can_include_request_logs(
    client,
    admin_headers,
    app_state,
) -> None:
    seed_request_log(app_state)

    response = client.get(
        "/api/admin/backups/export",
        headers=admin_headers,
        params={"include_logs": "true"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["include_request_logs"] is True
    assert len(payload["request_logs"]) == 1
    assert payload["request_logs"][0]["requested_group_name"] == "gpt-4o"


def test_import_backup_rejects_invalid_file(client, admin_headers) -> None:
    response = client.post(
        "/api/admin/backups/import",
        headers=admin_headers,
        files={"file": ("backup.json", b"not-json", "application/json")},
    )

    assert_error(response, 400, "Invalid backup file")


def test_import_backup_accepts_exported_bundle(
    client,
    admin_headers,
    create_site,
) -> None:
    create_site(valid_site_payload())
    exported = client.get("/api/admin/backups/export", headers=admin_headers)
    assert exported.status_code == 200

    response = client.post(
        "/api/admin/backups/import",
        headers=admin_headers,
        files={
            "file": (
                "backup.json",
                exported.content,
                "application/json",
            )
        },
    )

    assert response.status_code == 200
    assert "rows_affected" in response.json()

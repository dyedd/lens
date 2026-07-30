from __future__ import annotations

import json

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
    assert "version" not in payload
    assert payload["include_gateway_api_keys"] is True
    assert len(payload["sites"]) == 1
    assert "priority" not in payload["sites"][0]
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


def test_backup_round_trip_preserves_site_master_enabled(
    client,
    admin_headers,
    create_site,
) -> None:
    site = create_site(valid_site_payload())
    update_response = client.put(
        f"/api/admin/sites/{site['id']}/enabled",
        headers=admin_headers,
        json={"enabled": False},
    )
    assert update_response.status_code == 200
    exported = client.get("/api/admin/backups/export", headers=admin_headers)
    assert exported.status_code == 200
    assert exported.json()["sites"][0]["enabled"] is False
    assert "priority" not in exported.json()["sites"][0]

    response = client.post(
        "/api/admin/backups/import",
        headers=admin_headers,
        files={"file": ("backup.json", exported.content, "application/json")},
    )

    assert response.status_code == 200
    restored_site = client.get("/api/admin/sites", headers=admin_headers).json()[0]
    assert restored_site["enabled"] is False
    assert restored_site["protocols"][0]["enabled"] is True


def test_import_backup_rejects_obsolete_site_priority(
    client,
    admin_headers,
    create_site,
) -> None:
    create_site(valid_site_payload())
    exported = client.get("/api/admin/backups/export", headers=admin_headers)
    assert exported.status_code == 200
    payload = exported.json()
    payload["sites"][0]["priority"] = 6

    response = client.post(
        "/api/admin/backups/import",
        headers=admin_headers,
        files={
            "file": (
                "backup.json",
                json.dumps(payload).encode(),
                "application/json",
            )
        },
    )

    assert_error(response, 400, "Invalid backup file")


def test_import_backup_rejects_obsolete_version_field(
    client,
    admin_headers,
    create_site,
) -> None:
    create_site(valid_site_payload())
    exported = client.get("/api/admin/backups/export", headers=admin_headers)
    assert exported.status_code == 200
    payload = exported.json()
    payload["version"] = 4

    response = client.post(
        "/api/admin/backups/import",
        headers=admin_headers,
        files={
            "file": (
                "backup.json",
                json.dumps(payload).encode(),
                "application/json",
            )
        },
    )

    assert_error(response, 400, "Invalid backup file")


def test_import_backup_rejects_missing_site_enabled(
    client,
    admin_headers,
    create_site,
) -> None:
    create_site(valid_site_payload())
    exported = client.get("/api/admin/backups/export", headers=admin_headers)
    assert exported.status_code == 200
    payload = exported.json()
    payload["sites"][0].pop("enabled")
    payload["sites"][0]["protocols"][0]["enabled"] = False

    response = client.post(
        "/api/admin/backups/import",
        headers=admin_headers,
        files={
            "file": (
                "backup.json",
                json.dumps(payload).encode(),
                "application/json",
            )
        },
    )

    assert_error(response, 400, "Invalid backup file")

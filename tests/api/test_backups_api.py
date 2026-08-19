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
    site_payload = valid_site_payload()
    site_payload["credentials"][0].update(
        {
            "rate_source": "newapi",
            "rate_protocol_config_id": "pc-1",
            "rate_group": "vip",
        }
    )
    create_site(site_payload)

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
    credential = payload["sites"][0]["credentials"][0]
    assert credential["rate_source"] == "newapi"
    assert credential["rate_protocol_config_id"] == "pc-1"
    assert credential["rate_group"] == "vip"
    assert "rate_multiplier" not in credential
    assert "rate_observed_at" not in credential
    assert "rate_last_synced_at" not in credential
    assert "rate_last_error" not in credential
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
    site_payload = valid_site_payload()
    site_payload["credentials"][0].update(
        {
            "rate_source": "newapi",
            "rate_protocol_config_id": "pc-1",
            "rate_group": "vip",
        }
    )
    create_site(site_payload)
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
    restored = client.get("/api/admin/sites", headers=admin_headers).json()[0]
    credential = restored["credentials"][0]
    assert credential["rate_source"] == "newapi"
    assert credential["rate_protocol_config_id"] == "pc-1"
    assert credential["rate_group"] == "vip"
    assert credential["rate_multiplier"] is None


def test_import_backup_rejects_invalid_credential_rate_config(
    client,
    admin_headers,
    create_site,
) -> None:
    site_payload = valid_site_payload()
    site_payload["credentials"][0].update(
        {
            "rate_source": "newapi",
            "rate_protocol_config_id": "pc-1",
            "rate_group": "vip",
        }
    )
    create_site(site_payload)
    exported = client.get("/api/admin/backups/export", headers=admin_headers)
    assert exported.status_code == 200
    payload = exported.json()
    payload["sites"][0]["credentials"][0]["rate_group"] = ""

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

    assert_error(response, 400)


def test_backup_round_trip_preserves_site_master_enabled(
    client,
    admin_headers,
    create_site,
) -> None:
    site = create_site(valid_site_payload(tags=["production", "primary"]))
    update_response = client.put(
        f"/api/admin/sites/{site['id']}/enabled",
        headers=admin_headers,
        json={"enabled": False},
    )
    assert update_response.status_code == 200
    exported = client.get("/api/admin/backups/export", headers=admin_headers)
    assert exported.status_code == 200
    assert exported.json()["sites"][0]["enabled"] is False
    assert exported.json()["sites"][0]["tags"] == ["production", "primary"]
    assert "priority" not in exported.json()["sites"][0]

    response = client.post(
        "/api/admin/backups/import",
        headers=admin_headers,
        files={"file": ("backup.json", exported.content, "application/json")},
    )

    assert response.status_code == 200
    restored_site = client.get("/api/admin/sites", headers=admin_headers).json()[0]
    assert restored_site["enabled"] is False
    assert restored_site["tags"] == ["production", "primary"]
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


def test_import_backup_rejects_missing_site_tags(
    client,
    admin_headers,
    create_site,
) -> None:
    create_site(valid_site_payload())
    exported = client.get("/api/admin/backups/export", headers=admin_headers)
    assert exported.status_code == 200
    payload = exported.json()
    payload["sites"][0].pop("tags")

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


def test_import_backup_preserves_sync_targets(
    client,
    admin_headers,
    create_site,
) -> None:
    create_site(valid_site_payload())
    exported = client.get("/api/admin/backups/export", headers=admin_headers)
    assert exported.status_code == 200
    payload = exported.json()
    protocol_config = payload["sites"][0]["protocols"][0]
    protocol_config["models"][0]["source"] = "synced"

    invalid_response = client.post(
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
    assert_error(invalid_response, 400, "Model source does not match sync targets")

    protocol_config["sync_targets"] = [
        {
            "credential_id": protocol_config["models"][0]["credential_id"],
            "model_name": protocol_config["models"][0]["model_name"],
            "protocol": protocol_config["models"][0]["protocol"],
        }
    ]

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

    assert response.status_code == 200, response.text
    stored = client.get("/api/admin/sites", headers=admin_headers).json()[0]
    assert stored["protocols"][0]["sync_targets"] == protocol_config["sync_targets"]
    assert stored["protocols"][0]["models"][0]["source"] == "synced"

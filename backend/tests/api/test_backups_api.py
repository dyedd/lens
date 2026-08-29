from __future__ import annotations

import json

import pytest
from conftest import assert_error, seed_request_log, valid_site_payload


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
    seed_request_log(
        app_state,
        rate_multiplier=2.0,
        billing_mode="non_tokens",
        billing_units=2,
    )

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
    assert payload["request_logs"][0]["rate_multiplier"] == 2.0
    assert payload["request_logs"][0]["billing_mode"] == "non_tokens"
    assert payload["request_logs"][0]["billing_units"] == 2


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
    group = client.post(
        "/api/admin/model-groups",
        headers=admin_headers,
        json={
            "name": "backup-group",
            "param_override": [{"path": "temperature", "action": "set", "value": 0.2}],
            "headers": [{"name": "X-Group", "action": "override", "value": "enabled"}],
        },
    )
    assert group.status_code == 201, group.text
    exported = client.get("/api/admin/backups/export", headers=admin_headers)
    assert exported.status_code == 200
    payload = exported.json()
    for item in payload["settings"]:
        if item["key"] == "upstream_headers_config":
            item["value"] = json.dumps(
                {
                    "rules": [
                        {"name": "X-Global", "action": "override", "value": "enabled"}
                    ]
                }
            )
            break

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

    assert response.status_code == 200
    assert "rows_affected" in response.json()
    restored = client.get("/api/admin/sites", headers=admin_headers).json()[0]
    credential = restored["credentials"][0]
    assert credential["rate_source"] == "newapi"
    assert credential["rate_protocol_config_id"] == "pc-1"
    assert credential["rate_group"] == "vip"
    assert credential["rate_multiplier"] is None
    restored_group = client.get(
        "/api/admin/model-groups", headers=admin_headers
    ).json()[0]
    assert restored_group["param_override"] == [
        {"path": "temperature", "action": "set", "value": 0.2}
    ]
    assert restored_group["headers"] == [
        {"name": "X-Group", "action": "override", "value": "enabled", "match": None}
    ]
    settings = {
        item["key"]: item["value"]
        for item in client.get("/api/admin/settings", headers=admin_headers).json()
    }
    assert json.loads(settings["upstream_headers_config"]) == {
        "rules": [
            {
                "name": "X-Global",
                "action": "override",
                "value": "enabled",
                "match": None,
            }
        ]
    }


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


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(
            lambda payload: payload.update({"version": 4}),
            id="obsolete_top_level_field",
        ),
        pytest.param(
            lambda payload: payload["sites"][0].update({"priority": 6}),
            id="obsolete_site_field",
        ),
        pytest.param(
            lambda payload: payload["sites"][0].pop("enabled"),
            id="missing_site_field",
        ),
    ],
)
def test_import_backup_rejects_payloads_the_strict_schema_forbids(
    client,
    admin_headers,
    create_site,
    mutate,
) -> None:
    create_site(valid_site_payload())
    exported = client.get("/api/admin/backups/export", headers=admin_headers)
    assert exported.status_code == 200
    payload = exported.json()
    mutate(payload)

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

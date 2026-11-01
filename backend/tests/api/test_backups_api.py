from __future__ import annotations

import json

from conftest import seed_request_log


def test_backup_restores_archived_overview(client, admin_headers, app_state) -> None:
    seed_request_log(app_state)
    exported = client.get(
        "/api/admin/backups/export?include_logs=true", headers=admin_headers
    )
    assert exported.status_code == 200
    backup = exported.json()
    assert backup["request_logs"][0]["stats_archived"] is True
    assert backup["request_logs"][0]["attribution_archived"] is True
    assert backup["stats"]["request_daily"][0]["request_count"] == 1
    hourly = backup["stats"]["attribution_hourly"]
    assert len(hourly) == 1
    assert hourly[0]["upstream_model"] == "gpt-4o"
    assert hourly[0]["cache_read_input_tokens"] == 1

    cleared = client.delete("/api/admin/request-logs", headers=admin_headers)
    assert cleared.status_code == 204
    restored = client.post(
        "/api/admin/backups/import",
        headers=admin_headers,
        files={"file": ("lens-backup.json", json.dumps(backup), "application/json")},
    )
    assert restored.status_code == 200, restored.text
    reexported = client.get(
        "/api/admin/backups/export?include_logs=true", headers=admin_headers
    )
    assert reexported.status_code == 200
    assert reexported.json()["stats"] == backup["stats"]
    summary = client.get("/api/admin/overview-summary?days=-1", headers=admin_headers)
    assert summary.status_code == 200
    assert summary.json()["request_count"]["value"] == 1

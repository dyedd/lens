from __future__ import annotations

import json

from conftest import run_async, seed_request_log

from app.persistence.entities import RequestLogEntity


def test_backup_restores_archived_overview(client, admin_headers, app_state) -> None:
    codex = seed_request_log(app_state, user_agent="codex-tui/0.1")
    claude = seed_request_log(app_state, user_agent="claude-cli/1.0")

    async def align_log_times():
        async with app_state.session_factory.begin() as session:
            codex_row = await session.get(RequestLogEntity, codex.id)
            claude_row = await session.get(RequestLogEntity, claude.id)
            claude_row.created_at = codex_row.created_at

    run_async(align_log_times())
    exported = client.get(
        "/api/admin/backups/export?include_logs=true", headers=admin_headers
    )
    assert exported.status_code == 200
    backup = exported.json()
    assert backup["request_logs"][0]["stats_archived"] is True
    assert backup["request_logs"][0]["attribution_archived"] is True
    assert backup["stats"]["request_daily"][0]["request_count"] == 2
    hourly = backup["stats"]["attribution_hourly"]
    assert len(hourly) == 2
    assert {row["agent"] for row in hourly} == {"codex", "claude_code"}
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
    assert summary.json()["request_count"]["value"] == 2
    agents = client.get(
        "/api/admin/overview-attribution?days=-1&dimension=agent&metric=requests",
        headers=admin_headers,
    )
    assert agents.status_code == 200, agents.text
    assert {row["key"]: row["requests"] for row in agents.json()["items"]} == {
        "codex": 1,
        "claude_code": 1,
    }

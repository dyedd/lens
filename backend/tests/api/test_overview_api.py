from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from conftest import run_async, seed_request_log, valid_site_payload

from app.persistence.entities import RequestLogEntity


def test_overview_attribution_groups_agents_and_keeps_history(
    client, admin_headers, app_state
):
    seed_request_log(app_state, user_agent="codex-tui/0.1")
    seed_request_log(app_state, user_agent="claude-cli/1.0")
    params = {"days": -1, "dimension": "agent", "metric": "requests"}

    response = client.get(
        "/api/admin/overview-attribution", params=params, headers=admin_headers
    )
    assert response.status_code == 200, response.text
    before = {row["key"]: row for row in response.json()["items"]}
    assert before["codex"]["label"] == "Codex"
    assert before["codex"]["requests"] == 1
    assert before["claude_code"]["label"] == "Claude Code"
    assert before["claude_code"]["requests"] == 1

    assert (
        client.delete("/api/admin/request-logs", headers=admin_headers).status_code
        == 204
    )
    after = client.get(
        "/api/admin/overview-attribution", params=params, headers=admin_headers
    )
    assert after.status_code == 200, after.text
    assert after.json()["items"] == response.json()["items"]


def test_overview_keeps_batched_history_after_time_zone_changes(
    client, admin_headers
) -> None:
    count = 2101
    backup = {
        "exported_at": "2026-01-02T00:00:00",
        "lens_version": "test",
        "settings": [{"key": "time_zone", "value": "UTC"}],
        "include_request_logs": True,
        "request_logs": [
            {
                "protocol": "openai_chat",
                "success": index % 2 == 0,
                "created_at": "2026-01-01T20:00:00",
                "resolved_group_name": "gpt-4o",
                "upstream_model_name": "gpt-4o",
                "input_tokens": 10,
                "output_tokens": 2,
                "total_tokens": 12,
                "total_cost_usd": 0.125,
            }
            for index in range(count)
        ],
    }
    imported = client.post(
        "/api/admin/backups/import",
        headers=admin_headers,
        files={"file": ("history.json", json.dumps(backup), "application/json")},
    )
    assert imported.status_code == 200, imported.text
    before = client.get("/api/admin/overview-summary?days=0", headers=admin_headers)
    assert before.status_code == 200, before.text
    assert before.json()["request_count"]["value"] == count
    assert before.json()["total_tokens"]["value"] == count * 12
    assert before.json()["total_cost_usd"]["value"] == pytest.approx(count * 0.125)

    for time_zone, date in (("Asia/Shanghai", "20260102"), ("UTC", "20260101")):
        saved = client.put(
            "/api/admin/settings",
            headers=admin_headers,
            json={"items": [{"key": "time_zone", "value": time_zone}]},
        )
        assert saved.status_code == 200, saved.text
        daily = client.get("/api/admin/overview-daily?days=0", headers=admin_headers)
        assert daily.status_code == 200, daily.text
        [point] = daily.json()
        assert point["date"] == date
        assert point["request_count"] == count
        assert point["successful_requests"] == 1051
        assert point["failed_requests"] == 1050
        exported = client.get("/api/admin/backups/export", headers=admin_headers)
        assert exported.status_code == 200, exported.text
        assert (
            sum(
                row["request_count"]
                for row in exported.json()["stats"]["attribution_hourly"]
            )
            == count
        )

    cleared = client.delete("/api/admin/request-logs", headers=admin_headers)
    assert cleared.status_code == 204, cleared.text
    after = client.get("/api/admin/overview-summary?days=0", headers=admin_headers)
    assert after.status_code == 200, after.text
    assert after.json() == before.json()


def test_overview_summary_keeps_post_import_activity(client, admin_headers, app_state):
    now = datetime.now(UTC)
    old = (now - timedelta(seconds=1)).isoformat()
    backup = {
        "exported_at": now.isoformat(),
        "lens_version": "test",
        "settings": [{"key": "time_zone", "value": "UTC"}],
        "stats": {
            "imported_total": {"request_success": 5, "input_token": 50},
            "imported_daily": [
                {
                    "date": now.strftime("%Y%m%d"),
                    "request_success": 5,
                    "input_token": 50,
                }
            ],
        },
        "include_request_logs": True,
        "request_logs": [
            {"protocol": "openai_chat", "success": True, "created_at": old}
        ],
    }
    imported = client.post(
        "/api/admin/backups/import",
        headers=admin_headers,
        files={"file": ("history.json", json.dumps(backup), "application/json")},
    )
    assert imported.status_code == 200, imported.text
    seed_request_log(app_state)
    for days in (0, -1):
        summary = client.get(
            "/api/admin/overview-summary", params={"days": days}, headers=admin_headers
        )
        assert summary.status_code == 200, summary.text
        assert summary.json()["request_count"]["value"] == 6
        assert summary.json()["input_tokens"]["value"] == 60


def test_overview_attribution_survives_channel_deletion_and_log_cleanup(
    client, admin_headers, app_state, create_site
):
    site = create_site()
    seed_request_log(app_state)
    seed_request_log(app_state, resolved_group_name="other-model", success=False)
    params = {"days": -1, "dimension": "model", "metric": "cache"}
    response = client.get(
        "/api/admin/overview-attribution", params=params, headers=admin_headers
    )
    assert response.status_code == 200, response.text
    before = response.json()
    assert len(before["items"]) == 2
    assert before["items"][0]["cache_hit_rate"] == 0.1
    assert before["coverage"]["has_dimension_history"] is True
    hourly = client.get(
        "/api/admin/overview-daily?days=-1&granularity=hourly", headers=admin_headers
    )
    assert hourly.status_code == 200, hourly.text
    assert sum(point["request_count"] for point in hourly.json()) == 2
    assert all(len(point["date"]) == 10 for point in hourly.json())
    assert (
        client.delete(
            f"/api/admin/sites/{site['id']}", headers=admin_headers
        ).status_code
        == 204
    )
    assert (
        client.delete("/api/admin/request-logs", headers=admin_headers).status_code
        == 204
    )
    after = client.get(
        "/api/admin/overview-attribution", params=params, headers=admin_headers
    ).json()
    assert after["items"] == before["items"]
    assert after["trend"] == before["trend"]
    channels = client.get(
        "/api/admin/overview-attribution",
        params={**params, "dimension": "channel", "filter_key": "gpt-4o"},
        headers=admin_headers,
    )
    assert channels.status_code == 200, channels.text
    assert channels.json()["items"][0]["is_deleted"] is True
    assert channels.json()["items"][0]["requests"] == 1
    create_site(
        valid_site_payload(
            protocol_config_id="pc-new", base_id="base-new", credential_id="cred-new"
        )
    )
    seed_request_log(app_state, channel_id="pc-new_openai_chat")
    channels = client.get(
        "/api/admin/overview-attribution",
        params={**params, "dimension": "channel"},
        headers=admin_headers,
    ).json()
    assert len(channels["items"]) == 2
    assert {row["is_deleted"] for row in channels["items"]} == {True, False}
    assert sum(row["requests"] for row in channels["items"]) == 3
    hourly_after = client.get(
        "/api/admin/overview-daily?days=-1&granularity=hourly", headers=admin_headers
    )
    assert sum(point["request_count"] for point in hourly_after.json()) == 3


def test_cache_ratio_uses_total_input_and_keeps_unknown_usage(
    client, admin_headers, app_state
):
    first = seed_request_log(app_state)
    second = seed_request_log(app_state)
    unknown = seed_request_log(app_state, resolved_group_name=None)

    async def set_usage():
        async with app_state.session_factory.begin() as session:
            row = await session.get(RequestLogEntity, first.id)
            row.input_tokens, row.cache_read_input_tokens = 100, 80
            row = await session.get(RequestLogEntity, second.id)
            row.input_tokens, row.cache_read_input_tokens = 900, 90
            row = await session.get(RequestLogEntity, unknown.id)
            row.input_tokens, row.cache_read_input_tokens = 0, 0

    run_async(set_usage())
    params = {"days": -1, "dimension": "model", "metric": "cache"}
    response = client.get(
        "/api/admin/overview-attribution", params=params, headers=admin_headers
    )
    assert response.status_code == 200, response.text
    rows = {row["key"]: row for row in response.json()["items"]}
    assert rows["gpt-4o"]["cache_hit_rate"] == 0.17
    assert rows[""]["cache_hit_rate"] is None
    assert any(
        point["key"] == "" and point["value"] is None
        for point in response.json()["trend"]
    )
    assert (
        client.delete("/api/admin/request-logs", headers=admin_headers).status_code
        == 204
    )
    after = client.get(
        "/api/admin/overview-attribution", params=params, headers=admin_headers
    )
    assert after.json()["items"] == response.json()["items"]

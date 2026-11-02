from __future__ import annotations

from datetime import timedelta

from conftest import run_async, seed_request_log

from app.persistence.entities import RequestLogEntity


def test_request_log_page_returns_seeded_logs(client, admin_headers, app_state) -> None:
    logs = {
        "codex": seed_request_log(app_state, user_agent="CoDeX-TuI/0.1"),
        "claude_code": seed_request_log(app_state, user_agent="claude-cli/1.0"),
        "other": seed_request_log(app_state, user_agent="pytest"),
        "unknown": seed_request_log(app_state, user_agent=""),
    }

    response = client.get("/api/admin/request-logs/page", headers=admin_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 4
    assert {row["id"] for row in payload["items"]} == {log.id for log in logs.values()}
    for agent, log in logs.items():
        filtered = client.get(
            "/api/admin/request-logs/page",
            params={"agent": agent},
            headers=admin_headers,
        )
        assert filtered.status_code == 200, filtered.text
        assert filtered.json()["total"] == 1
        assert filtered.json()["items"][0]["id"] == log.id


def test_request_log_page_filters_overview_period_model_channel_and_agent(
    client, admin_headers, app_state
) -> None:
    matching = seed_request_log(app_state, resolved_group_name="model/a", success=False)
    old = seed_request_log(app_state, resolved_group_name="model/a", success=False)
    seed_request_log(app_state, resolved_group_name="model.a", success=False)
    seed_request_log(app_state, resolved_group_name="model/a", success=True)
    seed_request_log(
        app_state, resolved_group_name="model/a", channel_id="other", success=False
    )
    seed_request_log(
        app_state,
        resolved_group_name="model/a",
        user_agent="claude-cli/1.0",
        success=False,
    )

    async def set_old_date():
        async with app_state.session_factory.begin() as session:
            row = await session.get(RequestLogEntity, old.id)
            row.created_at -= timedelta(days=40)

    run_async(set_old_date())
    response = client.get(
        "/api/admin/request-logs/page",
        params={
            "days": -1,
            "status": "failed",
            "upstream_model": "model/a",
            "channel": matching.channel_id,
            "agent": "other",
        },
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["id"] == matching.id
    response = client.get(
        "/api/admin/request-logs/page",
        params={
            "days": 0,
            "status": "failed",
            "upstream_model": "model/a",
            "channel": matching.channel_id,
            "agent": "other",
        },
        headers=admin_headers,
    )
    assert response.json()["total"] == 2


def test_request_log_detail_returns_saved_content(
    client, admin_headers, app_state
) -> None:
    log = seed_request_log(app_state)

    response = client.get(f"/api/admin/request-logs/{log.id}", headers=admin_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == log.id
    assert payload["request_content"] == '{"model":"gpt-4o"}'
    assert payload["response_content"] == '{"ok":true}'


def test_clear_request_logs_removes_saved_logs(
    client, admin_headers, app_state
) -> None:
    seed_request_log(app_state)

    response = client.delete("/api/admin/request-logs", headers=admin_headers)

    assert response.status_code == 204
    page = client.get("/api/admin/request-logs/page", headers=admin_headers)
    assert page.json()["total"] == 0

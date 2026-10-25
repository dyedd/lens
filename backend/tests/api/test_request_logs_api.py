from __future__ import annotations

from conftest import seed_request_log


def test_request_log_page_returns_seeded_logs(client, admin_headers, app_state) -> None:
    log = seed_request_log(app_state)

    response = client.get("/api/admin/request-logs/page", headers=admin_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == log.id


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

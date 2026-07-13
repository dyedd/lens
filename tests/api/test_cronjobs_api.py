from __future__ import annotations

from typing import Any

import pytest

from conftest import assert_error
from lens_api.gateway.cronjob_runner import CronjobAlreadyRunningError


def test_list_cronjobs_requires_admin(client) -> None:
    response = client.get("/api/admin/cronjobs")

    assert_error(response, 401, "Not authenticated")


def test_list_cronjobs_returns_registered_tasks(client, admin_headers) -> None:
    response = client.get("/api/admin/cronjobs", headers=admin_headers)

    assert response.status_code == 200
    task_ids = {item["id"] for item in response.json()}
    assert {
        "request_log_prune",
        "model_price_sync",
        "request_log_stats_persist",
        "version_check",
        "channel_model_sync",
    } <= task_ids


def test_update_cronjob_changes_schedule(client, admin_headers) -> None:
    response = client.put(
        "/api/admin/cronjobs/request_log_prune",
        headers=admin_headers,
        json={
            "enabled": True,
            "schedule_type": "weekly",
            "run_at_time": "03:15",
            "weekdays": [3, 1, 3],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "request_log_prune"
    assert payload["schedule_type"] == "weekly"
    assert payload["run_at_time"] == "03:15"
    assert payload["weekdays"] == [1, 3]


def test_run_cronjob_executes_manual_task(client, admin_headers) -> None:
    response = client.post(
        "/api/admin/cronjobs/request_log_prune/runs",
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["cronjob"]["id"] == "request_log_prune"


@pytest.mark.parametrize(
    ("method", "path", "json"),
    [
        ("put", "/api/admin/cronjobs/missing", {"enabled": False}),
        ("post", "/api/admin/cronjobs/missing/runs", None),
    ],
)
def test_unknown_cronjob_returns_not_found(
    client,
    admin_headers,
    method: str,
    path: str,
    json: dict[str, bool] | None,
) -> None:
    response = client.request(method, path, headers=admin_headers, json=json)

    assert_error(response, 404, "missing")


def test_run_cronjob_reports_already_running(
    client,
    admin_headers,
    app_state,
    monkeypatch,
) -> None:
    async def already_running(_task_id: str) -> Any:
        raise CronjobAlreadyRunningError("request_log_prune")

    monkeypatch.setattr(app_state.cronjob_runner, "run_cronjob_now", already_running)

    response = client.post(
        "/api/admin/cronjobs/request_log_prune/runs",
        headers=admin_headers,
    )

    assert_error(response, 409, "already running")

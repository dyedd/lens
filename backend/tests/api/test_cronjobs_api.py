from __future__ import annotations

from typing import Any

from conftest import assert_error

from app.gateway.cronjob_runner import CronjobAlreadyRunningError


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

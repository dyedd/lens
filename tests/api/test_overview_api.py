from __future__ import annotations

from conftest import seed_request_log
from lens_api.models import RequestLogLifecycleStatus


def test_overview_counts_cancelled_usage_without_treating_it_as_failure(
    client,
    admin_headers,
    app_state,
) -> None:
    seed_request_log(app_state)
    seed_request_log(
        app_state,
        success=False,
        lifecycle_status=RequestLogLifecycleStatus.CANCELLED,
    )

    summary = client.get("/api/admin/overview-summary", headers=admin_headers)
    daily = client.get("/api/admin/overview-daily", headers=admin_headers)
    models = client.get(
        "/api/admin/overview-models",
        headers=admin_headers,
        params={"metric": "tokens"},
    )

    assert summary.status_code == 200
    assert summary.json()["request_count"]["value"] == 2
    assert summary.json()["total_tokens"]["value"] == 60
    assert summary.json()["total_cost_usd"]["value"] == 0.06

    assert daily.status_code == 200
    assert daily.json()[0]["request_count"] == 2
    assert daily.json()[0]["successful_requests"] == 1
    assert daily.json()[0]["failed_requests"] == 0

    assert models.status_code == 200
    assert models.json()["distribution"][0]["model"] == "gpt-4o"
    assert models.json()["distribution"][0]["requests"] == 1
    assert models.json()["distribution"][0]["total_tokens"] == 30

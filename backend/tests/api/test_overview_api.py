from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from conftest import run_async, seed_request_log
from sqlalchemy import update

from app.models.protocols import RequestLogLifecycleStatus
from app.persistence.entities import RequestLogEntity


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


@pytest.mark.parametrize("days", [0, 7])
def test_clearing_logs_preserves_accumulated_statistics(
    client, admin_headers, app_state, days
) -> None:
    for batch in range(2):
        for model in ("model-a", "model-b"):
            seed_request_log(app_state, resolved_group_name=model)
        seed_request_log(
            app_state,
            success=False,
            lifecycle_status=RequestLogLifecycleStatus.CANCELLED,
        )

        async def date_logs() -> None:
            async with app_state.session_factory() as session:
                await session.execute(
                    update(RequestLogEntity).values(
                        created_at=datetime.now(UTC).replace(tzinfo=None)
                        - timedelta(days=1)
                    )
                )
                await session.commit()

        run_async(date_logs())
        cleared = client.delete("/api/admin/request-logs", headers=admin_headers)
        assert cleared.status_code == 204
        summary = client.get(
            "/api/admin/overview-summary", headers=admin_headers, params={"days": days}
        )
        daily = client.get(
            "/api/admin/overview-daily", headers=admin_headers, params={"days": days}
        )
        models = client.get(
            "/api/admin/overview-models", headers=admin_headers, params={"days": days}
        )

        assert summary.status_code == daily.status_code == models.status_code == 200
        batches = batch + 1
        assert summary.json()["request_count"]["value"] == 3 * batches
        assert summary.json()["total_tokens"]["value"] == 90 * batches
        assert summary.json()["total_cost_usd"]["value"] == pytest.approx(
            0.09 * batches
        )
        assert sum(point["request_count"] for point in daily.json()) == 3 * batches
        distribution = {item["model"]: item for item in models.json()["distribution"]}
        assert set(distribution) == {"model-a", "model-b"}
        for item in distribution.values():
            assert item["requests"] == batches
            assert item["total_tokens"] == 30 * batches
            assert item["total_cost_usd"] == pytest.approx(0.03 * batches)

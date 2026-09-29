from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from conftest import run_async, seed_request_log
from sqlalchemy import update

from app.models.protocols import RequestLogLifecycleStatus
from app.persistence.entities import RequestLogEntity
from app.persistence.repositories.request_log import query, statistics
from app.persistence.settings_keys import SETTING_TIME_ZONE


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


@pytest.mark.parametrize(
    "days, age_days", [(0, 1), (7, 1), (0, 0), (-1, 0), (7, 0), (30, 0)]
)
def test_clearing_logs_preserves_accumulated_statistics(
    client, admin_headers, app_state, days, age_days
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
                        - timedelta(days=age_days)
                    )
                )
                await session.commit()

        run_async(date_logs())
        cleared = client.delete("/api/admin/request-logs", headers=admin_headers)
        assert cleared.status_code == 204
        archived = client.post(
            "/api/admin/cronjobs/request_log_stats_persist/runs", headers=admin_headers
        )
        assert archived.status_code == 200
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


@pytest.mark.parametrize("days", [7, 30])
@pytest.mark.parametrize("time_zone", ["UTC", "America/New_York"])
def test_overview_uses_matching_calendar_windows_before_and_after_archiving(
    client, admin_headers, app_state, monkeypatch, days, time_zone
) -> None:
    now = datetime(2026, 3, 8, 18, tzinfo=UTC)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return now.astimezone(tz) if tz else now.replace(tzinfo=None)

    monkeypatch.setattr(query, "datetime", Clock)
    monkeypatch.setattr(statistics, "datetime", Clock)
    configured = client.put(
        "/api/admin/settings",
        headers=admin_headers,
        json={"items": [{"key": SETTING_TIME_ZONE, "value": time_zone}]},
    )
    assert configured.status_code == 200
    end = now.astimezone(ZoneInfo(time_zone)).replace(
        hour=0, minute=0, second=0, microsecond=0
    ) + timedelta(days=1)
    start = end - timedelta(days=days)
    previous_start = start - timedelta(days=days)
    timestamps = (
        previous_start - timedelta(microseconds=1),
        previous_start,
        start - timedelta(microseconds=1),
        start,
        end - timedelta(microseconds=1),
        end,
    )
    dated_logs = [
        (seed_request_log(app_state).id, timestamp) for timestamp in timestamps
    ]

    async def date_logs() -> None:
        async with app_state.session_factory() as session:
            for log_id, timestamp in dated_logs:
                await session.execute(
                    update(RequestLogEntity)
                    .where(RequestLogEntity.id == log_id)
                    .values(created_at=timestamp.astimezone(UTC).replace(tzinfo=None))
                )
            await session.commit()

    run_async(date_logs())
    for archived in (False, True):
        if archived:
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
        assert summary.json()["request_count"] == {"value": 2, "delta": 0}
        assert summary.json()["total_cost_usd"]["value"] == pytest.approx(0.06)
        assert sum(point["request_count"] for point in daily.json()) == 2
        assert models.json()["distribution"][0]["requests"] == 2

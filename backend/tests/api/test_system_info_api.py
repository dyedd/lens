from __future__ import annotations

import httpx


def test_branding_metadata_and_version_check_round_trip(
    client, admin_headers, monkeypatch
) -> None:
    saved = client.put(
        "/api/admin/settings",
        headers=admin_headers,
        json={
            "items": [
                {"key": "site_name", "value": "Gateway audit"},
                {"key": "site_logo_url", "value": "https://example.com/logo.svg"},
                {"key": "time_zone", "value": "Asia/Shanghai"},
            ]
        },
    )
    assert saved.status_code == 200, saved.text
    branding = client.get("/api/public/branding")
    assert branding.status_code == 200
    assert branding.json() == {
        "site_name": "Gateway audit",
        "logo_url": "https://example.com/logo.svg",
    }
    info = client.get("/api/admin/app-info", headers=admin_headers)
    assert info.status_code == 200
    assert info.json()["site_name"] == "Gateway audit"
    assert info.json()["time_zone"] == "Asia/Shanghai"
    assert info.json()["system_version"]

    published_version = "9999.0.0\n"

    async def latest_release(_client, request, **_kwargs):
        assert str(request.url) == "https://dyedd.github.io/lens/version.txt"
        return httpx.Response(
            200,
            request=request,
            text=published_version,
        )

    monkeypatch.setattr(httpx.AsyncClient, "send", latest_release)
    jobs = client.get("/api/admin/cronjobs", headers=admin_headers)
    assert jobs.status_code == 200
    schedule = client.put(
        "/api/admin/cronjobs/version_check",
        headers=admin_headers,
        json={
            "enabled": True,
            "schedule_type": "weekly",
            "run_at_time": "09:30",
            "weekdays": [5, 1, 5],
        },
    )
    assert schedule.status_code == 200, schedule.text
    assert schedule.json()["weekdays"] == [1, 5]
    assert schedule.json()["next_run_at"]
    saved_jobs = client.get("/api/admin/cronjobs", headers=admin_headers)
    saved = next(job for job in saved_jobs.json() if job["id"] == "version_check")
    assert saved["schedule_type"] == "weekly"
    assert saved["run_at_time"] == "09:30"
    assert saved["weekdays"] == [1, 5]
    run = client.post("/api/admin/cronjobs/version_check/runs", headers=admin_headers)
    assert run.status_code == 200, run.text
    result = client.get("/api/admin/version-check", headers=admin_headers)
    assert result.status_code == 200
    assert result.json()["has_update"] is True
    assert result.json()["latest_version"] == "9999.0.0"
    assert (
        result.json()["release_url"]
        == "https://github.com/dyedd/lens/releases/tag/v9999.0.0"
    )
    assert result.json()["checked_at"]

    published_version = info.json()["system_version"]
    run = client.post("/api/admin/cronjobs/version_check/runs", headers=admin_headers)
    assert run.status_code == 200, run.text
    result = client.get("/api/admin/version-check", headers=admin_headers)
    assert result.status_code == 200
    assert result.json()["has_update"] is False
    assert result.json()["latest_version"] == ""
    assert result.json()["release_url"] == ""

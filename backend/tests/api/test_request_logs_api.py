from __future__ import annotations

import json
from datetime import timedelta

import httpx
import pytest
from conftest import gateway_headers, run_async, seed_request_log, valid_site_payload

from app.persistence.entities import RequestLogEntity


@pytest.mark.parametrize("mode", ["model", "channel"])
def test_request_health_summarizes_success_and_failure(
    client, admin_headers, app_state, create_site_group_and_key, mode
) -> None:
    site, group, _ = create_site_group_and_key()
    seed_request_log(app_state, success=True)
    seed_request_log(app_state, success=False)

    response = client.get(
        "/api/admin/model-health",
        headers=admin_headers,
        params={"mode": mode, "hours": 1},
    )
    assert response.status_code == 200, response.text
    name = group["name"] if mode == "model" else site["name"]
    item = next(item for item in response.json()["items"] if item["name"] == name)
    assert item["success_count"] == 1
    assert item["total_count"] == 2
    assert item["tier"] == "major"
    assert sum(bucket["total_count"] for bucket in item["buckets"]) == 2
    assert sum(bucket["success_count"] for bucket in item["buckets"]) == 1


@pytest.mark.parametrize("mode", ["model", "channel"])
@pytest.mark.parametrize("scope", ["key", "model", "channel"])
def test_health_cooldown_reset_restores_selected_routes(
    client,
    admin_headers,
    monkeypatch,
    create_site_group_and_key,
    create_site,
    mode,
    scope,
) -> None:
    import app.gateway.service.proxy.proxy_upstream as proxy_upstream

    site, group, key = create_site_group_and_key()
    other_site = create_site(
        valid_site_payload(
            name="Other Site",
            base_id="base-2",
            credential_id="cred-2",
            protocol_config_id="pc-2",
            model_name="other-model",
        )
    )
    settings = client.put(
        "/api/admin/settings",
        headers=admin_headers,
        json={
            "items": [
                {"key": "failover_cooled_wait_seconds", "value": "0"},
                {
                    "key": "cooldown_detection_rules",
                    "value": json.dumps(
                        {
                            "rules": [
                                {
                                    "name": "provider cooldown",
                                    "status_code": 429,
                                    "scope": scope,
                                    "action": "retry_key"
                                    if scope == "key"
                                    else "retry_channel",
                                    "category": "rate_limit",
                                    "cooldown_seconds": 120,
                                }
                            ]
                        }
                    ),
                },
            ]
        },
    )
    assert settings.status_code == 200, settings.text
    is_recovered = False
    upstream_calls = 0

    async def send(_client, upstream, *, stream, body_bytes):
        nonlocal upstream_calls
        upstream_calls += 1
        return httpx.Response(
            200 if is_recovered else 429,
            json=(
                {
                    "choices": [
                        {
                            "message": {"role": "assistant", "content": "ok"},
                            "finish_reason": "stop",
                        }
                    ]
                }
                if is_recovered
                else {"error": {"message": "provider cooldown"}}
            ),
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send)
    for model in (group["name"], "other-model"):
        response = client.post(
            "/v1/chat/completions",
            headers=gateway_headers(key),
            json={"model": model, "messages": [{"role": "user", "content": "hello"}]},
        )
        assert response.status_code == 429, response.text

    response = client.get(
        "/api/admin/model-health", headers=admin_headers, params={"mode": mode}
    )
    assert response.status_code == 200, response.text
    item_id = group["id"] if mode == "model" else site["id"]
    item = next(item for item in response.json()["items"] if item["id"] == item_id)
    assert 0 < item["cooldown_remaining_seconds"] <= 120
    assert item["total_count"] == 1

    reset = client.post(
        f"/api/admin/model-health/{item_id}/reset-cooldown",
        headers=admin_headers,
        params={"mode": mode},
    )
    assert reset.status_code == 204, reset.text
    items = client.get(
        "/api/admin/model-health", headers=admin_headers, params={"mode": mode}
    ).json()["items"]
    restored = next(item for item in items if item["id"] == item_id)
    assert restored["cooldown_remaining_seconds"] == 0
    assert restored["total_count"] == item["total_count"]
    assert restored["buckets"] != []
    other = next(item for item in items if item["id"] != item_id)
    assert other["cooldown_remaining_seconds"] > 0
    if mode == "channel":
        assert other["id"] == other_site["id"]

    is_recovered = True
    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(key),
        json={
            "model": group["name"],
            "messages": [{"role": "user", "content": "hello"}],
        },
    )
    assert response.status_code == 200, response.text
    assert upstream_calls == 3


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

    async def store_gemini_request():
        async with app_state.session_factory.begin() as session:
            row = await session.get(RequestLogEntity, log.id)
            row.request_content = json.dumps(
                {
                    "model": "gemini-test",
                    "generationConfig": {"thinkingConfig": {"thinkingLevel": "HIGH"}},
                    "reasoning_effort": "low",
                }
            )

    run_async(store_gemini_request())
    detail = client.get(f"/api/admin/request-logs/{log.id}", headers=admin_headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["reasoning_effort"] == "high"
    page = client.get("/api/admin/request-logs/page", headers=admin_headers)
    assert page.json()["items"][0]["reasoning_effort"] == "high"


def test_clear_request_logs_removes_saved_logs(
    client, admin_headers, app_state
) -> None:
    seed_request_log(app_state)

    response = client.delete("/api/admin/request-logs", headers=admin_headers)

    assert response.status_code == 204
    page = client.get("/api/admin/request-logs/page", headers=admin_headers)
    assert page.json()["total"] == 0

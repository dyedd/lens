from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from conftest import assert_error, gateway_headers, run_async, seed_request_log
from sqlalchemy import update

from app.models.protocols import ProtocolKind, RequestLogLifecycleStatus
from app.models.request_logs import RequestLogInput
from app.persistence.entities import RequestLogEntity


def test_request_log_page_returns_empty_result(client, admin_headers) -> None:
    response = client.get("/api/admin/request-logs/page", headers=admin_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"] == []
    assert payload["total"] == 0
    assert payload["limit"] == 100
    assert payload["offset"] == 0


def test_request_log_page_returns_seeded_logs_with_filters(
    client,
    admin_headers,
    app_state,
    create_gateway_key,
) -> None:
    gateway_key = create_gateway_key(remark="primary")
    log = seed_request_log(app_state, gateway_key_id=gateway_key["id"])

    response = client.get(
        "/api/admin/request-logs/page",
        headers=admin_headers,
        params={
            "status": "success",
            "protocol": "openai_chat",
            "keyword": "gpt-4o",
            "sort": "tokens",
            "gateway_key_id": gateway_key["id"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == log.id
    assert payload["gateway_keys"][0]["label"] == "primary"
    assert "gpt-4o" in payload["model_names"]


@pytest.mark.parametrize(
    ("seeds", "params", "expected"),
    [
        pytest.param(
            [
                {
                    "protocol": ProtocolKind.OPENAI_IMAGE.value,
                    "requested_group_name": "gpt-image-1",
                    "resolved_group_name": "gpt-image-1",
                    "billing_mode": "non_tokens",
                    "billing_units": 2,
                }
            ],
            {},
            {"billing_mode": "non_tokens", "billing_units": 2},
            id="non_token_billing",
        ),
        pytest.param(
            [
                {
                    "success": False,
                    "lifecycle_status": RequestLogLifecycleStatus.CANCELLED,
                },
                {},
            ],
            {"status": "cancelled"},
            {
                "lifecycle_status": "cancelled",
                "status_code": 200,
                "error_message": None,
            },
            id="cancelled_filter",
        ),
    ],
)
def test_request_log_page_reports_filtered_log_fields(
    client,
    admin_headers,
    app_state,
    seeds,
    params,
    expected,
) -> None:
    for seed in seeds:
        seed_request_log(app_state, **seed)

    response = client.get(
        "/api/admin/request-logs/page",
        headers=admin_headers,
        params=params,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    item = payload["items"][0]
    assert {key: item[key] for key in expected} == expected


def test_request_log_page_filters_failed_logs_with_na_options(
    client,
    admin_headers,
    app_state,
) -> None:
    failed_log = run_async(
        app_state.request_log_store.commands.create_request_log(
            RequestLogInput(
                protocol=ProtocolKind.OPENAI_CHAT.value,
                user_agent="pytest failed client",
                requested_group_name="deepseek-chat",
                resolved_group_name="deepseek-chat",
                upstream_model_name="deepseek-chat",
                channel_id=None,
                channel_name=None,
                gateway_key_id=None,
                status_code=500,
                success=False,
                lifecycle_status=RequestLogLifecycleStatus.FAILED,
                is_stream=False,
                first_token_latency_ms=0,
                latency_ms=80,
                input_tokens=1,
                output_tokens=0,
                total_tokens=1,
                input_cost_usd=0,
                output_cost_usd=0,
                total_cost_usd=0,
                error_message="upstream 500",
            )
        )
    )
    seed_request_log(app_state)

    response = client.get(
        "/api/admin/request-logs/page",
        headers=admin_headers,
        params={
            "status": "failed",
            "channel": "n/a",
            "gateway_key_id": "n/a",
            "model_prefix": "deepseek",
            "keyword": "500",
            "sort": "latency",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == failed_log.id
    assert payload["items"][0]["success"] is False
    assert payload["channels"][0]["id"] == "n/a"
    assert payload["gateway_keys"][0]["id"] == "n/a"


def test_request_log_page_does_not_mix_channel_with_previous_attempt_credential(
    client,
    admin_headers,
    app_state,
) -> None:
    run_async(
        app_state.request_log_store.commands.create_request_log(
            RequestLogInput(
                protocol=ProtocolKind.OPENAI_CHAT.value,
                user_agent="pytest failover client",
                requested_group_name="gpt-4o",
                resolved_group_name="gpt-4o",
                upstream_model_name="gpt-4o",
                channel_id="current-channel",
                channel_name="Current site",
                gateway_key_id=None,
                status_code=None,
                success=False,
                lifecycle_status=RequestLogLifecycleStatus.CONNECTING,
                is_stream=False,
                first_token_latency_ms=0,
                latency_ms=10,
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                input_cost_usd=0,
                output_cost_usd=0,
                total_cost_usd=0,
                attempts=[
                    {
                        "channel_id": "previous-channel",
                        "channel_name": "Previous site",
                        "credential_id": "previous-credential",
                        "credential_name": "l3",
                        "model_name": "gpt-4o",
                        "status_code": 500,
                        "success": False,
                        "duration_ms": 10,
                        "error_message": "failed",
                    }
                ],
            )
        )
    )

    response = client.get("/api/admin/request-logs/page", headers=admin_headers)

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["channel_name"] == "Current site"
    assert item["credential_id"] is None
    assert item["credential_name"] == ""


def test_request_log_detail_returns_body_and_attempts(
    client,
    admin_headers,
    app_state,
) -> None:
    log = seed_request_log(app_state)

    response = client.get(f"/api/admin/request-logs/{log.id}", headers=admin_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == log.id
    assert payload["request_content"] == '{"model":"gpt-4o"}'
    assert payload["response_content"] == '{"ok":true}'
    assert payload["attempts"][0]["success"] is True


def test_request_log_detail_missing_log_returns_not_found(
    client, admin_headers
) -> None:
    response = client.get("/api/admin/request-logs/999", headers=admin_headers)

    assert_error(response, 404, "999")


def test_clear_request_logs_removes_live_logs(client, admin_headers, app_state) -> None:
    seed_request_log(app_state)

    response = client.delete("/api/admin/request-logs", headers=admin_headers)

    assert response.status_code == 204
    page = client.get("/api/admin/request-logs/page", headers=admin_headers)
    assert page.json()["total"] == 0


def test_model_health_attributes_channel_logs_to_their_site(
    client,
    admin_headers,
    app_state,
    create_site,
) -> None:
    site = create_site()
    seed_request_log(app_state, resolved_group_name=None)

    response = client.get(
        "/api/admin/model-health",
        headers=admin_headers,
        params={"mode": "channel", "hours": "24"},
    )

    assert response.status_code == 200
    items = {item["name"]: item for item in response.json()["items"]}
    assert items[site["name"]]["total_count"] == 1
    assert items[site["name"]]["success_count"] == 1
    assert items[site["name"]]["tier"] == "healthy"


@pytest.mark.parametrize("is_stream", [False, True])
@pytest.mark.parametrize("maintenance", ["clear", "prune"])
def test_log_maintenance_preserves_inflight_accounting(
    client,
    admin_headers,
    app_state,
    monkeypatch,
    create_site_group_and_key,
    is_stream,
    maintenance,
) -> None:
    import app.gateway.service.proxy_upstream as proxy_upstream

    _, _, key = create_site_group_and_key()
    priced = client.put(
        "/api/admin/model-prices/gpt-4o",
        headers=admin_headers,
        json={
            "model_key": "gpt-4o",
            "input_price_per_million": 1000000,
            "output_price_per_million": 1000000,
        },
    )
    assert priced.status_code == 200

    async def send_upstream(_client, upstream, *, stream, body_bytes):
        assert stream == is_stream
        if maintenance == "prune":
            async with app_state.session_factory() as session:
                await session.execute(
                    update(RequestLogEntity)
                    .where(RequestLogEntity.gateway_key_id == key["id"])
                    .values(
                        created_at=datetime.now(UTC).replace(tzinfo=None)
                        - timedelta(days=45)
                    )
                )
                await session.commit()
            response = await asyncio.to_thread(
                client.post,
                "/api/admin/cronjobs/request_log_prune/runs",
                headers=admin_headers,
            )
            assert response.status_code == 200
        else:
            response = await asyncio.to_thread(
                client.delete, "/api/admin/request-logs", headers=admin_headers
            )
            assert response.status_code == 204
        if stream:
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=(
                    b'data: {"id":"response","model":"gpt-4o","choices":[{"index":0,"delta":{"role":"assistant","content":"ok"},"finish_reason":null}]}\n\n'
                    b'data: {"id":"response","model":"gpt-4o","choices":[{"index":0,"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":10,"completion_tokens":20,"total_tokens":30}}\n\n'
                    b"data: [DONE]\n\n"
                ),
                request=httpx.Request("POST", upstream.url),
            )
        return httpx.Response(
            200,
            json={
                "id": "response",
                "model": "gpt-4o",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "ok"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30,
                },
            },
            request=httpx.Request("POST", upstream.url),
        )

    monkeypatch.setattr(proxy_upstream, "_send_upstream", send_upstream)
    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers(key),
        json={
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "hello"}],
            "stream": is_stream,
        },
    )

    assert response.status_code == 200
    logs = client.get("/api/admin/request-logs/page", headers=admin_headers)
    keys = client.get("/api/admin/gateway-api-keys", headers=admin_headers)
    assert logs.status_code == keys.status_code == 200
    assert logs.json()["total"] == 1
    log = logs.json()["items"][0]
    assert log["lifecycle_status"] == "succeeded"
    assert log["total_cost_usd"] == 30
    assert (
        next(item["spent_cost_usd"] for item in keys.json() if item["id"] == key["id"])
        == 30
    )

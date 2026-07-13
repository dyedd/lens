from __future__ import annotations

from conftest import assert_error, run_async, seed_request_log
from lens_api.models import ProtocolKind, RequestLogLifecycleStatus


def test_request_log_page_requires_admin(client) -> None:
    response = client.get("/api/admin/request-logs/page")

    assert_error(response, 401, "Not authenticated")


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


def test_request_log_page_filters_failed_logs_with_na_options(
    client,
    admin_headers,
    app_state,
) -> None:
    failed_log = run_async(
        app_state.request_log_store.create_request_log(
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


def test_request_log_detail_returns_body_and_attempts(
    client,
    admin_headers,
    app_state,
) -> None:
    log = seed_request_log(app_state)

    response = client.get(
        f"/api/admin/request-logs/{log.id}", headers=admin_headers
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == log.id
    assert payload["request_content"] == '{"model":"gpt-4o"}'
    assert payload["response_content"] == '{"ok":true}'
    assert payload["attempts"][0]["success"] is True


def test_request_log_detail_missing_log_returns_not_found(client, admin_headers) -> None:
    response = client.get("/api/admin/request-logs/999", headers=admin_headers)

    assert_error(response, 404, "999")


def test_clear_request_logs_removes_live_logs(client, admin_headers, app_state) -> None:
    seed_request_log(app_state)

    response = client.delete("/api/admin/request-logs", headers=admin_headers)

    assert response.status_code == 204
    page = client.get("/api/admin/request-logs/page", headers=admin_headers)
    assert page.json()["total"] == 0

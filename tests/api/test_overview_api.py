from __future__ import annotations

from conftest import assert_error, seed_request_log


def test_overview_endpoints_require_admin(client) -> None:
    response = client.get("/api/admin/overview-summary")

    assert_error(response, 401, "Not authenticated")


def test_overview_summary_is_zero_without_logs(client, admin_headers) -> None:
    response = client.get("/api/admin/overview-summary", headers=admin_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["request_count"]["value"] == 0
    assert payload["total_tokens"]["value"] == 0
    assert payload["total_cost_usd"]["value"] == 0


def test_overview_endpoints_aggregate_request_logs(
    client,
    admin_headers,
    app_state,
) -> None:
    seed_request_log(app_state)

    summary = client.get("/api/admin/overview-summary", headers=admin_headers)
    daily = client.get("/api/admin/overview-daily", headers=admin_headers)
    models = client.get(
        "/api/admin/overview-models",
        headers=admin_headers,
        params={"metric": "tokens"},
    )

    assert summary.status_code == 200
    assert summary.json()["request_count"]["value"] == 1
    assert summary.json()["total_tokens"]["value"] == 30
    assert summary.json()["total_cost_usd"]["value"] == 0.03

    assert daily.status_code == 200
    assert daily.json()[0]["request_count"] == 1
    assert daily.json()[0]["successful_requests"] == 1

    assert models.status_code == 200
    assert models.json()["distribution"][0]["model"] == "gpt-4o"
    assert models.json()["distribution"][0]["total_tokens"] == 30


def test_overview_models_filters_by_gateway_key(
    client,
    admin_headers,
    app_state,
    create_gateway_key,
) -> None:
    first_key = create_gateway_key(remark="first")
    second_key = create_gateway_key(remark="second")
    seed_request_log(
        app_state,
        gateway_key_id=first_key["id"],
        requested_group_name="gpt-4o",
        resolved_group_name="gpt-4o",
    )
    seed_request_log(
        app_state,
        gateway_key_id=second_key["id"],
        requested_group_name="claude-3",
        resolved_group_name="claude-3",
    )

    response = client.get(
        "/api/admin/overview-models",
        headers=admin_headers,
        params={"gateway_key_id": second_key["id"], "metric": "requests"},
    )

    assert response.status_code == 200
    assert response.json()["available_models"] == ["claude-3"]
    assert response.json()["distribution"][0]["requests"] == 1

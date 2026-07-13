from __future__ import annotations

from conftest import assert_error


def test_gateway_api_key_endpoints_require_admin(client) -> None:
    response = client.get("/api/admin/gateway-api-keys")

    assert_error(response, 401, "Not authenticated")


def test_gateway_api_key_crud_round_trip(
    client,
    admin_headers,
    create_gateway_key,
) -> None:
    assert client.get("/api/admin/gateway-api-keys", headers=admin_headers).json() == []

    key = create_gateway_key(
        remark="  primary  ",
        allowed_models=[" gpt-4o ", "", "gpt-4o"],
        max_cost_usd=5,
    )
    assert key["remark"] == "primary"
    assert key["api_key"].startswith("sk-lens-")
    assert key["allowed_models"] == ["gpt-4o"]
    assert key["spent_cost_usd"] == 0

    updated = client.put(
        f"/api/admin/gateway-api-keys/{key['id']}",
        headers=admin_headers,
        json={
            "remark": "disabled",
            "enabled": False,
            "allowed_models": ["gpt-4.1"],
            "max_cost_usd": 10,
            "expires_at": None,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["enabled"] is False
    assert updated.json()["allowed_models"] == ["gpt-4.1"]

    listed = client.get("/api/admin/gateway-api-keys", headers=admin_headers)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [key["id"]]

    deleted = client.delete(
        f"/api/admin/gateway-api-keys/{key['id']}", headers=admin_headers
    )
    assert deleted.status_code == 204
    assert client.get("/api/admin/gateway-api-keys", headers=admin_headers).json() == []


def test_gateway_api_key_update_and_delete_missing_key_return_not_found(
    client,
    admin_headers,
) -> None:
    update = client.put(
        "/api/admin/gateway-api-keys/missing",
        headers=admin_headers,
        json={"remark": "missing"},
    )
    delete = client.delete(
        "/api/admin/gateway-api-keys/missing", headers=admin_headers
    )

    assert_error(update, 404, "missing")
    assert_error(delete, 404, "missing")


def test_gateway_api_key_rejects_invalid_expiration(client, admin_headers) -> None:
    response = client.post(
        "/api/admin/gateway-api-keys",
        headers=admin_headers,
        json={"expires_at": "not-a-date"},
    )

    assert_error(response, 400, "Invalid gateway API key expiration time")


def test_gateway_api_key_normalizes_and_clears_expiration(
    client,
    admin_headers,
    create_gateway_key,
) -> None:
    key = create_gateway_key(expires_at="2030-01-01T08:00:00+08:00")

    assert key["expires_at"] == "2030-01-01T00:00:00+00:00"

    response = client.put(
        f"/api/admin/gateway-api-keys/{key['id']}",
        headers=admin_headers,
        json={
            "remark": "cleared",
            "enabled": True,
            "allowed_models": [],
            "max_cost_usd": 0,
            "expires_at": "",
        },
    )

    assert response.status_code == 200
    assert response.json()["expires_at"] is None

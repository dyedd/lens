from __future__ import annotations


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

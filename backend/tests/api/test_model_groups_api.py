from __future__ import annotations


def test_model_group_crud_round_trip(client, admin_headers, create_model_group) -> None:
    assert client.get("/api/admin/model-groups", headers=admin_headers).json() == []

    group = create_model_group(name="gpt-4o")
    assert group["name"] == "gpt-4o"

    detail = client.get(f"/api/admin/model-groups/{group['id']}", headers=admin_headers)
    assert detail.status_code == 200
    assert detail.json()["id"] == group["id"]

    update = client.put(
        f"/api/admin/model-groups/{group['id']}",
        headers=admin_headers,
        json={"name": "gpt-4.1"},
    )
    assert update.status_code == 200
    assert update.json()["name"] == "gpt-4.1"

    delete = client.delete(
        f"/api/admin/model-groups/{group['id']}", headers=admin_headers
    )
    assert delete.status_code == 204
    assert client.get("/api/admin/model-groups", headers=admin_headers).json() == []

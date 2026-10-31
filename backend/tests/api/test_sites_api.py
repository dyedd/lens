from __future__ import annotations

from conftest import valid_site_payload


def test_site_crud_round_trip(client, admin_headers, create_site) -> None:
    assert client.get("/api/admin/sites", headers=admin_headers).json() == []

    site = create_site(valid_site_payload())
    assert site["name"] == "OpenAI Site"
    assert site["protocols"][0]["models"][0]["model_name"] == "gpt-4o"

    update = client.put(
        f"/api/admin/sites/{site['id']}",
        headers=admin_headers,
        json=valid_site_payload(name="Renamed Site", model_name="gpt-4.1"),
    )
    assert update.status_code == 200
    assert update.json()["name"] == "Renamed Site"

    delete = client.delete(f"/api/admin/sites/{site['id']}", headers=admin_headers)
    assert delete.status_code == 204
    assert client.get("/api/admin/sites", headers=admin_headers).json() == []


def test_site_accepts_long_credential_model_pattern(
    client, admin_headers, create_site
) -> None:
    pattern = "|".join(f"^model-{index}$" for index in range(80))
    payload = valid_site_payload()
    payload["credentials"][0]["model_pattern"] = pattern

    response = client.post("/api/admin/sites", headers=admin_headers, json=payload)

    assert response.status_code == 201, response.text
    assert response.json()["credentials"][0]["model_pattern"] == pattern

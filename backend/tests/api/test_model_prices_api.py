from __future__ import annotations

import httpx


def test_model_price_save_and_restore_round_trip(
    client, admin_headers, create_model_group, monkeypatch
) -> None:
    create_model_group(name="vendor/model")

    async def fetch_prices(_client, url, **_kwargs):
        return httpx.Response(
            200,
            request=httpx.Request("GET", url),
            json={"vendor/model": {"input_cost_per_token": 0.000002}},
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", fetch_prices)
    path = "/api/admin/model-prices/vendor%2Fmodel"
    saved = client.put(path, headers=admin_headers, json={"input_price_per_million": 3})
    assert saved.status_code == 200, saved.text
    assert saved.json()["model_key"] == "vendor/model"
    assert saved.json()["input_price_per_million"] == 3
    assert saved.json()["manual_override"] is True

    restored = client.post(f"{path}/restore-automatic", headers=admin_headers)
    assert restored.status_code == 200, restored.text
    price = next(
        item for item in restored.json()["items"] if item["model_key"] == "vendor/model"
    )
    assert price["input_price_per_million"] == 2
    assert price["manual_override"] is False

    legacy_update = client.put(
        path,
        headers=admin_headers,
        json={"model_key": "vendor/model", "input_price_per_million": 4},
    )
    assert legacy_update.status_code == 200
    conflicting_update = client.put(
        path, headers=admin_headers, json={"model_key": "another-model"}
    )
    assert conflicting_update.status_code == 400

    schema = client.get("/openapi.json").json()
    response_schema = schema["paths"]["/api/admin/model-prices/{model_key}"]["put"][
        "responses"
    ]["422"]["content"]["application/json"]["schema"]
    assert response_schema == {"$ref": "#/components/schemas/ErrorResponse"}

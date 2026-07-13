from __future__ import annotations

from typing import Any

from conftest import assert_error


def test_update_model_price_requires_admin(client) -> None:
    response = client.put("/api/admin/model-prices/gpt-4o", json={"model_key": "x"})

    assert_error(response, 401, "Not authenticated")


def test_update_model_price_requires_existing_model_group(
    client,
    admin_headers,
) -> None:
    response = client.put(
        "/api/admin/model-prices/gpt-4o",
        headers=admin_headers,
        json={"model_key": "ignored", "input_price_per_million": 1},
    )

    assert_error(response, 400, "existing model groups")


def test_update_model_price_upserts_existing_group_price(
    client,
    admin_headers,
    create_model_group,
) -> None:
    create_model_group(name="gpt-4o")

    response = client.put(
        "/api/admin/model-prices/gpt-4o",
        headers=admin_headers,
        json={
            "model_key": "ignored",
            "display_name": "GPT 4o",
            "input_price_per_million": 1.25,
            "output_price_per_million": 5,
            "cache_read_price_per_million": 0.25,
            "cache_write_price_per_million": 0.5,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["model_key"] == "gpt-4o"
    assert payload["display_name"] == "GPT 4o"
    assert payload["protocols"] == ["openai_chat"]
    assert payload["input_price_per_million"] == 1.25


def test_sync_model_prices_runs_sync_task_and_returns_price_list(
    client,
    admin_headers,
    create_model_group,
    monkeypatch,
) -> None:
    create_model_group(name="gpt-4o")
    calls: list[Any] = []

    async def fake_sync(state: Any, *, overwrite_existing: bool) -> None:
        calls.append((state, overwrite_existing))

    import lens_api.gateway.service.admin.model_prices as model_prices

    monkeypatch.setattr(model_prices, "_sync_group_prices", fake_sync)

    response = client.post("/api/admin/model-price-sync-jobs", headers=admin_headers)

    assert response.status_code == 200
    assert calls and calls[0][1] is True
    assert response.json()["items"][0]["model_key"] == "gpt-4o"

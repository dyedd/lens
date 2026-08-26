from __future__ import annotations

from typing import Any

import httpx
from conftest import assert_error, run_async

from lens_api.gateway.service import model_price_tasks
from lens_api.persistence.repositories import model_price_repository


def _litellm_client(payload: object) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "model_prices_and_context_window.json" in str(request.url)
        return httpx.Response(200, json=payload)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


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
    assert payload["protocols"] == []
    assert payload["input_price_per_million"] == 1.25
    assert payload["pricing_mode"] == "tokens"
    assert payload["image_price_per_image"] == 0


def test_sync_model_prices_fetches_source_and_returns_updated_prices(
    client,
    admin_headers,
    create_model_group,
    monkeypatch,
) -> None:
    create_model_group(name="nano-banana-pro")
    create_model_group(name="gpt-4o")
    source_client = _litellm_client(
        {
            "nano-banana-pro": {
                "mode": "image_generation",
                "output_cost_per_image": 0.04,
            },
            "gpt-4o": {
                "mode": "chat",
                "input_cost_per_token": 2.5e-6,
                "output_cost_per_token": 1e-5,
                "input_cost_per_image": 0.04,
            },
        }
    )
    monkeypatch.setattr(
        model_price_tasks.httpx,
        "AsyncClient",
        lambda **_kwargs: source_client,
    )

    response = client.post("/api/admin/model-price-sync-jobs", headers=admin_headers)

    assert response.status_code == 200
    payload = response.json()
    items = {item["model_key"]: item for item in payload["items"]}
    assert items["nano-banana-pro"]["pricing_mode"] == "non_tokens"
    assert items["nano-banana-pro"]["input_price_per_million"] == 0
    assert items["nano-banana-pro"]["image_price_per_image"] == 0.04
    assert items["gpt-4o"]["pricing_mode"] == "tokens"
    assert items["gpt-4o"]["input_price_per_million"] == 2.5
    assert items["gpt-4o"]["image_price_per_image"] == 0
    assert payload["last_synced_at"]


def test_sync_model_prices_rolls_back_when_timestamp_write_fails(
    client,
    app_state,
    admin_headers,
    create_model_group,
    monkeypatch,
) -> None:
    create_model_group(name="gpt-4o")
    initial = client.put(
        "/api/admin/model-prices/gpt-4o",
        headers=admin_headers,
        json={"model_key": "gpt-4o", "input_price_per_million": 1.25},
    )
    assert initial.status_code == 200

    source_client = _litellm_client({"gpt-4o": {"input_cost_per_token": 2.5e-6}})
    monkeypatch.setattr(
        model_price_tasks.httpx,
        "AsyncClient",
        lambda **_kwargs: source_client,
    )

    async def fail_timestamp_write(_session: Any, _value: str) -> None:
        raise RuntimeError("timestamp write failed")

    monkeypatch.setattr(
        model_price_repository,
        "_set_model_price_sync_time",
        fail_timestamp_write,
    )

    response = client.post("/api/admin/model-price-sync-jobs", headers=admin_headers)

    assert response.status_code == 500
    stored = run_async(app_state.model_price_repo.list_model_prices())
    assert stored.items[0].input_price_per_million == 1.25
    assert stored.last_synced_at is None

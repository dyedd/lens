from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
from conftest import assert_error, run_async

from lens_api.gateway.service import model_price_tasks
from lens_api.gateway.service.admin import model_prices
from lens_api.gateway.service.model_price_tasks import ModelPriceSyncError
from lens_api.persistence.repositories import model_price_repository


def _price_sync_state(proxy_url: str) -> SimpleNamespace:
    return SimpleNamespace(
        settings_repo=SimpleNamespace(
            get_runtime_settings=AsyncMock(return_value={"proxy_url": proxy_url})
        ),
        group_repo=SimpleNamespace(list_group_names=AsyncMock(return_value=["gpt-4o"])),
        model_price_repo=SimpleNamespace(
            sync_model_prices=AsyncMock(),
        ),
    )


def _models_dev_client(payload: object) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://models.dev/api.json"
        return httpx.Response(200, json=payload)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


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


def test_sync_model_prices_fetches_source_and_returns_updated_prices(
    client,
    admin_headers,
    create_model_group,
    monkeypatch,
) -> None:
    create_model_group(name="gpt-4o")
    source_client = _models_dev_client(
        {"openai": {"models": {"gpt-4o": {"cost": {"input": 2.5}}}}}
    )
    monkeypatch.setattr(
        model_price_tasks.httpx,
        "AsyncClient",
        lambda **_kwargs: source_client,
    )

    response = client.post("/api/admin/model-price-sync-jobs", headers=admin_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["model_key"] == "gpt-4o"
    assert payload["items"][0]["input_price_per_million"] == 2.5
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

    source_client = _models_dev_client(
        {"openai": {"models": {"gpt-4o": {"cost": {"input": 2.5}}}}}
    )
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


@pytest.mark.parametrize(
    ("proxy_url", "expected_proxy", "expected_trust_env"),
    [
        ("", None, True),
        ("http://proxy.example:8080", "http://proxy.example:8080", False),
    ],
)
def test_sync_group_prices_uses_expected_proxy_policy(
    monkeypatch,
    proxy_url: str,
    expected_proxy: str | None,
    expected_trust_env: bool,
) -> None:
    state = _price_sync_state(proxy_url)
    client_options: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://models.dev/api.json"
        return httpx.Response(
            200,
            json={
                "openai": {"models": {"gpt-4o": {"cost": {"input": 2.5, "output": 10}}}}
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    def create_client(**kwargs: Any) -> httpx.AsyncClient:
        client_options.update(kwargs)
        return client

    monkeypatch.setattr(model_price_tasks.httpx, "AsyncClient", create_client)

    asyncio.run(model_price_tasks._sync_group_prices(state))

    assert client_options["proxy"] == expected_proxy
    assert client_options["trust_env"] is expected_trust_env
    assert client_options["timeout"] == 30
    state.model_price_repo.sync_model_prices.assert_awaited_once()
    assert state.model_price_repo.sync_model_prices.await_args.kwargs["synced_at"]


@pytest.mark.parametrize(
    ("failure", "expected_message"),
    [
        ("status", "Model price source returned HTTP 503"),
        ("transport", "Model price source request failed: ConnectError"),
        ("json", "Model price source returned invalid data"),
        ("shape", "Model price source returned invalid data"),
        ("empty", "Model price source returned invalid data"),
        ("cost", "Model price source returned invalid data"),
    ],
)
def test_sync_group_prices_does_not_write_when_price_source_fails(
    monkeypatch,
    failure: str,
    expected_message: str,
) -> None:
    state = _price_sync_state("")

    def handler(request: httpx.Request) -> httpx.Response:
        if failure == "status":
            return httpx.Response(503, request=request)
        if failure == "transport":
            raise httpx.ConnectError("connection failed", request=request)
        if failure == "json":
            return httpx.Response(200, content=b"not-json", request=request)
        if failure == "shape":
            return httpx.Response(200, json=[], request=request)
        if failure == "empty":
            return httpx.Response(200, json={}, request=request)
        return httpx.Response(
            200,
            json={"openai": {"models": {"gpt-4o": {"cost": {"input": {}}}}}},
            request=request,
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(
        model_price_tasks.httpx,
        "AsyncClient",
        lambda **_kwargs: client,
    )

    with pytest.raises(ModelPriceSyncError, match=expected_message):
        asyncio.run(model_price_tasks._sync_group_prices(state))

    state.model_price_repo.sync_model_prices.assert_not_awaited()


def test_sync_model_prices_returns_bad_gateway_for_source_failure(
    client,
    admin_headers,
    monkeypatch,
) -> None:
    async def failing_sync(_state: Any) -> None:
        raise ModelPriceSyncError("Model price source request failed")

    monkeypatch.setattr(model_prices, "_sync_group_prices", failing_sync)

    response = client.post("/api/admin/model-price-sync-jobs", headers=admin_headers)

    assert_error(response, 502, "Model price source request failed")

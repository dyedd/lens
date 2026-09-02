from __future__ import annotations

from datetime import UTC, datetime

import httpx

from ....core.model_prices import (
    build_group_price_payloads,
    build_litellm_price_index,
)
from ..app_state import AppState


class ModelPriceSyncError(Exception):
    """Raised when the remote model price source cannot be synchronized."""


LITELLM_PRICE_URL = (
    "https://cdn.jsdelivr.net/gh/BerriAI/litellm@main/"
    "model_prices_and_context_window.json"
)


async def _fetch_litellm_price_index(
    proxy_url: str,
) -> dict[str, dict[str, float | str]]:
    try:
        async with httpx.AsyncClient(
            proxy=proxy_url or None,
            timeout=30,
            trust_env=not proxy_url,
            headers={"Accept": "application/json"},
        ) as client:
            response = await client.get(LITELLM_PRICE_URL)
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict):
            raise TypeError("Model price payload must be an object")
        price_index = build_litellm_price_index(payload)
        if not price_index:
            raise ValueError("Model price index is empty")
        return price_index
    except httpx.HTTPStatusError as exc:
        raise ModelPriceSyncError(
            f"Model price source returned HTTP {exc.response.status_code}"
        ) from exc
    except httpx.HTTPError as exc:
        raise ModelPriceSyncError(
            f"Model price source request failed: {type(exc).__name__}"
        ) from exc
    except (TypeError, ValueError) as exc:
        raise ModelPriceSyncError("Model price source returned invalid data") from exc


async def _sync_group_prices(state: AppState) -> None:
    group_names = await state.group_repo.list_group_names(include_routed=True)
    if not group_names:
        await state.model_price_repo.replace_model_prices([])
        return

    runtime = await state.settings_repo.get_runtime_settings()
    proxy_url = str(runtime["proxy_url"]).strip()
    price_index = await _fetch_litellm_price_index(proxy_url)
    payloads = build_group_price_payloads(group_names, price_index)
    await state.model_price_repo.sync_model_prices(
        payloads,
        allowed_keys=group_names,
        synced_at=datetime.now(UTC).isoformat(),
    )

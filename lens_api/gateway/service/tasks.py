from __future__ import annotations

from .runtime_context import (
    AppState,
    UTC,
    build_group_price_payloads,
    build_models_dev_price_index,
    datetime,
)


async def _sync_group_prices(state: AppState, overwrite_existing: bool = False) -> None:
    group_names = await state.domain_store.list_group_names(include_routed=True)
    if not group_names:
        await state.domain_store.replace_model_prices([])
        return

    response = await state.http.get("https://models.dev/api.json")
    response.raise_for_status()
    price_index = build_models_dev_price_index(response.json())
    payloads = build_group_price_payloads(group_names, price_index)
    await state.domain_store.sync_model_prices(
        payloads, overwrite_existing=overwrite_existing, allowed_keys=group_names
    )
    await state.domain_store.set_model_price_sync_time(datetime.now(UTC).isoformat())

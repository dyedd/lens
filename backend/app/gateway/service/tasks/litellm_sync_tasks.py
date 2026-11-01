from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select

from ....core.context_windows import coerce_context_window
from ....core.errors import LensError, ResourceNotFoundError
from ....core.model_prices import (
    build_group_price_payloads,
    build_litellm_price_index,
    canonical_model_price_key,
)
from ....persistence.entities import SiteDiscoveredModelEntity
from ..app_state import AppState

logger = logging.getLogger(__name__)


class ModelPriceSyncError(Exception):
    """Raised when the remote model price source cannot be synchronized."""


LiteLLMSyncError = ModelPriceSyncError

LITELLM_PRICE_URL = (
    "https://cdn.jsdelivr.net/gh/BerriAI/litellm@main/"
    "model_prices_and_context_window.json"
)


async def _fetch_litellm_payload(proxy_url: str) -> dict[str, Any]:
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
            raise TypeError("LiteLLM payload must be an object")
        return payload
    except httpx.HTTPStatusError as exc:
        raise ModelPriceSyncError(
            f"LiteLLM source returned HTTP {exc.response.status_code}"
        ) from exc
    except httpx.HTTPError as exc:
        raise ModelPriceSyncError(
            f"LiteLLM source request failed: {type(exc).__name__}"
        ) from exc
    except (TypeError, ValueError) as exc:
        raise ModelPriceSyncError("LiteLLM source returned invalid data") from exc


def extract_context_windows(payload: Mapping[str, Any]) -> dict[str, int]:
    index: dict[str, int] = {}
    for model_key, entry in payload.items():
        if not isinstance(entry, Mapping):
            continue
        mode = str(entry.get("mode") or "").strip().lower()
        if any(
            kind in mode for kind in ("image", "video", "audio", "embedding", "rerank")
        ):
            continue
        tokens = entry.get("max_input_tokens") or entry.get("max_tokens")
        window = coerce_context_window(tokens)
        name = str(model_key).strip().lower()
        if window is None or not name:
            continue
        index[name] = window

    # Tail aliases: e.g. "openrouter/anthropic/claude-3-5-sonnet" -> "claude-3-5-sonnet"
    aliases: dict[str, int] = {}
    for name, window in index.items():
        if "/" not in name:
            continue
        alias = name.rsplit("/", 1)[-1].strip()
        if alias and alias not in index:
            known = aliases.get(alias)
            aliases[alias] = window if known is None else min(known, window)
    for alias, window in aliases.items():
        index.setdefault(alias, window)
    return index


def find_context_window(windows: Mapping[str, int], model_name: str) -> int | None:
    name = model_name.strip().lower()
    if not name:
        return None
    if name in windows:
        return windows[name]
    if "/" in name:
        tail = name.rsplit("/", 1)[-1].strip()
        return windows.get(tail)
    return None


async def _sync_channel_model_contexts(
    state: AppState,
    catalog_windows: Mapping[str, int],
) -> int:
    if not catalog_windows:
        return 0
    updated_count = 0
    async with state.session_factory() as session:
        result = await session.execute(select(SiteDiscoveredModelEntity))
        for entity in result.scalars():
            window = find_context_window(catalog_windows, entity.model_name)
            if entity.litellm_context_window != window:
                entity.litellm_context_window = window
                updated_count += 1
        if updated_count:
            await session.commit()
    return updated_count


async def sync_litellm_metadata(
    state: AppState, *, restore_key: str | None = None
) -> None:
    runtime = await state.settings_repo.get_runtime_settings()
    proxy_url = str(runtime["proxy_url"]).strip()
    payload = await _fetch_litellm_payload(proxy_url)

    if restore_key is None:
        try:
            catalog_windows = extract_context_windows(payload)
            synced_models = await _sync_channel_model_contexts(state, catalog_windows)
            if synced_models:
                logger.info(
                    "LiteLLM context sync updated %d channel models",
                    synced_models,
                )
        except Exception as exc:
            logger.warning("Failed to sync model context windows from LiteLLM: %s", exc)

    group_names = await state.group_repo.list_group_names(include_routed=True)
    if restore_key is not None:
        restore_key = canonical_model_price_key(restore_key)
        group_names = [
            name
            for name in group_names
            if canonical_model_price_key(name) == restore_key
        ]
        if not group_names:
            raise ResourceNotFoundError(restore_key)
    if not group_names:
        await state.model_price_repo.replace_model_prices([])
        return

    price_index = build_litellm_price_index(payload)
    if not price_index:
        raise ModelPriceSyncError("Model price index is empty")
    payloads = build_group_price_payloads(group_names, price_index)
    if restore_key is not None and not payloads:
        raise LensError(
            "No matching LiteLLM price; manual price remains locked",
            status_code=409,
            error_type="conflict",
        )
    await state.model_price_repo.sync_model_prices(
        payloads,
        allowed_keys=group_names,
        restore_key=restore_key,
        synced_at=datetime.now(UTC).isoformat(),
    )


sync_group_prices = sync_litellm_metadata

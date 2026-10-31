"""Context windows published by a shared model catalog.

Lens already downloads LiteLLM's model price JSON. The same document lists each
model's input window, so a channel model whose upstream list omits the size can
still be sized. The snapshot lives in memory: resolving a window runs on every
group read and must not touch the network.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx

from .context_windows import coerce_context_window

CATALOG_URL = (
    "https://cdn.jsdelivr.net/gh/BerriAI/litellm@main/"
    "model_prices_and_context_window.json"
)

# Catalog entries carry the window under these keys, in priority order.
_CONTEXT_FIELDS = ("max_input_tokens", "max_tokens")


class ModelCatalogError(Exception):
    """Raised when the shared model catalog cannot be loaded."""


class ModelCatalog:
    """In-memory map from model name to the window the catalog publishes."""

    def __init__(self) -> None:
        self._windows: dict[str, int] = {}

    def replace(self, windows: Mapping[str, int]) -> None:
        self._windows = dict(windows)

    def find_context_window(self, model_name: str) -> int | None:
        name = model_name.strip().lower()
        if not name:
            return None
        window = self._windows.get(name)
        if window is not None:
            return window
        alias = _tail_alias(name)
        return self._windows.get(alias) if alias else None


def build_catalog_context_index(payload: Mapping[str, Any]) -> dict[str, int]:
    """Index catalog windows by model key, then by bare model name.

    Provider-prefixed entries such as `openrouter/anthropic/claude-sonnet-4`
    also register their trailing name. The unprefixed entry wins when both
    exist, and the smallest prefixed window wins otherwise: a shared alias has
    to fit every deployment it names.
    """
    index: dict[str, int] = {}
    for model_key, entry in payload.items():
        if not isinstance(entry, Mapping):
            continue
        window = _entry_context_window(entry)
        name = str(model_key).strip().lower()
        if window is None or not name:
            continue
        index[name] = window

    aliases: dict[str, int] = {}
    for name, window in index.items():
        alias = _tail_alias(name)
        if alias is None or alias in index:
            continue
        known = aliases.get(alias)
        aliases[alias] = window if known is None else min(known, window)
    for alias, window in aliases.items():
        index.setdefault(alias, window)
    return index


def _entry_context_window(entry: Mapping[str, Any]) -> int | None:
    for field in _CONTEXT_FIELDS:
        window = coerce_context_window(entry.get(field))
        if window is not None:
            return window
    return None


def _tail_alias(name: str) -> str | None:
    if "/" not in name:
        return None
    return name.rsplit("/", 1)[-1].strip() or None


async def refresh_model_catalog(catalog: ModelCatalog, proxy_url: str) -> None:
    """Replace the catalog snapshot with a freshly fetched one."""
    catalog.replace(await _fetch_catalog_context_index(proxy_url))


async def _fetch_catalog_context_index(proxy_url: str) -> dict[str, int]:
    try:
        async with httpx.AsyncClient(
            proxy=proxy_url or None,
            timeout=30,
            trust_env=not proxy_url,
            headers={"Accept": "application/json"},
        ) as client:
            response = await client.get(CATALOG_URL)
            response.raise_for_status()
            payload: Any = response.json()
    except httpx.HTTPStatusError as exc:
        raise ModelCatalogError(
            f"Model catalog returned HTTP {exc.response.status_code}"
        ) from exc
    except httpx.HTTPError as exc:
        raise ModelCatalogError(
            f"Model catalog request failed: {type(exc).__name__}"
        ) from exc
    except ValueError as exc:
        raise ModelCatalogError("Model catalog returned invalid data") from exc

    if not isinstance(payload, Mapping):
        raise ModelCatalogError("Model catalog payload must be an object")
    windows = build_catalog_context_index(payload)
    if not windows:
        raise ModelCatalogError("Model catalog has no context windows")
    return windows

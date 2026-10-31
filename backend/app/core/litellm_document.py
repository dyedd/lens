"""Shared download helper for LiteLLM's model document."""

from __future__ import annotations

from typing import Any

import httpx

LITELLM_DOCUMENT_URL = (
    "https://cdn.jsdelivr.net/gh/BerriAI/litellm@main/"
    "model_prices_and_context_window.json"
)


class LiteLLMDocumentError(Exception):
    """Raised when the LiteLLM model document cannot be loaded."""


async def fetch_litellm_document(proxy_url: str) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(
            proxy=proxy_url or None,
            timeout=30,
            trust_env=not proxy_url,
            headers={"Accept": "application/json"},
        ) as client:
            response = await client.get(LITELLM_DOCUMENT_URL)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPStatusError as exc:
        raise LiteLLMDocumentError(
            f"LiteLLM document returned HTTP {exc.response.status_code}"
        ) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise LiteLLMDocumentError(
            f"LiteLLM document request failed: {type(exc).__name__}"
        ) from exc
    if not isinstance(payload, dict):
        raise LiteLLMDocumentError("LiteLLM document payload must be an object")
    return payload

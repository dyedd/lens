from typing import Any

PRICE_PAYLOAD_FIELDS = (
    "input_price_per_million",
    "output_price_per_million",
    "cache_read_price_per_million",
    "cache_write_price_per_million",
)


def normalize_model_key(value: str | None) -> str:
    """Normalize a model identifier for price lookup."""
    return (value or "").strip().lower()


def _has_price_value(price_payload: dict[str, float]) -> bool:
    return any(price_payload[field] > 0 for field in PRICE_PAYLOAD_FIELDS)


def build_models_dev_price_index(
    payload: dict[str, Any],
) -> dict[str, dict[str, float]]:
    """Build a normalized model price index from a models.dev payload."""
    index: dict[str, dict[str, float]] = {}
    for provider_id, provider_payload in payload.items():
        if not isinstance(provider_payload, dict):
            continue
        models = provider_payload.get("models")
        if not isinstance(models, dict):
            continue

        normalized_provider_id = normalize_model_key(provider_id)
        for model_id, model_payload in models.items():
            if not isinstance(model_payload, dict):
                continue
            cost_payload = model_payload.get("cost")
            if not isinstance(cost_payload, dict):
                continue

            aliases = {
                normalize_model_key(str(model_id)),
                normalize_model_key(f"{normalized_provider_id}/{model_id}"),
            }
            if "/" in (model_id or ""):
                tail = model_id.rsplit("/", 1)[-1].strip()
                if tail:
                    aliases.add(normalize_model_key(tail))
            price_payload = {
                "input_price_per_million": float(cost_payload.get("input") or 0.0),
                "output_price_per_million": float(cost_payload.get("output") or 0.0),
                "cache_read_price_per_million": float(
                    cost_payload.get("cache_read") or 0.0
                ),
                "cache_write_price_per_million": float(
                    cost_payload.get("cache_write") or 0.0
                ),
            }
            for alias in aliases:
                if not alias:
                    continue
                existing = index.get(alias)
                if existing is None or (
                    not _has_price_value(existing) and _has_price_value(price_payload)
                ):
                    index[alias] = price_payload
    return index


def build_group_price_payloads(
    group_names: list[str], price_index: dict[str, dict[str, float]]
) -> list[dict[str, float | str]]:
    """Build price payloads for model groups present in a price index."""
    payloads: list[dict[str, float | str]] = []
    seen: set[str] = set()

    for raw_name in group_names:
        display_name = raw_name.strip()
        model_key = normalize_model_key(display_name)
        if not model_key or model_key in seen:
            continue
        seen.add(model_key)

        price_payload = price_index.get(model_key)
        if price_payload is None and "/" in model_key:
            price_payload = price_index.get(model_key.split("/", 1)[1])
        if price_payload is None:
            continue

        payloads.append(
            {
                "model_key": model_key,
                "display_name": display_name,
                "input_price_per_million": price_payload["input_price_per_million"],
                "output_price_per_million": price_payload["output_price_per_million"],
                "cache_read_price_per_million": price_payload[
                    "cache_read_price_per_million"
                ],
                "cache_write_price_per_million": price_payload[
                    "cache_write_price_per_million"
                ],
            }
        )

    return payloads

from math import isfinite
from typing import Any

PRICE_PAYLOAD_FIELDS = (
    "input_price_per_million",
    "output_price_per_million",
    "cache_read_price_per_million",
    "cache_write_price_per_million",
    "image_price_per_image",
)


def normalize_model_key(value: str | None) -> str:
    """Normalize a model identifier for price lookup."""
    return (value or "").strip().lower()


def _has_price_value(price_payload: dict[str, Any]) -> bool:
    return any(price_payload.get(field, 0.0) > 0 for field in PRICE_PAYLOAD_FIELDS)


def _pricing_mode(payload: dict[str, Any]) -> str:
    mode = str(payload.get("mode") or "").strip().lower()
    if "image" in mode or "video" in mode:
        return "non_tokens"
    return "tokens"


def _price_value(cost_payload: dict[str, Any], field: str) -> float:
    if field not in cost_payload:
        return 0.0
    value = cost_payload[field]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"Invalid LiteLLM cost field: {field}")
    price = float(value)
    if not isfinite(price) or price < 0:
        raise ValueError(f"Invalid LiteLLM cost field: {field}")
    return price


def _litellm_price(payload: dict[str, Any], field: str) -> float:
    return _price_value(payload, field) * 1_000_000


def build_litellm_price_index(
    payload: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Build Lens prices from LiteLLM's model price JSON."""
    index: dict[str, dict[str, Any]] = {}
    exact_keys = {normalize_model_key(str(model_id)) for model_id in payload}
    for model_id, model_payload in payload.items():
        if not isinstance(model_payload, dict):
            continue
        pricing_mode = _pricing_mode(model_payload)
        if pricing_mode == "non_tokens":
            image_field = (
                "output_cost_per_image"
                if "output_cost_per_image" in model_payload
                else "input_cost_per_image"
            )
            price_payload = {field: 0.0 for field in PRICE_PAYLOAD_FIELDS} | {
                "image_price_per_image": _price_value(model_payload, image_field),
                "pricing_mode": pricing_mode,
            }
        else:
            price_payload = {
                "input_price_per_million": _litellm_price(
                    model_payload, "input_cost_per_token"
                ),
                "output_price_per_million": _litellm_price(
                    model_payload, "output_cost_per_token"
                ),
                "cache_read_price_per_million": _litellm_price(
                    model_payload, "cache_read_input_token_cost"
                ),
                "cache_write_price_per_million": _litellm_price(
                    model_payload, "cache_creation_input_token_cost"
                ),
                "image_price_per_image": 0.0,
                "pricing_mode": pricing_mode,
            }
        if pricing_mode == "tokens" and not _has_price_value(price_payload):
            continue
        aliases = {normalize_model_key(str(model_id))}
        if "/" in str(model_id):
            tail = str(model_id).rsplit("/", 1)[-1].strip()
            normalized_tail = normalize_model_key(tail)
            if normalized_tail and normalized_tail not in exact_keys:
                aliases.add(normalized_tail)
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
    group_names: list[str], price_index: dict[str, dict[str, Any]]
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
                "image_price_per_image": price_payload["image_price_per_image"],
                "pricing_mode": price_payload["pricing_mode"],
            }
        )

    return payloads

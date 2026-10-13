import json
import re
from collections.abc import Iterable, Mapping
from math import isfinite
from typing import Any

PRICE_PAYLOAD_FIELDS = (
    "input_price_per_million",
    "image_input_price_per_million",
    "output_price_per_million",
    "cache_read_price_per_million",
    "cache_write_price_per_million",
    "image_price_per_image",
)
CONTEXT_TIER_PRICE_FIELDS = (
    "input_price_per_million",
    "output_price_per_million",
    "cache_read_price_per_million",
    "cache_write_price_per_million",
)
MAX_CONTEXT_PRICE_TIERS = 8
_LITELLM_CONTEXT_TIER_FIELDS = {
    "input_cost_per_token": "input_price_per_million",
    "output_cost_per_token": "output_price_per_million",
    "cache_read_input_token_cost": "cache_read_price_per_million",
    "cache_creation_input_token_cost": "cache_write_price_per_million",
}
_LITELLM_ABOVE_TOKENS_RE = re.compile(
    r"^(?P<field>input_cost_per_token|output_cost_per_token"
    r"|cache_read_input_token_cost|cache_creation_input_token_cost)"
    r"_above_(?P<thousands>\d+)k_tokens$"
)


def canonical_model_price_key(value: str | None) -> str:
    """Build a stable model identifier for price lookup."""
    return (value or "").strip().lower()


def _has_price_value(price_payload: dict[str, Any]) -> bool:
    return any(price_payload.get(field, 0.0) > 0 for field in PRICE_PAYLOAD_FIELDS)


def _pricing_mode(payload: dict[str, Any]) -> str:
    mode = str(payload.get("mode") or "").strip().lower()
    if "image" in mode or "video" in mode:
        if any(
            field in payload
            for field in (
                "input_cost_per_token",
                "output_cost_per_token",
                "input_cost_per_image_token",
                "output_cost_per_image_token",
            )
        ):
            return "tokens"
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


def _optional_price_per_million(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    price = float(value)
    if not isfinite(price) or price < 0:
        return None
    return price * 1_000_000


def _context_price_tier(tier: Mapping[str, Any]) -> dict[str, float | int]:
    return {
        "above_input_tokens": int(tier["above_input_tokens"]),
        **{field: float(tier.get(field) or 0.0) for field in CONTEXT_TIER_PRICE_FIELDS},
    }


def parse_context_price_tiers(raw: str | None) -> list[dict[str, float | int]]:
    """Parse stored context price tiers ordered by their input-token threshold."""
    if not raw:
        return []
    tiers = json.loads(raw)
    if not isinstance(tiers, list):
        raise ValueError("Context price tiers must be a JSON list")
    return sorted(
        (_context_price_tier(tier) for tier in tiers),
        key=lambda tier: tier["above_input_tokens"],
    )


def dump_context_price_tiers(tiers: Iterable[Mapping[str, Any]]) -> str:
    """Serialize context price tiers for the model price JSON column."""
    return json.dumps(
        sorted(
            (_context_price_tier(tier) for tier in tiers),
            key=lambda tier: tier["above_input_tokens"],
        ),
        separators=(",", ":"),
    )


def find_context_price_tier(
    tiers: Iterable[Mapping[str, Any]], input_tokens: int
) -> Mapping[str, Any] | None:
    """Find the highest tier whose threshold the request input exceeds.

    Providers bill the whole request at the long-context rate once the prompt
    crosses a threshold, so the selected tier replaces the base token prices.
    """
    matched: Mapping[str, Any] | None = None
    for tier in tiers:
        threshold = int(tier["above_input_tokens"])
        if input_tokens > threshold and (
            matched is None or threshold > int(matched["above_input_tokens"])
        ):
            matched = tier
    return matched


def _litellm_tiered_pricing(
    payload: Mapping[str, Any],
) -> list[tuple[int, Mapping[str, Any]]]:
    raw_tiers = payload.get("tiered_pricing")
    if not isinstance(raw_tiers, list):
        return []
    tiers: list[tuple[int, Mapping[str, Any]]] = []
    for tier in raw_tiers:
        if not isinstance(tier, Mapping):
            continue
        bounds = tier.get("range")
        if not isinstance(bounds, list) or not bounds:
            continue
        lower_bound = bounds[0]
        if (
            isinstance(lower_bound, bool)
            or not isinstance(lower_bound, (int, float))
            or not isfinite(lower_bound)
            or lower_bound < 0
        ):
            continue
        tiers.append((int(lower_bound), tier))
    return sorted(tiers, key=lambda item: item[0])


def _with_tiered_base_prices(payload: dict[str, Any]) -> dict[str, Any]:
    """Use the first ``tiered_pricing`` range as base prices when none are set."""
    base_tier = next(
        (tier for lower, tier in _litellm_tiered_pricing(payload) if lower == 0),
        None,
    )
    if base_tier is None:
        return payload
    merged = dict(payload)
    for field in _LITELLM_CONTEXT_TIER_FIELDS:
        if merged.get(field) is None and base_tier.get(field) is not None:
            merged[field] = base_tier[field]
    return merged


def _litellm_context_tiers(
    payload: Mapping[str, Any], base_prices: Mapping[str, Any]
) -> list[dict[str, float | int]]:
    prices_by_threshold: dict[int, dict[str, float]] = {}
    for field, value in payload.items():
        match = _LITELLM_ABOVE_TOKENS_RE.fullmatch(field)
        price = _optional_price_per_million(value)
        if match is None or price is None:
            continue
        threshold = int(match.group("thousands")) * 1000
        price_field = _LITELLM_CONTEXT_TIER_FIELDS[match.group("field")]
        prices_by_threshold.setdefault(threshold, {})[price_field] = price
    for threshold, tier in _litellm_tiered_pricing(payload):
        if threshold <= 0:
            continue
        for source_field, price_field in _LITELLM_CONTEXT_TIER_FIELDS.items():
            price = _optional_price_per_million(tier.get(source_field))
            if price is not None:
                prices_by_threshold.setdefault(threshold, {})[price_field] = price

    tiers: list[dict[str, float | int]] = []
    inherited = {
        field: float(base_prices[field]) for field in CONTEXT_TIER_PRICE_FIELDS
    }
    for threshold in sorted(prices_by_threshold):
        inherited = inherited | prices_by_threshold[threshold]
        tiers.append({"above_input_tokens": threshold, **inherited})
    return tiers[:MAX_CONTEXT_PRICE_TIERS]


def _litellm_price(
    payload: dict[str, Any], field: str, fallback_field: str | None = None
) -> float:
    if (
        field not in payload or payload.get(field) is None
    ) and fallback_field is not None:
        field = fallback_field
    if payload.get(field) is None:
        return 0.0
    return _price_value(payload, field) * 1_000_000


def build_litellm_price_index(
    payload: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Build Lens prices from LiteLLM's model price JSON."""
    index: dict[str, dict[str, Any]] = {}
    exact_keys = {canonical_model_price_key(str(model_id)) for model_id in payload}
    for model_id, model_payload in payload.items():
        if not isinstance(model_payload, dict):
            continue
        model_payload = _with_tiered_base_prices(model_payload)
        pricing_mode = _pricing_mode(model_payload)
        if pricing_mode == "non_tokens":
            image_field = (
                "output_cost_per_image"
                if "output_cost_per_image" in model_payload
                else "input_cost_per_image"
            )
            price_payload = dict.fromkeys(PRICE_PAYLOAD_FIELDS, 0.0) | {
                "image_price_per_image": _price_value(model_payload, image_field),
                "pricing_mode": pricing_mode,
                "context_tiers": [],
            }
        else:
            price_payload = {
                "input_price_per_million": _litellm_price(
                    model_payload,
                    "input_cost_per_token",
                    "input_cost_per_image_token",
                ),
                "image_input_price_per_million": _litellm_price(
                    model_payload, "input_cost_per_image_token", "input_cost_per_token"
                ),
                "output_price_per_million": _litellm_price(
                    model_payload,
                    "output_cost_per_token",
                    "output_cost_per_image_token",
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
            price_payload["context_tiers"] = _litellm_context_tiers(
                model_payload, price_payload
            )
        if not _has_price_value(price_payload):
            if not any(
                key in model_payload and model_payload[key] is not None
                for key in (
                    "input_cost_per_token",
                    "output_cost_per_token",
                    "input_cost_per_image_token",
                    "output_cost_per_image_token",
                    "input_cost_per_image",
                    "output_cost_per_image",
                )
            ):
                continue
            price_payload["pricing_mode"] = "free"
            price_payload["context_tiers"] = []
        aliases = {canonical_model_price_key(str(model_id))}
        if "/" in str(model_id):
            tail = str(model_id).rsplit("/", 1)[-1].strip()
            canonical_tail_key = canonical_model_price_key(tail)
            if canonical_tail_key and canonical_tail_key not in exact_keys:
                aliases.add(canonical_tail_key)
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
) -> list[dict[str, Any]]:
    """Build price payloads for model groups present in a price index."""
    payloads: list[dict[str, Any]] = []
    seen: set[str] = set()

    for raw_name in group_names:
        display_name = raw_name.strip()
        model_key = canonical_model_price_key(display_name)
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
                "image_input_price_per_million": price_payload[
                    "image_input_price_per_million"
                ],
                "output_price_per_million": price_payload["output_price_per_million"],
                "cache_read_price_per_million": price_payload[
                    "cache_read_price_per_million"
                ],
                "cache_write_price_per_million": price_payload[
                    "cache_write_price_per_million"
                ],
                "image_price_per_image": price_payload["image_price_per_image"],
                "pricing_mode": price_payload["pricing_mode"],
                "context_tiers": price_payload.get("context_tiers", []),
            }
        )

    return payloads

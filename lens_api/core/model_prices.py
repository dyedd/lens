from __future__ import annotations

from typing import Any


def normalize_model_key(value: str | None) -> str:
    return (value or '').strip().lower()


def build_models_dev_price_index(payload: dict[str, Any]) -> dict[str, dict[str, float]]:
    index: dict[str, dict[str, float]] = {}
    for provider_id, provider_payload in payload.items():
        if not isinstance(provider_payload, dict):
            continue
        models = provider_payload.get('models')
        if not isinstance(models, dict):
            continue

        normalized_provider_id = normalize_model_key(str(provider_id))
        for model_id, model_payload in models.items():
            if not isinstance(model_payload, dict):
                continue
            cost_payload = model_payload.get('cost')
            if not isinstance(cost_payload, dict):
                continue

            input_price = float(cost_payload.get('input') or 0.0)
            output_price = float(cost_payload.get('output') or 0.0)
            cache_read_price = float(cost_payload.get('cache_read') or 0.0)
            cache_write_price = float(cost_payload.get('cache_write') or 0.0)
            aliases = {
                normalize_model_key(str(model_id)),
                normalize_model_key(f'{normalized_provider_id}/{model_id}'),
            }
            price_payload = {
                'input_price_per_million': input_price,
                'output_price_per_million': output_price,
                'cache_read_price_per_million': cache_read_price,
                'cache_write_price_per_million': cache_write_price,
            }
            for alias in aliases:
                if alias:
                    index[alias] = price_payload
    return index


def build_group_price_payloads(group_names: list[str], price_index: dict[str, dict[str, float]]) -> list[dict[str, float | str]]:
    payloads: list[dict[str, float | str]] = []
    seen: set[str] = set()

    for raw_name in group_names:
        display_name = raw_name.strip()
        model_key = normalize_model_key(display_name)
        if not model_key or model_key in seen:
            continue
        seen.add(model_key)

        price_payload = price_index.get(model_key)
        if price_payload is None and '/' in model_key:
            price_payload = price_index.get(model_key.split('/', 1)[1])
        if price_payload is None:
            continue

        payloads.append(
            {
                'model_key': model_key,
                'display_name': display_name,
                'input_price_per_million': price_payload['input_price_per_million'],
                'output_price_per_million': price_payload['output_price_per_million'],
                'cache_read_price_per_million': price_payload['cache_read_price_per_million'],
                'cache_write_price_per_million': price_payload['cache_write_price_per_million'],
            }
        )

    return payloads

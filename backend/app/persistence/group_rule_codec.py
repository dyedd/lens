"""Single codec for the model-group rule columns shared by repositories and backup."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel

from app.models.upstream_rules import HeaderRule, ParamOverrideRule
from app.persistence.entities import ModelPriceEntity


def dump_rules(
    rules: Iterable[HeaderRule | ParamOverrideRule | dict[str, Any]],
) -> str:
    # Partial updates arrive as plain dicts (payload.model_dump), saves as models.
    return json.dumps(
        [
            rule.model_dump(mode="json") if isinstance(rule, BaseModel) else rule
            for rule in rules
        ],
        ensure_ascii=True,
    )


def dump_fallback_group_ids(fallback_group_ids: list[str]) -> str:
    return json.dumps(fallback_group_ids, ensure_ascii=True)


def parse_param_override(raw: str) -> list[ParamOverrideRule]:
    return [ParamOverrideRule.model_validate(item) for item in json.loads(raw)]


def parse_headers(raw: str) -> list[HeaderRule]:
    return [HeaderRule.model_validate(item) for item in json.loads(raw)]


def parse_fallback_group_ids(raw: str) -> list[str]:
    return json.loads(raw)


def group_price_kwargs(price: ModelPriceEntity | None) -> dict[str, Any]:
    """Price columns defaulted the same way everywhere a group is materialized."""
    return {
        "input_price_per_million": (
            float(price.input_price_per_million) if price is not None else 0.0
        ),
        "output_price_per_million": (
            float(price.output_price_per_million) if price is not None else 0.0
        ),
        "cache_read_price_per_million": (
            float(price.cache_read_price_per_million) if price is not None else 0.0
        ),
        "cache_write_price_per_million": (
            float(price.cache_write_price_per_million) if price is not None else 0.0
        ),
        "image_price_per_image": (
            float(price.image_price_per_image) if price is not None else 0.0
        ),
        "pricing_mode": (price.pricing_mode if price is not None else "tokens"),
    }

"""Single codec for the model-group rule columns shared by repositories and backup."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, TypeAdapter

from app.models.upstream_rules import HeaderRule, ParamOverrideRule
from app.persistence.entities import ModelPriceEntity

from .json_columns import STRING_LIST, load_json_column

_HEADER_RULES = TypeAdapter(list[HeaderRule])
_PARAM_RULES = TypeAdapter(list[ParamOverrideRule])


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
    return load_json_column(raw, _PARAM_RULES, "param_override")


def parse_headers(raw: str) -> list[HeaderRule]:
    return load_json_column(raw, _HEADER_RULES, "headers_json")


def parse_fallback_group_ids(raw: str) -> list[str]:
    return load_json_column(raw, STRING_LIST, "fallback_group_ids_json")


def group_price_kwargs(price: ModelPriceEntity | None) -> dict[str, Any]:
    """Price columns defaulted the same way everywhere a group is materialized."""
    pricing_mode = price.pricing_mode if price is not None else "free"
    if price is not None and not any(
        float(getattr(price, field) or 0.0) > 0
        for field in (
            "input_price_per_million",
            "image_input_price_per_million",
            "output_price_per_million",
            "cache_read_price_per_million",
            "cache_write_price_per_million",
            "image_price_per_image",
        )
    ):
        pricing_mode = "free"
    return {
        "input_price_per_million": (
            float(price.input_price_per_million) if price is not None else 0.0
        ),
        "image_input_price_per_million": (
            float(price.image_input_price_per_million) if price is not None else 0.0
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
        "pricing_mode": pricing_mode,
        "manual_override": bool(price.manual_override) if price is not None else False,
    }

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from .model_name_parser import parse_model_name

_MAX_MULTIMODAL_FALLBACKS = 100


def serialize_multimodal_fallback(value: str) -> str:
    """Validate and serialize the model-to-vision fallback map."""
    raw = value.strip()
    payload: Any = {} if not raw else json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Multimodal fallback must be a JSON object")
    if len(payload) > _MAX_MULTIMODAL_FALLBACKS:
        raise ValueError(
            f"Multimodal fallback must not contain more than {_MAX_MULTIMODAL_FALLBACKS} items"
        )
    result: dict[str, str] = {}
    for raw_key, raw_value in payload.items():
        if not isinstance(raw_key, str) or not isinstance(raw_value, str):
            raise ValueError("Multimodal fallback keys and values must be strings")
        key = raw_key.strip()
        fallback = raw_value.strip()
        if not key or not fallback:
            raise ValueError("Multimodal fallback model names must not be empty")
        base_key = parse_model_name(key).base_model
        base_fallback = parse_model_name(fallback).base_model
        if base_key == base_fallback:
            raise ValueError("A model cannot fall back to itself")
        if base_key in result:
            raise ValueError(f"Duplicate multimodal fallback model: {base_key}")
        result[base_key] = base_fallback
    return json.dumps(result, ensure_ascii=True, separators=(",", ":"))


def parse_multimodal_fallback(value: str | Mapping[str, Any] | None) -> dict[str, str]:
    """Load the validated runtime model-to-vision fallback map."""
    if value is None or value == "":
        return {}
    payload = json.loads(value) if isinstance(value, str) else value
    if not isinstance(payload, Mapping):
        raise ValueError("Multimodal fallback must be a JSON object")
    result: dict[str, str] = {}
    for key, target in payload.items():
        if not isinstance(key, str) or not isinstance(target, str):
            raise ValueError("Multimodal fallback keys and values must be strings")
        result[parse_model_name(key).base_model] = parse_model_name(target).base_model
    return result


__all__ = ["parse_multimodal_fallback", "serialize_multimodal_fallback"]

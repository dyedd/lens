import json


def validate_param_override(value: str) -> str:
    """Validate and normalize a request parameter override JSON object."""
    normalized = value.strip()
    if not normalized:
        return ""
    try:
        override = json.loads(normalized)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid param override JSON: {exc.msg} at line {exc.lineno} "
            f"column {exc.colno}"
        ) from exc
    if not isinstance(override, dict):
        raise ValueError("Param override must be a JSON object")
    if "model" in override:
        raise ValueError("Param override cannot override model")
    return normalized

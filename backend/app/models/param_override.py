import json


def validate_param_override(value: str) -> str:
    """Validate a request parameter override JSON object."""
    trimmed_value = value.strip()
    if not trimmed_value:
        return ""
    try:
        override = json.loads(trimmed_value)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid param override JSON: {exc.msg} at line {exc.lineno} "
            f"column {exc.colno}"
        ) from exc
    if not isinstance(override, dict):
        raise ValueError("Param override must be a JSON object")
    if "model" in override:
        raise ValueError("Param override cannot override model")
    return trimmed_value

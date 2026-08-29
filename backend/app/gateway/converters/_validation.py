from typing import Any


def _required_string(value: Any, message: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        raise ValueError(message)
    return value

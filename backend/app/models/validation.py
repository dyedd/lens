import re

from pydantic import BaseModel, ConfigDict


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _validate_regex_pattern(pattern: str, *, error_label: str = "regex pattern") -> str:
    if not pattern:
        return pattern
    try:
        re.compile(pattern)
    except re.error as exc:
        raise ValueError(f"Invalid {error_label}: {pattern}. {exc}") from exc
    return pattern

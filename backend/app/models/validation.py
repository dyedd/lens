import re
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from ..core.context_windows import MAX_CONTEXT_WINDOW, MIN_CONTEXT_WINDOW


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


ContextWindow = Annotated[int, Field(ge=MIN_CONTEXT_WINDOW, le=MAX_CONTEXT_WINDOW)]


def validate_regex_pattern(pattern: str, *, error_label: str = "regex pattern") -> str:
    if not pattern:
        return pattern
    try:
        re.compile(pattern)
    except re.error as exc:
        raise ValueError(f"Invalid {error_label}: {pattern}. {exc}") from exc
    return pattern

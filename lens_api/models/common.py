from typing import Any
from urllib.parse import urlsplit, urlunsplit
import re

from pydantic import BaseModel, ConfigDict

from enum import Enum
import json
import re
from typing import Any, Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def normalize_base_url(value: Any) -> Any:
    """Normalize a provider base URL by removing supported API suffixes."""
    text = str(value).strip()
    parsed = urlsplit(text)
    path = parsed.path.rstrip("/")
    if path.endswith("/v1beta"):
        path = path[:-7]
    elif path.endswith("/v1"):
        path = path[:-3]
    rebuilt = urlunsplit(
        (parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment)
    )
    before_fragment, fragment_separator, _ = text.partition("#")
    has_empty_query = "?" in before_fragment and parsed.query == ""
    has_empty_fragment = bool(fragment_separator) and parsed.fragment == ""
    if has_empty_query:
        if "#" in rebuilt:
            rebuilt = rebuilt.replace("#", "?#", 1)
        else:
            rebuilt += "?"
    if has_empty_fragment and "#" not in rebuilt:
        rebuilt += "#"
    return rebuilt


def _validate_regex_pattern(
    pattern: str, *, error_label: str = "regex pattern"
) -> str:
    if not pattern:
        return pattern
    try:
        re.compile(pattern)
    except re.error as exc:
        raise ValueError(f"Invalid {error_label}: {pattern}. {exc}") from exc
    return pattern

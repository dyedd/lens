import re

_HEADER_NAME_PATTERN = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")


def validate_header_name(name: str) -> str:
    value = name.strip()
    if not value or not _HEADER_NAME_PATTERN.fullmatch(value):
        raise ValueError("Invalid HTTP header name")
    return value


def validate_header_value(value: str) -> str:
    value = value.strip()
    if any(char in value for char in "\r\n\x00"):
        raise ValueError("HTTP header values must not contain CR, LF, or NUL")
    return value


def canonicalize_header_map(headers: dict[str, str]) -> dict[str, str]:
    canonical_headers: dict[str, str] = {}
    lower_to_key: dict[str, str] = {}
    for raw_key, raw_value in headers.items():
        key = str(raw_key).strip()
        if not key:
            continue
        lower_key = key.lower()
        existing_key = lower_to_key.get(lower_key)
        if existing_key is not None:
            canonical_headers.pop(existing_key, None)
        lower_to_key[lower_key] = key
        canonical_headers[key] = str(raw_value).strip()
    return canonical_headers

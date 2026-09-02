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

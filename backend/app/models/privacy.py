"""Validated rule privacy settings and content-free audit summaries."""

from re import _parser as regex_parser
from re import error as RegexSyntaxError
from typing import Annotated, Literal

import regex
from pydantic import Field, field_validator

from .validation import StrictBaseModel

PrivacyAction = Literal["mask", "warn", "block"]
PrivacyCategory = Literal["secrets", "personal", "custom"]
PrivacyTerm = Annotated[str, Field(min_length=1, max_length=256)]
REGEX_TIMEOUT_SECONDS = 0.025


class PrivacyRegexRule(StrictBaseModel):
    pattern: str = Field(min_length=1, max_length=512)

    @field_validator("pattern")
    @classmethod
    def validate_pattern(cls, pattern: str) -> str:
        try:
            # note (Codex): Width analysis rejects zero-length matches without executing user patterns.
            if regex_parser.parse(pattern, 0).getwidth()[0] == 0:
                raise ValueError("Privacy patterns must consume text")
            compiled = regex.compile(pattern, regex.VERSION1)
            if compiled.search("", timeout=REGEX_TIMEOUT_SECONDS) is not None:
                raise ValueError("Privacy patterns must not match empty text")
        except (RegexSyntaxError, regex.error, TimeoutError) as exc:
            raise ValueError("Invalid privacy pattern") from exc
        return pattern


class PrivacyConfig(StrictBaseModel):
    enabled: bool = False
    categories: list[Literal["secrets", "personal"]] = Field(
        default_factory=lambda: ["secrets", "personal"], max_length=2
    )
    action: PrivacyAction = "mask"
    words: list[PrivacyTerm] = Field(default_factory=list, max_length=100)
    regex_rules: list[PrivacyRegexRule] = Field(default_factory=list, max_length=20)
    exceptions: list[PrivacyTerm] = Field(default_factory=list, max_length=100)

    @field_validator("words", "exceptions")
    @classmethod
    def validate_terms(cls, terms: list[str]) -> list[str]:
        if any(not term.strip() for term in terms):
            raise ValueError("Privacy terms must contain visible text")
        return list(dict.fromkeys(terms))


class PrivacyHit(StrictBaseModel):
    category: PrivacyCategory
    action: PrivacyAction
    count: int = Field(ge=1)
    placeholders: list[
        Annotated[
            str,
            Field(pattern=r"^\[\[LENS_(?:SECRETS|PERSONAL|CUSTOM)_[0-9a-f]{32}\]\]$"),
        ]
    ] = Field(default_factory=list, max_length=4096)


class PrivacyPreviewRequest(StrictBaseModel):
    text: str = Field(max_length=100_000)
    config: PrivacyConfig | None = None


class PrivacyPreviewResponse(StrictBaseModel):
    text: str
    hits: list[PrivacyHit]
    blocked: bool

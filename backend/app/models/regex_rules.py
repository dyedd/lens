from typing import Annotated, Any

from pydantic import AfterValidator, Field, field_validator

from .validation import StrictBaseModel, validate_regex_pattern

MAX_REGEX_RULES = 200
MAX_REGEX_RULE_REFERENCES = 20


def canonicalize_regex_rule_ids(rule_ids: list[str]) -> list[str]:
    """Trim, drop empty entries, and dedupe referenced rule ids in order."""
    canonical_ids = list(
        dict.fromkeys(rule_id.strip() for rule_id in rule_ids if rule_id.strip())
    )
    if len(canonical_ids) > MAX_REGEX_RULE_REFERENCES:
        raise ValueError(
            f"At most {MAX_REGEX_RULE_REFERENCES} regex rules can be referenced"
        )
    return canonical_ids


RegexRuleIds = Annotated[list[str], AfterValidator(canonicalize_regex_rule_ids)]


def _strip_rule_text(value: Any) -> Any:
    return value.strip() if isinstance(value, str) else value


def _strip_rule_pattern(value: Any) -> Any:
    # Matching is always case-insensitive, so a leading ``(?i)`` is redundant.
    if not isinstance(value, str):
        return value
    return value.strip().removeprefix("(?i)").strip()


def _validate_rule_pattern(value: str | None) -> str | None:
    if value is None:
        return None
    return validate_regex_pattern(value, error_label="regex rule pattern")


class RegexRuleCreate(StrictBaseModel):
    name: str = Field(min_length=1, max_length=60)
    pattern: str = Field(min_length=1, max_length=500)
    description: str = Field(default="", max_length=200)

    _strip_text = field_validator("name", "description", mode="before")(
        _strip_rule_text
    )
    _strip_pattern = field_validator("pattern", mode="before")(_strip_rule_pattern)
    _validate_pattern = field_validator("pattern")(_validate_rule_pattern)


class RegexRuleUpdate(StrictBaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    pattern: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=200)

    _strip_text = field_validator("name", "description", mode="before")(
        _strip_rule_text
    )
    _strip_pattern = field_validator("pattern", mode="before")(_strip_rule_pattern)
    _validate_pattern = field_validator("pattern")(_validate_rule_pattern)


class RegexRule(StrictBaseModel):
    """A stored regex rule as written to backups."""

    id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=60)
    pattern: str = Field(min_length=1)
    description: str = ""

    _validate_pattern = field_validator("pattern")(_validate_rule_pattern)


class RegexRuleReferenceView(StrictBaseModel):
    id: str
    name: str


class RegexRuleView(StrictBaseModel):
    id: str
    name: str
    pattern: str
    description: str = ""
    sites: list[RegexRuleReferenceView] = Field(default_factory=list)
    groups: list[RegexRuleReferenceView] = Field(default_factory=list)

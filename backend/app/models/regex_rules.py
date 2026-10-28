from typing import Annotated

from pydantic import AfterValidator

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

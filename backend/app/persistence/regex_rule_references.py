"""Regex rule ids referenced by sites and model groups, stored as JSON lists."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .entities import RegexRuleEntity


def dump_rule_ids(rule_ids: list[str]) -> str:
    return json.dumps(rule_ids, ensure_ascii=True)


def parse_rule_ids(raw: str) -> list[str]:
    return json.loads(raw)


async def validate_rule_ids(session: AsyncSession, rule_ids: Iterable[str]) -> None:
    """Reject references to regex rules that do not exist."""
    requested_ids = list(dict.fromkeys(rule_ids))
    if not requested_ids:
        return
    found_ids = set(
        (
            await session.execute(
                select(RegexRuleEntity.id).where(RegexRuleEntity.id.in_(requested_ids))
            )
        ).scalars()
    )
    missing_id = next(
        (rule_id for rule_id in requested_ids if rule_id not in found_ids), None
    )
    if missing_id is not None:
        raise ValueError(f"Regex rule not found: {missing_id}")


async def load_rule_patterns(
    session: AsyncSession, rule_ids: Iterable[str]
) -> dict[str, re.Pattern[str]]:
    """Compile the referenced rule patterns once; matching ignores case."""
    requested_ids = set(rule_ids)
    if not requested_ids:
        return {}
    rows = await session.execute(
        select(RegexRuleEntity.id, RegexRuleEntity.pattern).where(
            RegexRuleEntity.id.in_(requested_ids)
        )
    )
    patterns: dict[str, re.Pattern[str]] = {}
    for rule_id, pattern in rows.all():
        try:
            patterns[rule_id] = re.compile(pattern, re.IGNORECASE)
        except re.error:
            # Writes validate patterns; a broken stored one must not fail reads.
            continue
    return patterns

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.regex_rules import RegexRule
from app.persistence.entities import RegexRuleEntity


async def load_regex_rules(self, session: AsyncSession) -> list[RegexRule]:
    rows = (
        (await session.execute(select(RegexRuleEntity).order_by(RegexRuleEntity.name)))
        .scalars()
        .all()
    )
    return [
        RegexRule(
            id=row.id,
            name=row.name,
            pattern=row.pattern,
            description=row.description,
        )
        for row in rows
    ]


async def replace_regex_rules(
    self, session: AsyncSession, rules: list[RegexRule]
) -> set[str]:
    await session.execute(delete(RegexRuleEntity))
    rule_ids: set[str] = set()
    folded_names: set[str] = set()
    for rule in rules:
        if rule.id in rule_ids:
            raise ValueError(f"Duplicate regex rule id in backup: {rule.id}")
        if rule.name.casefold() in folded_names:
            raise ValueError(f"Duplicate regex rule name in backup: {rule.name}")
        rule_ids.add(rule.id)
        folded_names.add(rule.name.casefold())
        session.add(
            RegexRuleEntity(
                id=rule.id,
                name=rule.name,
                pattern=rule.pattern,
                description=rule.description,
            )
        )
    return rule_ids


def validate_backup_rule_ids(
    rule_ids: Iterable[str], backup_rule_ids: set[str]
) -> None:
    """Reject references to regex rules missing from the backup."""
    missing_id = next(
        (rule_id for rule_id in rule_ids if rule_id not in backup_rule_ids), None
    )
    if missing_id is not None:
        raise ValueError(f"Regex rule not found in backup: {missing_id}")

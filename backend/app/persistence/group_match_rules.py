"""Model group match rules, evaluated the same way for reconcile and previews."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.entities import ModelGroupEntity
from app.persistence.group_rule_codec import parse_match_models
from app.persistence.regex_rule_references import load_rule_patterns, parse_rule_ids


@dataclass(frozen=True, slots=True)
class GroupMatchRules:
    """A group's match models and compiled regex rules."""

    match_models: frozenset[str]
    patterns: tuple[re.Pattern[str], ...]

    @property
    def is_empty(self) -> bool:
        return not self.match_models and not self.patterns

    def matches(self, model_name: str) -> bool:
        return model_name.casefold() in self.match_models or any(
            pattern.search(model_name) for pattern in self.patterns
        )


def build_group_match_rules(
    match_models: Iterable[str],
    rule_ids: Iterable[str],
    rule_patterns: Mapping[str, re.Pattern[str]],
) -> GroupMatchRules:
    return GroupMatchRules(
        match_models=frozenset(name.casefold() for name in match_models),
        patterns=tuple(
            rule_patterns[rule_id] for rule_id in rule_ids if rule_id in rule_patterns
        ),
    )


def is_auto_joined(group_name: str, rules: GroupMatchRules, model_name: str) -> bool:
    """Return whether reconcile would put this model name back into the group."""
    return rules.matches(model_name) or model_name.casefold() == group_name.casefold()


async def load_match_rules(
    session: AsyncSession, match_models: Iterable[str], rule_ids: Iterable[str]
) -> GroupMatchRules:
    """Compile unsaved match models and library rule ids into match rules."""
    rule_id_list = list(rule_ids)
    return build_group_match_rules(
        match_models, rule_id_list, await load_rule_patterns(session, rule_id_list)
    )


async def load_group_match_rules(
    session: AsyncSession, entities: Iterable[ModelGroupEntity]
) -> dict[str, GroupMatchRules]:
    """Return match rules for each execution group, keyed by group id."""
    execution_groups = [
        entity for entity in entities if not entity.route_group_id.strip()
    ]
    rule_patterns = await load_rule_patterns(
        session,
        (
            rule_id
            for entity in execution_groups
            for rule_id in parse_rule_ids(entity.match_rule_ids_json)
        ),
    )
    return {
        entity.id: build_group_match_rules(
            parse_match_models(entity.match_models_json),
            parse_rule_ids(entity.match_rule_ids_json),
            rule_patterns,
        )
        for entity in execution_groups
    }

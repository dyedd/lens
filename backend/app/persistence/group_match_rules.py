"""Model group match rules, evaluated the same way for reconcile and previews."""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.entities import ModelGroupEntity, RegexRuleEntity
from app.persistence.group_rule_codec import parse_match_models
from app.persistence.regex_rule_references import load_rule_patterns, parse_rule_ids


def default_group_match_pattern(group_name: str) -> str:
    """生成新建模型组默认的名称前缀正则。"""
    escaped_name = re.escape(group_name.strip()).replace(r"\-", "-")
    return f"^{escaped_name}"


async def create_default_group_match_rule(
    session: AsyncSession, group_name: str
) -> RegexRuleEntity:
    """在共享规则库中创建模型组默认的名称前缀规则。"""
    base_name = f"模型组匹配：{group_name.strip()}"
    base_name = base_name[:60]
    existing_names = {
        name.casefold()
        for name in (await session.execute(select(RegexRuleEntity.name))).scalars()
    }
    rule_name = base_name
    suffix = 2
    while rule_name.casefold() in existing_names:
        suffix_text = f" ({suffix})"
        rule_name = f"{base_name[: 60 - len(suffix_text)]}{suffix_text}"
        suffix += 1
    rule = RegexRuleEntity(
        id=str(uuid.uuid4()),
        name=rule_name,
        pattern=default_group_match_pattern(group_name),
        description="模型组创建时生成，可在设置的规则库中修改",
    )
    session.add(rule)
    return rule


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


def is_auto_joined(rules: GroupMatchRules, model_name: str) -> bool:
    """Return whether reconcile would put this model name back into the group."""
    return rules.matches(model_name)


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

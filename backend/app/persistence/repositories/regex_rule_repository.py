from __future__ import annotations

import re
import uuid
from collections import defaultdict
from collections.abc import Iterable, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import ResourceConflictError, ResourceNotFoundError
from app.models.regex_rules import (
    MAX_REGEX_RULES,
    RegexRuleCreate,
    RegexRuleReferenceView,
    RegexRuleUpdate,
    RegexRuleView,
)
from app.persistence.entities import ModelGroupEntity, RegexRuleEntity
from app.persistence.regex_rule_references import (
    dump_rule_ids,
    load_rule_patterns,
    parse_rule_ids,
)

_GROUP_HAS_RULES = ModelGroupEntity.match_rule_ids_json != "[]"


class RegexRuleRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def list_rules(self) -> list[RegexRuleView]:
        """Return every regex rule with its referencing groups and sites."""
        async with self._session_factory() as session:
            rules = (await session.execute(select(RegexRuleEntity))).scalars().all()
            views = await self._build_rule_views(session, rules)
        return sorted(views, key=lambda view: view.name.casefold())

    async def create_rule(self, payload: RegexRuleCreate) -> RegexRuleView:
        """Create a regex rule with a case-insensitively unique name."""
        async with self._session_factory() as session:
            rule_count = await session.scalar(select(func.count(RegexRuleEntity.id)))
            if (rule_count or 0) >= MAX_REGEX_RULES:
                raise ResourceConflictError(
                    f"At most {MAX_REGEX_RULES} regex rules are allowed"
                )
            await self._validate_rule_name(session, payload.name)
            entity = RegexRuleEntity(
                id=str(uuid.uuid4()),
                name=payload.name,
                pattern=payload.pattern,
                description=payload.description,
            )
            session.add(entity)
            await session.commit()
            return (await self._build_rule_views(session, [entity]))[0]

    async def update_rule(
        self, rule_id: str, payload: RegexRuleUpdate
    ) -> RegexRuleView:
        """Update a regex rule; every referencing group and site follows it."""
        async with self._session_factory() as session:
            entity = await session.get(RegexRuleEntity, rule_id)
            if entity is None:
                raise ResourceNotFoundError(rule_id)
            if payload.name is not None:
                await self._validate_rule_name(
                    session, payload.name, exclude_rule_id=rule_id
                )
                entity.name = payload.name
            if payload.pattern is not None:
                entity.pattern = payload.pattern
            if payload.description is not None:
                entity.description = payload.description
            await session.commit()
            return (await self._build_rule_views(session, [entity]))[0]

    async def delete_rule(self, rule_id: str) -> None:
        """Delete a regex rule and every model group reference to it."""
        async with self._session_factory() as session:
            entity = await session.get(RegexRuleEntity, rule_id)
            if entity is None:
                raise ResourceNotFoundError(rule_id)
            groups = await session.execute(
                select(ModelGroupEntity).where(_GROUP_HAS_RULES)
            )
            for group in groups.scalars():
                _drop_rule_reference(group, "match_rule_ids_json", rule_id)
            await session.delete(entity)
            await session.commit()

    async def load_patterns(
        self, rule_ids: Iterable[str]
    ) -> dict[str, re.Pattern[str]]:
        """Return compiled case-insensitive patterns keyed by rule id."""
        async with self._session_factory() as session:
            return await load_rule_patterns(session, rule_ids)

    @staticmethod
    async def _validate_rule_name(
        session: AsyncSession, name: str, *, exclude_rule_id: str | None = None
    ) -> None:
        folded_name = name.casefold()
        rows = await session.execute(select(RegexRuleEntity.id, RegexRuleEntity.name))
        if any(
            rule_id != exclude_rule_id and rule_name.casefold() == folded_name
            for rule_id, rule_name in rows.all()
        ):
            raise ResourceConflictError(f"Regex rule already exists: {name}")

    @staticmethod
    async def _build_rule_views(
        session: AsyncSession, rules: Sequence[RegexRuleEntity]
    ) -> list[RegexRuleView]:
        groups_by_rule: dict[str, list[RegexRuleReferenceView]] = defaultdict(list)
        group_rows = await session.execute(
            select(
                ModelGroupEntity.id,
                ModelGroupEntity.name,
                ModelGroupEntity.match_rule_ids_json,
            )
            .where(_GROUP_HAS_RULES)
            .order_by(ModelGroupEntity.name)
        )
        for group_id, group_name, rule_ids_json in group_rows.all():
            group = RegexRuleReferenceView(id=group_id, name=group_name)
            for rule_id in parse_rule_ids(rule_ids_json):
                groups_by_rule[rule_id].append(group)

        return [
            RegexRuleView(
                id=rule.id,
                name=rule.name,
                pattern=rule.pattern,
                description=rule.description,
                groups=groups_by_rule.get(rule.id, []),
            )
            for rule in rules
        ]


def _drop_rule_reference(entity: object, column: str, rule_id: str) -> None:
    rule_ids = parse_rule_ids(getattr(entity, column))
    if rule_id in rule_ids:
        setattr(
            entity,
            column,
            dump_rule_ids([item for item in rule_ids if item != rule_id]),
        )

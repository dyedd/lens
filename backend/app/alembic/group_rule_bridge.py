"""保留旧迁移删除后又重新添加的模型组规则引用。"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any

import sqlalchemy as sa
from alembic.runtime.migration import MigrationContext, MigrationInfo, MigrationStep
from sqlalchemy.engine import Connection

_DROP_RULES_REVISION = "e7a9b1c3d5f7"
_RESTORE_RULES_REVISION = "f8b0c2d4e6a8"
_SNAPSHOT = sa.Table(
    "_lens_group_rule_snapshot",
    sa.MetaData(),
    sa.Column("group_id", sa.String(80), primary_key=True),
    sa.Column("rule_ids_json", sa.Text(), nullable=False),
)
_GROUPS = sa.table(
    "model_groups",
    sa.column("id", sa.String(80)),
    sa.column("match_rule_ids_json", sa.Text()),
)


def preserve_group_rules(
    steps: Iterable[MigrationStep], connection: Connection
) -> Iterator[MigrationStep]:
    for step in steps:
        info = step.info
        if not info.is_upgrade or info.is_stamp:
            yield step
            continue
        if info.up_revision_id == _DROP_RULES_REVISION:
            _SNAPSHOT.create(connection, checkfirst=True)
            connection.execute(_SNAPSHOT.delete())
            connection.execute(
                _SNAPSHOT.insert().from_select(
                    ["group_id", "rule_ids_json"],
                    sa.select(_GROUPS.c.id, _GROUPS.c.match_rule_ids_json),
                )
            )
        elif info.up_revision_id == _RESTORE_RULES_REVISION and sa.inspect(
            connection
        ).has_table(_SNAPSHOT.name):
            # SQLite 旧事务模式不为 DDL 开启事务；空写入让加列和还原一起回滚。
            connection.execute(_SNAPSHOT.delete().where(sa.false()))
        yield step


def restore_group_rules(
    *, ctx: MigrationContext, step: MigrationInfo, **_: Any
) -> None:
    if (
        not step.is_upgrade
        or step.is_stamp
        or step.up_revision_id != _RESTORE_RULES_REVISION
    ):
        return
    connection = ctx.bind
    if not sa.inspect(connection).has_table(_SNAPSHOT.name):
        return
    connection.execute(
        _GROUPS.update()
        .where(_GROUPS.c.id.in_(sa.select(_SNAPSHOT.c.group_id)))
        .values(
            match_rule_ids_json=sa.select(_SNAPSHOT.c.rule_ids_json)
            .where(_SNAPSHOT.c.group_id == _GROUPS.c.id)
            .scalar_subquery()
        )
    )
    _SNAPSHOT.drop(connection)

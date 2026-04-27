"""rename scheduled task table to cronjobs

Revision ID: a1c9e2f4b6d8
Revises: f4b7c9d2e1a3
Create Date: 2026-04-27 00:00:01.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1c9e2f4b6d8"
down_revision: Union[str, Sequence[str], None] = "f4b7c9d2e1a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX_RENAMES = (
    ("ix_scheduled_tasks_status", "ix_cronjobs_status", "status"),
    ("ix_scheduled_tasks_next_run_at", "ix_cronjobs_next_run_at", "next_run_at"),
    ("ix_scheduled_tasks_lease_owner", "ix_cronjobs_lease_owner", "lease_owner"),
    ("ix_scheduled_tasks_lease_until", "ix_cronjobs_lease_until", "lease_until"),
)


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _index_names(table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _rename_indexes(table_name: str, renames: Sequence[tuple[str, str, str]]) -> None:
    indexes = _index_names(table_name)
    with op.batch_alter_table(table_name) as batch_op:
        for old_name, new_name, column_name in renames:
            if old_name in indexes:
                batch_op.drop_index(old_name)
                indexes.remove(old_name)
            if new_name not in indexes:
                batch_op.create_index(new_name, [column_name], unique=False)
                indexes.add(new_name)


def upgrade() -> None:
    tables = _tables()
    if "scheduled_tasks" in tables and "cronjobs" not in tables:
        op.rename_table("scheduled_tasks", "cronjobs")

    if "cronjobs" in _tables():
        _rename_indexes("cronjobs", INDEX_RENAMES)


def downgrade() -> None:
    reverse = tuple((new_name, old_name, column_name) for old_name, new_name, column_name in INDEX_RENAMES)
    if "cronjobs" in _tables():
        _rename_indexes("cronjobs", reverse)

    tables = _tables()
    if "cronjobs" in tables and "scheduled_tasks" not in tables:
        op.rename_table("cronjobs", "scheduled_tasks")

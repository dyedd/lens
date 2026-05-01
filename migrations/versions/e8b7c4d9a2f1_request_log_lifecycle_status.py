"""request log lifecycle status

Revision ID: e8b7c4d9a2f1
Revises: c2d4e6f8a9b1
Create Date: 2026-04-29 22:30:00.000000

"""
from __future__ import annotations

from typing import Any, Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e8b7c4d9a2f1"
down_revision: Union[str, Sequence[str], None] = "c2d4e6f8a9b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    _recover_request_logs_batch_table()
    columns = _request_logs_columns()
    if "lifecycle_status" not in columns:
        op.add_column(
            "request_logs",
            sa.Column(
                "lifecycle_status",
                sa.String(length=32),
                nullable=True,
            )
        )

    op.execute(
        """
        UPDATE request_logs
        SET lifecycle_status = CASE
            WHEN success = 1 THEN 'succeeded'
            ELSE 'failed'
        END
        WHERE lifecycle_status IS NULL
        """
    )

    sa.inspect(op.get_bind()).clear_cache()

    columns = _request_logs_columns()
    indexes = _request_logs_indexes()
    lifecycle_column = columns.get("lifecycle_status")
    status_code_column = columns.get("status_code")
    if (
        lifecycle_column is not None
        and lifecycle_column.get("nullable") is False
        and status_code_column is not None
        and status_code_column.get("nullable") is True
        and "ix_request_logs_lifecycle_status" in indexes
    ):
        return

    with op.batch_alter_table("request_logs") as batch_op:
        batch_op.alter_column(
            "status_code",
            existing_type=sa.Integer(),
            nullable=True,
        )
        batch_op.alter_column(
            "lifecycle_status",
            existing_type=sa.String(length=32),
            nullable=False,
        )
        if "ix_request_logs_lifecycle_status" not in indexes:
            batch_op.create_index(
                batch_op.f("ix_request_logs_lifecycle_status"),
                ["lifecycle_status"],
                unique=False,
            )


def downgrade() -> None:
    op.execute("UPDATE request_logs SET status_code = 0 WHERE status_code IS NULL")
    _recover_request_logs_batch_table()
    with op.batch_alter_table("request_logs") as batch_op:
        batch_op.drop_index(batch_op.f("ix_request_logs_lifecycle_status"))
        batch_op.alter_column(
            "status_code",
            existing_type=sa.Integer(),
            nullable=False,
        )
        batch_op.drop_column("lifecycle_status")


def _recover_request_logs_batch_table() -> None:
    tables = _table_names()
    has_request_logs = "request_logs" in tables
    has_tmp_request_logs = "_alembic_tmp_request_logs" in tables
    if has_request_logs and has_tmp_request_logs:
        op.drop_table("_alembic_tmp_request_logs")
    elif has_tmp_request_logs:
        op.rename_table("_alembic_tmp_request_logs", "request_logs")


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _request_logs_columns() -> dict[str, dict[str, Any]]:
    return {
        column["name"]: column
        for column in sa.inspect(op.get_bind()).get_columns("request_logs")
    }


def _request_logs_indexes() -> set[str]:
    return {
        index["name"]
        for index in sa.inspect(op.get_bind()).get_indexes("request_logs")
    }

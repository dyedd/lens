"""model group routing

Revision ID: 0006
Revises: 397693802f63
Create Date: 2026-04-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "397693802f63"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    group_columns = {col["name"] for col in inspector.get_columns("model_groups")}
    if "route_group_id" not in group_columns:
        op.add_column(
            "model_groups",
            sa.Column(
                "route_group_id",
                sa.String(length=80),
                nullable=False,
                server_default="",
            ),
        )

    request_log_columns = {col["name"] for col in inspector.get_columns("request_logs")}
    if "requested_group_name" not in request_log_columns:
        op.add_column(
            "request_logs",
            sa.Column("requested_group_name", sa.String(length=120), nullable=True),
        )
    if "resolved_group_name" not in request_log_columns:
        op.add_column(
            "request_logs",
            sa.Column("resolved_group_name", sa.String(length=120), nullable=True),
        )
    if "upstream_model_name" not in request_log_columns:
        op.add_column(
            "request_logs",
            sa.Column("upstream_model_name", sa.String(length=200), nullable=True),
        )

    op.execute(
        """
        UPDATE request_logs
        SET requested_group_name = COALESCE(requested_group_name, matched_group_name, requested_model),
            resolved_group_name = COALESCE(resolved_group_name, matched_group_name, requested_model),
            upstream_model_name = COALESCE(upstream_model_name, resolved_model)
        """
    )

    group_columns = {
        col["name"] for col in sa.inspect(conn).get_columns("model_groups")
    }
    if "use_real_model" in group_columns:
        with op.batch_alter_table("model_groups") as batch_op:
            batch_op.drop_column("use_real_model")
    group_indexes = {
        index["name"] for index in sa.inspect(conn).get_indexes("model_groups")
    }
    if "ix_model_groups_route_group_id" not in group_indexes:
        op.create_index(
            "ix_model_groups_route_group_id",
            "model_groups",
            ["route_group_id"],
        )

    request_log_columns = {
        col["name"] for col in sa.inspect(conn).get_columns("request_logs")
    }
    old_request_log_columns = [
        column_name
        for column_name in ("requested_model", "matched_group_name", "resolved_model")
        if column_name in request_log_columns
    ]
    if old_request_log_columns:
        request_log_indexes = {
            index["name"] for index in sa.inspect(conn).get_indexes("request_logs")
        }
        if (
            "resolved_model" in old_request_log_columns
            and "ix_request_logs_resolved_model" in request_log_indexes
        ):
            op.drop_index(
                "ix_request_logs_resolved_model",
                table_name="request_logs",
            )
        with op.batch_alter_table("request_logs") as batch_op:
            for column_name in old_request_log_columns:
                batch_op.drop_column(column_name)
    request_log_indexes = {
        index["name"] for index in sa.inspect(conn).get_indexes("request_logs")
    }
    if "ix_request_logs_resolved_group_name" not in request_log_indexes:
        op.create_index(
            "ix_request_logs_resolved_group_name",
            "request_logs",
            ["resolved_group_name"],
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    group_columns = {col["name"] for col in inspector.get_columns("model_groups")}
    if "use_real_model" not in group_columns:
        op.add_column(
            "model_groups",
            sa.Column(
                "use_real_model", sa.Integer(), nullable=False, server_default="0"
            ),
        )

    request_log_columns = {col["name"] for col in inspector.get_columns("request_logs")}
    if "requested_model" not in request_log_columns:
        op.add_column(
            "request_logs",
            sa.Column("requested_model", sa.String(length=200), nullable=True),
        )
    if "matched_group_name" not in request_log_columns:
        op.add_column(
            "request_logs",
            sa.Column("matched_group_name", sa.String(length=120), nullable=True),
        )
    if "resolved_model" not in request_log_columns:
        op.add_column(
            "request_logs",
            sa.Column("resolved_model", sa.String(length=200), nullable=True),
        )
    request_log_indexes = {
        index["name"] for index in inspector.get_indexes("request_logs")
    }
    if "ix_request_logs_resolved_group_name" in request_log_indexes:
        op.drop_index(
            "ix_request_logs_resolved_group_name",
            table_name="request_logs",
        )

    op.execute(
        """
        UPDATE request_logs
        SET requested_model = COALESCE(requested_model, requested_group_name),
            matched_group_name = COALESCE(matched_group_name, requested_group_name),
            resolved_model = COALESCE(resolved_model, upstream_model_name)
        """
    )

    group_columns = {
        col["name"] for col in sa.inspect(conn).get_columns("model_groups")
    }
    if "route_group_id" in group_columns:
        group_indexes = {
            index["name"] for index in sa.inspect(conn).get_indexes("model_groups")
        }
        if "ix_model_groups_route_group_id" in group_indexes:
            op.drop_index("ix_model_groups_route_group_id", table_name="model_groups")
        with op.batch_alter_table("model_groups") as batch_op:
            batch_op.drop_column("route_group_id")

    request_log_columns = {
        col["name"] for col in sa.inspect(conn).get_columns("request_logs")
    }
    new_request_log_columns = [
        column_name
        for column_name in (
            "requested_group_name",
            "resolved_group_name",
            "upstream_model_name",
        )
        if column_name in request_log_columns
    ]
    if new_request_log_columns:
        with op.batch_alter_table("request_logs") as batch_op:
            for column_name in new_request_log_columns:
                batch_op.drop_column(column_name)
    request_log_indexes = {
        index["name"] for index in sa.inspect(conn).get_indexes("request_logs")
    }
    if "ix_request_logs_resolved_model" not in request_log_indexes:
        op.create_index(
            "ix_request_logs_resolved_model",
            "request_logs",
            ["resolved_model"],
        )

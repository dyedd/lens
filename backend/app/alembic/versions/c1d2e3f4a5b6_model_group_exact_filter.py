"""允许模型组同步筛选使用等于。"""

from alembic import op

revision = "c1d2e3f4a5b6"
down_revision = "fbc4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("model_groups") as batch:
        batch.drop_constraint("ck_model_groups_sync_filter_mode", type_="check")
        batch.create_check_constraint(
            "ck_model_groups_sync_filter_mode",
            "sync_filter_mode IN ('', 'contains', 'exact', 'regex')",
        )


def downgrade() -> None:
    op.execute(
        "UPDATE model_groups SET sync_filter_mode = 'contains' "
        "WHERE sync_filter_mode = 'exact'"
    )
    with op.batch_alter_table("model_groups") as batch:
        batch.drop_constraint("ck_model_groups_sync_filter_mode", type_="check")
        batch.create_check_constraint(
            "ck_model_groups_sync_filter_mode",
            "sync_filter_mode IN ('', 'contains', 'regex')",
        )

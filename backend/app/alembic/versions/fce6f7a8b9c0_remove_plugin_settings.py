"""Remove settings used by the deleted plugin system."""

import sqlalchemy as sa
from alembic import op

revision = "fce6f7a8b9c0"
down_revision = "e3f5a7b9c1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM cronjobs WHERE id NOT IN ("
            "'request_log_prune', 'model_price_sync', "
            "'request_log_stats_persist', 'version_check', "
            "'channel_model_sync', 'credential_rate_sync'"
            ")"
        )
    )
    op.execute(
        sa.text(
            "UPDATE model_groups SET strategy = 'failover' WHERE strategy LIKE '%/%'"
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM settings WHERE key IN ('plugins_disabled', 'plugins_config')"
        )
    )


def downgrade() -> None:
    pass

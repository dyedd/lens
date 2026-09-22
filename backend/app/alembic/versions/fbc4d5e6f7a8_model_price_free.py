"""将零价模型标记为免费。"""

from alembic import op

revision = "fbc4d5e6f7a8"
down_revision = "fab3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE model_prices SET pricing_mode = 'free' "
        "WHERE input_price_per_million = 0 "
        "AND image_input_price_per_million = 0 "
        "AND output_price_per_million = 0 "
        "AND cache_read_price_per_million = 0 "
        "AND cache_write_price_per_million = 0 "
        "AND image_price_per_image = 0"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE model_prices SET pricing_mode = 'tokens' WHERE pricing_mode = 'free'"
    )
    op.execute(
        "UPDATE request_logs SET billing_mode = 'tokens' WHERE billing_mode = 'free'"
    )

"""address protocols combo refactor

Revision ID: 3e9a1f7c
Revises: d1e2f3a4b5c6
Create Date: 2026-05-27 00:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "3e9a1f7c"
down_revision: Union[str, Sequence[str], None] = "d1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 0: 归一化冲突 combo（同一 site+base_url+credential 多行配置不一致）
    # 以每组 MIN(id) 行的共享配置覆盖同组其余行，与 Step 9 保留 MIN(id) 的逻辑一致，
    # 使后续聚合无歧义、可平滑升级。必须在任何 DDL 之前执行。
    conn = op.get_bind()
    dialect = conn.dialect.name
    if dialect == "sqlite":
        op.execute("""
            UPDATE site_protocol_configs AS t
            SET enabled = c.enabled, headers_json = c.headers_json,
                channel_proxy = c.channel_proxy, param_override = c.param_override,
                match_regex = c.match_regex
            FROM (
                SELECT s.* FROM site_protocol_configs s
                JOIN (SELECT site_id, base_url_id, credential_id, MIN(id) AS cid
                      FROM site_protocol_configs
                      GROUP BY site_id, base_url_id, credential_id) m ON s.id = m.cid
            ) AS c
            WHERE t.site_id = c.site_id AND t.base_url_id = c.base_url_id
              AND t.credential_id = c.credential_id AND t.id <> c.id
        """)
    elif dialect == "postgresql":
        op.execute("""
            UPDATE site_protocol_configs AS t
            SET enabled = c.enabled, headers_json = c.headers_json,
                channel_proxy = c.channel_proxy, param_override = c.param_override,
                match_regex = c.match_regex
            FROM (
                SELECT s.* FROM site_protocol_configs s
                JOIN (SELECT site_id, base_url_id, credential_id, MIN(id) AS cid
                      FROM site_protocol_configs
                      GROUP BY site_id, base_url_id, credential_id) m ON s.id = m.cid
            ) AS c
            WHERE t.site_id = c.site_id AND t.base_url_id = c.base_url_id
              AND t.credential_id = c.credential_id AND t.id <> c.id
        """)
    else:
        raise RuntimeError(f"Unsupported dialect for migration 3e9a1f7c: {dialect}")

    # Step 1: site_base_urls 新增 compatible_protocols_json
    with op.batch_alter_table("site_base_urls") as batch_op:
        batch_op.add_column(
            sa.Column(
                "compatible_protocols_json",
                sa.Text(),
                nullable=False,
                server_default="[]",
            )
        )

    # Step 2: site_discovered_models 新增 protocol（nullable）
    with op.batch_alter_table("site_discovered_models") as batch_op:
        batch_op.add_column(sa.Column("protocol", sa.String(40), nullable=True))

    # Step 3: Back-fill site_base_urls.compatible_protocols_json
    # 跨方言：SQLite 用 json_group_array，PostgreSQL 用 json_agg(...)::text
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        op.execute("""
            UPDATE site_base_urls
            SET compatible_protocols_json = COALESCE(
                (SELECT json_group_array(protocol) FROM (
                    SELECT DISTINCT p.protocol
                    FROM site_protocol_configs p
                    WHERE p.site_id = site_base_urls.site_id
                      AND p.base_url_id = site_base_urls.id
                    ORDER BY p.protocol
                )), '[]'
            )
        """)
    elif dialect == "postgresql":
        op.execute("""
            UPDATE site_base_urls
            SET compatible_protocols_json = COALESCE(
                (SELECT json_agg(sub.protocol ORDER BY sub.protocol)::text FROM (
                    SELECT DISTINCT p.protocol
                    FROM site_protocol_configs p
                    WHERE p.site_id = site_base_urls.site_id
                      AND p.base_url_id = site_base_urls.id
                ) AS sub),
                '[]'
            )
        """)
    else:
        raise RuntimeError(f"Unsupported dialect for migration 3e9a1f7c: {dialect}")

    # Step 4: Back-fill site_discovered_models.protocol
    op.execute("""
        UPDATE site_discovered_models
        SET protocol = (
            SELECT p.protocol FROM site_protocol_configs p
            WHERE p.id = site_discovered_models.protocol_config_id
        )
    """)

    # Step 5: 迁移 model_group_items.channel_id → 复合 ID
    op.execute("""
        UPDATE model_group_items
        SET channel_id = (
            SELECT canon.canonical_id || '_' || p.protocol
            FROM site_protocol_configs p
            JOIN (
                SELECT site_id, base_url_id, credential_id, MIN(id) AS canonical_id
                FROM site_protocol_configs
                GROUP BY site_id, base_url_id, credential_id
            ) AS canon ON canon.site_id = p.site_id
                AND canon.base_url_id = p.base_url_id
                AND canon.credential_id = p.credential_id
            WHERE p.id = model_group_items.channel_id
        )
        WHERE channel_id IN (SELECT id FROM site_protocol_configs)
    """)

    # Step 6: 迁移 request_logs.channel_id → 复合 ID
    op.execute("""
        UPDATE request_logs
        SET channel_id = (
            SELECT canon.canonical_id || '_' || p.protocol
            FROM site_protocol_configs p
            JOIN (
                SELECT site_id, base_url_id, credential_id, MIN(id) AS canonical_id
                FROM site_protocol_configs
                GROUP BY site_id, base_url_id, credential_id
            ) AS canon ON canon.site_id = p.site_id
                AND canon.base_url_id = p.base_url_id
                AND canon.credential_id = p.credential_id
            WHERE p.id = request_logs.channel_id
        )
        WHERE channel_id IN (SELECT id FROM site_protocol_configs)
    """)

    # Step 8: 迁移 site_discovered_models.protocol_config_id → canonical combo_id
    op.execute("""
        UPDATE site_discovered_models
        SET protocol_config_id = (
            SELECT canon.canonical_id
            FROM site_protocol_configs p
            JOIN (
                SELECT site_id, base_url_id, credential_id, MIN(id) AS canonical_id
                FROM site_protocol_configs
                GROUP BY site_id, base_url_id, credential_id
            ) AS canon ON canon.site_id = p.site_id
                AND canon.base_url_id = p.base_url_id
                AND canon.credential_id = p.credential_id
            WHERE p.id = site_discovered_models.protocol_config_id
        )
        WHERE protocol_config_id IN (SELECT id FROM site_protocol_configs)
    """)

    # Step 9: 删除非 canonical combo 行（保留每组 MIN(id) 那行）
    op.execute("""
        DELETE FROM site_protocol_configs
        WHERE id NOT IN (
            SELECT MIN(id) FROM site_protocol_configs
            GROUP BY site_id, base_url_id, credential_id
        )
    """)

    # Step 9.5: 扩展 channel_id 列为 String(160)
    with op.batch_alter_table("model_group_items") as batch_op:
        batch_op.alter_column("channel_id", type_=sa.String(160))
    with op.batch_alter_table("request_logs") as batch_op:
        batch_op.alter_column("channel_id", type_=sa.String(160), nullable=True)

    # Step 10: 删除 site_protocol_configs.protocol 列及其索引
    with op.batch_alter_table("site_protocol_configs") as batch_op:
        batch_op.drop_index("ix_site_protocol_configs_protocol")
        batch_op.drop_column("protocol")


def downgrade() -> None:
    raise NotImplementedError(
        "Downgrade not supported: protocol configs were merged into combos. "
        "Restore from backup to revert."
    )

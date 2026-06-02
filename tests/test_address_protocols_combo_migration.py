from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def _load_migration():
    path = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "3e9a1f7c_address_protocols_combo_refactor.py"
    )
    spec = importlib.util.spec_from_file_location(
        "address_protocols_combo_migration", path
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _run(conn, fn_name: str) -> None:
    migration = _load_migration()
    context = MigrationContext.configure(conn)
    migration.op = Operations(context)
    getattr(migration, fn_name)()


def _create_old_schema(conn) -> None:
    conn.execute(sa.text("""
        CREATE TABLE site_base_urls (
            id VARCHAR(80) PRIMARY KEY,
            site_id VARCHAR(80) NOT NULL,
            url VARCHAR(500) NOT NULL,
            name VARCHAR(120) NOT NULL DEFAULT '',
            enabled INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0
        )
    """))
    conn.execute(sa.text("""
        CREATE TABLE site_protocol_configs (
            id VARCHAR(80) PRIMARY KEY,
            site_id VARCHAR(80) NOT NULL,
            name VARCHAR(120) NOT NULL DEFAULT '',
            protocol VARCHAR(40) NOT NULL,
            credential_id VARCHAR(80) NOT NULL DEFAULT '',
            enabled INTEGER NOT NULL DEFAULT 1,
            headers_json TEXT NOT NULL DEFAULT '{}',
            channel_proxy TEXT NOT NULL DEFAULT '',
            param_override TEXT NOT NULL DEFAULT '',
            match_regex TEXT NOT NULL DEFAULT '',
            base_url_id VARCHAR(80) NOT NULL DEFAULT ''
        )
    """))
    conn.execute(
        sa.text(
            "CREATE INDEX ix_site_protocol_configs_protocol "
            "ON site_protocol_configs (protocol)"
        )
    )
    conn.execute(sa.text("""
        CREATE TABLE site_discovered_models (
            id VARCHAR(80) PRIMARY KEY,
            protocol_config_id VARCHAR(80) NOT NULL,
            credential_id VARCHAR(80) NOT NULL DEFAULT '',
            model_name VARCHAR(200) NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0
        )
    """))
    conn.execute(sa.text("""
        CREATE TABLE model_group_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id VARCHAR(80) NOT NULL
        )
    """))
    conn.execute(sa.text("""
        CREATE TABLE request_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id VARCHAR(80)
        )
    """))


def _seed_two_protocol_combo(conn) -> None:
    conn.execute(sa.text("""
        INSERT INTO site_base_urls (id, site_id, url)
        VALUES ('base-1', 'site-1', 'https://api.example.com')
    """))
    # 同一 base_url + credential 声明两个协议 → 应聚合进 compatible_protocols_json
    conn.execute(sa.text("""
        INSERT INTO site_protocol_configs
            (id, site_id, protocol, credential_id, base_url_id)
        VALUES
            ('combo-chat', 'site-1', 'openai_chat', 'cred-1', 'base-1'),
            ('combo-anthropic', 'site-1', 'anthropic', 'cred-1', 'base-1')
    """))


def test_upgrade_backfills_compatible_protocols_json() -> None:
    """Step 3：同一地址多协议声明聚合进 compatible_protocols_json（SQLite 路径）。"""
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        _create_old_schema(conn)
        _seed_two_protocol_combo(conn)

        _run(conn, "upgrade")

        row = conn.execute(
            sa.text(
                "SELECT compatible_protocols_json FROM site_base_urls "
                "WHERE id = 'base-1'"
            )
        ).scalar_one()
        # json_group_array 按 protocol 排序：anthropic 在前
        assert row == '["anthropic","openai_chat"]'


def test_upgrade_merges_combo_to_canonical_and_drops_protocol_column() -> None:
    """Step 9 + Step 10：非 canonical combo 行被合并删除，protocol 列被移除。"""
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        _create_old_schema(conn)
        _seed_two_protocol_combo(conn)

        _run(conn, "upgrade")

        # 只保留 canonical（MIN(id)）那行
        remaining = conn.execute(
            sa.text("SELECT id FROM site_protocol_configs ORDER BY id")
        ).scalars().all()
        assert remaining == ["combo-anthropic"]

        # protocol 列已删除
        columns = {
            row[1]
            for row in conn.execute(
                sa.text("PRAGMA table_info(site_protocol_configs)")
            ).all()
        }
        assert "protocol" not in columns


def test_upgrade_aborts_on_conflicting_combos() -> None:
    """Step 5：同 base_url+credential 多条配置但参数不同 → 中止迁移。"""
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        _create_old_schema(conn)
        conn.execute(sa.text("""
            INSERT INTO site_base_urls (id, site_id, url)
            VALUES ('base-1', 'site-1', 'https://api.example.com')
        """))
        conn.execute(sa.text("""
            INSERT INTO site_protocol_configs
                (id, site_id, protocol, credential_id, base_url_id, channel_proxy)
            VALUES
                ('c1', 'site-1', 'openai_chat', 'cred-1', 'base-1', 'proxy-a'),
                ('c2', 'site-1', 'anthropic', 'cred-1', 'base-1', 'proxy-b')
        """))

        with pytest.raises(RuntimeError, match="conflicting combo"):
            _run(conn, "upgrade")


def test_downgrade_not_supported() -> None:
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        with pytest.raises(NotImplementedError, match="Downgrade not supported"):
            _run(conn, "downgrade")

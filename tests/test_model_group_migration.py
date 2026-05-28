from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import IntegrityError


def _load_migration():
    path = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "4f6a8c2d9e1b_model_group_protocols_json.py"
    )
    spec = importlib.util.spec_from_file_location(
        "model_group_protocols_migration", path
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
        CREATE TABLE model_groups (
            id VARCHAR(80) PRIMARY KEY,
            name VARCHAR(120) NOT NULL,
            protocol VARCHAR(40) NOT NULL,
            strategy VARCHAR(40) NOT NULL DEFAULT 'round_robin',
            route_group_id VARCHAR(80) NOT NULL DEFAULT '',
            sync_filter_mode VARCHAR(20) NOT NULL DEFAULT '',
            sync_filter_query TEXT NOT NULL DEFAULT ''
        )
    """))
    conn.execute(
        sa.text("CREATE INDEX ix_model_groups_protocol ON model_groups (protocol)")
    )
    conn.execute(sa.text("CREATE INDEX ix_model_groups_name ON model_groups (name)"))


def _create_new_schema(conn) -> None:
    conn.execute(sa.text("""
        CREATE TABLE model_groups (
            id VARCHAR(80) PRIMARY KEY,
            name VARCHAR(120) NOT NULL,
            protocols_json TEXT NOT NULL DEFAULT '[]',
            strategy VARCHAR(40) NOT NULL DEFAULT 'round_robin',
            route_group_id VARCHAR(80) NOT NULL DEFAULT '',
            sync_filter_mode VARCHAR(20) NOT NULL DEFAULT '',
            sync_filter_query TEXT NOT NULL DEFAULT ''
        )
    """))
    conn.execute(
        sa.text("CREATE UNIQUE INDEX ix_model_groups_name ON model_groups (name)")
    )


def test_upgrade_backfills_protocols_json() -> None:
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        _create_old_schema(conn)
        conn.execute(sa.text("""
            INSERT INTO model_groups (id, name, protocol)
            VALUES ('group-1', 'Anthropic', 'anthropic')
        """))

        _run(conn, "upgrade")

        row = conn.execute(
            sa.text("SELECT protocols_json FROM model_groups WHERE id = 'group-1'")
        ).scalar_one()
        assert row == '["anthropic"]'


def test_upgrade_rejects_duplicate_group_names() -> None:
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        _create_old_schema(conn)
        conn.execute(sa.text("""
            INSERT INTO model_groups (id, name, protocol)
            VALUES
                ('group-1', 'Duplicate', 'openai_chat'),
                ('group-2', 'Duplicate', 'anthropic')
        """))

        with pytest.raises(RuntimeError, match="duplicate model group names"):
            _run(conn, "upgrade")


def test_downgrade_restores_first_protocol() -> None:
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        _create_new_schema(conn)
        conn.execute(sa.text("""
            INSERT INTO model_groups (id, name, protocols_json)
            VALUES ('group-1', 'Chat', '["openai_chat", "openai_responses"]')
        """))

        _run(conn, "downgrade")

        row = conn.execute(
            sa.text("SELECT protocol FROM model_groups WHERE id = 'group-1'")
        ).scalar_one()
        assert row == "openai_chat"


def test_upgrade_rebuilds_name_unique_index() -> None:
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        _create_old_schema(conn)
        conn.execute(sa.text("""
            INSERT INTO model_groups (id, name, protocol)
            VALUES ('group-1', 'Chat', 'openai_chat')
        """))

        _run(conn, "upgrade")

        with pytest.raises(IntegrityError):
            conn.execute(sa.text("""
                INSERT INTO model_groups (id, name, protocols_json)
                VALUES ('group-2', 'Chat', '["anthropic"]')
            """))

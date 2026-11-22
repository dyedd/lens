from __future__ import annotations

import argparse
import os
from pathlib import Path

import pytest
from conftest import run_async
from sqlalchemy import delete

import app.cli as cli
from app.gateway.service.app_state import AppState
from app.persistence.entities import AdminUserEntity


def test_main_dispatches_database_upgrade_with_head_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    revisions: list[str] = []

    def capture_upgrade(args: argparse.Namespace) -> None:
        revisions.append(args.revision)

    monkeypatch.setattr(cli, "db_upgrade", capture_upgrade)

    cli.main(["db", "upgrade"])

    assert revisions == ["head"]


def test_main_requires_a_seed_admin_credential(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["seed-admin"])

    assert exit_info.value.code == 2
    assert "one of the arguments --password --generate-password is required" in (
        capsys.readouterr().err
    )


def test_seed_admin_command_saves_a_working_generated_credential(
    app_state: AppState,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    run_async(_delete_existing_admins(app_state))
    password_file = tmp_path / "private" / "initial-admin-password"

    cli.main(
        [
            "seed-admin",
            "--username",
            "first-admin",
            "--generate-password",
            "--password-file",
            str(password_file),
        ]
    )

    saved_password = password_file.read_text(encoding="utf-8").strip()
    output = capsys.readouterr().out
    assert "seeded admin: first-admin" in output
    assert saved_password and saved_password not in output
    admin = run_async(app_state.admin_repo.authenticate("first-admin", saved_password))
    assert admin is not None
    if os.name != "nt":
        assert password_file.stat().st_mode & 0o777 == 0o600


def test_seed_admin_command_rolls_back_when_credential_write_fails(
    app_state: AppState,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_async(_delete_existing_admins(app_state))

    def fail_write(_path: Path, _value: str) -> None:
        raise OSError("credential file write failed")

    monkeypatch.setattr(cli, "_write_private_text", fail_write)

    with pytest.raises(OSError, match="credential file write failed"):
        cli.main(
            [
                "seed-admin",
                "--username",
                "first-admin",
                "--generate-password",
                "--password-file",
                str(tmp_path / "admin-password"),
            ]
        )

    admin = run_async(app_state.admin_repo.find_by_username("first-admin"))
    assert admin is None


async def _delete_existing_admins(state: AppState) -> None:
    async with state.engine.begin() as connection:
        await connection.execute(delete(AdminUserEntity))

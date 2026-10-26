import logging
from pathlib import Path

import pytest

from app.prestart import main
from app.storage.db import connect
from app.storage.migrate import current_version


def make_migrations(folder: Path, migrations: dict[str, str]) -> Path:
    folder.mkdir()
    for name, sql in migrations.items():
        (folder / name).write_text(sql, encoding="utf-8")
    return folder


def error_lines(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [record.getMessage() for record in caplog.records if record.levelno >= logging.ERROR]


def test_ac7_invalid_setting_exits_with_one_log_line(
    clean_env: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    # Given an invalid setting
    clean_env.setenv("RRMC_DATA_DIR", str(tmp_path))
    clean_env.setenv("RRMC_ENGINES", "both")

    # When the start checks run
    exit_code = main(migrations_dir=make_migrations(tmp_path / "migrations", {}))

    # Then they fail with one line naming the setting and its allowed values
    assert exit_code == 1
    assert error_lines(caplog) == ["Invalid setting RRMC_ENGINES: expected real or fake"]


def test_ac10_failing_migration_exits_with_one_log_line(
    clean_env: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    # Given a migration that fails
    clean_env.setenv("RRMC_DATA_DIR", str(tmp_path))
    migrations = make_migrations(
        tmp_path / "migrations", {"0001_broken.sql": "INSERT INTO missing VALUES (1);"}
    )

    # When the start checks run
    exit_code = main(migrations_dir=migrations)

    # Then they fail with one line naming the migration and the database stays at version 0
    assert exit_code == 1
    assert error_lines(caplog) == ["Migration 0001_broken.sql failed: no such table: missing"]
    connection = connect(tmp_path / "db" / "rrmc.db")
    assert current_version(connection) == 0
    connection.close()


def test_ac8_start_creates_and_migrates_database(
    clean_env: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Given no database and one migration
    clean_env.setenv("RRMC_DATA_DIR", str(tmp_path))
    migrations = make_migrations(
        tmp_path / "migrations", {"0001_create_item.sql": "CREATE TABLE item (id INTEGER);"}
    )

    # When the start checks run
    exit_code = main(migrations_dir=migrations)

    # Then the database exists at the newest version
    assert exit_code == 0
    connection = connect(tmp_path / "db" / "rrmc.db")
    assert current_version(connection) == 1
    connection.close()

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.storage.db import connect
from app.storage.migrate import MigrationError, current_version, migrate

CREATE_ITEM = "CREATE TABLE item (id INTEGER PRIMARY KEY);"
# Depends on 0001, so it only succeeds when the migrations run in order.
ADD_ITEM_NAME = "ALTER TABLE item ADD COLUMN name TEXT NOT NULL DEFAULT '';"
CREATE_TABLE_THEN_FAIL = "CREATE TABLE half_done (id INTEGER);\nINSERT INTO missing VALUES (1);"


@pytest.fixture
def connection(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    connection = connect(tmp_path / "test.db")
    yield connection
    connection.close()


def make_migrations(folder: Path, migrations: dict[str, str]) -> Path:
    """Write throwaway migration files named `NNNN_name.sql`."""
    folder.mkdir(exist_ok=True)
    for name, sql in migrations.items():
        (folder / name).write_text(sql, encoding="utf-8")
    return folder


def table_names(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    return {row["name"] for row in rows}


def test_ac8_first_run_applies_all_migrations_in_order(
    connection: sqlite3.Connection, tmp_path: Path
) -> None:
    # Given an empty database and migrations 1 and 2
    migrations = make_migrations(
        tmp_path / "migrations",
        {"0002_add_item_name.sql": ADD_ITEM_NAME, "0001_create_item.sql": CREATE_ITEM},
    )

    # When the migrations run
    applied = migrate(connection, migrations)

    # Then both are applied in order and the version is 2
    assert applied == [1, 2]
    assert current_version(connection) == 2
    columns = [row["name"] for row in connection.execute("PRAGMA table_info(item)")]
    assert columns == ["id", "name"]


def test_ac9_second_run_applies_nothing(connection: sqlite3.Connection, tmp_path: Path) -> None:
    # Given a database at the newest version
    migrations = make_migrations(
        tmp_path / "migrations",
        {"0001_create_item.sql": CREATE_ITEM, "0002_add_item_name.sql": ADD_ITEM_NAME},
    )
    migrate(connection, migrations)

    # When the migrations run again
    applied = migrate(connection, migrations)

    # Then nothing is applied and the version is unchanged
    assert applied == []
    assert current_version(connection) == 2


def test_ac10_failing_migration_leaves_database_unchanged(
    connection: sqlite3.Connection, tmp_path: Path
) -> None:
    # Given a database at version 1 and a migration 2 that creates a table and then fails
    folder = tmp_path / "migrations"
    migrate(connection, make_migrations(folder, {"0001_create_item.sql": CREATE_ITEM}))
    make_migrations(folder, {"0002_broken.sql": CREATE_TABLE_THEN_FAIL})

    # When the migrations run
    with pytest.raises(MigrationError) as error:
        migrate(connection, folder)

    # Then the version is still 1 and the table of migration 2 is absent
    assert str(error.value) == "Migration 0002_broken.sql failed"
    assert current_version(connection) == 1
    assert "half_done" not in table_names(connection)
    assert not connection.in_transaction

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
# The conflict makes SQLite roll back the transaction itself before the error reaches Python.
CREATE_TABLE_THEN_ROLL_BACK = (
    "CREATE TABLE rolled_back (id INTEGER PRIMARY KEY);\n"
    "INSERT INTO rolled_back VALUES (1);\n"
    "INSERT OR ROLLBACK INTO rolled_back VALUES (1);"
)


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


def test_ac10_migration_rolled_back_by_sqlite_leaves_database_unchanged(
    connection: sqlite3.Connection, tmp_path: Path
) -> None:
    # Given a database at version 1 and a migration 2 whose failure ends the transaction
    folder = tmp_path / "migrations"
    migrate(connection, make_migrations(folder, {"0001_create_item.sql": CREATE_ITEM}))
    make_migrations(folder, {"0002_rolled_back.sql": CREATE_TABLE_THEN_ROLL_BACK})

    # When the migrations run
    with pytest.raises(MigrationError) as error:
        migrate(connection, folder)

    # Then the same error is raised, the version is still 1 and the table is absent
    assert str(error.value) == "Migration 0002_rolled_back.sql failed"
    assert current_version(connection) == 1
    assert "rolled_back" not in table_names(connection)
    assert not connection.in_transaction


CREATE_PARENT_AND_CHILD = (
    "CREATE TABLE parent (id INTEGER PRIMARY KEY, name TEXT NOT NULL);\n"
    "CREATE TABLE child (id INTEGER PRIMARY KEY,"
    " parent_id INTEGER NOT NULL REFERENCES parent (id) ON DELETE CASCADE);"
)
# SQLite's documented table rebuild; with foreign keys on, DROP TABLE would cascade.
REBUILD_PARENT = (
    "CREATE TABLE parent_new (id INTEGER PRIMARY KEY, name TEXT);\n"
    "INSERT INTO parent_new (id, name) SELECT id, name FROM parent;\n"
    "DROP TABLE parent;\n"
    "ALTER TABLE parent_new RENAME TO parent;"
)
ADD_ORPHAN_CHILD = "INSERT INTO child (id, parent_id) VALUES (2, 99);"


def foreign_keys_on(connection: sqlite3.Connection) -> bool:
    return connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_table_rebuild_keeps_cascading_children(
    connection: sqlite3.Connection, tmp_path: Path
) -> None:
    # Given a parent with a child that is deleted with it, and a migration that rebuilds the
    # parent table (receipt-management Plan P2)
    folder = tmp_path / "migrations"
    migrate(connection, make_migrations(folder, {"0001_tables.sql": CREATE_PARENT_AND_CHILD}))
    connection.execute("INSERT INTO parent (id, name) VALUES (1, 'a')")
    connection.execute("INSERT INTO child (id, parent_id) VALUES (1, 1)")
    make_migrations(folder, {"0002_rebuild.sql": REBUILD_PARENT})

    # When the migrations run
    migrate(connection, folder)

    # Then the child is still there and foreign keys are on again
    assert current_version(connection) == 2
    rows = connection.execute("SELECT id, parent_id FROM child").fetchall()
    assert [tuple(row) for row in rows] == [(1, 1)]
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert foreign_keys_on(connection)


def test_migration_leaving_a_dangling_reference_is_rolled_back(
    connection: sqlite3.Connection, tmp_path: Path
) -> None:
    # Given a database at version 1 and a migration 2 that adds a child without a parent
    folder = tmp_path / "migrations"
    migrate(connection, make_migrations(folder, {"0001_tables.sql": CREATE_PARENT_AND_CHILD}))
    make_migrations(folder, {"0002_orphan.sql": ADD_ORPHAN_CHILD})

    # When the migrations run
    with pytest.raises(MigrationError) as error:
        migrate(connection, folder)

    # Then the version is still 1, the child is absent and foreign keys are on again
    assert str(error.value) == "Migration 0002_orphan.sql failed"
    assert current_version(connection) == 1
    assert connection.execute("SELECT COUNT(*) FROM child").fetchone()[0] == 0
    assert not connection.in_transaction
    assert foreign_keys_on(connection)

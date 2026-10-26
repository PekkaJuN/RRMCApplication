"""Schema migrations: numbered SQL files applied in order."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.storage.db import connect

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


class MigrationError(Exception):
    """A migration failed; the database stays at the last successful version."""


def migrate_database(db_path: Path, migrations_dir: Path = MIGRATIONS_DIR) -> int:
    """Create the database if needed, apply pending migrations and return the version."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = connect(db_path)
    try:
        migrate(connection, migrations_dir)
        return current_version(connection)
    finally:
        connection.close()


def migrate(connection: sqlite3.Connection, migrations_dir: Path) -> list[int]:
    """Apply the migration files in `migrations_dir` that are newer than the database.

    Each file runs in its own transaction, so it must not contain BEGIN or COMMIT.
    Returns the applied versions in order.

    Raises:
        MigrationError: a migration failed; earlier migrations stay applied.
    """
    connection.execute(
        "CREATE TABLE IF NOT EXISTS schema_version ("
        "version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    start_version = current_version(connection)
    applied: list[int] = []
    for path in sorted(migrations_dir.glob("[0-9][0-9][0-9][0-9]_*.sql")):
        version = int(path.name[:4])
        if version <= start_version:
            continue
        _apply(connection, path, version)
        applied.append(version)
    return applied


def _apply(connection: sqlite3.Connection, path: Path, version: int) -> None:
    # executescript() runs statements one by one without a transaction of its own, so the
    # BEGIN is part of the script; the version row then commits together with the DDL.
    try:
        connection.executescript("BEGIN;\n" + path.read_text(encoding="utf-8"))
        connection.execute(
            "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
            (version, datetime.now(UTC).isoformat()),
        )
        connection.execute("COMMIT")
    except sqlite3.Error as error:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise MigrationError(f"Migration {path.name} failed") from error


def current_version(connection: sqlite3.Connection) -> int:
    """Return the newest applied version, or 0 for a new database."""
    row = connection.execute("SELECT MAX(version) FROM schema_version").fetchone()
    return row[0] or 0

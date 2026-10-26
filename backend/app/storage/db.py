"""SQLite connection."""

import sqlite3
from pathlib import Path


def connect(path: Path) -> sqlite3.Connection:
    """Open the database at `path`, creating the file if it does not exist.

    The connection does not open transactions implicitly (`isolation_level=None`); callers
    start them with `BEGIN`, so a migration's DDL and its version row commit together.
    """
    connection = sqlite3.connect(path, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def is_available(path: Path) -> bool:
    """Tell whether the existing database at `path` answers a query. Never creates it."""
    try:
        # mode=rw opens an existing file only; a plain connect would create an empty one.
        connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=rw", uri=True)
    except sqlite3.Error:
        return False
    try:
        # SELECT 1 would not read the file; reading the schema fails on a damaged file.
        connection.execute("SELECT count(*) FROM sqlite_master")
        return True
    except sqlite3.Error:
        return False
    finally:
        connection.close()

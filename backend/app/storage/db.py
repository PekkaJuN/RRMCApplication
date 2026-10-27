"""SQLite connection."""

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path


def connect(path: Path) -> sqlite3.Connection:
    """Open the database at `path`, creating the file if it does not exist.

    The connection does not open transactions implicitly (`isolation_level=None`); callers
    start them with `BEGIN`, so a migration's DDL and its version row commit together.
    """
    # FastAPI may open a request's connection in one threadpool thread and use it in another.
    # A connection is never shared between requests, so it is used by one thread at a time.
    connection = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
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


@contextmanager
def transaction(connection: sqlite3.Connection) -> Generator[None]:
    """Run the block in one transaction: commit at the end, roll back on any exception."""
    # IMMEDIATE takes the write lock at the start, so checks made inside the block still
    # hold when the block writes.
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        connection.execute("ROLLBACK")
        raise
    connection.execute("COMMIT")

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.storage.db import connect
from app.storage.migrate import migrate_database


@pytest.fixture
def db(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """A connection to a temporary database with every migration applied."""
    path = tmp_path / "rrmc.db"
    migrate_database(path)
    connection = connect(path)
    yield connection
    connection.close()

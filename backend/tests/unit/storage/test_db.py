from pathlib import Path

from app.storage.db import connect, is_available


def test_ac8_connect_creates_database_with_foreign_keys_and_wal(tmp_path: Path) -> None:
    # Given no database file
    path = tmp_path / "rrmc.db"

    # When a connection is opened
    connection = connect(path)

    # Then the file exists, foreign keys are enforced and the journal is WAL
    assert path.exists()
    assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    connection.close()


def test_ac12_existing_database_is_available(tmp_path: Path) -> None:
    path = tmp_path / "rrmc.db"
    connect(path).close()

    assert is_available(path)


def test_ac12_missing_database_is_unavailable_and_not_created(tmp_path: Path) -> None:
    path = tmp_path / "rrmc.db"

    assert not is_available(path)
    assert not path.exists()


def test_ac12_file_that_is_not_a_database_is_unavailable(tmp_path: Path) -> None:
    path = tmp_path / "rrmc.db"
    path.write_bytes(b"not a database" * 100)

    assert not is_available(path)

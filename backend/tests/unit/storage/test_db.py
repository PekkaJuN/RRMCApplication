import threading
from pathlib import Path

import pytest

from app.storage.db import (
    INTEGER_MAX,
    INTEGER_MIN,
    connect,
    fits_integer,
    is_available,
    transaction,
)


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


def test_transaction_commits_the_block(tmp_path: Path) -> None:
    path = tmp_path / "rrmc.db"
    connection = connect(path)
    connection.execute("CREATE TABLE item (id INTEGER PRIMARY KEY)")

    with transaction(connection):
        connection.execute("INSERT INTO item VALUES (1)")
    connection.close()

    reopened = connect(path)
    assert reopened.execute("SELECT count(*) FROM item").fetchone()[0] == 1
    reopened.close()


def test_transaction_rolls_back_and_reraises_on_error(tmp_path: Path) -> None:
    connection = connect(tmp_path / "rrmc.db")
    connection.execute("CREATE TABLE item (id INTEGER PRIMARY KEY)")

    with pytest.raises(ValueError, match="stop"), transaction(connection):
        connection.execute("INSERT INTO item VALUES (1)")
        raise ValueError("stop")

    assert not connection.in_transaction
    assert connection.execute("SELECT count(*) FROM item").fetchone()[0] == 0
    connection.close()


def test_connection_can_be_used_in_another_thread(tmp_path: Path) -> None:
    # FastAPI may open a request's connection in one threadpool thread (the dependency)
    # and run the route in another; see docs/learnings.md.
    connection = connect(tmp_path / "rrmc.db")
    errors: list[Exception] = []

    def query() -> None:
        try:
            connection.execute("SELECT 1")
        except Exception as error:  # noqa: BLE001 - the test reports any failure
            errors.append(error)

    worker = threading.Thread(target=query)
    worker.start()
    worker.join()
    connection.close()

    assert errors == []


@pytest.mark.parametrize("value", [INTEGER_MIN, 0, INTEGER_MAX])
def test_ac23_values_in_sqlite_range_fit(value: int) -> None:
    assert fits_integer(value)


@pytest.mark.parametrize("value", [INTEGER_MIN - 1, INTEGER_MAX + 1])
def test_ac23_values_outside_sqlite_range_do_not_fit(value: int) -> None:
    # SQLite would raise OverflowError for these, which gave 500 (line-editing PC11).
    assert not fits_integer(value)


def test_ac23_range_is_signed_64_bit() -> None:
    assert (INTEGER_MIN, INTEGER_MAX) == (-(2**63), 2**63 - 1)

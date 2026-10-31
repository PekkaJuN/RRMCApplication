import sqlite3
from pathlib import Path

import pytest

from app.storage.db import connect
from app.storage.migrate import MIGRATIONS_DIR, migrate

HASH = "a" * 64


def add_receipt(db: sqlite3.Connection, image_hash: str) -> None:
    db.execute(
        "INSERT INTO receipts (image_hash, file_name, imported_at) VALUES (?, ?, ?)",
        (image_hash, "a.jpg", "2026-10-28T10:00:00Z"),
    )


def test_ac1_migration_creates_the_receipts_table(db: sqlite3.Connection) -> None:
    columns = [row["name"] for row in db.execute("PRAGMA table_info(receipts)")]

    assert columns[:4] == ["id", "image_hash", "file_name", "imported_at"]
    # Later migrations add columns and raise the newest version; 2 must still be applied.
    assert db.execute("SELECT 1 FROM schema_version WHERE version = 2").fetchone() is not None


def test_ac4_image_hash_is_unique(db: sqlite3.Connection) -> None:
    add_receipt(db, HASH)

    with pytest.raises(sqlite3.IntegrityError):
        add_receipt(db, HASH)


def test_ac1_image_hash_must_have_64_characters(db: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        add_receipt(db, "abc")


def test_ac19_existing_receipts_are_unreviewed(tmp_path: Path) -> None:
    # Given a database at version 4 with two receipts
    connection = connect(tmp_path / "rrmc.db")
    older = tmp_path / "older"
    older.mkdir()
    for path in sorted(MIGRATIONS_DIR.glob("000[1-4]_*.sql")):
        (older / path.name).write_text(path.read_text("utf-8"), "utf-8")
    migrate(connection, older)
    add_receipt(connection, "a" * 64)
    add_receipt(connection, "b" * 64)

    # When migration 5 runs
    applied = migrate(connection, MIGRATIONS_DIR)

    # Then both receipts are unreviewed
    assert applied[0] == 5
    rows = connection.execute("SELECT reviewed FROM receipts ORDER BY id").fetchall()
    assert [row["reviewed"] for row in rows] == [0, 0]
    connection.close()


def test_ac19_review_state_is_a_flag(db: sqlite3.Connection) -> None:
    add_receipt(db, HASH)

    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE receipts SET reviewed = 2")

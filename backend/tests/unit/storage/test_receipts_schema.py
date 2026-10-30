import sqlite3

import pytest

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

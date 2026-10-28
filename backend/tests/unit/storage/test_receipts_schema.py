import sqlite3

import pytest

from app.storage.migrate import current_version

HASH = "a" * 64


def add_receipt(db: sqlite3.Connection, image_hash: str) -> None:
    db.execute(
        "INSERT INTO receipts (image_hash, file_name, imported_at) VALUES (?, ?, ?)",
        (image_hash, "a.jpg", "2026-10-28T10:00:00Z"),
    )


def test_ac1_migration_creates_the_receipts_table(db: sqlite3.Connection) -> None:
    columns = [row["name"] for row in db.execute("PRAGMA table_info(receipts)")]

    assert columns == ["id", "image_hash", "file_name", "imported_at"]
    assert current_version(db) == 2


def test_ac4_image_hash_is_unique(db: sqlite3.Connection) -> None:
    add_receipt(db, HASH)

    with pytest.raises(sqlite3.IntegrityError):
        add_receipt(db, HASH)


def test_ac1_image_hash_must_have_64_characters(db: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        add_receipt(db, "abc")

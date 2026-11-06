import sqlite3
from collections.abc import Iterator
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


def migrate_up_to(connection: sqlite3.Connection, folder: Path, last: int) -> None:
    """Apply the real migrations 1 to `last` only."""
    folder.mkdir()
    for path in sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9][0-9]_*.sql")):
        if int(path.name[:4]) <= last:
            (folder / path.name).write_text(path.read_text("utf-8"), "utf-8")
    migrate(connection, folder)


def all_rows(connection: sqlite3.Connection, table: str) -> list[tuple[object, ...]]:
    return [tuple(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY id")]  # noqa: S608 - fixed table names


@pytest.fixture
def version_5(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """A version-5 database with receipt A (OCR text, two lines with categories, sources and
    a product link) and reviewed receipt R with one line; synthetic data."""
    connection = connect(tmp_path / "rrmc.db")
    migrate_up_to(connection, tmp_path / "older", 5)
    connection.executescript(
        "INSERT INTO categories (id, name, name_key, kind, parent_id) VALUES"
        " (1, 'Ruoka', 'ruoka', 'group', NULL),"
        " (2, 'Maitotuotteet', 'maitotuotteet', 'category', 1),"
        " (3, 'Juomat', 'juomat', 'category', 1);"
        "INSERT INTO products (id, name, name_key, category_id) VALUES (1, 'Maito', 'maito', 2);"
    )
    connection.executemany(
        "INSERT INTO receipts (id, image_hash, file_name, imported_at, store, purchase_date,"
        " total_cents, ocr_text, reviewed) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                7,
                HASH,
                "a.jpg",
                "2026-10-28T10:00:00Z",
                "Testikauppa",
                "2026-10-05",
                349,
                "TESTIKAUPPA",
                0,
            ),
            (
                9,
                "b" * 64,
                "r.png",
                "2026-10-29T10:00:00Z",
                "Testikauppa",
                "2026-10-06",
                125,
                None,
                1,
            ),
        ],
    )
    connection.executescript(
        "INSERT INTO receipt_lines (id, receipt_id, position, name, amount_cents,"
        " is_deposit_refund, category_id, category_source, product_id) VALUES"
        " (11, 7, 1, 'Maito', 125, 0, 2, 'remembered', 1),"
        " (12, 7, 2, 'Limu', 224, 0, 3, 'model', NULL),"
        " (13, 9, 1, 'Maito', 125, 0, 2, 'user', 1);"
    )
    yield connection
    connection.close()


def test_ac15_migration_keeps_existing_data(version_5: sqlite3.Connection) -> None:
    # Given a version-5 database with receipts and lines
    receipts = all_rows(version_5, "receipts")
    lines = all_rows(version_5, "receipt_lines")

    # When the migrations run
    applied = migrate(version_5, MIGRATIONS_DIR)

    # Then migration 6 ran first and every row reads back the same
    assert applied[0] == 6
    assert all_rows(version_5, "receipts") == receipts
    assert all_rows(version_5, "receipt_lines") == lines
    assert version_5.execute("PRAGMA foreign_key_check").fetchall() == []


def test_ac15_hash_and_name_both_or_neither(db: sqlite3.Connection) -> None:
    insert = "INSERT INTO receipts (image_hash, file_name, imported_at) VALUES (?, ?, ?)"
    db.execute(insert, (None, None, "2026-11-02T10:00:00Z"))

    with pytest.raises(sqlite3.IntegrityError):
        db.execute(insert, (HASH, None, "2026-11-02T10:00:00Z"))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute(insert, (None, "a.jpg", "2026-11-02T10:00:00Z"))


def test_ac15_hash_still_unique_after_migration(version_5: sqlite3.Connection) -> None:
    migrate(version_5, MIGRATIONS_DIR)

    with pytest.raises(sqlite3.IntegrityError):
        add_receipt(version_5, HASH)


def test_ac14_many_receipts_without_an_image(db: sqlite3.Connection) -> None:
    insert = "INSERT INTO receipts (image_hash, file_name, imported_at) VALUES (NULL, NULL, ?)"
    db.execute(insert, ("2026-11-02T10:00:00Z",))
    db.execute(insert, ("2026-11-02T10:00:00Z",))

    count = db.execute("SELECT COUNT(*) FROM receipts WHERE image_hash IS NULL").fetchone()[0]
    assert count == 2


def test_ac15_ids_are_not_reused_after_a_delete(version_5: sqlite3.Connection) -> None:
    # Given the migrated database, whose largest receipt id is 9
    migrate(version_5, MIGRATIONS_DIR)

    # When receipt 9 is deleted and a new receipt is added
    version_5.execute("DELETE FROM receipts WHERE id = 9")
    cursor = version_5.execute(
        "INSERT INTO receipts (image_hash, file_name, imported_at) VALUES (NULL, NULL, ?)",
        ("2026-11-02T10:00:00Z",),
    )

    # Then the new receipt gets a larger id than any before
    assert cursor.lastrowid == 10

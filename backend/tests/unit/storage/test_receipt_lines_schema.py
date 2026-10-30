import sqlite3
from pathlib import Path

import pytest

from app.storage.db import connect
from app.storage.migrate import MIGRATIONS_DIR, current_version, migrate

HASH = "a" * 64


def add_receipt(db: sqlite3.Connection, purchase_date: str | None = None) -> int:
    cursor = db.execute(
        "INSERT INTO receipts (image_hash, file_name, imported_at, purchase_date)"
        " VALUES (?, 'a.jpg', '2026-10-30T10:00:00Z', ?)",
        (HASH, purchase_date),
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def add_line(
    db: sqlite3.Connection,
    receipt_id: int,
    *,
    position: int = 1,
    name: str = "Maito",
    amount: int = 125,
    refund: int = 0,
) -> None:
    db.execute(
        "INSERT INTO receipt_lines"
        " (receipt_id, position, name, amount_cents, is_deposit_refund) VALUES (?, ?, ?, ?, ?)",
        (receipt_id, position, name, amount, refund),
    )


def test_ac13_migration_3_adds_read_fields_and_lines(db: sqlite3.Connection) -> None:
    receipt_columns = [row["name"] for row in db.execute("PRAGMA table_info(receipts)")]
    line_columns = [row["name"] for row in db.execute("PRAGMA table_info(receipt_lines)")]

    assert receipt_columns == [
        "id",
        "image_hash",
        "file_name",
        "imported_at",
        "store",
        "purchase_date",
        "total_cents",
        "ocr_text",
    ]
    assert line_columns == [
        "id",
        "receipt_id",
        "position",
        "name",
        "amount_cents",
        "is_deposit_refund",
    ]
    assert current_version(db) == 3


def test_receipts_imported_before_reading_keep_empty_read_fields(tmp_path: Path) -> None:
    # Given a database at version 2 with one receipt
    connection = connect(tmp_path / "rrmc.db")
    older = tmp_path / "older"
    older.mkdir()
    for name in ("0001_catalog.sql", "0002_receipts.sql"):
        (older / name).write_text((MIGRATIONS_DIR / name).read_text("utf-8"), "utf-8")
    migrate(connection, older)
    with connection:
        add_receipt_v2 = (
            "INSERT INTO receipts (image_hash, file_name, imported_at) VALUES (?, ?, ?)"
        )
        connection.execute(add_receipt_v2, (HASH, "a.jpg", "2026-10-28T10:00:00Z"))

    # When migration 3 runs
    assert migrate(connection, MIGRATIONS_DIR) == [3]

    # Then the receipt is still there with empty read fields
    row = connection.execute("SELECT * FROM receipts").fetchone()
    assert (row["image_hash"], row["file_name"]) == (HASH, "a.jpg")
    assert (row["store"], row["purchase_date"], row["total_cents"], row["ocr_text"]) == (
        None,
        None,
        None,
        None,
    )
    connection.close()


def test_ac17_deleting_a_receipt_deletes_its_lines(db: sqlite3.Connection) -> None:
    receipt_id = add_receipt(db)
    add_line(db, receipt_id, position=1)
    add_line(db, receipt_id, position=2)

    db.execute("DELETE FROM receipts WHERE id = ?", (receipt_id,))

    assert db.execute("SELECT count(*) FROM receipt_lines").fetchone()[0] == 0


@pytest.mark.parametrize(
    "line",
    [
        {"name": "  "},
        {"refund": 1, "amount": 40},
        {"refund": 2, "amount": -40},
        {"position": 0},
    ],
    ids=["blank name", "refund with positive amount", "flag not 0 or 1", "position 0"],
)
def test_line_constraints(db: sqlite3.Connection, line: dict[str, int | str]) -> None:
    receipt_id = add_receipt(db)

    with pytest.raises(sqlite3.IntegrityError):
        add_line(db, receipt_id, **line)  # pyright: ignore[reportArgumentType]


def test_line_position_is_unique_per_receipt(db: sqlite3.Connection) -> None:
    receipt_id = add_receipt(db)
    add_line(db, receipt_id, position=1)

    with pytest.raises(sqlite3.IntegrityError):
        add_line(db, receipt_id, position=1)


def test_line_needs_its_receipt(db: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        add_line(db, 999)


@pytest.mark.parametrize("text", ["05.10.2026", "2026-10-5", ""])
def test_purchase_date_must_look_like_an_iso_date(db: sqlite3.Connection, text: str) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        add_receipt(db, purchase_date=text)


def test_purchase_date_may_be_empty_or_an_iso_date(db: sqlite3.Connection) -> None:
    add_receipt(db, purchase_date="2026-10-05")
    db.execute("DELETE FROM receipts")
    add_receipt(db, purchase_date=None)

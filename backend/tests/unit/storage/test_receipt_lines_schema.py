import sqlite3
from pathlib import Path

import pytest

from app.storage.db import connect
from app.storage.migrate import MIGRATIONS_DIR, migrate

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
    assert line_columns[:6] == [
        "id",
        "receipt_id",
        "position",
        "name",
        "amount_cents",
        "is_deposit_refund",
    ]
    # Later migrations add columns and raise the newest version; 3 must still be applied.
    assert db.execute("SELECT 1 FROM schema_version WHERE version = 3").fetchone() is not None


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

    # When migration 3 runs (later migrations run after it)
    assert migrate(connection, MIGRATIONS_DIR)[0] == 3

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


# Categorization spec: migration 0004 adds the category, its source and the product link.


def add_category(db: sqlite3.Connection, name: str = "Leivät") -> int:
    cursor = db.execute(
        "INSERT INTO categories (name, name_key, kind) VALUES (?, ?, 'category')",
        (name, name.casefold()),
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def add_product(db: sqlite3.Connection, category_id: int, name: str = "Ruisleipä") -> int:
    cursor = db.execute(
        "INSERT INTO products (name, name_key, category_id) VALUES (?, ?, ?)",
        (name, name.casefold(), category_id),
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def add_categorized_line(
    db: sqlite3.Connection,
    receipt_id: int,
    *,
    category_id: int | None,
    source: str | None,
    product_id: int | None = None,
    refund: int = 0,
) -> int:
    cursor = db.execute(
        "INSERT INTO receipt_lines (receipt_id, position, name, amount_cents,"
        " is_deposit_refund, category_id, category_source, product_id)"
        " VALUES (?, 1, 'Ruisleipä', ?, ?, ?, ?, ?)",
        (receipt_id, -40 if refund else 189, refund, category_id, source, product_id),
    )
    assert cursor.lastrowid is not None
    return cursor.lastrowid


def test_ac22_existing_lines_have_no_category(tmp_path: Path) -> None:
    # Given a database at version 3 with a receipt and two lines
    connection = connect(tmp_path / "rrmc.db")
    older = tmp_path / "older"
    older.mkdir()
    for path in sorted(MIGRATIONS_DIR.glob("000[1-3]_*.sql")):
        (older / path.name).write_text(path.read_text("utf-8"), "utf-8")
    migrate(connection, older)
    receipt_id = add_receipt(connection)
    add_line(connection, receipt_id, position=1, name="Maito", amount=125)
    add_line(connection, receipt_id, position=2, name="Limu", amount=224)

    # When migration 4 runs
    assert migrate(connection, MIGRATIONS_DIR) == [4]

    # Then both lines keep their data and have no category, source or product
    rows = connection.execute(
        "SELECT name, amount_cents, category_id, category_source, product_id"
        " FROM receipt_lines ORDER BY position"
    ).fetchall()
    assert [tuple(row) for row in rows] == [
        ("Maito", 125, None, None, None),
        ("Limu", 224, None, None, None),
    ]
    connection.close()


@pytest.mark.parametrize(
    ("source", "with_category", "refund"),
    [("guess", True, 0), ("model", False, 0), (None, True, 0), ("model", True, 1)],
    ids=["unknown source", "source without category", "category without source", "refund"],
)
def test_line_category_constraints(
    db: sqlite3.Connection, source: str | None, with_category: bool, refund: int
) -> None:
    receipt_id = add_receipt(db)
    category_id = add_category(db) if with_category else None

    with pytest.raises(sqlite3.IntegrityError):
        add_categorized_line(db, receipt_id, category_id=category_id, source=source, refund=refund)


def test_line_product_needs_a_category(db: sqlite3.Connection) -> None:
    receipt_id = add_receipt(db)
    product_id = add_product(db, add_category(db))

    with pytest.raises(sqlite3.IntegrityError):
        add_categorized_line(db, receipt_id, category_id=None, source=None, product_id=product_id)


def test_category_used_by_a_line_cannot_be_deleted(db: sqlite3.Connection) -> None:
    category_id = add_category(db)
    add_categorized_line(db, add_receipt(db), category_id=category_id, source="model")

    with pytest.raises(sqlite3.IntegrityError):
        db.execute("DELETE FROM categories WHERE id = ?", (category_id,))


def test_deleting_a_product_keeps_the_line_category(db: sqlite3.Connection) -> None:
    category_id = add_category(db)
    product_id = add_product(db, category_id)
    add_categorized_line(
        db, add_receipt(db), category_id=category_id, source="remembered", product_id=product_id
    )

    db.execute("DELETE FROM products WHERE id = ?", (product_id,))

    row = db.execute(
        "SELECT category_id, category_source, product_id FROM receipt_lines"
    ).fetchone()
    assert tuple(row) == (category_id, "remembered", None)

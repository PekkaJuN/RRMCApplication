"""The archive tables of migration 0008 (archiving spec P2)."""

import sqlite3

import pytest

HASH = "a" * 64


def add_receipt(
    db: sqlite3.Connection,
    receipt_id: int = 1,
    year: int = 2025,
    purchase_date: str = "2025-03-10",
    image_hash: str | None = HASH,
    file_name: str | None = "a.jpg",
) -> None:
    db.execute(
        "INSERT INTO archived_receipts (id, year, purchase_date, store, total_cents,"
        " image_hash, file_name, imported_at, archived_at)"
        " VALUES (?, ?, ?, 'Kauppa', 100, ?, ?, '2025-03-10T10:00:00Z', '2026-11-13T10:00:00Z')",
        (receipt_id, year, purchase_date, image_hash, file_name),
    )


def add_line(
    db: sqlite3.Connection,
    *,
    position: int = 1,
    category: str | None = "Maito",
    group: str | None = "Maitotuotteet",
    is_deposit_refund: int = 0,
    amount: int = 100,
) -> None:
    db.execute(
        "INSERT INTO archived_lines (receipt_id, position, name, product_name, amount_cents,"
        " is_deposit_refund, category_name, group_name)"
        " VALUES (1, ?, 'MAITO', 'Maito 1l', ?, ?, ?, ?)",
        (position, amount, is_deposit_refund, category, group),
    )


def test_p2_migration_creates_the_archive_tables(db: sqlite3.Connection) -> None:
    receipts = [row["name"] for row in db.execute("PRAGMA table_info(archived_receipts)")]
    lines = [row["name"] for row in db.execute("PRAGMA table_info(archived_lines)")]

    assert receipts == [
        "id",
        "year",
        "purchase_date",
        "store",
        "total_cents",
        "image_hash",
        "file_name",
        "imported_at",
        "archived_at",
    ]
    assert lines == [
        "id",
        "receipt_id",
        "position",
        "name",
        "product_name",
        "amount_cents",
        "is_deposit_refund",
        "category_name",
        "group_name",
    ]
    assert db.execute("SELECT max(version) FROM schema_version").fetchone()[0] == 8


def test_p2_a_year_that_differs_from_the_purchase_date_is_refused(
    db: sqlite3.Connection,
) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        add_receipt(db, year=2024, purchase_date="2025-03-10")


def test_p2_an_image_hash_without_a_file_name_is_refused(db: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        add_receipt(db, file_name=None)


def test_p2_a_receipt_without_an_image_is_allowed(db: sqlite3.Connection) -> None:
    add_receipt(db, image_hash=None, file_name=None)
    add_receipt(db, receipt_id=2, image_hash=None, file_name=None)

    assert db.execute("SELECT count(*) FROM archived_receipts").fetchone()[0] == 2


def test_p2_the_image_hash_is_unique(db: sqlite3.Connection) -> None:
    add_receipt(db)

    with pytest.raises(sqlite3.IntegrityError):
        add_receipt(db, receipt_id=2, file_name="b.jpg")


def test_p2_a_group_without_a_category_is_refused(db: sqlite3.Connection) -> None:
    add_receipt(db)

    with pytest.raises(sqlite3.IntegrityError):
        add_line(db, category=None, group="Maitotuotteet")


def test_p2_a_deposit_refund_with_a_category_is_refused(db: sqlite3.Connection) -> None:
    add_receipt(db)

    with pytest.raises(sqlite3.IntegrityError):
        add_line(db, is_deposit_refund=1, amount=-40, group=None)


def test_p2_deleting_an_archived_receipt_deletes_its_lines(db: sqlite3.Connection) -> None:
    add_receipt(db)
    add_line(db)
    add_line(db, position=2, category=None, group=None, is_deposit_refund=1, amount=-40)

    db.execute("DELETE FROM archived_receipts WHERE id = 1")

    assert db.execute("SELECT count(*) FROM archived_lines").fetchone()[0] == 0

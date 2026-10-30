import sqlite3

import pytest

from app.storage.receipt_repository import LineRow, ReceiptRepository, ReceiptRow

HASH = "b" * 64
TIME = "2026-10-28T10:00:00Z"


def test_ac1_add_returns_the_stored_row(db: sqlite3.Connection) -> None:
    repository = ReceiptRepository(db)

    row = repository.add(HASH, "kuitti (2).jpg", TIME)

    assert row == ReceiptRow(
        id=row.id, image_hash=HASH, file_name="kuitti (2).jpg", imported_at=TIME
    )


def test_ac4_get_by_hash_finds_the_receipt(db: sqlite3.Connection) -> None:
    repository = ReceiptRepository(db)
    added = repository.add(HASH, "a.jpg", TIME)

    assert repository.get_by_hash(HASH) == added
    assert repository.get_by_hash("c" * 64) is None


def test_ac12_delete_removes_the_receipt(db: sqlite3.Connection) -> None:
    repository = ReceiptRepository(db)
    added = repository.add(HASH, "a.jpg", TIME)

    repository.delete(added.id)

    assert repository.get_by_hash(HASH) is None


def test_ac5_add_with_an_existing_hash_is_refused(db: sqlite3.Connection) -> None:
    repository = ReceiptRepository(db)
    repository.add(HASH, "a.jpg", TIME)

    with pytest.raises(sqlite3.IntegrityError):
        repository.add(HASH, "b.jpg", TIME)


def test_ac14_transaction_rolls_back_on_error(db: sqlite3.Connection) -> None:
    repository = ReceiptRepository(db)

    with pytest.raises(RuntimeError), repository.transaction():
        repository.add(HASH, "a.jpg", TIME)
        raise RuntimeError

    assert repository.get_by_hash(HASH) is None


def test_ac13_add_stores_the_read_fields_and_lines(db: sqlite3.Connection) -> None:
    repository = ReceiptRepository(db)

    with repository.transaction():
        row = repository.add(
            HASH,
            "a.jpg",
            TIME,
            store="Testikauppa",
            purchase_date="2026-10-05",
            total_cents=349,
            ocr_text="TESTIKAUPPA\n",
        )
        repository.add_line(row.id, 1, "Maito", 125, is_deposit_refund=False)
        repository.add_line(row.id, 2, "Panttipalautus", -40, is_deposit_refund=True)

    assert repository.get_by_hash(HASH) == ReceiptRow(
        id=row.id,
        image_hash=HASH,
        file_name="a.jpg",
        imported_at=TIME,
        store="Testikauppa",
        purchase_date="2026-10-05",
        total_cents=349,
        ocr_text="TESTIKAUPPA\n",
    )
    assert repository.lines(row.id) == [
        LineRow(position=1, name="Maito", amount_cents=125, is_deposit_refund=False),
        LineRow(position=2, name="Panttipalautus", amount_cents=-40, is_deposit_refund=True),
    ]


def test_ac16_failed_line_rolls_back_the_receipt_and_its_lines(db: sqlite3.Connection) -> None:
    repository = ReceiptRepository(db)

    with pytest.raises(sqlite3.IntegrityError), repository.transaction():
        row = repository.add(HASH, "a.jpg", TIME, store="", total_cents=0, ocr_text="x")
        repository.add_line(row.id, 1, "Maito", 125, is_deposit_refund=False)
        repository.add_line(row.id, 1, "Limu", 224, is_deposit_refund=False)

    assert repository.get_by_hash(HASH) is None
    assert db.execute("SELECT count(*) FROM receipt_lines").fetchone()[0] == 0


def test_ac17_delete_removes_the_lines_too(db: sqlite3.Connection) -> None:
    repository = ReceiptRepository(db)
    with repository.transaction():
        row = repository.add(HASH, "a.jpg", TIME)
        repository.add_line(row.id, 1, "Maito", 125, is_deposit_refund=False)

    with repository.transaction():
        repository.delete(row.id)

    assert repository.lines(row.id) == []

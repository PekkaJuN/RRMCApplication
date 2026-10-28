import sqlite3

import pytest

from app.storage.receipt_repository import ReceiptRepository, ReceiptRow

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

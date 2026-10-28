"""SQL for receipts. Holds no rules; import owns those."""

import sqlite3
from contextlib import AbstractContextManager
from dataclasses import dataclass

from app.storage.db import transaction

_RECEIPT_SELECT = "SELECT id, image_hash, file_name, imported_at FROM receipts"


@dataclass(frozen=True)
class ReceiptRow:
    """An imported receipt image."""

    id: int
    image_hash: str
    file_name: str
    imported_at: str


def _receipt(row: sqlite3.Row) -> ReceiptRow:
    return ReceiptRow(
        id=row["id"],
        image_hash=row["image_hash"],
        file_name=row["file_name"],
        imported_at=row["imported_at"],
    )


class ReceiptRepository:
    """Receipt queries on one connection. Callers own the transaction."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def transaction(self) -> AbstractContextManager[None]:
        """One transaction on this repository's connection (see `db.transaction`)."""
        return transaction(self._connection)

    def add(self, image_hash: str, file_name: str, imported_at: str) -> ReceiptRow:
        """Store a receipt. Raises `sqlite3.IntegrityError` when the hash exists."""
        cursor = self._connection.execute(
            "INSERT INTO receipts (image_hash, file_name, imported_at) VALUES (?, ?, ?)",
            (image_hash, file_name, imported_at),
        )
        assert cursor.lastrowid is not None  # noqa: S101 - set by every successful INSERT
        return ReceiptRow(cursor.lastrowid, image_hash, file_name, imported_at)

    def get_by_hash(self, image_hash: str) -> ReceiptRow | None:
        row = self._connection.execute(
            _RECEIPT_SELECT + " WHERE image_hash = ?", (image_hash,)
        ).fetchone()
        return _receipt(row) if row else None

    def delete(self, receipt_id: int) -> None:
        self._connection.execute("DELETE FROM receipts WHERE id = ?", (receipt_id,))

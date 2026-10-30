"""SQL for receipts and their lines. Holds no rules; import owns those."""

import sqlite3
from contextlib import AbstractContextManager
from dataclasses import dataclass

from app.storage.db import transaction

_RECEIPT_SELECT = (
    "SELECT id, image_hash, file_name, imported_at, store, purchase_date, total_cents, ocr_text"
    " FROM receipts"
)


@dataclass(frozen=True)
class ReceiptRow:
    """An imported receipt image and what was read from it.

    The read fields are None for receipts imported before reading existed.
    """

    id: int
    image_hash: str
    file_name: str
    imported_at: str
    store: str | None = None
    purchase_date: str | None = None
    total_cents: int | None = None
    ocr_text: str | None = None


@dataclass(frozen=True)
class LineRow:
    position: int
    name: str
    amount_cents: int
    is_deposit_refund: bool


def _receipt(row: sqlite3.Row) -> ReceiptRow:
    return ReceiptRow(
        id=row["id"],
        image_hash=row["image_hash"],
        file_name=row["file_name"],
        imported_at=row["imported_at"],
        store=row["store"],
        purchase_date=row["purchase_date"],
        total_cents=row["total_cents"],
        ocr_text=row["ocr_text"],
    )


class ReceiptRepository:
    """Receipt queries on one connection. Callers own the transaction."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def transaction(self) -> AbstractContextManager[None]:
        """One transaction on this repository's connection (see `db.transaction`)."""
        return transaction(self._connection)

    def add(
        self,
        image_hash: str,
        file_name: str,
        imported_at: str,
        *,
        store: str | None = None,
        purchase_date: str | None = None,
        total_cents: int | None = None,
        ocr_text: str | None = None,
    ) -> ReceiptRow:
        """Store a receipt. Raises `sqlite3.IntegrityError` when the hash exists."""
        cursor = self._connection.execute(
            "INSERT INTO receipts"
            " (image_hash, file_name, imported_at, store, purchase_date, total_cents, ocr_text)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (image_hash, file_name, imported_at, store, purchase_date, total_cents, ocr_text),
        )
        assert cursor.lastrowid is not None  # noqa: S101 - set by every successful INSERT
        return ReceiptRow(
            cursor.lastrowid,
            image_hash,
            file_name,
            imported_at,
            store,
            purchase_date,
            total_cents,
            ocr_text,
        )

    def add_line(
        self,
        receipt_id: int,
        position: int,
        name: str,
        amount_cents: int,
        *,
        is_deposit_refund: bool,
    ) -> None:
        self._connection.execute(
            "INSERT INTO receipt_lines"
            " (receipt_id, position, name, amount_cents, is_deposit_refund)"
            " VALUES (?, ?, ?, ?, ?)",
            (receipt_id, position, name, amount_cents, int(is_deposit_refund)),
        )

    def get_by_hash(self, image_hash: str) -> ReceiptRow | None:
        row = self._connection.execute(
            _RECEIPT_SELECT + " WHERE image_hash = ?", (image_hash,)
        ).fetchone()
        return _receipt(row) if row else None

    def lines(self, receipt_id: int) -> list[LineRow]:
        """The receipt's lines in printed order."""
        rows = self._connection.execute(
            "SELECT position, name, amount_cents, is_deposit_refund FROM receipt_lines"
            " WHERE receipt_id = ? ORDER BY position",
            (receipt_id,),
        )
        return [
            LineRow(
                position=row["position"],
                name=row["name"],
                amount_cents=row["amount_cents"],
                is_deposit_refund=bool(row["is_deposit_refund"]),
            )
            for row in rows
        ]

    def delete(self, receipt_id: int) -> None:
        """Delete a receipt; its lines go with it (`ON DELETE CASCADE`)."""
        self._connection.execute("DELETE FROM receipts WHERE id = ?", (receipt_id,))

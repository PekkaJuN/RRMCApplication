"""SQL for receipts and their lines. Holds no rules; import owns those."""

import sqlite3
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Literal

from app.storage.db import transaction

type CategorySource = Literal["remembered", "model", "user"]

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
class LineCategory:
    """A line's category, where it came from (FR-15) and the product it follows, if any."""

    category_id: int
    source: CategorySource
    product_id: int | None


@dataclass(frozen=True)
class LineRow:
    """A line as listed with its receipt; the category fields are None without a category."""

    position: int
    name: str
    amount_cents: int
    is_deposit_refund: bool
    category_id: int | None = None
    category_source: CategorySource | None = None
    product_id: int | None = None


@dataclass(frozen=True)
class StoredLine:
    """One line looked up by its id, for changing its category."""

    id: int
    receipt_id: int
    name: str
    is_deposit_refund: bool
    category: LineCategory | None


def _category_values(category: LineCategory | None) -> tuple[int | None, str | None, int | None]:
    if category is None:
        return None, None, None
    return category.category_id, category.source, category.product_id


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
        category: LineCategory | None = None,
    ) -> None:
        self._connection.execute(
            "INSERT INTO receipt_lines (receipt_id, position, name, amount_cents,"
            " is_deposit_refund, category_id, category_source, product_id)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                receipt_id,
                position,
                name,
                amount_cents,
                int(is_deposit_refund),
                *_category_values(category),
            ),
        )

    def get_line(self, line_id: int) -> StoredLine | None:
        row = self._connection.execute(
            "SELECT id, receipt_id, name, is_deposit_refund, category_id, category_source,"
            " product_id FROM receipt_lines WHERE id = ?",
            (line_id,),
        ).fetchone()
        if row is None:
            return None
        category = (
            None
            if row["category_id"] is None
            else LineCategory(row["category_id"], row["category_source"], row["product_id"])
        )
        return StoredLine(
            id=row["id"],
            receipt_id=row["receipt_id"],
            name=row["name"],
            is_deposit_refund=bool(row["is_deposit_refund"]),
            category=category,
        )

    def set_line_category(self, line_id: int, category: LineCategory | None) -> None:
        self._connection.execute(
            "UPDATE receipt_lines SET category_id = ?, category_source = ?, product_id = ?"
            " WHERE id = ?",
            (*_category_values(category), line_id),
        )

    def get_by_hash(self, image_hash: str) -> ReceiptRow | None:
        row = self._connection.execute(
            _RECEIPT_SELECT + " WHERE image_hash = ?", (image_hash,)
        ).fetchone()
        return _receipt(row) if row else None

    def lines(self, receipt_id: int) -> list[LineRow]:
        """The receipt's lines in printed order."""
        rows = self._connection.execute(
            "SELECT position, name, amount_cents, is_deposit_refund, category_id,"
            " category_source, product_id FROM receipt_lines"
            " WHERE receipt_id = ? ORDER BY position",
            (receipt_id,),
        )
        return [
            LineRow(
                position=row["position"],
                name=row["name"],
                amount_cents=row["amount_cents"],
                is_deposit_refund=bool(row["is_deposit_refund"]),
                category_id=row["category_id"],
                category_source=row["category_source"],
                product_id=row["product_id"],
            )
            for row in rows
        ]

    def delete(self, receipt_id: int) -> None:
        """Delete a receipt; its lines go with it (`ON DELETE CASCADE`)."""
        self._connection.execute("DELETE FROM receipts WHERE id = ?", (receipt_id,))

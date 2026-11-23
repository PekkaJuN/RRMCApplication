"""SQL for receipts and their lines. Holds no rules; import owns those."""

import sqlite3
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Literal

from app.storage.db import transaction

type CategorySource = Literal["remembered", "model", "user"]

_RECEIPT_SELECT = (
    "SELECT id, image_hash, file_name, imported_at, store, purchase_date, total_cents, ocr_text,"
    " reviewed FROM receipts"
)

_SUMMARY_SELECT = (
    "SELECT receipts.id, store, purchase_date, total_cents, reviewed,"
    " COALESCE(SUM(receipt_lines.amount_cents), 0) AS line_sum_cents"
    " FROM receipts LEFT JOIN receipt_lines ON receipt_lines.receipt_id = receipts.id"
)
_SUMMARY_ORDER = (
    " GROUP BY receipts.id ORDER BY purchase_date IS NOT NULL, purchase_date DESC, receipts.id DESC"
)
# Closed with ")" after the line conditions (receipt search P4).
_MATCHING_LINE = (
    "EXISTS (SELECT 1 FROM receipt_lines AS m"
    " LEFT JOIN products AS p ON p.id = m.product_id"
    " WHERE m.receipt_id = receipts.id AND "
)
# COALESCE keeps NULL away from the Python function; SQLite may call it even after a
# failed IS NOT NULL. An empty store never contains a non-empty key (store search P3).
_MATCHING_STORE = "instr(name_key(COALESCE(receipts.store, '')), ?) > 0"


@dataclass(frozen=True)
class ReceiptRow:
    """A receipt: an imported image and what was read from it, or a manual receipt.

    The read fields are None for receipts imported before reading existed. `image_hash` and
    `file_name` are both None for a manual receipt without an image.
    """

    id: int
    image_hash: str | None
    file_name: str | None
    imported_at: str
    store: str | None = None
    purchase_date: str | None = None
    total_cents: int | None = None
    ocr_text: str | None = None
    reviewed: bool = False


@dataclass(frozen=True)
class ReceiptSummaryRow:
    """A receipt as listed, with the sum of its line amounts (0 without lines)."""

    id: int
    store: str | None
    purchase_date: str | None
    total_cents: int | None
    reviewed: bool
    line_sum_cents: int


@dataclass(frozen=True)
class LineCategory:
    """A line's category, where it came from (FR-15) and the product it follows, if any."""

    category_id: int
    source: CategorySource
    product_id: int | None


@dataclass(frozen=True)
class LineRow:
    """A line as listed with its receipt; the category fields are None without a category."""

    id: int
    position: int
    name: str
    amount_cents: int
    is_deposit_refund: bool
    category_id: int | None = None
    category_source: CategorySource | None = None
    product_id: int | None = None


@dataclass(frozen=True)
class StoredLine:
    """One line looked up by its id, for changing it."""

    id: int
    receipt_id: int
    name: str
    amount_cents: int
    is_deposit_refund: bool
    category: LineCategory | None


@dataclass(frozen=True)
class DatedLineRow:
    """A line with its receipt's purchase date, for the totals; no product name (NFR-3)."""

    purchase_date: str
    amount_cents: int
    category_id: int | None
    is_deposit_refund: bool


@dataclass(frozen=True)
class YearLineRow:
    """A reviewed line with the current catalog names, for the year totals (year with
    products spec P3). The product name is the linked product's name, else the line's."""

    purchase_date: str
    amount_cents: int
    product_name: str
    category_name: str | None
    group_name: str | None
    is_deposit_refund: bool


@dataclass(frozen=True)
class ExportLineRow:
    """A line with the names the lines file shows (export spec P4)."""

    purchase_date: str
    store: str | None
    name: str
    amount_cents: int
    is_deposit_refund: bool
    group_name: str | None
    category_name: str | None
    reviewed: bool


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
        reviewed=bool(row["reviewed"]),
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
        image_hash: str | None,
        file_name: str | None,
        imported_at: str,
        *,
        store: str | None = None,
        purchase_date: str | None = None,
        total_cents: int | None = None,
        ocr_text: str | None = None,
    ) -> ReceiptRow:
        """Store a receipt; hash and name are both None for a receipt without an image.
        Raises `sqlite3.IntegrityError` when the hash exists."""
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
    ) -> int:
        """Store a line and return its id."""
        cursor = self._connection.execute(
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
        assert cursor.lastrowid is not None  # noqa: S101 - set by every successful INSERT
        return cursor.lastrowid

    def get_line(self, line_id: int) -> StoredLine | None:
        row = self._connection.execute(
            "SELECT id, receipt_id, name, amount_cents, is_deposit_refund, category_id,"
            " category_source, product_id FROM receipt_lines WHERE id = ?",
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
            amount_cents=row["amount_cents"],
            is_deposit_refund=bool(row["is_deposit_refund"]),
            category=category,
        )

    def set_line_category(self, line_id: int, category: LineCategory | None) -> None:
        self._connection.execute(
            "UPDATE receipt_lines SET category_id = ?, category_source = ?, product_id = ?"
            " WHERE id = ?",
            (*_category_values(category), line_id),
        )

    def update_line(
        self,
        line_id: int,
        *,
        name: str,
        amount_cents: int,
        is_deposit_refund: bool,
        category: LineCategory | None,
    ) -> None:
        """Write the line's resulting state at once, so the schema's CHECKs see one
        consistent row (a refund is negative and has no category)."""
        self._connection.execute(
            "UPDATE receipt_lines SET name = ?, amount_cents = ?, is_deposit_refund = ?,"
            " category_id = ?, category_source = ?, product_id = ? WHERE id = ?",
            (name, amount_cents, int(is_deposit_refund), *_category_values(category), line_id),
        )

    def next_position(self, receipt_id: int) -> int:
        """The position after the receipt's last line; 1 without lines. Positions can have
        gaps after a delete."""
        row = self._connection.execute(
            "SELECT COALESCE(MAX(position), 0) + 1 FROM receipt_lines WHERE receipt_id = ?",
            (receipt_id,),
        ).fetchone()
        return row[0]

    def delete_line(self, line_id: int) -> bool:
        """False when the line does not exist."""
        cursor = self._connection.execute("DELETE FROM receipt_lines WHERE id = ?", (line_id,))
        return cursor.rowcount == 1

    def get(self, receipt_id: int) -> ReceiptRow | None:
        row = self._connection.execute(_RECEIPT_SELECT + " WHERE id = ?", (receipt_id,)).fetchone()
        return _receipt(row) if row else None

    def set_reviewed(self, receipt_id: int, *, reviewed: bool) -> bool:
        """Set the review state (FR-21). False when the receipt does not exist."""
        cursor = self._connection.execute(
            "UPDATE receipts SET reviewed = ? WHERE id = ?", (int(reviewed), receipt_id)
        )
        return cursor.rowcount == 1

    def set_fields(
        self,
        receipt_id: int,
        *,
        store: str | None,
        purchase_date: str | None,
        total_cents: int | None,
    ) -> bool:
        """Write the store, purchase date and total. False when the receipt does not exist."""
        cursor = self._connection.execute(
            "UPDATE receipts SET store = ?, purchase_date = ?, total_cents = ? WHERE id = ?",
            (store, purchase_date, total_cents, receipt_id),
        )
        return cursor.rowcount == 1

    def summaries(
        self,
        *,
        name_key: str | None = None,
        store_key: str | None = None,
        uncategorized: bool = False,
        key: Callable[[str], str] | None = None,
    ) -> list[ReceiptSummaryRow]:
        """Receipts with their line sum: receipts without a purchase date first, then the
        newest date first; the newest import first within a date (receipt-review PC1).

        With line conditions, only receipts with one line that meets every line condition
        (receipt search P4): `name_key` is in the line's name folded by `key`, or in its
        product's key; `uncategorized` is a line without a category that is not a deposit
        refund. `store_key` is in the receipt's store folded by `key`; it is a receipt
        condition, not a line condition (store search P3). The line sum stays the sum of
        all lines."""
        if (name_key or store_key) and key is None:
            raise ValueError("a name or store condition needs the key function")
        if key is not None:
            # Names and stores are stored as display names; SQLite cannot fold Ä to ä, so
            # the caller's key function does it. instr() matches % and _ literally.
            self._connection.create_function("name_key", 1, key, deterministic=True)
        receipt_conditions: list[str] = []
        line_conditions: list[str] = []
        parameters: list[str] = []
        if store_key:
            receipt_conditions.append(_MATCHING_STORE)
            parameters.append(store_key)
        if name_key:
            line_conditions.append("(instr(name_key(m.name), ?) > 0 OR instr(p.name_key, ?) > 0)")
            parameters += [name_key, name_key]
        if uncategorized:
            line_conditions.append("m.category_id IS NULL AND m.is_deposit_refund = 0")
        if line_conditions:
            receipt_conditions.append(_MATCHING_LINE + " AND ".join(line_conditions) + ")")
        # Only the fixed fragments above are joined; the search texts are bound parameters.
        where = " WHERE " + " AND ".join(receipt_conditions) if receipt_conditions else ""
        rows = self._connection.execute(_SUMMARY_SELECT + where + _SUMMARY_ORDER, parameters)
        return [
            ReceiptSummaryRow(
                id=row["id"],
                store=row["store"],
                purchase_date=row["purchase_date"],
                total_cents=row["total_cents"],
                reviewed=bool(row["reviewed"]),
                line_sum_cents=row["line_sum_cents"],
            )
            for row in rows
        ]

    def dated_lines(
        self, start: str, end: str, *, reviewed_only: bool = False
    ) -> list[DatedLineRow]:
        """The lines of the receipts dated from `start` to `end` (`YYYY-MM-DD`, inclusive).

        The column's `CHECK` keeps every date in that shape, so text order is date order.
        """
        query = (
            "SELECT receipts.purchase_date, receipt_lines.amount_cents,"
            " receipt_lines.category_id, receipt_lines.is_deposit_refund"
            " FROM receipt_lines JOIN receipts ON receipts.id = receipt_lines.receipt_id"
            " WHERE receipts.purchase_date BETWEEN ? AND ?"
        )
        if reviewed_only:
            query += " AND receipts.reviewed = 1"
        rows = self._connection.execute(query, (start, end))
        return [
            DatedLineRow(
                purchase_date=row["purchase_date"],
                amount_cents=row["amount_cents"],
                category_id=row["category_id"],
                is_deposit_refund=bool(row["is_deposit_refund"]),
            )
            for row in rows
        ]

    def year_lines(self, start: str, end: str) -> list[YearLineRow]:
        """The lines of the reviewed receipts dated from `start` to `end` (inclusive), with
        the current product, category and group names (year with products spec P3)."""
        rows = self._connection.execute(
            "SELECT r.purchase_date, l.amount_cents, coalesce(p.name, l.name) AS product_name,"
            " c.name AS category_name, g.name AS group_name, l.is_deposit_refund"
            " FROM receipt_lines AS l"
            " JOIN receipts AS r ON r.id = l.receipt_id"
            " LEFT JOIN products AS p ON p.id = l.product_id"
            " LEFT JOIN categories AS c ON c.id = l.category_id"
            " LEFT JOIN categories AS g ON g.id = c.parent_id"
            " WHERE r.reviewed = 1 AND r.purchase_date BETWEEN ? AND ?"
            " ORDER BY r.purchase_date, r.id, l.position",
            (start, end),
        )
        return [
            YearLineRow(
                purchase_date=row["purchase_date"],
                amount_cents=row["amount_cents"],
                product_name=row["product_name"],
                category_name=row["category_name"],
                group_name=row["group_name"],
                is_deposit_refund=bool(row["is_deposit_refund"]),
            )
            for row in rows
        ]

    def export_lines(self, start: str, end: str) -> list[ExportLineRow]:
        """The lines of the receipts dated from `start` to `end` (inclusive), in date order,
        then import order, then position on the receipt."""
        rows = self._connection.execute(
            "SELECT receipts.purchase_date, receipts.store, receipt_lines.name,"
            " receipt_lines.amount_cents, receipt_lines.is_deposit_refund,"
            " category_group.name AS group_name, category.name AS category_name,"
            " receipts.reviewed"
            " FROM receipt_lines JOIN receipts ON receipts.id = receipt_lines.receipt_id"
            " LEFT JOIN categories AS category ON category.id = receipt_lines.category_id"
            " LEFT JOIN categories AS category_group ON category_group.id = category.parent_id"
            " WHERE receipts.purchase_date BETWEEN ? AND ?"
            " ORDER BY receipts.purchase_date, receipts.id, receipt_lines.position",
            (start, end),
        )
        return [
            ExportLineRow(
                purchase_date=row["purchase_date"],
                store=row["store"],
                name=row["name"],
                amount_cents=row["amount_cents"],
                is_deposit_refund=bool(row["is_deposit_refund"]),
                group_name=row["group_name"],
                category_name=row["category_name"],
                reviewed=bool(row["reviewed"]),
            )
            for row in rows
        ]

    def count_unreviewed(self, start: str, end: str) -> int:
        """How many unreviewed receipts are dated from `start` to `end` (inclusive)."""
        row = self._connection.execute(
            "SELECT COUNT(*) FROM receipts WHERE reviewed = 0 AND purchase_date BETWEEN ? AND ?",
            (start, end),
        ).fetchone()
        return int(row[0])

    def count_undated(self) -> int:
        """How many receipts have no purchase date."""
        row = self._connection.execute(
            "SELECT COUNT(*) FROM receipts WHERE purchase_date IS NULL"
        ).fetchone()
        return int(row[0])

    def get_by_hash(self, image_hash: str) -> ReceiptRow | None:
        row = self._connection.execute(
            _RECEIPT_SELECT + " WHERE image_hash = ?", (image_hash,)
        ).fetchone()
        return _receipt(row) if row else None

    def image_known(self, image_hash: str) -> bool:
        """Tell whether an active or archived receipt has the image: the duplicate check of
        import and of a manual receipt's image (FR-3, FR-42)."""
        row = self._connection.execute(
            "SELECT EXISTS (SELECT 1 FROM receipts WHERE image_hash = ?)"
            " OR EXISTS (SELECT 1 FROM archived_receipts WHERE image_hash = ?)",
            (image_hash, image_hash),
        ).fetchone()
        return bool(row[0])

    def lines(self, receipt_id: int) -> list[LineRow]:
        """The receipt's lines in printed order."""
        rows = self._connection.execute(
            "SELECT id, position, name, amount_cents, is_deposit_refund, category_id,"
            " category_source, product_id FROM receipt_lines"
            " WHERE receipt_id = ? ORDER BY position",
            (receipt_id,),
        )
        return [
            LineRow(
                id=row["id"],
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

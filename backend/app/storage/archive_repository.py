"""SQL of the archive (archiving spec P1, P3). Holds no rules; the archive service owns them."""

import sqlite3
from contextlib import AbstractContextManager
from dataclasses import dataclass

from app.storage.db import transaction

# The queries below select the active receipts of a year with
# `substr(purchase_date, 1, 4) = ?`, the year as four-digit text; NULL dates never match.


@dataclass(frozen=True)
class YearCounts:
    """Active receipts dated in a year, and how many of them are unreviewed."""

    receipts: int
    unreviewed: int


@dataclass(frozen=True)
class ArchiveRun:
    """What one archiving moved; `images` are (receipt id, file name in the done folder)."""

    receipts: int
    lines: int
    images: list[tuple[int, str]]


@dataclass(frozen=True)
class ArchivedYearRow:
    year: int
    receipts: int
    lines: int
    images: int


@dataclass(frozen=True)
class CandidateRow:
    year: int
    receipts: int
    lines: int
    images: int
    unreviewed: int


@dataclass(frozen=True)
class ArchiveLineRow:
    """An archived line with its receipt's purchase date, for the year totals."""

    purchase_date: str
    amount_cents: int
    product_name: str
    category_name: str | None
    group_name: str | None
    is_deposit_refund: bool


class ArchiveRepository:
    """Archive queries on one connection. Callers own the transaction."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def transaction(self) -> AbstractContextManager[None]:
        return transaction(self._connection)

    def year_counts(self, year: int) -> YearCounts:
        row = self._connection.execute(
            "SELECT count(*), coalesce(sum(reviewed = 0), 0) FROM receipts"
            " WHERE substr(purchase_date, 1, 4) = ?",
            (f"{year:04d}",),
        ).fetchone()
        return YearCounts(receipts=row[0], unreviewed=row[1])

    def archive_year(self, year: int, archived_at: str) -> ArchiveRun:
        """Copy the year's active receipts and lines into the archive and delete them from
        the active tables. Product, category and group are copied as names (P3 step 4)."""
        key = (f"{year:04d}",)
        images = [
            (row["id"], row["file_name"])
            for row in self._connection.execute(
                "SELECT id, file_name FROM receipts"
                " WHERE file_name IS NOT NULL AND substr(purchase_date, 1, 4) = ? ORDER BY id",
                key,
            )
        ]
        receipts = self._connection.execute(
            "INSERT INTO archived_receipts (id, year, purchase_date, store, total_cents,"
            " image_hash, file_name, imported_at, archived_at)"
            " SELECT id, ?, purchase_date, store, total_cents, image_hash, file_name,"
            " imported_at, ? FROM receipts WHERE substr(purchase_date, 1, 4) = ?",
            (year, archived_at, *key),
        ).rowcount
        lines = self._connection.execute(
            "INSERT INTO archived_lines (id, receipt_id, position, name, product_name,"
            " amount_cents, is_deposit_refund, category_name, group_name)"
            " SELECT l.id, l.receipt_id, l.position, l.name, coalesce(p.name, l.name),"
            " l.amount_cents, l.is_deposit_refund, c.name, g.name"
            " FROM receipt_lines AS l"
            " JOIN receipts AS r ON r.id = l.receipt_id"
            " LEFT JOIN categories AS c ON c.id = l.category_id"
            " LEFT JOIN categories AS g ON g.id = c.parent_id"
            " LEFT JOIN products AS p ON p.id = l.product_id"
            " WHERE substr(r.purchase_date, 1, 4) = ?",
            key,
        ).rowcount
        # The lines go with their receipts (ON DELETE CASCADE).
        self._connection.execute("DELETE FROM receipts WHERE substr(purchase_date, 1, 4) = ?", key)
        return ArchiveRun(receipts=receipts, lines=lines, images=images)

    def set_file_names(self, names: list[tuple[int, str]]) -> None:
        """Store each moved image's name in the archive folder."""
        self._connection.executemany(
            "UPDATE archived_receipts SET file_name = ? WHERE id = ?",
            [(name, receipt_id) for receipt_id, name in names],
        )

    def archived(self) -> list[ArchivedYearRow]:
        rows = self._connection.execute(
            "SELECT r.year, count(*) AS receipts,"
            " coalesce(sum((SELECT count(*) FROM archived_lines AS l"
            " WHERE l.receipt_id = r.id)), 0) AS lines,"
            " count(r.file_name) AS images"
            " FROM archived_receipts AS r GROUP BY r.year ORDER BY r.year DESC"
        )
        return [
            ArchivedYearRow(row["year"], row["receipts"], row["lines"], row["images"])
            for row in rows
        ]

    def candidates(self, before_year: int) -> list[CandidateRow]:
        """Years before `before_year` with active dated receipts, newest first."""
        rows = self._connection.execute(
            "SELECT CAST(substr(r.purchase_date, 1, 4) AS INTEGER) AS year,"
            " count(*) AS receipts,"
            " coalesce(sum((SELECT count(*) FROM receipt_lines AS l"
            " WHERE l.receipt_id = r.id)), 0) AS lines,"
            " count(r.file_name) AS images, sum(r.reviewed = 0) AS unreviewed"
            " FROM receipts AS r WHERE r.purchase_date IS NOT NULL"
            " GROUP BY year HAVING year < ? ORDER BY year DESC",
            (before_year,),
        )
        return [
            CandidateRow(
                row["year"], row["receipts"], row["lines"], row["images"], row["unreviewed"]
            )
            for row in rows
        ]

    def delete_year(self, year: int) -> tuple[int, int]:
        """Delete the year's archived receipts and lines; returns their counts."""
        lines = self._connection.execute(
            "SELECT count(*) FROM archived_lines AS l"
            " JOIN archived_receipts AS r ON r.id = l.receipt_id WHERE r.year = ?",
            (year,),
        ).fetchone()[0]
        receipts = self._connection.execute(
            "DELETE FROM archived_receipts WHERE year = ?", (year,)
        ).rowcount
        return receipts, lines

    def has_year(self, year: int) -> bool:
        row = self._connection.execute(
            "SELECT EXISTS (SELECT 1 FROM archived_receipts WHERE year = ?)", (year,)
        ).fetchone()
        return bool(row[0])

    def year_lines(self, year: int) -> list[ArchiveLineRow]:
        rows = self._connection.execute(
            "SELECT r.purchase_date, l.amount_cents, l.product_name, l.category_name,"
            " l.group_name, l.is_deposit_refund"
            " FROM archived_lines AS l JOIN archived_receipts AS r ON r.id = l.receipt_id"
            " WHERE r.year = ? ORDER BY r.purchase_date, r.id, l.position",
            (year,),
        )
        return [
            ArchiveLineRow(
                row["purchase_date"],
                row["amount_cents"],
                row["product_name"],
                row["category_name"],
                row["group_name"],
                bool(row["is_deposit_refund"]),
            )
            for row in rows
        ]

    def archived_years(self, first_year: int, last_year: int) -> list[int]:
        """The archived years from `first_year` to `last_year`, ascending."""
        rows = self._connection.execute(
            "SELECT DISTINCT year FROM archived_receipts WHERE year BETWEEN ? AND ? ORDER BY year",
            (first_year, last_year),
        )
        return [row[0] for row in rows]

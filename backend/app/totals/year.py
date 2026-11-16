"""Totals of the current year per group, category and product (year with products spec).

The tree is the archived year's (archiving PC11), built from the current catalog names, so
the page and its CSV file look like an archived year's."""

from dataclasses import dataclass
from datetime import date

from app.calculation.archive_totals import ArchiveLine, ArchiveTotals, archive_totals
from app.storage.receipt_repository import ReceiptRepository


@dataclass(frozen=True)
class YearTotals:
    totals: ArchiveTotals
    # Unreviewed receipts of the year are not in the totals; the page tells how many (PC4).
    unreviewed: int


def read_year_totals(receipts: ReceiptRepository, year: int) -> YearTotals:
    """The year's totals of reviewed receipts, read in one transaction; shared with the CSV
    export, so the file and the page agree (PC5)."""
    start, end = f"{year:04d}-01-01", f"{year:04d}-12-31"
    with receipts.transaction():
        rows = receipts.year_lines(start, end)
        unreviewed = receipts.count_unreviewed(start, end)
    lines = [
        ArchiveLine(
            date.fromisoformat(row.purchase_date),
            row.amount_cents,
            row.product_name,
            row.category_name,
            row.group_name,
            row.is_deposit_refund,
        )
        for row in rows
    ]
    return YearTotals(archive_totals(year, lines), unreviewed)

"""The totals service split for export (export spec P4): period() and read()."""

import sqlite3

import pytest

from app.calculation.period import parse_period
from app.storage.archive_repository import ArchiveRepository
from app.storage.catalog_repository import CatalogRepository
from app.storage.receipt_repository import LineCategory, ReceiptRepository
from app.totals.errors import InvalidPeriodError
from app.totals.service import TotalsService


def service(db: sqlite3.Connection) -> TotalsService:
    return TotalsService(CatalogRepository(db), ReceiptRepository(db), ArchiveRepository(db))


@pytest.mark.parametrize(
    ("unit", "first", "last"),
    [(None, "2026-10", "2026-10"), ("month", "2026-13", "2026-13"), ("day", "1", "1")],
)
def test_export_ac8_period_refuses_an_invalid_period(
    db: sqlite3.Connection, unit: str | None, first: str, last: str
) -> None:
    with pytest.raises(InvalidPeriodError):
        service(db).period(unit, first, last)


def test_period_parses_a_valid_period(db: sqlite3.Connection) -> None:
    assert service(db).period("week", "2026-W40", "2026-W41") == parse_period(
        "week", "2026-W40", "2026-W41"
    )


def test_export_ac3_read_gives_the_same_totals_as_the_view(db: sqlite3.Connection) -> None:
    catalog = CatalogRepository(db)
    leivat = catalog.add_category("Leivät", "leivät", "category", None)
    receipts = ReceiptRepository(db)
    receipt = receipts.add("1" * 64, "a.jpg", "2026-11-02T10:00:00Z", purchase_date="2026-10-06")
    receipts.add_line(
        receipt.id,
        1,
        "Ruisleipä",
        300,
        is_deposit_refund=False,
        category=LineCategory(leivat, "user", None),
    )
    october = parse_period("month", "2026-10", "2026-10")

    totals = service(db).read(october)

    assert totals == service(db).totals("month", "2026-10", "2026-10").totals
    assert totals.month_totals == [300]

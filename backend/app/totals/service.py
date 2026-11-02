"""Totals of a period from the database (totals spec PC2, P4). The sums are in calculation."""

from dataclasses import dataclass
from datetime import date

from app.calculation.period import PeriodError, parse_period
from app.calculation.period_totals import PeriodTotals, RowCategory, TotalLine, period_totals
from app.categorization.service import CategoryService
from app.storage.catalog_repository import CatalogRepository
from app.storage.receipt_repository import ReceiptRepository
from app.totals.errors import InvalidPeriodError


@dataclass(frozen=True)
class TotalsView:
    totals: PeriodTotals
    unreviewed_receipts: int
    undated_receipts: int


class TotalsService:
    def __init__(self, catalog: CatalogRepository, receipts: ReceiptRepository) -> None:
        self._catalog = catalog
        self._receipts = receipts

    def totals(self, unit: str | None, first: str | None, last: str | None) -> TotalsView:
        """Raises: InvalidPeriodError."""
        try:
            period = parse_period(unit, first, last)
        except PeriodError as error:
            raise InvalidPeriodError from error
        start, end = period.start.isoformat(), period.end.isoformat()
        # One transaction, so the lines, the counts and the catalog agree.
        with self._receipts.transaction():
            lines = [
                TotalLine(
                    date.fromisoformat(row.purchase_date),
                    row.amount_cents,
                    row.category_id,
                    is_deposit_refund=row.is_deposit_refund,
                )
                for row in self._receipts.dated_lines(start, end)
            ]
            unreviewed = self._receipts.count_unreviewed(start, end)
            undated = self._receipts.count_undated()
            catalog = [
                RowCategory(row.id, row.name, row.kind, row.parent_id)
                for row in CategoryService(self._catalog).list()
            ]
        return TotalsView(period_totals(period, lines, catalog), unreviewed, undated)

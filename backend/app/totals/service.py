"""Totals of a period from the database (totals spec PC2, P4). The sums are in calculation."""

from dataclasses import dataclass
from datetime import date

from app.calculation.period import Period, PeriodError, parse_period
from app.calculation.period_totals import PeriodTotals, RowCategory, TotalLine, period_totals
from app.categorization.service import CategoryService
from app.storage.archive_repository import ArchiveRepository
from app.storage.catalog_repository import CatalogRepository
from app.storage.receipt_repository import ReceiptRepository
from app.totals.errors import InvalidPeriodError


@dataclass(frozen=True)
class TotalsView:
    totals: PeriodTotals
    unreviewed_receipts: int
    undated_receipts: int
    # Archived years that overlap the period; their receipts are not counted (archiving PC10).
    archived_years: list[int]


class TotalsService:
    def __init__(
        self, catalog: CatalogRepository, receipts: ReceiptRepository, archive: ArchiveRepository
    ) -> None:
        self._catalog = catalog
        self._receipts = receipts
        self._archive = archive

    def totals(self, unit: str | None, first: str | None, last: str | None) -> TotalsView:
        """Raises: InvalidPeriodError."""
        period = self.period(unit, first, last)
        start, end = period.start.isoformat(), period.end.isoformat()
        # One transaction, so the lines, the counts and the catalog agree.
        with self._receipts.transaction():
            totals = self.read(period)
            unreviewed = self._receipts.count_unreviewed(start, end)
            undated = self._receipts.count_undated()
            archived = self._archive.archived_years(period.start.year, period.end.year)
        return TotalsView(totals, unreviewed, undated, archived)

    def period(self, unit: str | None, first: str | None, last: str | None) -> Period:
        """Raises: InvalidPeriodError."""
        try:
            return parse_period(unit, first, last)
        except PeriodError as error:
            raise InvalidPeriodError from error

    def read(self, period: Period) -> PeriodTotals:
        """The totals of the period. Opens no transaction: the caller holds one."""
        lines = [
            TotalLine(
                date.fromisoformat(row.purchase_date),
                row.amount_cents,
                row.category_id,
                is_deposit_refund=row.is_deposit_refund,
            )
            for row in self._receipts.dated_lines(period.start.isoformat(), period.end.isoformat())
        ]
        catalog = [
            RowCategory(row.id, row.name, row.kind, row.parent_id)
            for row in CategoryService(self._catalog).list()
        ]
        return period_totals(period, lines, catalog)

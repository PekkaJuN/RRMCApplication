"""Monthly budgets and their comparison from the database (budget spec P7).

The sums are in calculation.
"""

from dataclasses import dataclass
from datetime import date

from app.budget.errors import InvalidBudgetAmountError, NotABudgetRowError
from app.calculation.budget_comparison import (
    BudgetRow,
    Comparison,
    budget_comparison,
    budget_rows,
)
from app.calculation.money import AMOUNT_LIMIT
from app.calculation.period import PeriodError, comparison_period
from app.calculation.period_totals import RowCategory, TotalLine
from app.categorization.errors import NotFoundError
from app.categorization.service import CategoryService
from app.storage.archive_repository import ArchiveRepository
from app.storage.catalog_repository import CatalogRepository
from app.storage.receipt_repository import ReceiptRepository
from app.totals.errors import InvalidPeriodError


@dataclass(frozen=True)
class BudgetView:
    rows: list[BudgetRow]
    total_cents: int


@dataclass(frozen=True)
class ComparisonView:
    comparison: Comparison
    kind: str
    unreviewed_receipts: int
    undated_receipts: int
    # Archived years that overlap the period (archiving spec PC10).
    archived_years: list[int]


class BudgetService:
    def __init__(
        self, catalog: CatalogRepository, receipts: ReceiptRepository, archive: ArchiveRepository
    ) -> None:
        self._catalog = catalog
        self._receipts = receipts
        self._archive = archive

    def rows(self) -> BudgetView:
        with self._catalog.transaction():
            rows = budget_rows(self._catalog_rows(), self._catalog.budgets())
        return BudgetView(rows, sum(row.amount_cents for row in rows))

    def save(self, item_id: int, amount_cents: int) -> BudgetView:
        """Raises: NotFoundError, NotABudgetRowError, InvalidBudgetAmountError."""
        with self._catalog.transaction():
            item = self._catalog.get_category(item_id)
            if item is None:
                raise NotFoundError()
            if item.parent_id is not None:
                raise NotABudgetRowError()
            if not 0 <= amount_cents <= AMOUNT_LIMIT:
                raise InvalidBudgetAmountError()
            self._catalog.set_budget(item.id, amount_cents)
        return self.rows()

    def comparison(self, month: str | None, kind: str | None) -> ComparisonView:
        """Raises: InvalidPeriodError."""
        try:
            period = comparison_period(month, kind)
        except PeriodError as error:
            raise InvalidPeriodError from error
        start, end = period.start.isoformat(), period.end.isoformat()
        # One transaction, so the lines, the budgets, the counts and the catalog agree.
        with self._receipts.transaction():
            lines = [
                TotalLine(
                    date.fromisoformat(row.purchase_date),
                    row.amount_cents,
                    row.category_id,
                    is_deposit_refund=row.is_deposit_refund,
                )
                for row in self._receipts.dated_lines(start, end, reviewed_only=True)
            ]
            comparison = budget_comparison(
                period, lines, self._catalog_rows(), self._catalog.budgets()
            )
            unreviewed = self._receipts.count_unreviewed(start, end)
            undated = self._receipts.count_undated()
            archived = self._archive.archived_years(period.start.year, period.end.year)
        return ComparisonView(comparison, kind or "calendar", unreviewed, undated, archived)

    def _catalog_rows(self) -> list[RowCategory]:
        return [
            RowCategory(row.id, row.name, row.kind, row.parent_id)
            for row in CategoryService(self._catalog).list()
        ]

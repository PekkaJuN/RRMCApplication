"""The period's lines and totals for the exporters (export spec P4, PDF export spec P7)."""

from collections.abc import Callable
from datetime import date

from app import texts
from app.budget.service import BudgetService
from app.calculation.period import Unit
from app.errors import AppError
from app.export.exporter import (
    ComparisonReport,
    Exporter,
    ExportFile,
    ExportLine,
    ReportExporter,
    TotalsReport,
)
from app.export.limits import check_pdf_length
from app.storage.catalog_repository import CatalogRepository
from app.storage.receipt_repository import ReceiptRepository
from app.totals.service import TotalsService


class ExportService:
    def __init__(
        self,
        catalog: CatalogRepository,
        receipts: ReceiptRepository,
        exporter: Exporter,
        report_exporter: ReportExporter,
        today: Callable[[], date],
    ) -> None:
        self._receipts = receipts
        self._totals = TotalsService(catalog, receipts)
        self._budget = BudgetService(catalog, receipts)
        self._exporter = exporter
        self._report_exporter = report_exporter
        self._today = today

    def lines_file(self, unit: str | None, first: str | None, last: str | None) -> ExportFile:
        """Raises: InvalidPeriodError."""
        period = self._totals.period(unit, first, last)
        with self._receipts.transaction():
            rows = self._receipts.export_lines(period.start.isoformat(), period.end.isoformat())
        lines = [
            ExportLine(
                purchase_date=date.fromisoformat(row.purchase_date),
                store=row.store,
                name=row.name,
                amount_cents=row.amount_cents,
                is_deposit_refund=row.is_deposit_refund,
                group_name=row.group_name,
                category_name=row.category_name,
                reviewed=row.reviewed,
            )
            for row in rows
        ]
        return self._exporter.lines_file(period, lines)

    def totals_file(
        self, unit: str | None, first: str | None, last: str | None, by: str | None
    ) -> ExportFile:
        """Raises: InvalidPeriodError, then AppError `invalid_request` for a bad `by`."""
        period = self._totals.period(unit, first, last)
        by_unit = _by(by)
        # One transaction, so the lines and the catalog agree.
        with self._receipts.transaction():
            totals = self._totals.read(period)
        return self._exporter.totals_file(totals, by_unit)

    def totals_pdf(
        self, unit: str | None, first: str | None, last: str | None, by: str | None
    ) -> ExportFile:
        """Raises: InvalidPeriodError, AppError `invalid_request`, PeriodTooLongError,
        in this order (PDF export spec PC8)."""
        period = self._totals.period(unit, first, last)
        by_unit = _by(by)
        check_pdf_length(period, by_unit)
        # The same view as the Yhteenveto page: totals and both counts in one transaction.
        view = self._totals.totals(unit, first, last)
        report = TotalsReport(
            view.totals, view.unreviewed_receipts, view.undated_receipts, self._today()
        )
        return self._report_exporter.totals_report(report, by_unit)

    def comparison_pdf(self, month: str | None, kind: str | None) -> ExportFile:
        """Raises: InvalidPeriodError."""
        view = self._budget.comparison(month, kind)
        report = ComparisonReport(
            view.comparison,
            view.kind,
            view.unreviewed_receipts,
            view.undated_receipts,
            self._today(),
        )
        return self._report_exporter.comparison_report(report)


def _by(by: str | None) -> Unit:
    if by == "week" or by == "month":
        return by
    raise AppError("invalid_request", texts.INVALID_REQUEST, 422)

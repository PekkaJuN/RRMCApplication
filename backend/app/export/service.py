"""The period's lines and totals for the exporter (export spec P4)."""

from datetime import date

from app import texts
from app.errors import AppError
from app.export.exporter import Exporter, ExportFile, ExportLine
from app.storage.catalog_repository import CatalogRepository
from app.storage.receipt_repository import ReceiptRepository
from app.totals.service import TotalsService


class ExportService:
    def __init__(
        self, catalog: CatalogRepository, receipts: ReceiptRepository, exporter: Exporter
    ) -> None:
        self._receipts = receipts
        self._totals = TotalsService(catalog, receipts)
        self._exporter = exporter

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
        if by == "week" or by == "month":
            # One transaction, so the lines and the catalog agree.
            with self._receipts.transaction():
                totals = self._totals.read(period)
            return self._exporter.totals_file(totals, by)
        raise AppError("invalid_request", texts.INVALID_REQUEST, 422)

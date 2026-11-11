"""The exporter interface (export spec PC1, P1): the endpoints build files only through it."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from app.calculation.budget_comparison import Comparison
from app.calculation.period import Period, Unit
from app.calculation.period_totals import PeriodTotals


@dataclass(frozen=True)
class ExportFile:
    name: str
    media_type: str
    content: bytes


@dataclass(frozen=True)
class ExportLine:
    """A receipt line with what the lines file shows of its receipt and category."""

    purchase_date: date
    store: str | None
    name: str
    amount_cents: int
    is_deposit_refund: bool
    group_name: str | None
    category_name: str | None
    reviewed: bool


class Exporter(Protocol):
    def lines_file(self, period: Period, lines: Sequence[ExportLine]) -> ExportFile: ...

    def totals_file(self, totals: PeriodTotals, by: Unit) -> ExportFile:
        """The totals of the week columns (`by` `week`) or the month columns (`month`)."""
        ...

    def comparison_file(self, comparison: Comparison, kind: str, *, weeks: bool) -> ExportFile:
        """The budget comparison of a `calendar` or `mid` period, with or without its weeks
        (comparison CSV export spec P4)."""
        ...


@dataclass(frozen=True)
class TotalsReport:
    """What the Yhteenveto page shows of a period, and the day the file is made."""

    totals: PeriodTotals
    unreviewed_receipts: int
    undated_receipts: int
    created: date


@dataclass(frozen=True)
class ComparisonReport:
    """What the Vertailu page shows of a comparison period (`kind` `calendar` or `mid`)."""

    comparison: Comparison
    kind: str
    unreviewed_receipts: int
    undated_receipts: int
    created: date


class ReportExporter(Protocol):
    """Files of a whole report (PDF export spec PC1, P2), beside the CSV `Exporter`.

    Two small protocols instead of one: a report file has no lines file, and the CSV totals
    file needs no counts.
    """

    def totals_report(self, report: TotalsReport, by: Unit) -> ExportFile: ...

    def comparison_report(self, report: ComparisonReport) -> ExportFile: ...

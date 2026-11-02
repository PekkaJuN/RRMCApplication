"""The exporter interface (export spec PC1, P1): the endpoints build files only through it."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Protocol

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

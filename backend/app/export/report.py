"""Rows of the totals PDF files: every group expanded (PDF export spec PC4, P3)."""

from dataclasses import dataclass

from app import texts
from app.calculation.period import Period, Unit
from app.calculation.period_totals import PeriodTotals, TotalsRow
from app.export.limits import MONTH_DAYS, period_days


@dataclass(frozen=True)
class ReportRow:
    """A row of a PDF table: `level` 1 is a category inside a group."""

    name: str
    level: int
    bold: bool
    amounts: list[int]


def expanded_rows(totals: PeriodTotals, by: Unit) -> list[ReportRow]:
    """The Yhteenveto rows with every group's categories under it, then `Yhteensä`."""

    def amounts(row: TotalsRow) -> list[int]:
        return row.weeks if by == "week" else row.months

    rows: list[ReportRow] = []
    for row in totals.rows:
        name = row.name if row.name is not None else texts.NO_CATEGORY
        rows.append(ReportRow(name, 0, row.kind == "group", amounts(row)))
        rows.extend(
            ReportRow(child.name or texts.NO_CATEGORY, 1, False, amounts(child))
            for child in row.categories
        )
    total = totals.week_totals if by == "week" else totals.month_totals
    rows.append(ReportRow(texts.TOTAL, 0, True, total))
    return rows


def period_rows(totals: PeriodTotals) -> list[ReportRow]:
    """The rows of the period block: each row's total over the whole period."""
    return [
        ReportRow(row.name, row.level, row.bold, [sum(row.amounts)])
        for row in expanded_rows(totals, "month")
    ]


def has_period_block(period: Period) -> bool:
    """A period of one month's length, also mid-month, would repeat its month blocks."""
    return period_days(period) > MONTH_DAYS


def has_lines(totals: PeriodTotals) -> bool:
    """Whether any line is counted; the totals hold a row only for counted lines."""
    return bool(totals.rows)

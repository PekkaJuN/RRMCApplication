"""Rows of the comparison CSV file in long format (comparison CSV export spec PC3, PC4, P2)."""

from dataclasses import dataclass
from datetime import date

from app.calculation.budget_comparison import Comparison
from app.calculation.period_totals import RowKind


@dataclass(frozen=True)
class ComparisonCsvRow:
    """A budget row in one block: the whole period (`block` None) or one week column."""

    block: str | None
    start: date
    end: date
    partial: bool
    kind: RowKind
    name: str | None
    budget_cents: int
    actual_cents: int
    remaining_cents: int


def comparison_rows(comparison: Comparison, *, weeks: bool) -> list[ComparisonCsvRow]:
    """The whole period's block, then with `weeks` one block per week in date order.

    Each block lists the rows in the page's order. The total is not a row (PC4).
    """
    period = comparison.period
    rows = [
        ComparisonCsvRow(
            None,
            period.start,
            period.end,
            False,
            row.kind,
            row.name,
            row.budget_cents,
            row.actual_cents,
            row.remaining_cents,
        )
        for row in comparison.rows
    ]
    if weeks:
        for index, column in enumerate(comparison.weeks):
            for row in comparison.rows:
                figures = row.weeks[index]
                rows.append(
                    ComparisonCsvRow(
                        column.key,
                        column.start,
                        column.end,
                        column.partial,
                        row.kind,
                        row.name,
                        figures.budget_cents,
                        figures.actual_cents,
                        figures.remaining_cents,
                    )
                )
    return rows

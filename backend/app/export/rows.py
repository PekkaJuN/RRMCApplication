"""Rows of the totals file in long format (export spec PC3, P3)."""

from dataclasses import dataclass

from app import texts
from app.calculation.period import Column, Unit
from app.calculation.period_totals import PeriodTotals, TotalsRow


@dataclass(frozen=True)
class LongRow:
    column: Column
    group_name: str | None
    category_name: str
    amount_cents: int


def long_rows(totals: PeriodTotals, by: Unit) -> list[LongRow]:
    """One row per column of kind `by` and category with counted lines in that column.

    Group sums are left out: a pivot table computes them from the group name.
    """
    leaves: list[tuple[str | None, TotalsRow]] = []
    for row in totals.rows:
        if row.kind == "group":
            leaves.extend((row.name, child) for child in row.categories)
        else:
            leaves.append((None, row))
    columns = totals.weeks if by == "week" else totals.months
    result: list[LongRow] = []
    for index, column in enumerate(columns):
        for group_name, leaf in leaves:
            amounts, counts = (
                (leaf.weeks, leaf.week_counts) if by == "week" else (leaf.months, leaf.month_counts)
            )
            if counts[index] > 0:
                name = leaf.name if leaf.name is not None else texts.NO_CATEGORY
                result.append(LongRow(column, group_name, name, amounts[index]))
    return result

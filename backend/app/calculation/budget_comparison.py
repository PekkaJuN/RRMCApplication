"""Budget rows and the comparison with actual spending, in integer cents (budget spec P4)."""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from app.calculation.period import Column, Period
from app.calculation.period_totals import (
    RowCategory,
    RowKind,
    TotalLine,
    TotalsRow,
    period_totals,
)


@dataclass(frozen=True)
class BudgetRow:
    """A group or a category without a group, with its monthly budget."""

    kind: RowKind
    id: int
    name: str
    amount_cents: int


@dataclass(frozen=True)
class WeekFigures:
    budget_cents: int
    actual_cents: int


@dataclass(frozen=True)
class ComparisonRow:
    kind: RowKind
    id: int | None
    name: str | None
    budget_cents: int
    actual_cents: int
    remaining_cents: int
    weeks: list[WeekFigures]


@dataclass(frozen=True)
class ComparisonTotal:
    budget_cents: int
    actual_cents: int
    remaining_cents: int
    weeks: list[WeekFigures]


@dataclass(frozen=True)
class Comparison:
    period: Period
    weeks: list[Column]
    rows: list[ComparisonRow]
    total: ComparisonTotal


def budget_rows(catalog: Sequence[RowCategory], budgets: Mapping[int, int]) -> list[BudgetRow]:
    """The budget rows in catalog order; a category inside a group is not one."""
    return [
        BudgetRow(item.kind, item.id, item.name, budgets.get(item.id, 0))
        for item in catalog
        if item.kind == "group" or item.parent_id is None
    ]


def weekly_budget(amount_cents: int, period: Period, weeks: Sequence[Column]) -> list[int]:
    """Each week's share by its days in the period.

    A week is the difference of two cumulative shares, so rounding cannot change the sum:
    the weeks always add up to `amount_cents`.
    """
    days = (period.end - period.start).days + 1

    def share(day: int) -> int:
        # The first `day` days' share, half up. An amount is never negative.
        return (2 * amount_cents * day + days) // (2 * days)

    return [
        share((week.end - period.start).days + 1) - share((week.start - period.start).days)
        for week in weeks
    ]


def budget_comparison(
    period: Period,
    lines: Iterable[TotalLine],
    catalog: Sequence[RowCategory],
    budgets: Mapping[int, int],
) -> Comparison:
    """The figures of every budget row. The spending rules are those of `period_totals`."""
    totals = period_totals(period, lines, catalog)
    weeks = totals.weeks
    spent = {(row.kind, row.id): row for row in totals.rows}

    def row_of(
        kind: RowKind, item_id: int | None, name: str | None, budget_cents: int
    ) -> ComparisonRow:
        actual = _week_amounts(spent.get((kind, item_id)), len(weeks))
        figures = [
            WeekFigures(budget, amount)
            for budget, amount in zip(
                weekly_budget(budget_cents, period, weeks), actual, strict=True
            )
        ]
        return ComparisonRow(
            kind,
            item_id,
            name,
            budget_cents,
            sum(actual),
            budget_cents - sum(actual),
            figures,
        )

    rows = [
        row_of(row.kind, row.id, row.name, row.amount_cents)
        for row in budget_rows(catalog, budgets)
    ]
    if ("none", None) in spent:
        rows.append(row_of("none", None, None, 0))
    return Comparison(period, weeks, rows, _total(rows, len(weeks)))


def _week_amounts(row: TotalsRow | None, width: int) -> list[int]:
    return row.weeks if row is not None else [0] * width


def _total(rows: Sequence[ComparisonRow], width: int) -> ComparisonTotal:
    budget_cents = sum(row.budget_cents for row in rows)
    actual_cents = sum(row.actual_cents for row in rows)
    weeks = [
        WeekFigures(
            sum(row.weeks[index].budget_cents for row in rows),
            sum(row.weeks[index].actual_cents for row in rows),
        )
        for index in range(width)
    ]
    return ComparisonTotal(budget_cents, actual_cents, budget_cents - actual_cents, weeks)

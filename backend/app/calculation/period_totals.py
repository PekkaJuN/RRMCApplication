"""Category and group totals per week and month of a period (totals spec PC1, P2)."""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from app.calculation.period import Column, Period

RowKind = Literal["group", "category", "none"]


@dataclass(frozen=True)
class TotalLine:
    purchase_date: date
    amount_cents: int
    category_id: int | None
    is_deposit_refund: bool


@dataclass(frozen=True)
class RowCategory:
    """A catalog item: a group or a category, given in catalog order."""

    id: int
    name: str
    kind: Literal["group", "category"]
    parent_id: int | None


@dataclass(frozen=True)
class TotalsRow:
    kind: RowKind
    id: int | None
    name: str | None
    weeks: list[int]
    months: list[int]
    categories: list["TotalsRow"] = field(default_factory=lambda: list[TotalsRow]())


@dataclass(frozen=True)
class PeriodTotals:
    period: Period
    weeks: list[Column]
    months: list[Column]
    rows: list[TotalsRow]
    week_totals: list[int]
    month_totals: list[int]


def period_totals(
    period: Period, lines: Iterable[TotalLine], catalog: Sequence[RowCategory]
) -> PeriodTotals:
    weeks, months = period.week_columns(), period.month_columns()
    week_index = {column.key: index for index, column in enumerate(weeks)}
    month_index = {column.key: index for index, column in enumerate(months)}
    # Amounts per category id (None: no category), one list entry per column.
    week_sums: dict[int | None, list[int]] = defaultdict(lambda: [0] * len(weeks))
    month_sums: dict[int | None, list[int]] = defaultdict(lambda: [0] * len(months))
    for line in lines:
        # Deposit refunds are not spending (FR-44).
        if line.is_deposit_refund or not period.contains(line.purchase_date):
            continue
        year, week, _ = line.purchase_date.isocalendar()
        day = line.purchase_date
        week_sums[line.category_id][week_index[f"{year:04d}-W{week:02d}"]] += line.amount_cents
        month_sums[line.category_id][month_index[f"{day.year:04d}-{day.month:02d}"]] += (
            line.amount_cents
        )

    def category_row(item: RowCategory) -> TotalsRow:
        return TotalsRow("category", item.id, item.name, week_sums[item.id], month_sums[item.id])

    rows: list[TotalsRow] = []
    for item in catalog:
        if item.kind == "group":
            members = [
                category_row(child)
                for child in catalog
                if child.parent_id == item.id and child.id in week_sums
            ]
            if members:
                rows.append(
                    TotalsRow(
                        "group",
                        item.id,
                        item.name,
                        _column_sums([row.weeks for row in members], len(weeks)),
                        _column_sums([row.months for row in members], len(months)),
                        members,
                    )
                )
        elif item.parent_id is None and item.id in week_sums:
            rows.append(category_row(item))
    if None in week_sums:
        rows.append(TotalsRow("none", None, None, week_sums[None], month_sums[None]))
    return PeriodTotals(
        period=period,
        weeks=weeks,
        months=months,
        rows=rows,
        week_totals=_column_sums([row.weeks for row in rows], len(weeks)),
        month_totals=_column_sums([row.months for row in rows], len(months)),
    )


def _column_sums(amounts: Sequence[Sequence[int]], width: int) -> list[int]:
    return [sum(row[index] for row in amounts) for index in range(width)]

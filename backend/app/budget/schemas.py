"""API schemas of /api/budget (budget spec, API shape)."""

from typing import Self

from pydantic import BaseModel, ConfigDict, StrictInt

from app.budget.service import BudgetView, ComparisonView
from app.calculation.budget_comparison import BudgetRow, ComparisonRow, WeekFigures
from app.calculation.period_totals import RowKind
from app.totals.schemas import ColumnOut


class BudgetUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount_cents: StrictInt


class BudgetRowOut(BaseModel):
    kind: RowKind
    id: int
    name: str
    amount_cents: int

    @classmethod
    def from_row(cls, row: BudgetRow) -> Self:
        return cls(kind=row.kind, id=row.id, name=row.name, amount_cents=row.amount_cents)


class BudgetOut(BaseModel):
    rows: list[BudgetRowOut]
    total_cents: int

    @classmethod
    def from_view(cls, view: BudgetView) -> Self:
        return cls(
            rows=[BudgetRowOut.from_row(row) for row in view.rows],
            total_cents=view.total_cents,
        )


class WeekFiguresOut(BaseModel):
    budget_cents: int
    actual_cents: int

    @classmethod
    def from_figures(cls, figures: WeekFigures) -> Self:
        return cls(budget_cents=figures.budget_cents, actual_cents=figures.actual_cents)


class ComparisonRowOut(BaseModel):
    kind: RowKind
    id: int | None
    name: str | None
    budget_cents: int
    actual_cents: int
    remaining_cents: int
    weeks: list[WeekFiguresOut]

    @classmethod
    def from_row(cls, row: ComparisonRow) -> Self:
        return cls(
            kind=row.kind,
            id=row.id,
            name=row.name,
            budget_cents=row.budget_cents,
            actual_cents=row.actual_cents,
            remaining_cents=row.remaining_cents,
            weeks=[WeekFiguresOut.from_figures(week) for week in row.weeks],
        )


class ComparisonTotalOut(BaseModel):
    budget_cents: int
    actual_cents: int
    remaining_cents: int
    weeks: list[WeekFiguresOut]


class ComparisonOut(BaseModel):
    month: str
    period: str
    start_date: str
    end_date: str
    weeks: list[ColumnOut]
    rows: list[ComparisonRowOut]
    total: ComparisonTotalOut
    unreviewed_receipts: int
    undated_receipts: int

    @classmethod
    def from_view(cls, view: ComparisonView) -> Self:
        comparison, period, total = view.comparison, view.comparison.period, view.comparison.total
        return cls(
            month=period.first,
            period=view.kind,
            start_date=period.start.isoformat(),
            end_date=period.end.isoformat(),
            weeks=[ColumnOut.from_column(column) for column in comparison.weeks],
            rows=[ComparisonRowOut.from_row(row) for row in comparison.rows],
            total=ComparisonTotalOut(
                budget_cents=total.budget_cents,
                actual_cents=total.actual_cents,
                remaining_cents=total.remaining_cents,
                weeks=[WeekFiguresOut.from_figures(week) for week in total.weeks],
            ),
            unreviewed_receipts=view.unreviewed_receipts,
            undated_receipts=view.undated_receipts,
        )

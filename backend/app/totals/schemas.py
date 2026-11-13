"""API schemas of /api/totals (totals spec, API shape)."""

from typing import Self

from pydantic import BaseModel, Field

from app.calculation.period import Column
from app.calculation.period_totals import RowKind, TotalsRow
from app.totals.service import TotalsView


class ColumnOut(BaseModel):
    key: str
    start_date: str
    end_date: str
    partial: bool

    @classmethod
    def from_column(cls, column: Column) -> Self:
        return cls(
            key=column.key,
            start_date=column.start.isoformat(),
            end_date=column.end.isoformat(),
            partial=column.partial,
        )


class TotalsRowOut(BaseModel):
    kind: RowKind
    id: int | None
    name: str | None
    weeks: list[int]
    months: list[int]
    categories: list["TotalsRowOut"]

    @classmethod
    def from_row(cls, row: TotalsRow) -> Self:
        return cls(
            kind=row.kind,
            id=row.id,
            name=row.name,
            weeks=row.weeks,
            months=row.months,
            categories=[cls.from_row(child) for child in row.categories],
        )


class TotalsOut(BaseModel):
    unit: str
    # `from` is a Python keyword.
    from_: str = Field(serialization_alias="from")
    to: str
    start_date: str
    end_date: str
    weeks: list[ColumnOut]
    months: list[ColumnOut]
    rows: list[TotalsRowOut]
    week_totals: list[int]
    month_totals: list[int]
    unreviewed_receipts: int
    undated_receipts: int
    archived_years: list[int]

    @classmethod
    def from_view(cls, view: TotalsView) -> Self:
        totals, period = view.totals, view.totals.period
        return cls(
            unit=period.unit,
            from_=period.first,
            to=period.last,
            start_date=period.start.isoformat(),
            end_date=period.end.isoformat(),
            weeks=[ColumnOut.from_column(column) for column in totals.weeks],
            months=[ColumnOut.from_column(column) for column in totals.months],
            rows=[TotalsRowOut.from_row(row) for row in totals.rows],
            week_totals=totals.week_totals,
            month_totals=totals.month_totals,
            unreviewed_receipts=view.unreviewed_receipts,
            undated_receipts=view.undated_receipts,
            archived_years=view.archived_years,
        )

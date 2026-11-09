"""Synthetic reports for the PDF exporter tests: the PDF export spec's fixture."""

from collections.abc import Mapping, Sequence
from datetime import date

from app.calculation.budget_comparison import budget_comparison
from app.calculation.period import comparison_period, parse_period
from app.calculation.period_totals import RowCategory, TotalLine, period_totals
from app.export.exporter import ComparisonReport, TotalsReport

RUOKA, LEIVAT, MAITO, JUOMAT = 1, 12, 13, 30
CATALOG = [
    RowCategory(RUOKA, "Ruoka", "group", None),
    RowCategory(LEIVAT, "Leivät", "category", RUOKA),
    RowCategory(MAITO, "Maitotuotteet", "category", RUOKA),
    RowCategory(JUOMAT, "Juomat", "category", None),
]
CREATED = date(2026, 11, 9)
# Receipt A (unreviewed), receipt B and receipt C.
UNREVIEWED_LINES = [TotalLine(date(2026, 10, 2), 125, MAITO, is_deposit_refund=False)]
REVIEWED_LINES = [
    TotalLine(date(2026, 10, 6), 300, LEIVAT, is_deposit_refund=False),
    TotalLine(date(2026, 10, 6), 250, JUOMAT, is_deposit_refund=False),
    TotalLine(date(2026, 10, 6), 199, None, is_deposit_refund=False),
    TotalLine(date(2026, 10, 6), -40, None, is_deposit_refund=True),
    TotalLine(date(2026, 11, 1), 999, LEIVAT, is_deposit_refund=False),
]
LINES = UNREVIEWED_LINES + REVIEWED_LINES
BUDGETS = {RUOKA: 40000, JUOMAT: 5000}


def totals_report(
    unit: str,
    first: str,
    last: str,
    *,
    lines: Sequence[TotalLine] = LINES,
    catalog: Sequence[RowCategory] = CATALOG,
    unreviewed: int = 1,
    undated: int = 0,
) -> TotalsReport:
    totals = period_totals(parse_period(unit, first, last), lines, catalog)
    return TotalsReport(totals, unreviewed, undated, CREATED)


def comparison_report(
    month: str,
    kind: str = "calendar",
    *,
    lines: Sequence[TotalLine] = REVIEWED_LINES,
    budgets: Mapping[int, int] = BUDGETS,
    unreviewed: int = 1,
    undated: int = 0,
) -> ComparisonReport:
    comparison = budget_comparison(comparison_period(month, kind), lines, CATALOG, budgets)
    return ComparisonReport(comparison, kind, unreviewed, undated, CREATED)


def standalone_catalog(count: int) -> list[RowCategory]:
    """`Kategoria 01` … as categories without a group, ids from 100."""
    return [
        RowCategory(100 + n, f"Kategoria {n:02d}", "category", None) for n in range(1, count + 1)
    ]


def one_line_each(catalog: Sequence[RowCategory], days: Sequence[date]) -> list[TotalLine]:
    return [
        TotalLine(day, 100, item.id, is_deposit_refund=False) for item in catalog for day in days
    ]

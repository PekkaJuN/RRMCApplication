"""The synthetic example of the comparison CSV export spec (its Acceptance Criteria)."""

from collections.abc import Mapping, Sequence
from datetime import date

from app.calculation.budget_comparison import Comparison, budget_comparison
from app.calculation.period import comparison_period
from app.calculation.period_totals import RowCategory, TotalLine

RUOKA, MAITO, JUOMAT = 1, 13, 30
CATALOG = [
    RowCategory(RUOKA, "Ruoka", "group", None),
    RowCategory(MAITO, "Maitotuotteet", "category", RUOKA),
    RowCategory(JUOMAT, "Juomat", "category", None),
]
BUDGETS = {RUOKA: 40000, JUOMAT: 5000}
LINES = [
    TotalLine(date(2026, 10, 1), 12500, MAITO, is_deposit_refund=False),
    TotalLine(date(2026, 10, 6), 1250, JUOMAT, is_deposit_refund=False),
    TotalLine(date(2026, 10, 6), 199, None, is_deposit_refund=False),
]


def comparison(
    month: str = "2026-10",
    kind: str = "calendar",
    *,
    lines: Sequence[TotalLine] = LINES,
    catalog: Sequence[RowCategory] = CATALOG,
    budgets: Mapping[int, int] = BUDGETS,
) -> Comparison:
    return budget_comparison(comparison_period(month, kind), lines, catalog, budgets)

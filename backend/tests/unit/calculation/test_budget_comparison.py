from datetime import date

import pytest

from app.calculation.budget_comparison import (
    BudgetRow,
    ComparisonRow,
    WeekFigures,
    budget_comparison,
    budget_rows,
    weekly_budget,
)
from app.calculation.period import comparison_period
from app.calculation.period_totals import RowCategory, TotalLine

RUOKA = RowCategory(1, "Ruoka", "group", None)
MAITO = RowCategory(2, "Maitotuotteet", "category", 1)
AUTO = RowCategory(20, "Auto", "category", None)
JUOMAT = RowCategory(30, "Juomat", "category", None)
CATALOG = [RUOKA, MAITO, AUTO, JUOMAT]
BUDGETS = {1: 40000, 30: 5000}
OCTOBER = comparison_period("2026-10", None)


def line(day: date, cents: int, category_id: int | None, *, refund: bool = False) -> TotalLine:
    return TotalLine(day, cents, category_id, is_deposit_refund=refund)


def row_of(rows: list[ComparisonRow], name: str | None) -> ComparisonRow:
    return next(row for row in rows if row.name == name)


def weekly(amount: int, month: str, kind: str | None = None) -> list[int]:
    period = comparison_period(month, kind)
    return weekly_budget(amount, period, period.week_columns())


# Budget rows


def test_ac1_rows_are_groups_and_standalone_categories_in_catalog_order() -> None:
    assert budget_rows(CATALOG, {}) == [
        BudgetRow("group", 1, "Ruoka", 0),
        BudgetRow("category", 20, "Auto", 0),
        BudgetRow("category", 30, "Juomat", 0),
    ]


def test_ac2_rows_carry_their_saved_amounts() -> None:
    rows = budget_rows(CATALOG, BUDGETS)

    assert [row.amount_cents for row in rows] == [40000, 0, 5000]


# Weekly budget


@pytest.mark.parametrize(
    ("amount", "expected"),
    [(10000, [1290, 2258, 2258, 2259, 1935]), (31000, [4000, 7000, 7000, 7000, 6000])],
)
def test_ac5_weekly_budgets_follow_the_days(amount: int, expected: list[int]) -> None:
    assert weekly(amount, "2026-10") == expected
    assert sum(expected) == amount


def test_ac5_a_zero_budget_gives_zero_weeks() -> None:
    assert weekly(0, "2026-10") == [0, 0, 0, 0, 0]


def test_ac6_rounding_in_a_month_of_four_whole_weeks() -> None:
    assert weekly(10002, "2027-02") == [2501, 2500, 2501, 2500]


@pytest.mark.parametrize("amount", [1, 7, 99, 10001, 99_999_999, 199_999_998])
@pytest.mark.parametrize("month", ["2026-10", "2026-12", "2027-02", "2028-02"])
@pytest.mark.parametrize("kind", ["calendar", "mid"])
def test_ac5_ac27_weekly_budgets_add_up_to_the_month(amount: int, month: str, kind: str) -> None:
    assert sum(weekly(amount, month, kind)) == amount


def test_ac27_weekly_budgets_of_a_mid_period() -> None:
    assert weekly(5000, "2026-10", "mid") == [645, 1129, 1129, 1129, 968]


def test_ac28_weekly_budgets_of_a_mid_period_across_the_year() -> None:
    assert weekly(10000, "2026-12", "mid") == [1935, 2259, 2258, 2258, 1290]


def test_ac28_weekly_budgets_of_a_mid_period_over_february() -> None:
    assert weekly(10002, "2027-02", "mid") == [2501, 2500, 2501, 2500]


# Comparison


def test_ac6_the_weekly_total_sums_the_rows() -> None:
    catalog = [JUOMAT, AUTO]
    period = comparison_period("2027-02", None)

    comparison = budget_comparison(period, [], catalog, {20: 10002, 30: 10002})

    assert [row.weeks[0].budget_cents for row in comparison.rows] == [2501, 2501]
    assert [week.budget_cents for week in comparison.total.weeks] == [5002, 5000, 5002, 5000]
    assert not any(week.partial for week in comparison.weeks)


def test_ac8_over_budget_gives_a_negative_remaining() -> None:
    lines = [line(date(2026, 10, 2), 5100, 30)]

    juomat = row_of(budget_comparison(OCTOBER, lines, CATALOG, BUDGETS).rows, "Juomat")

    assert juomat.remaining_cents == -100
    assert juomat.weeks[0] == WeekFigures(645, 5100)


def test_ac10_lines_fall_in_their_weeks_and_lines_outside_are_left_out() -> None:
    lines = [line(date(2026, 10, 2), 100, 30), line(date(2026, 11, 1), 999, 30)]

    juomat = row_of(budget_comparison(OCTOBER, lines, CATALOG, BUDGETS).rows, "Juomat")

    assert [week.budget_cents for week in juomat.weeks] == [645, 1129, 1129, 1129, 968]
    assert [week.actual_cents for week in juomat.weeks] == [100, 0, 0, 0, 0]


def test_ac11_a_week_of_the_previous_iso_year() -> None:
    period = comparison_period("2027-01", None)
    lines = [line(date(2027, 1, 2), 100, 30)]

    comparison = budget_comparison(period, lines, CATALOG, BUDGETS)

    first = comparison.weeks[0]
    assert (first.key, first.start, first.end) == (
        "2026-W53",
        date(2027, 1, 1),
        date(2027, 1, 3),
    )
    assert first.partial
    assert row_of(comparison.rows, "Juomat").weeks[0] == WeekFigures(484, 100)


def test_ac12_deposit_refunds_do_not_count() -> None:
    lines = [
        line(date(2026, 10, 5), 229, 2),
        line(date(2026, 10, 5), -40, None, refund=True),
    ]

    comparison = budget_comparison(OCTOBER, lines, CATALOG, BUDGETS)

    assert row_of(comparison.rows, "Ruoka").actual_cents == 229
    assert all(row.kind != "none" for row in comparison.rows)


def test_ac13_lines_without_a_category_are_the_last_row() -> None:
    lines = [line(date(2026, 10, 5), 300, 30), line(date(2026, 10, 5), 199, None)]

    comparison = budget_comparison(OCTOBER, lines, CATALOG, BUDGETS)

    last = comparison.rows[-1]
    assert (last.kind, last.id, last.name) == ("none", None, None)
    assert (last.budget_cents, last.actual_cents, last.remaining_cents) == (0, 199, -199)
    assert comparison.total.actual_cents == 499


def test_ac14_a_month_without_lines_lists_every_row() -> None:
    comparison = budget_comparison(OCTOBER, [], CATALOG, BUDGETS)

    assert [row.name for row in comparison.rows] == ["Ruoka", "Auto", "Juomat"]
    assert all(row.actual_cents == 0 for row in comparison.rows)
    assert comparison.total.budget_cents == 45000
    assert comparison.total.remaining_cents == 45000


def test_ac23_a_category_in_a_group_counts_toward_the_group() -> None:
    lines = [line(date(2026, 10, 5), 125, 2)]

    ruoka = row_of(budget_comparison(OCTOBER, lines, CATALOG, BUDGETS).rows, "Ruoka")

    assert (ruoka.actual_cents, ruoka.remaining_cents) == (125, 39875)


def test_ac24_a_standalone_category_counts_toward_its_own_row() -> None:
    catalog = [RUOKA, RowCategory(2, "Maitotuotteet", "category", None)]
    lines = [line(date(2026, 10, 5), 125, 2)]

    rows = budget_comparison(OCTOBER, lines, catalog, BUDGETS).rows

    assert row_of(rows, "Ruoka").actual_cents == 0
    assert row_of(rows, "Maitotuotteet").actual_cents == 125


def test_ac27_the_figures_of_a_mid_period() -> None:
    period = comparison_period("2026-10", "mid")
    lines = [line(date(2026, 10, 15), 100, 30), line(date(2026, 11, 14), 200, 30)]

    juomat = row_of(budget_comparison(period, lines, CATALOG, BUDGETS).rows, "Juomat")

    assert (juomat.budget_cents, juomat.actual_cents, juomat.remaining_cents) == (5000, 300, 4700)
    assert [week.actual_cents for week in juomat.weeks] == [100, 0, 0, 0, 200]


def test_ac8_the_total_of_a_week_sums_budget_and_actual() -> None:
    lines = [line(date(2026, 10, 2), 5100, 30), line(date(2026, 10, 3), 100, 2)]

    total = budget_comparison(OCTOBER, lines, CATALOG, BUDGETS).total

    assert total.weeks[0] == WeekFigures(5161 + 645, 5200)
    assert total.actual_cents == 5200
    assert total.remaining_cents == 39800

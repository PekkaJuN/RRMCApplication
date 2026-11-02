"""Rows of the totals file in long format (export spec PC3, P3)."""

from datetime import date

from app.calculation.period import parse_period
from app.calculation.period_totals import RowCategory, TotalLine, period_totals
from app.export.rows import LongRow, long_rows

RUOKA, LEIVAT, MAITO, JUOMAT = 1, 12, 13, 30
CATALOG = [
    RowCategory(RUOKA, "Ruoka", "group", None),
    RowCategory(LEIVAT, "Leivät", "category", RUOKA),
    RowCategory(MAITO, "Maitotuotteet", "category", RUOKA),
    RowCategory(JUOMAT, "Juomat", "category", None),
]
OCTOBER = parse_period("month", "2026-10", "2026-10")
FIXTURE = [
    TotalLine(date(2026, 10, 2), 125, MAITO, is_deposit_refund=False),
    TotalLine(date(2026, 10, 6), 300, LEIVAT, is_deposit_refund=False),
    TotalLine(date(2026, 10, 6), 250, JUOMAT, is_deposit_refund=False),
    TotalLine(date(2026, 10, 6), 199, None, is_deposit_refund=False),
    TotalLine(date(2026, 10, 6), -40, None, is_deposit_refund=True),
    TotalLine(date(2026, 11, 1), 999, LEIVAT, is_deposit_refund=False),
]


def simple(rows: list[LongRow]) -> list[tuple[str, str | None, str, int]]:
    return [(row.column.key, row.group_name, row.category_name, row.amount_cents) for row in rows]


def test_ac2_weekly_rows_only_where_a_column_has_lines() -> None:
    rows = long_rows(period_totals(OCTOBER, FIXTURE, CATALOG), "week")
    assert simple(rows) == [
        ("2026-W40", "Ruoka", "Maitotuotteet", 125),
        ("2026-W41", "Ruoka", "Leivät", 300),
        ("2026-W41", None, "Juomat", 250),
        ("2026-W41", None, "Ei kategoriaa", 199),
    ]
    assert rows[0].column.partial
    assert (rows[0].column.start, rows[0].column.end) == (date(2026, 10, 1), date(2026, 10, 4))


def test_ac16_monthly_rows_in_category_order() -> None:
    rows = long_rows(period_totals(OCTOBER, FIXTURE, CATALOG), "month")
    assert simple(rows) == [
        ("2026-10", "Ruoka", "Leivät", 300),
        ("2026-10", "Ruoka", "Maitotuotteet", 125),
        ("2026-10", None, "Juomat", 250),
        ("2026-10", None, "Ei kategoriaa", 199),
    ]


def test_ac4_partial_months_of_a_week_period() -> None:
    period = parse_period("week", "2026-W40", "2026-W40")
    lines = [
        TotalLine(date(2026, 9, 30), 100, LEIVAT, is_deposit_refund=False),
        TotalLine(date(2026, 10, 1), 200, LEIVAT, is_deposit_refund=False),
    ]
    totals = period_totals(period, lines, CATALOG)
    assert simple(long_rows(totals, "week")) == [("2026-W40", "Ruoka", "Leivät", 300)]
    months = long_rows(totals, "month")
    assert simple(months) == [
        ("2026-09", "Ruoka", "Leivät", 100),
        ("2026-10", "Ruoka", "Leivät", 200),
    ]
    assert [row.column.partial for row in months] == [True, True]


def test_ac5_a_sum_of_zero_with_lines_is_listed() -> None:
    lines = [
        TotalLine(date(2026, 10, 5), 300, LEIVAT, is_deposit_refund=False),
        TotalLine(date(2026, 10, 5), -300, LEIVAT, is_deposit_refund=False),
    ]
    totals = period_totals(OCTOBER, lines, CATALOG)
    assert simple(long_rows(totals, "week")) == [("2026-W41", "Ruoka", "Leivät", 0)]
    assert simple(long_rows(totals, "month")) == [("2026-10", "Ruoka", "Leivät", 0)]


def test_ac7_no_lines_no_rows() -> None:
    totals = period_totals(OCTOBER, [], CATALOG)
    assert long_rows(totals, "week") == []
    assert long_rows(totals, "month") == []

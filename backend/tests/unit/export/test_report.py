"""Rows of the totals PDF files (PDF export spec PC4, P3)."""

from datetime import date

from app.calculation.period import parse_period
from app.calculation.period_totals import PeriodTotals, RowCategory, TotalLine, period_totals
from app.export.report import ReportRow, expanded_rows, has_lines, has_period_block, period_rows

RUOKA, LEIVAT, MAITO, JUOMAT = 1, 12, 13, 30
CATALOG = [
    RowCategory(RUOKA, "Ruoka", "group", None),
    RowCategory(LEIVAT, "Leivät", "category", RUOKA),
    RowCategory(MAITO, "Maitotuotteet", "category", RUOKA),
    RowCategory(JUOMAT, "Juomat", "category", None),
]
# The spec's fixture: receipts A, B and C.
LINES = [
    TotalLine(date(2026, 10, 2), 125, MAITO, is_deposit_refund=False),
    TotalLine(date(2026, 10, 6), 300, LEIVAT, is_deposit_refund=False),
    TotalLine(date(2026, 10, 6), 250, JUOMAT, is_deposit_refund=False),
    TotalLine(date(2026, 10, 6), 199, None, is_deposit_refund=False),
    TotalLine(date(2026, 10, 6), -40, None, is_deposit_refund=True),
    TotalLine(date(2026, 11, 1), 999, LEIVAT, is_deposit_refund=False),
]


def totals(unit: str, first: str, last: str, lines: list[TotalLine] = LINES) -> PeriodTotals:
    return period_totals(parse_period(unit, first, last), lines, CATALOG)


def test_ac2_groups_are_expanded_in_catalog_order() -> None:
    rows = expanded_rows(totals("month", "2026-10", "2026-10"), "week")
    assert [(row.name, row.level, row.bold) for row in rows] == [
        ("Ruoka", 0, True),
        ("Leivät", 1, False),
        ("Maitotuotteet", 1, False),
        ("Juomat", 0, False),
        ("Ei kategoriaa", 0, False),
        ("Yhteensä", 0, True),
    ]


def test_ac1_rows_hold_the_week_amounts() -> None:
    rows = expanded_rows(totals("month", "2026-10", "2026-10"), "week")
    by_name = {row.name: row.amounts for row in rows}
    assert by_name["Ruoka"] == [125, 300, 0, 0, 0]
    assert by_name["Maitotuotteet"] == [125, 0, 0, 0, 0]
    assert by_name["Ei kategoriaa"] == [0, 199, 0, 0, 0]
    assert by_name["Yhteensä"] == [125, 749, 0, 0, 0]


def test_ac3_rows_hold_the_month_amounts() -> None:
    rows = expanded_rows(totals("month", "2026-10", "2026-11"), "month")
    by_name = {row.name: row.amounts for row in rows}
    assert by_name["Leivät"] == [300, 999]
    assert by_name["Yhteensä"] == [874, 999]


def test_ac3_period_rows_add_each_rows_months() -> None:
    rows = period_rows(totals("month", "2026-10", "2026-11"))
    by_name = {row.name: row.amounts for row in rows}
    assert by_name["Leivät"] == [1299]
    assert by_name["Ruoka"] == [1424]
    assert by_name["Yhteensä"] == [1873]
    assert rows[0] == ReportRow("Ruoka", 0, True, [1424])


def test_ac4_period_block_only_for_a_period_over_31_days() -> None:
    assert not has_period_block(parse_period("month", "2026-10", "2026-10"))
    assert not has_period_block(parse_period("range", "2026-10-15", "2026-11-14"))
    assert has_period_block(parse_period("range", "2026-10-15", "2026-11-15"))
    assert has_period_block(parse_period("month", "2026-10", "2026-11"))


def test_ac10_has_lines() -> None:
    assert not has_lines(totals("month", "2026-12", "2026-12"))
    assert has_lines(totals("month", "2026-10", "2026-10"))
    zero = [TotalLine(date(2026, 12, 1), 0, JUOMAT, is_deposit_refund=False)]
    assert has_lines(totals("month", "2026-12", "2026-12", zero))


def test_ac4_a_period_of_deposit_refunds_only_has_no_lines() -> None:
    refund = [TotalLine(date(2026, 12, 1), -40, None, is_deposit_refund=True)]
    assert not has_lines(totals("month", "2026-12", "2026-12", refund))

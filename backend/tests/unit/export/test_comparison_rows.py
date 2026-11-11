"""Rows of the comparison CSV file (comparison CSV export spec PC3, PC4, P2)."""

from datetime import date

from app.export.comparison_rows import ComparisonCsvRow, comparison_rows
from tests.unit.export.comparison_data import comparison

OCT_1, OCT_4, OCT_31 = date(2026, 10, 1), date(2026, 10, 4), date(2026, 10, 31)


def test_ac1_without_weeks_the_whole_period_block_only() -> None:
    assert comparison_rows(comparison(), weeks=False) == [
        ComparisonCsvRow(None, OCT_1, OCT_31, False, "group", "Ruoka", 40000, 12500, 27500),
        ComparisonCsvRow(None, OCT_1, OCT_31, False, "category", "Juomat", 5000, 1250, 3750),
        ComparisonCsvRow(None, OCT_1, OCT_31, False, "none", None, 0, 199, -199),
    ]


def test_ac3_with_weeks_the_week_blocks_follow_in_date_order() -> None:
    rows = comparison_rows(comparison(), weeks=True)

    assert len(rows) == 3 * 6
    assert [row.block for row in rows[::3]] == [
        None,
        "2026-W40",
        "2026-W41",
        "2026-W42",
        "2026-W43",
        "2026-W44",
    ]
    assert rows[3:6] == [
        ComparisonCsvRow("2026-W40", OCT_1, OCT_4, True, "group", "Ruoka", 5161, 12500, -7339),
        ComparisonCsvRow("2026-W40", OCT_1, OCT_4, True, "category", "Juomat", 645, 0, 645),
        ComparisonCsvRow("2026-W40", OCT_1, OCT_4, True, "none", None, 0, 0, 0),
    ]
    assert [row.partial for row in rows[::3]] == [False, True, False, False, False, True]
    assert (rows[15].start, rows[15].end) == (date(2026, 10, 26), OCT_31)


def test_ac3_each_rows_week_budgets_add_up_to_its_budget() -> None:
    rows = comparison_rows(comparison(), weeks=True)

    for position in range(3):
        whole, *weeks = rows[position::3]
        assert sum(week.budget_cents for week in weeks) == whole.budget_cents
        assert sum(week.actual_cents for week in weeks) == whole.actual_cents


def test_ac6_mid_period_dates_and_weeks() -> None:
    rows = comparison_rows(comparison(kind="mid"), weeks=True)

    assert (rows[0].start, rows[0].end) == (date(2026, 10, 15), date(2026, 11, 14))
    assert (rows[3].block, rows[3].start, rows[3].end, rows[3].partial) == (
        "2026-W42",
        date(2026, 10, 15),
        date(2026, 10, 18),
        True,
    )
    assert (rows[-1].block, rows[-1].start, rows[-1].end, rows[-1].partial) == (
        "2026-W46",
        date(2026, 11, 9),
        date(2026, 11, 14),
        True,
    )


def test_ac7_every_budget_row_and_no_none_row_without_such_lines() -> None:
    rows = comparison_rows(comparison("2026-11"), weeks=False)

    figures = [(row.name, row.budget_cents, row.actual_cents, row.remaining_cents) for row in rows]
    assert figures == [("Ruoka", 40000, 0, 40000), ("Juomat", 5000, 0, 5000)]


def test_ac8_an_empty_catalog_gives_no_rows() -> None:
    assert comparison_rows(comparison("2026-11", lines=[], catalog=[]), weeks=True) == []


def test_pc4_the_total_is_never_a_row() -> None:
    rows = comparison_rows(comparison(), weeks=True)

    assert all(row.budget_cents != 45000 for row in rows)
    assert {row.kind for row in rows} == {"group", "category", "none"}

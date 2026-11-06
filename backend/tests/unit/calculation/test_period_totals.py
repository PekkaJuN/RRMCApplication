from datetime import date

from app.calculation.period import parse_period
from app.calculation.period_totals import RowCategory, TotalLine, TotalsRow, period_totals

RUOKA, MAITO, LEIPA, POLTTO = 1, 12, 13, 30
# Catalog order: each group followed by its categories, then the categories without a group.
CATALOG = [
    RowCategory(RUOKA, "Ruoka", "group", None),
    RowCategory(MAITO, "Maitotuotteet", "category", RUOKA),
    RowCategory(LEIPA, "Leipä", "category", RUOKA),
    RowCategory(POLTTO, "Polttoaineet", "category", None),
]
OCTOBER = parse_period("month", "2026-10", "2026-10")


def line(day: str, amount: int, category: int | None, *, refund: bool = False) -> TotalLine:
    return TotalLine(date.fromisoformat(day), amount, category, is_deposit_refund=refund)


def test_ac1_category_group_and_month_totals() -> None:
    lines = [line("2026-10-05", 125, MAITO), line("2026-10-05", 300, LEIPA)]
    lines.append(line("2026-10-20", 200, MAITO))
    totals = period_totals(OCTOBER, lines, CATALOG)
    [ruoka] = totals.rows
    assert (ruoka.kind, ruoka.id, ruoka.name, ruoka.months) == ("group", RUOKA, "Ruoka", [625])
    assert [(row.name, row.months) for row in ruoka.categories] == [
        ("Maitotuotteet", [325]),
        ("Leipä", [300]),
    ]
    assert totals.month_totals == [625]
    assert [column.key for column in totals.months] == ["2026-10"]


def test_ac2_week_amounts_and_lines_outside_the_period() -> None:
    lines = [
        line("2026-10-02", 100, LEIPA),
        line("2026-10-05", 300, LEIPA),
        line("2026-11-01", 999, LEIPA),
        line("2026-09-30", 999, LEIPA),
    ]
    totals = period_totals(OCTOBER, lines, CATALOG)
    [ruoka] = totals.rows
    assert ruoka.categories[0].weeks == [100, 300, 0, 0, 0]
    assert totals.week_totals == [100, 300, 0, 0, 0]
    assert totals.month_totals == [400]


def test_ac3_week_period_splits_months() -> None:
    period = parse_period("week", "2026-W40", "2026-W40")
    lines = [line("2026-09-30", 100, LEIPA), line("2026-10-01", 200, LEIPA)]
    totals = period_totals(period, lines, CATALOG)
    assert totals.week_totals == [300]
    assert totals.month_totals == [100, 200]


def test_ac5_week_53_line_in_january() -> None:
    period = parse_period("week", "2026-W53", "2026-W53")
    totals = period_totals(period, [line("2027-01-02", 100, LEIPA)], CATALOG)
    assert totals.week_totals == [100]
    assert totals.month_totals == [0, 100]


def test_ac6_deposit_refund_is_in_no_total() -> None:
    lines = [line("2026-10-05", 229, MAITO), line("2026-10-05", -40, None, refund=True)]
    totals = period_totals(OCTOBER, lines, CATALOG)
    assert [row.kind for row in totals.rows] == ["group"]
    assert totals.rows[0].categories[0].months == [229]
    assert totals.month_totals == [229]


def test_ac7_lines_without_category_form_the_last_row() -> None:
    lines = [line("2026-10-05", 199, None), line("2026-10-05", 300, LEIPA)]
    totals = period_totals(OCTOBER, lines, CATALOG)
    assert totals.rows[-1] == TotalsRow("none", None, None, [0, 199, 0, 0, 0], [199], [])
    assert totals.month_totals == [499]


def test_ac10_rows_follow_the_catalog_and_list_only_used_categories() -> None:
    lines = [line("2026-10-05", 5000, POLTTO), line("2026-10-06", 300, LEIPA)]
    totals = period_totals(OCTOBER, lines, CATALOG)
    assert [(row.kind, row.name) for row in totals.rows] == [
        ("group", "Ruoka"),
        ("category", "Polttoaineet"),
    ]
    assert [row.name for row in totals.rows[0].categories] == ["Leipä"]
    assert totals.rows[1].categories == []
    assert totals.month_totals == [5300]


def test_ac10_category_whose_lines_sum_to_zero_is_listed() -> None:
    lines = [line("2026-10-05", 300, LEIPA), line("2026-10-06", -300, LEIPA)]
    totals = period_totals(OCTOBER, lines, CATALOG)
    assert totals.rows[0].categories[0].months == [0]


def test_ac13_no_lines_gives_columns_and_zero_totals() -> None:
    totals = period_totals(parse_period("month", "2026-03", "2026-03"), [], CATALOG)
    assert totals.rows == []
    assert totals.week_totals == [0] * len(totals.weeks)
    assert totals.month_totals == [0]
    assert len(totals.weeks) == 6


def test_unknown_category_does_not_crash() -> None:
    # Cannot happen (ON DELETE RESTRICT); the line is then in no row.
    totals = period_totals(OCTOBER, [line("2026-10-05", 100, 999)], CATALOG)
    assert totals.rows == []
    assert totals.month_totals == [0]


def test_lines_in_a_year_below_1000_find_their_columns() -> None:
    period = parse_period("month", "0999-01", "0999-01")
    totals = period_totals(period, [line("0999-01-05", 100, LEIPA)], CATALOG)
    assert totals.month_totals == [100]


def test_export_ac5_line_counts_per_column() -> None:
    lines = [
        line("2026-10-05", 300, LEIPA),
        line("2026-10-05", -300, LEIPA),
        line("2026-10-06", 125, MAITO),
        line("2026-10-06", -40, None, refund=True),
        line("2026-11-01", 999, LEIPA),
    ]
    totals = period_totals(OCTOBER, lines, CATALOG)
    [ruoka] = totals.rows
    leipa = next(row for row in ruoka.categories if row.id == LEIPA)
    assert (leipa.months, leipa.month_counts) == ([0], [2])
    assert leipa.week_counts == [0, 2, 0, 0, 0]
    assert ruoka.month_counts == [3]
    assert ruoka.week_counts == [0, 3, 0, 0, 0]


def test_export_line_counts_of_the_no_category_row() -> None:
    totals = period_totals(OCTOBER, [line("2026-10-05", 199, None)], CATALOG)
    [none] = totals.rows
    assert (none.week_counts, none.month_counts) == ([0, 1, 0, 0, 0], [1])


def test_date_range_ac6_the_rules_stay_the_same() -> None:
    period = parse_period("range", "2026-10-15", "2026-11-14")
    lines = [
        line("2026-10-14", 999, MAITO),
        line("2026-10-15", 100, MAITO),
        line("2026-10-16", -40, None, refund=True),
        line("2026-11-14", 200, None),
        line("2026-11-15", 999, MAITO),
    ]

    totals = period_totals(period, lines, CATALOG)

    assert totals.month_totals == [100, 200]
    assert [row.kind for row in totals.rows] == ["group", "none"]

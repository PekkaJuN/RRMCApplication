from datetime import date

import pytest

from app.calculation.period import Column, PeriodError, parse_period


def test_ac1_one_month_covers_its_days() -> None:
    period = parse_period("month", "2026-10", "2026-10")
    assert (period.unit, period.first, period.last) == ("month", "2026-10", "2026-10")
    assert (period.start, period.end) == (date(2026, 10, 1), date(2026, 10, 31))


def test_ac1_month_range_ends_on_the_last_day_of_its_last_month() -> None:
    period = parse_period("month", "2026-11", "2027-02")
    assert (period.start, period.end) == (date(2026, 11, 1), date(2027, 2, 28))


def test_ac3_one_week_runs_from_monday_to_sunday() -> None:
    period = parse_period("week", "2026-W40", "2026-W40")
    assert (period.start, period.end) == (date(2026, 9, 28), date(2026, 10, 4))


def test_ac5_week_53_of_2026_exists() -> None:
    period = parse_period("week", "2026-W53", "2026-W53")
    assert (period.start, period.end) == (date(2026, 12, 28), date(2027, 1, 3))


@pytest.mark.parametrize(
    ("unit", "first", "last"),
    [
        ("day", "2026-10", "2026-10"),
        (None, "2026-10", "2026-10"),
        ("month", "2026-13", "2026-13"),
        ("month", "2026-1", "2026-1"),
        ("month", "2026-00", "2026-00"),
        ("month", "2026-W40", "2026-W40"),
        ("week", "2026-10", "2026-10"),
        ("week", "2026-W54", "2026-W54"),
        ("week", "2026-W00", "2026-W00"),
        ("week", "2027-W53", "2027-W53"),
        ("month", None, "2026-10"),
        ("month", "2026-10", None),
        ("month", "", ""),
        ("month", "2026-11", "2026-10"),
        ("week", "2026-W41", "2026-W40"),
        ("month", "2024-10", "2026-10"),
        ("week", "2025-W01", "2026-W53"),
        ("month", " 2026-10", "2026-10"),
        ("month", "2026-10\n", "2026-10"),
    ],
)
def test_ac12_invalid_period_is_refused(
    unit: str | None, first: str | None, last: str | None
) -> None:
    with pytest.raises(PeriodError):
        parse_period(unit, first, last)


def test_ac12_the_limits_are_accepted() -> None:
    assert parse_period("month", "2024-11", "2026-10").start == date(2024, 11, 1)
    assert parse_period("week", "2025-W01", "2026-W52").end == date(2026, 12, 27)


def test_ac2_month_has_partial_weeks_at_both_ends() -> None:
    period = parse_period("month", "2026-10", "2026-10")
    assert period.week_columns() == [
        Column("2026-W40", date(2026, 10, 1), date(2026, 10, 4), partial=True),
        Column("2026-W41", date(2026, 10, 5), date(2026, 10, 11), partial=False),
        Column("2026-W42", date(2026, 10, 12), date(2026, 10, 18), partial=False),
        Column("2026-W43", date(2026, 10, 19), date(2026, 10, 25), partial=False),
        Column("2026-W44", date(2026, 10, 26), date(2026, 10, 31), partial=True),
    ]
    assert period.month_columns() == [
        Column("2026-10", date(2026, 10, 1), date(2026, 10, 31), partial=False)
    ]


def test_ac3_week_period_has_partial_months() -> None:
    period = parse_period("week", "2026-W40", "2026-W40")
    assert period.week_columns() == [
        Column("2026-W40", date(2026, 9, 28), date(2026, 10, 4), partial=False)
    ]
    assert period.month_columns() == [
        Column("2026-09", date(2026, 9, 28), date(2026, 9, 30), partial=True),
        Column("2026-10", date(2026, 10, 1), date(2026, 10, 4), partial=True),
    ]


def test_ac4_first_week_of_the_year_starts_in_december() -> None:
    columns = parse_period("month", "2026-01", "2026-01").week_columns()
    assert columns[0] == Column("2026-W01", date(2026, 1, 1), date(2026, 1, 4), partial=True)
    assert columns[-1] == Column("2026-W05", date(2026, 1, 26), date(2026, 1, 31), partial=True)


def test_ac5_week_53_spans_two_years() -> None:
    period = parse_period("week", "2026-W53", "2026-W53")
    assert period.month_columns() == [
        Column("2026-12", date(2026, 12, 28), date(2026, 12, 31), partial=True),
        Column("2027-01", date(2027, 1, 1), date(2027, 1, 3), partial=True),
    ]


def test_ac2_whole_weeks_and_months_are_not_partial() -> None:
    # February 2027 starts on a Monday and ends on a Sunday: four whole weeks.
    period = parse_period("month", "2027-02", "2027-02")
    assert [column.partial for column in period.week_columns()] == [False] * 4
    assert [column.key for column in period.week_columns()] == [
        "2027-W05",
        "2027-W06",
        "2027-W07",
        "2027-W08",
    ]


@pytest.mark.parametrize(("unit", "value"), [("month", "0000-01"), ("week", "0000-W01")])
def test_ac12_year_zero_is_refused(unit: str, value: str) -> None:
    with pytest.raises(PeriodError):
        parse_period(unit, value, value)


@pytest.mark.parametrize(("unit", "value"), [("month", "9999-12"), ("week", "9999-W52")])
def test_ac12_year_9999_is_refused(unit: str, value: str) -> None:
    # Its columns would run past the last date Python can hold.
    with pytest.raises(PeriodError):
        parse_period(unit, value, value)


def test_column_keys_have_four_digit_years() -> None:
    period = parse_period("month", "0999-01", "0999-01")
    assert period.month_columns()[0].key == "0999-01"
    assert period.week_columns()[0].key == "0999-W01"

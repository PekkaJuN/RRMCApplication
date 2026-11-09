"""Length limits of the PDF files (PDF export spec PC8, P5)."""

import pytest

from app.calculation.period import Unit, parse_period
from app.export.errors import PeriodTooLongError
from app.export.limits import check_pdf_length


@pytest.mark.parametrize(
    ("unit", "first", "last", "by"),
    [
        ("range", "2026-10-01", "2026-10-31", "week"),  # AC6: 31 days
        ("week", "2026-W40", "2026-W43", "week"),  # AC7: 28 days
        ("month", "2026-01", "2026-12", "month"),  # AC8: 365 days
        ("range", "2026-01-15", "2027-01-14", "month"),  # AC8: 365 days, 13 months
        ("range", "2026-01-01", "2027-01-01", "month"),  # AC8: 366 days
    ],
)
def test_ac6_ac7_ac8_periods_within_the_limit_pass(
    unit: str, first: str, last: str, by: Unit
) -> None:
    check_pdf_length(parse_period(unit, first, last), by)


@pytest.mark.parametrize(
    ("unit", "first", "last", "by"),
    [
        ("range", "2026-10-01", "2026-11-01", "week"),  # AC6: 32 days
        ("week", "2026-W40", "2026-W44", "week"),  # AC7: 35 days
        ("range", "2026-01-01", "2027-01-02", "month"),  # AC8: 367 days
        ("month", "2026-01", "2027-01", "month"),  # AC8: 396 days
    ],
)
def test_ac6_ac7_ac8_periods_over_the_limit_are_refused(
    unit: str, first: str, last: str, by: Unit
) -> None:
    with pytest.raises(PeriodTooLongError) as raised:
        check_pdf_length(parse_period(unit, first, last), by)
    assert raised.value.code == "period_too_long"
    assert raised.value.status == 422
    assert raised.value.message == "Jakso on liian pitkä PDF-tiedostoon."

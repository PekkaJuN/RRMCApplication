"""Money, dates and column headings of the PDF files (PDF export spec PC4, PC6, P4)."""

from datetime import date

import pytest

from app.calculation.period import Column
from app.export.finnish import column_heading, day, money, month_label, week_label


@pytest.mark.parametrize(
    ("cents", "text"),
    [(125, "1,25 €"), (-40, "-0,40 €"), (0, "0,00 €"), (123456, "1234,56 €"), (5, "0,05 €")],
)
def test_pc6_money_as_on_the_pages(cents: int, text: str) -> None:
    assert money(cents) == text


def test_pc6_day_without_leading_zeros() -> None:
    assert day(date(2026, 10, 5)) == "5.10.2026"
    assert day(date(2027, 1, 14)) == "14.1.2027"


def test_ac1_week_and_month_labels() -> None:
    assert week_label("2026-W40") == "vk 40/2026"
    assert week_label("2027-W03") == "vk 3/2027"
    assert month_label("2027-01") == "1/2027"
    assert month_label("2026-10") == "10/2026"


def test_ac1_full_column_heading() -> None:
    column = Column("2026-W41", date(2026, 10, 5), date(2026, 10, 11), partial=False)
    assert column_heading(column, "week") == "vk 41/2026"


def test_ac1_partial_column_heading_shows_its_days() -> None:
    column = Column("2026-W40", date(2026, 10, 1), date(2026, 10, 4), partial=True)
    assert column_heading(column, "week") == "vk 40/2026 (osittainen) 1.10.–4.10.2026"


def test_ac4_partial_month_heading() -> None:
    column = Column("2026-10", date(2026, 10, 15), date(2026, 10, 31), partial=True)
    assert column_heading(column, "month") == "10/2026 (osittainen) 15.10.–31.10.2026"


def test_ac5_partial_heading_across_a_year_shows_both_years() -> None:
    column = Column("2026-W53", date(2026, 12, 30), date(2027, 1, 2), partial=True)
    assert column_heading(column, "week") == "vk 53/2026 (osittainen) 30.12.2026–2.1.2027"

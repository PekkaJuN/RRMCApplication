"""The year of an archive request (archiving spec PC3 step 1, AC9)."""

import pytest

from app.archive.errors import InvalidYearError
from app.archive.service import parse_year


@pytest.mark.parametrize("text", ["abcd", "1999", "10000", "02025", "", " 2025", "２０２５"])
def test_ac9_a_bad_year_is_invalid(text: str) -> None:
    with pytest.raises(InvalidYearError):
        parse_year(text)


@pytest.mark.parametrize(("text", "year"), [("2000", 2000), ("2025", 2025), ("9999", 9999)])
def test_ac9_a_four_digit_year_from_2000(text: str, year: int) -> None:
    assert parse_year(text) == year

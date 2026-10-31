import pytest

from app.review.errors import InvalidAmountError, InvalidDateError, InvalidStoreError
from app.review.fields import check_amount, check_date, check_store, check_total


@pytest.mark.parametrize("cents", [-99_999_999, -40, 0, 99_999_999])
def test_ac14_amount_in_range(cents: int) -> None:
    assert check_amount(cents) == cents


@pytest.mark.parametrize("cents", [-100_000_000, 100_000_000])
def test_ac14_amount_out_of_range(cents: int) -> None:
    with pytest.raises(InvalidAmountError) as raised:
        check_amount(cents)

    assert (raised.value.code, raised.value.message) == ("invalid_amount", "Summa ei kelpaa.")


@pytest.mark.parametrize("cents", [0, 99_999_999])
def test_ac21_total_in_range(cents: int) -> None:
    assert check_total(cents) == cents


@pytest.mark.parametrize("cents", [-1, 100_000_000])
def test_ac21_total_out_of_range(cents: int) -> None:
    with pytest.raises(InvalidAmountError):
        check_total(cents)


@pytest.mark.parametrize(
    ("text", "store"),
    [("  Uusi   kauppa ", "Uusi kauppa"), ("", ""), ("   ", ""), ("a" * 100, "a" * 100)],
)
def test_ac19_store_display_form(text: str, store: str) -> None:
    assert check_store(text) == store


def test_ac21_store_too_long() -> None:
    with pytest.raises(InvalidStoreError) as raised:
        check_store("a" * 101)

    assert (raised.value.code, raised.value.message) == (
        "invalid_store",
        "Kaupan nimi saa olla enintään 100 merkkiä.",
    )


def test_ac19_real_date() -> None:
    assert check_date("2026-10-06") == "2026-10-06"


@pytest.mark.parametrize(
    "text",
    ["2026-02-30", "5.10.2026", "", "20261005", "２０２６-10-06", "2026-10-06 ", "2026-1-06"],
)
def test_ac21_not_a_date(text: str) -> None:
    with pytest.raises(InvalidDateError) as raised:
        check_date(text)

    assert (raised.value.code, raised.value.message) == ("invalid_date", "Päivämäärä ei kelpaa.")

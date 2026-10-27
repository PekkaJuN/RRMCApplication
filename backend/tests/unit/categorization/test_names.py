import pytest

from app.categorization.errors import InvalidNameError
from app.categorization.names import (
    finnish_sort_key,
    normalize_display,
    normalize_key,
    validate_category_name,
    validate_product_name,
)


def test_ac3_ac16_display_name_is_trimmed_and_collapsed() -> None:
    assert normalize_display("  Kevytmaito   1L ") == "Kevytmaito 1L"


def test_ac16_display_name_collapses_tabs_and_newlines() -> None:
    assert normalize_display("Kevyt\t\nmaito") == "Kevyt maito"


def test_ac17_key_is_case_folded() -> None:
    assert normalize_key("KEVYTMAITO  1l") == "kevytmaito 1l"


def test_ac17_key_keeps_nordic_letters() -> None:
    assert normalize_key("RUISLEIPÄ ÅÖ") == "ruisleipä åö"


def test_ac17_key_is_nfc() -> None:
    assert normalize_key("ä") == "ä"


def test_ac17_display_name_is_nfc() -> None:
    assert normalize_display("ä") == "ä"


def test_ac23_finnish_order_puts_a_ring_a_diaeresis_and_o_diaeresis_after_z() -> None:
    names = ["Öljy", "Ananas", "Zucchini", "Äyriäiset", "Åkerbär"]

    assert sorted(names, key=finnish_sort_key) == [
        "Ananas",
        "Zucchini",
        "Åkerbär",
        "Äyriäiset",
        "Öljy",
    ]


def test_ac23_finnish_order_ignores_case() -> None:
    assert sorted(["leivät", "Juomat", "auto"], key=finnish_sort_key) == [
        "auto",
        "Juomat",
        "leivät",
    ]


@pytest.mark.parametrize("name", ["", "   "])
def test_ac5_empty_category_name_is_invalid(name: str) -> None:
    with pytest.raises(InvalidNameError):
        validate_category_name(name)


def test_ac5_category_name_of_50_characters_is_valid_and_51_is_not() -> None:
    assert validate_category_name("a" * 50) == "a" * 50
    with pytest.raises(InvalidNameError):
        validate_category_name("a" * 51)


def test_ac5_category_name_length_is_measured_after_normalization() -> None:
    assert validate_category_name("  " + "a" * 50 + "  ") == "a" * 50


@pytest.mark.parametrize("name", ["", "   "])
def test_ac18_empty_product_name_is_invalid(name: str) -> None:
    with pytest.raises(InvalidNameError):
        validate_product_name(name)


def test_ac18_product_name_of_100_characters_is_valid_and_101_is_not() -> None:
    assert validate_product_name("  " + "b" * 100 + "  ") == "b" * 100
    with pytest.raises(InvalidNameError):
        validate_product_name("b" * 101)

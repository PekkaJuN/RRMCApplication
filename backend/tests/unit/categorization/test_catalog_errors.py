import pytest

from app.categorization.errors import (
    CategoryHasProductsError,
    CategoryInUseError,
    DepositRefundLineError,
    DuplicateNameError,
    GroupNotEmptyError,
    InvalidParentError,
    NotACategoryError,
    NotFoundError,
    UnknownCategoryError,
)
from app.errors import AppError


@pytest.mark.parametrize(
    ("error", "code", "status"),
    [
        (DuplicateNameError.for_product(), "duplicate_name", 409),
        (DuplicateNameError.for_category(), "duplicate_name", 409),
        (InvalidParentError(), "invalid_parent", 422),
        (UnknownCategoryError(), "unknown_category", 422),
        (NotACategoryError(), "not_a_category", 422),
        (CategoryHasProductsError(), "category_has_products", 409),
        (NotFoundError(), "not_found", 404),
    ],
)
def test_ac4_ac10_ac12_ac19_ac26_ac33_codes_and_statuses(
    error: AppError, code: str, status: int
) -> None:
    assert (error.code, error.status) == (code, status)
    assert error.message
    assert error.extra == {}


def test_ac13_category_in_use_tells_the_product_count() -> None:
    error = CategoryInUseError(3)

    assert (error.code, error.status, error.extra) == ("category_in_use", 409, {"product_count": 3})
    assert error.message == "Kategoriaa käyttää 3 tuotetta."


def test_ac13_category_in_use_by_one_product_is_singular() -> None:
    assert CategoryInUseError(1).message == "Kategoriaa käyttää 1 tuote."


def test_ac14_group_not_empty_tells_the_category_count() -> None:
    error = GroupNotEmptyError(3)

    assert (error.code, error.status, error.extra) == (
        "group_not_empty",
        409,
        {"category_count": 3},
    )
    assert error.message == "Ryhmässä on 3 kategoriaa."


def test_ac14_group_with_one_category_is_singular() -> None:
    assert GroupNotEmptyError(1).message == "Ryhmässä on 1 kategoria."


# Categorization spec AC20, AC20b, AC16


@pytest.mark.parametrize(
    ("products", "lines", "message", "extra"),
    [
        (2, 3, "Kategoriaa käyttää 2 tuotetta ja 3 kuittiriviä.", {"line_count": 3}),
        (0, 1, "Kategoriaa käyttää 1 kuittirivi.", {"line_count": 1}),
        (1, 0, "Kategoriaa käyttää 1 tuote.", {}),
    ],
)
def test_ac20_category_in_use_tells_products_and_lines(
    products: int, lines: int, message: str, extra: dict[str, int]
) -> None:
    error = CategoryInUseError(products, lines)

    assert error.message == message
    assert error.extra == {"product_count": products, **extra}


def test_ac16_deposit_refund_line_error() -> None:
    error = DepositRefundLineError()

    assert (error.code, error.status, error.extra) == ("deposit_refund_line", 422, {})
    assert error.message == "Pantinpalautusriville ei voi valita kategoriaa."


def test_ac20_category_with_lines_cannot_become_a_group_text() -> None:
    assert CategoryHasProductsError().message == (
        "Kategoriaa, jossa on tuotteita tai kuittirivejä, ei voi muuttaa ryhmäksi."
    )

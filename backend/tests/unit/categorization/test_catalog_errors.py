import pytest

from app.categorization.errors import (
    CategoryHasProductsError,
    CategoryInUseError,
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

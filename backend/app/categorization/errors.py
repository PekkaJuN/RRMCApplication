"""Error codes of the catalog (product-management spec, Validation and API)."""

from app import texts
from app.errors import AppError


class InvalidNameError(AppError):
    def __init__(self, max_length: int) -> None:
        super().__init__("invalid_name", texts.invalid_name(max_length), 422)


class DuplicateNameError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__("duplicate_name", message, 409)

    @classmethod
    def for_product(cls) -> "DuplicateNameError":
        return cls(texts.DUPLICATE_PRODUCT_NAME)

    @classmethod
    def for_category(cls) -> "DuplicateNameError":
        return cls(texts.DUPLICATE_CATEGORY_NAME)


class InvalidParentError(AppError):
    def __init__(self) -> None:
        super().__init__("invalid_parent", texts.INVALID_PARENT, 422)


class UnknownCategoryError(AppError):
    def __init__(self) -> None:
        super().__init__("unknown_category", texts.UNKNOWN_CATEGORY, 422)


class NotACategoryError(AppError):
    def __init__(self) -> None:
        super().__init__("not_a_category", texts.NOT_A_CATEGORY, 422)


class CategoryHasProductsError(AppError):
    def __init__(self) -> None:
        super().__init__("category_has_products", texts.CATEGORY_HAS_PRODUCTS, 409)


class CategoryInUseError(AppError):
    def __init__(self, product_count: int) -> None:
        super().__init__(
            "category_in_use",
            texts.category_in_use(product_count),
            409,
            extra={"product_count": product_count},
        )


class GroupNotEmptyError(AppError):
    def __init__(self, category_count: int) -> None:
        super().__init__(
            "group_not_empty",
            texts.group_not_empty(category_count),
            409,
            extra={"category_count": category_count},
        )


class NotFoundError(AppError):
    def __init__(self) -> None:
        super().__init__("not_found", texts.NOT_FOUND, 404)

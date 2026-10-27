"""Name normalization, validation and Finnish sort order (product-management spec, PC6).

Every comparison of product, category or group names goes through these functions.
"""

import unicodedata

from app.categorization.errors import InvalidNameError

CATEGORY_NAME_MAX = 50
PRODUCT_NAME_MAX = 100

# Finnish sorts å, ä and ö after z; the next code points after "z" keep that order.
_FINNISH_ORDER = str.maketrans({"å": "{", "ä": "|", "ö": "}"})


def normalize_display(name: str) -> str:
    """The name as shown: NFC, trimmed, inner whitespace collapsed to one space."""
    return " ".join(unicodedata.normalize("NFC", name).split())


def normalize_key(name: str) -> str:
    """The name as compared: the display name, case-folded."""
    return normalize_display(name).casefold()


def finnish_sort_key(name: str) -> str:
    return normalize_key(name).translate(_FINNISH_ORDER)


def validate_category_name(name: str) -> str:
    """Return the display name of a group or category.

    Raises:
        InvalidNameError: it is empty or longer than 50 characters.
    """
    return _validate(name, CATEGORY_NAME_MAX)


def validate_product_name(name: str) -> str:
    """Return the display name of a product.

    Raises:
        InvalidNameError: it is empty or longer than 100 characters.
    """
    return _validate(name, PRODUCT_NAME_MAX)


def _validate(name: str, max_length: int) -> str:
    display = normalize_display(name)
    if not 1 <= len(display) <= max_length:
        raise InvalidNameError(max_length)
    return display

"""Checks of the values a user edits on a receipt (line-editing PC3, PC8). No I/O."""

import re
from datetime import date

from app.calculation.money import AMOUNT_LIMIT
from app.categorization.names import normalize_display
from app.review.errors import InvalidAmountError, InvalidDateError, InvalidStoreError

STORE_MAX = 100
# ASCII digits only: `\d` would also match other scripts' digits, and `date.fromisoformat`
# alone also accepts forms like `20261005`.
_ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def check_amount(cents: int) -> int:
    """A line amount; any sign. Raises: InvalidAmountError."""
    if not -AMOUNT_LIMIT <= cents <= AMOUNT_LIMIT:
        raise InvalidAmountError()
    return cents


def check_total(cents: int) -> int:
    """A receipt total, never negative. Raises: InvalidAmountError."""
    if not 0 <= cents <= AMOUNT_LIMIT:
        raise InvalidAmountError()
    return cents


def check_store(text: str) -> str:
    """The store as shown; `""` means no store. Raises: InvalidStoreError."""
    store = normalize_display(text)
    if len(store) > STORE_MAX:
        raise InvalidStoreError()
    return store


def check_date(text: str) -> str:
    """A real calendar date as `YYYY-MM-DD`. Raises: InvalidDateError."""
    if not _ISO_DATE.fullmatch(text):
        raise InvalidDateError()
    try:
        date.fromisoformat(text)
    except ValueError:
        raise InvalidDateError() from None
    return text

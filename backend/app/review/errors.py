"""Error codes of the receipt review and line editing (their specs, Error codes)."""

from app import texts
from app.errors import AppError


class ImageMissingError(AppError):
    def __init__(self) -> None:
        super().__init__("image_missing", texts.IMAGE_MISSING, 404)


class InvalidAmountError(AppError):
    def __init__(self) -> None:
        super().__init__("invalid_amount", texts.INVALID_AMOUNT, 422)


class DepositRefundAmountError(AppError):
    def __init__(self) -> None:
        super().__init__("deposit_refund_amount", texts.DEPOSIT_REFUND_AMOUNT, 422)


class InvalidDateError(AppError):
    def __init__(self) -> None:
        super().__init__("invalid_date", texts.INVALID_DATE, 422)


class InvalidStoreError(AppError):
    def __init__(self) -> None:
        super().__init__("invalid_store", texts.INVALID_STORE, 422)

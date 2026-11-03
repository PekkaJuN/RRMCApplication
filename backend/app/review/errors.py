"""Error codes of the receipt review and line editing (their specs, Error codes)."""

from app import texts
from app.errors import AppError


class ImageMissingError(AppError):
    def __init__(self) -> None:
        super().__init__("image_missing", texts.IMAGE_MISSING, 404)


class NoImageError(AppError):
    """A receipt typed in without an image (receipt-management PC6)."""

    def __init__(self) -> None:
        super().__init__("no_image", texts.NO_IMAGE, 404)


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


class ReceiptReviewedError(AppError):
    """A reviewed receipt cannot be deleted (receipt-management PC1)."""

    def __init__(self) -> None:
        super().__init__("receipt_reviewed", texts.RECEIPT_REVIEWED, 409)


class FoldersUnavailableError(AppError):
    """The failed folder cannot be listed (receipt-management PC7). The same code and text as
    the import's; review must not import from import."""

    def __init__(self) -> None:
        super().__init__("folders_unavailable", texts.FOLDERS_UNAVAILABLE, 503)


class ImageNotFoundError(AppError):
    """No usable failed image by that name: 404 for a preview (PC8), 422 for a new receipt
    (PC4 step 1)."""

    def __init__(self, status: int) -> None:
        super().__init__("image_not_found", texts.FAILED_IMAGE_NOT_FOUND, status)


class UnsupportedFormatError(AppError):
    """The chosen failed image is neither JPEG nor PNG (PC4 step 2); the import's text."""

    def __init__(self) -> None:
        super().__init__("unsupported_format", texts.UNSUPPORTED_FORMAT, 422)


class DuplicateImageError(AppError):
    """The chosen image is already some receipt's image (PC4 step 3)."""

    def __init__(self) -> None:
        super().__init__("duplicate_image", texts.DUPLICATE_IMAGE, 409)


class ImageMoveFailedError(AppError):
    """The image could not go to the done folder, so no receipt was created (PC4)."""

    def __init__(self) -> None:
        super().__init__("image_move_failed", texts.IMAGE_MOVE_FAILED, 503)

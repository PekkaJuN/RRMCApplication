"""Error codes of the receipt review (receipt-review spec, Error codes)."""

from app import texts
from app.errors import AppError


class ImageMissingError(AppError):
    def __init__(self) -> None:
        super().__init__("image_missing", texts.IMAGE_MISSING, 404)

"""Error codes of the totals (totals spec, Error codes)."""

from app import texts
from app.errors import AppError


class InvalidPeriodError(AppError):
    def __init__(self) -> None:
        super().__init__("invalid_period", texts.INVALID_PERIOD, 422)

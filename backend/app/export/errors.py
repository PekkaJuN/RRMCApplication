"""Error codes of the export (PDF export spec PC8)."""

from app import texts
from app.errors import AppError


class PeriodTooLongError(AppError):
    def __init__(self) -> None:
        super().__init__("period_too_long", texts.PERIOD_TOO_LONG, 422)

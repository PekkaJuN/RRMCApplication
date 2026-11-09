"""Length limits of the PDF files (PDF export spec PC8, P5).

The limits keep every column on one sheet width, so columns are never split over pages.
"""

from app.calculation.period import Period, Unit
from app.export.errors import PeriodTooLongError

# A month's period: also a 15th-to-14th period. Without a period block (PC4) at this length.
MONTH_DAYS = 31
# A year, also a leap year or a 15th-to-14th year with 13 month columns.
YEAR_DAYS = 366


def period_days(period: Period) -> int:
    return (period.end - period.start).days + 1


def check_pdf_length(period: Period, by: Unit) -> None:
    """Raises: PeriodTooLongError."""
    limit = MONTH_DAYS if by == "week" else YEAR_DAYS
    if period_days(period) > limit:
        raise PeriodTooLongError()

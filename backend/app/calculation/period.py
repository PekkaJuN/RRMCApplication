"""The period of the totals: whole calendar months or whole ISO weeks (totals spec PC3, P1).

A period's columns are the weeks and months that have a day in it, clipped to its days.
"""

import re
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

Unit = Literal["month", "week"]

MAX_MONTHS = 24
MAX_WEEKS = 104
# Years 1–9998: the columns of a period in 9999 would run past `date.max`.
MAX_YEAR = 9998

# fullmatch with explicit digits: `\d` would also accept non-ASCII digits.
_MONTH = re.compile(r"([0-9]{4})-(0[1-9]|1[0-2])")
_WEEK = re.compile(r"([0-9]{4})-W(0[1-9]|[1-4][0-9]|5[0-3])")


class PeriodError(ValueError):
    """The unit, a bound, their order or the length is not a valid period."""


@dataclass(frozen=True)
class Column:
    key: str
    start: date
    end: date
    partial: bool


@dataclass(frozen=True)
class Period:
    unit: Unit
    first: str
    last: str
    start: date
    end: date

    def contains(self, day: date) -> bool:
        return self.start <= day <= self.end

    def week_columns(self) -> list[Column]:
        columns: list[Column] = []
        monday = self.start - timedelta(days=self.start.weekday())
        while monday <= self.end:
            year, week, _ = monday.isocalendar()
            columns.append(
                self._clip(f"{year:04d}-W{week:02d}", monday, monday + timedelta(days=6))
            )
            monday += timedelta(days=7)
        return columns

    def month_columns(self) -> list[Column]:
        columns: list[Column] = []
        year, month = self.start.year, self.start.month
        while date(year, month, 1) <= self.end:
            first_day = date(year, month, 1)
            last_day = date(year, month, monthrange(year, month)[1])
            columns.append(self._clip(f"{year:04d}-{month:02d}", first_day, last_day))
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
        return columns

    def _clip(self, key: str, start: date, end: date) -> Column:
        clipped_start, clipped_end = max(start, self.start), min(end, self.end)
        partial = (clipped_start, clipped_end) != (start, end)
        return Column(key, clipped_start, clipped_end, partial=partial)


def parse_period(unit: str | None, first: str | None, last: str | None) -> Period:
    """The period from the request's values; `PeriodError` for every invalid one."""
    if first is None or last is None:
        raise PeriodError
    if unit == "month":
        first_year, first_month = _month(first)
        last_year, last_month = _month(last)
        length = (last_year * 12 + last_month) - (first_year * 12 + first_month) + 1
        if not 1 <= length <= MAX_MONTHS:
            raise PeriodError
        end = date(last_year, last_month, monthrange(last_year, last_month)[1])
        return Period("month", first, last, date(first_year, first_month, 1), end)
    if unit == "week":
        start = _monday(first)
        last_monday = _monday(last)
        length = (last_monday - start).days // 7 + 1
        if not 1 <= length <= MAX_WEEKS:
            raise PeriodError
        return Period("week", first, last, start, last_monday + timedelta(days=6))
    raise PeriodError


def _month(value: str) -> tuple[int, int]:
    match = _MONTH.fullmatch(value)
    if match is None or not 1 <= int(match[1]) <= MAX_YEAR:
        raise PeriodError
    return int(match[1]), int(match[2])


def _monday(value: str) -> date:
    match = _WEEK.fullmatch(value)
    if match is None or not 1 <= int(match[1]) <= MAX_YEAR:
        raise PeriodError
    try:
        # Raises for week 53 of a year that has only 52 weeks.
        return date.fromisocalendar(int(match[1]), int(match[2]), 1)
    except ValueError as error:
        raise PeriodError from error

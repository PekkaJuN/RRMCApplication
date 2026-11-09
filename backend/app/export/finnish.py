"""Money, dates and column headings as the pages show them (PDF export spec PC6, P4).

The same rules as the frontend's `format.ts` and `period.ts`, so a PDF reads like the page.
"""

from datetime import date

from app import texts
from app.calculation.period import Column, Unit


def money(cents: int) -> str:
    """`-40` → `-0,40 €`; no thousands separator."""
    sign = "-" if cents < 0 else ""
    euros, rest = divmod(abs(cents), 100)
    return f"{sign}{euros},{rest:02d} €"


def day(value: date) -> str:
    """`2026-10-05` → `5.10.2026`."""
    return f"{value.day}.{value.month}.{value.year}"


def week_label(key: str) -> str:
    """`2026-W40` → `vk 40/2026`."""
    year, week = key.split("-W")
    return f"vk {int(week)}/{year}"


def month_label(key: str) -> str:
    """`2027-01` → `1/2027`."""
    year, month = key.split("-")
    return f"{int(month)}/{year}"


def column_heading(column: Column, by: Unit) -> str:
    """A partial column adds the mark and its days; both years when they differ."""
    name = week_label(column.key) if by == "week" else month_label(column.key)
    if not column.partial:
        return name
    if column.start.year == column.end.year:
        first = f"{column.start.day}.{column.start.month}."
    else:
        first = day(column.start)
    return f"{name} {texts.PARTIAL} {first}–{day(column.end)}"

"""CSV files for Finnish Excel (export spec PC2–PC5, P2; PRD FR-26)."""

from collections.abc import Sequence
from datetime import date

from app import texts
from app.calculation.budget_comparison import Comparison
from app.calculation.period import Period, Unit
from app.calculation.period_totals import PeriodTotals, RowKind
from app.export.comparison_rows import comparison_rows
from app.export.exporter import ExportFile, ExportLine
from app.export.rows import long_rows

MEDIA_TYPE = "text/csv; charset=utf-8"
# Excel reads a CSV file as UTF-8 only when it starts with a byte order mark.
BOM = "﻿"
LINES_HEADER = (
    "Päivä",
    "Viikko",
    "Kuukausi",
    "Kauppa",
    "Tuote",
    "Summa",
    "Ryhmä",
    "Kategoria",
    "Pantinpalautus",
    "Kuitin tila",
)
TOTALS_HEADER = ("Jakso", "Alkaa", "Päättyy", "Osittainen", "Ryhmä", "Kategoria", "Summa")
YES, NO = "kyllä", "ei"
UNREVIEWED, CONFIRMED = "Tarkistamaton", "Vahvistettu"
TOTALS_NAMES: dict[Unit, str] = {"week": "summat_viikot", "month": "summat_kuukaudet"}
COMPARISON_HEADER = (
    "Jakso",
    "Alkaa",
    "Päättyy",
    "Osittainen",
    "Tyyppi",
    "Nimi",
    "Budjetti",
    "Toteutunut",
    "Jäljellä",
)
# The row of lines without a category is a category row too (comparison CSV spec PC3).
ROW_KINDS: dict[RowKind, str] = {"group": "ryhmä", "category": "kategoria", "none": "kategoria"}


class CsvExporter:
    def lines_file(self, period: Period, lines: Sequence[ExportLine]) -> ExportFile:
        rows = [[_cell(name) for name in LINES_HEADER]]
        for line in lines:
            year, week, _ = line.purchase_date.isocalendar()
            day = line.purchase_date
            rows.append(
                [
                    _cell(_finnish_day(day)),
                    _cell(f"{year:04d}-W{week:02d}"),
                    _cell(f"{day.year:04d}-{day.month:02d}"),
                    _text(line.store),
                    _text(line.name),
                    _cell(_money(line.amount_cents)),
                    _text(line.group_name),
                    _text(line.category_name),
                    _cell(YES if line.is_deposit_refund else NO),
                    _cell(CONFIRMED if line.reviewed else UNREVIEWED),
                ]
            )
        return _file(f"kuittirivit_{_bounds(period)}.csv", rows)

    def totals_file(self, totals: PeriodTotals, by: Unit) -> ExportFile:
        rows = [[_cell(name) for name in TOTALS_HEADER]]
        for row in long_rows(totals, by):
            rows.append(
                [
                    _cell(row.column.key),
                    _cell(_finnish_day(row.column.start)),
                    _cell(_finnish_day(row.column.end)),
                    _cell(YES if row.column.partial else NO),
                    _text(row.group_name),
                    _text(row.category_name),
                    _cell(_money(row.amount_cents)),
                ]
            )
        return _file(f"{TOTALS_NAMES[by]}_{_bounds(totals.period)}.csv", rows)

    def comparison_file(self, comparison: Comparison, kind: str, *, weeks: bool) -> ExportFile:
        """Comparison CSV export spec PC3–PC6, P3."""
        rows = [[_cell(name) for name in COMPARISON_HEADER]]
        for row in comparison_rows(comparison, weeks=weeks):
            rows.append(
                [
                    _cell(row.block if row.block is not None else texts.PERIOD_BLOCK),
                    _cell(_finnish_day(row.start)),
                    _cell(_finnish_day(row.end)),
                    _cell(YES if row.partial else NO),
                    _cell(ROW_KINDS[row.kind]),
                    _text(row.name if row.name is not None else texts.NO_CATEGORY),
                    _cell(_money(row.budget_cents)),
                    _cell(_money(row.actual_cents)),
                    _cell(_money(row.remaining_cents)),
                ]
            )
        prefix = "vertailu_viikot" if weeks else "vertailu"
        if kind == "mid":
            prefix += "_15-14"
        # comparison_period has checked the month, so it holds only digits and `-`.
        return _file(f"{prefix}_{comparison.period.first}.csv", rows)


def _bounds(period: Period) -> str:
    # parse_period has checked both bounds, so they hold only digits, `-` and `W`.
    return f"{period.first}_{period.last}"


def _file(name: str, rows: list[list[str]]) -> ExportFile:
    content = BOM + "".join(";".join(row) + "\r\n" for row in rows)
    return ExportFile(name, MEDIA_TYPE, content.encode("utf-8"))


def _finnish_day(day: date) -> str:
    """`01.10.2026`, with the zeros Finnish Excel reads as a date: the one date form of all
    CSV files (Finnish CSV dates spec PC5). The PDF's `finnish.day` leaves the zeros out."""
    return f"{day.day:02d}.{day.month:02d}.{day.year:04d}"


def _cell(value: str) -> str:
    """RFC 4180 quoting; also quotes edge spaces, which `csv.QUOTE_MINIMAL` does not."""
    if any(mark in value for mark in ';"\r\n') or value != value.strip(" "):
        return '"' + value.replace('"', '""') + '"'
    return value


def _text(value: str | None) -> str:
    """A cell of user text. A leading `'` keeps Excel from running it as a formula (PC5)."""
    if value is None:
        return ""
    if value.startswith(("=", "+", "-", "@")):
        value = "'" + value
    return _cell(value)


def _money(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    euros, rest = divmod(abs(cents), 100)
    return f"{sign}{euros},{rest:02d}"

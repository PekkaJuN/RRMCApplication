"""The monthly totals PDF: stacked month blocks (PDF export spec PC4, P6)."""

import re
from collections.abc import Sequence
from datetime import date

import pytest

from app.calculation.period_totals import RowCategory, TotalLine
from app.export.exporter import ExportFile
from app.export.pdf_exporter import PdfExporter
from tests.pdf_reader import Page, Pdf, read_pdf
from tests.unit.export.pdf_data import (
    CATALOG,
    LINES,
    one_line_each,
    standalone_catalog,
    totals_report,
)

A4_LONG, A4_SHORT = 841.89, 595.28
MARGIN = 42.0
PERIOD_BLOCK = "Koko jakso"


def monthly_file(
    unit: str = "month",
    first: str = "2026-10",
    last: str = "2026-11",
    *,
    lines: Sequence[TotalLine] = LINES,
    catalog: Sequence[RowCategory] = CATALOG,
) -> ExportFile:
    report = totals_report(unit, first, last, lines=lines, catalog=catalog)
    return PdfExporter().totals_report(report, "month")


def monthly(*args: str, **kwargs: object) -> Pdf:
    return read_pdf(monthly_file(*args, **kwargs).content)  # pyright: ignore[reportArgumentType]


def all_rows(pdf: Pdf) -> list[str]:
    return [row for page in pdf.pages for row in page.rows()]


def block(rows: list[str], heading: str) -> list[str]:
    """The rows from `heading` to the block's `Yhteensä`, both included."""
    start = rows.index(heading)
    end = next(i for i in range(start, len(rows)) if rows[i].startswith("Yhteensä |"))
    return rows[start : end + 1]


def many(count: int, days: Sequence[date], first: str, last: str) -> Pdf:
    catalog = standalone_catalog(count)
    return monthly("month", first, last, lines=one_line_each(catalog, days), catalog=catalog)


def test_ac3_file_name_and_portrait_a4() -> None:
    file = monthly_file()
    assert file.name == "summat_kuukaudet_2026-10_2026-11.pdf"
    page = read_pdf(file.content).pages[0]
    assert page.width == pytest.approx(A4_SHORT, abs=0.5)
    assert page.height == pytest.approx(A4_LONG, abs=0.5)


def test_ac3_header() -> None:
    rows = monthly().pages[0].rows()
    assert rows[:3] == ["Kuukausisummat", "Jakso: 1.10.2026–30.11.2026", "Luotu 9.11.2026"]
    assert "Tarkistamattomia kuitteja jaksolla: 1" in rows


def test_ac3_blocks_in_order_with_their_amounts() -> None:
    rows = all_rows(monthly())
    headings = [row for row in rows if row in ("10/2026", "11/2026", PERIOD_BLOCK)]
    assert headings == ["10/2026", "11/2026", PERIOD_BLOCK]
    assert block(rows, "10/2026") == [
        "10/2026",
        "Kategoria | Summa",
        "Ruoka | 4,25 €",
        "Leivät | 3,00 €",
        "Maitotuotteet | 1,25 €",
        "Juomat | 2,50 €",
        "Ei kategoriaa | 1,99 €",
        "Yhteensä | 8,74 €",
    ]
    november = block(rows, "11/2026")
    assert "Leivät | 9,99 €" in november
    assert november[-1] == "Yhteensä | 9,99 €"
    period = block(rows, PERIOD_BLOCK)
    assert "Leivät | 12,99 €" in period
    assert "Ruoka | 14,24 €" in period
    assert period[-1] == "Yhteensä | 18,73 €"


def test_ac4_one_month_has_no_period_block_and_no_deposit_refund() -> None:
    pdf = monthly("month", "2026-10", "2026-10")
    rows = all_rows(pdf)
    assert "10/2026" in rows
    assert PERIOD_BLOCK not in rows
    assert "-0,40 €" not in pdf.text
    assert "Yhteensä | 8,74 €" in rows


def test_ac4_a_mid_month_period_of_31_days_has_no_period_block() -> None:
    rows = all_rows(monthly("range", "2026-10-15", "2026-11-14"))
    assert "10/2026 (osittainen) 15.10.–31.10.2026" in rows
    assert "11/2026 (osittainen) 1.11.–14.11.2026" in rows
    assert PERIOD_BLOCK not in rows


def test_ac4_a_period_of_32_days_ends_with_the_period_block() -> None:
    rows = all_rows(monthly("range", "2026-10-15", "2026-11-15"))
    assert PERIOD_BLOCK in rows
    assert rows.index(PERIOD_BLOCK) > rows.index("11/2026 (osittainen) 1.11.–15.11.2026")


def test_ac10_empty_period() -> None:
    pdf = monthly("month", "2026-12", "2026-12")
    assert "Ei ostoksia valitulla jaksolla." in all_rows(pdf)
    assert "Kategoria" not in pdf.text


def test_ac14_a_month_block_is_never_split() -> None:
    days = [date(2026, 10, 6), date(2026, 11, 6), date(2026, 12, 6)]
    pdf = many(30, days, "2026-10", "2026-12")
    for heading in ("10/2026", "11/2026", "12/2026", PERIOD_BLOCK):
        pages = [page for page in pdf.pages if heading in page.rows()]
        assert len(pages) == 1, heading
        rows = block(pages[0].rows(), heading)
        assert len([row for row in rows if re.match(r"Kategoria \d\d \| ", row)]) == 30
    assert "(jatkuu)" not in pdf.text
    count = len(pdf.pages)
    for number, page in enumerate(pdf.pages, start=1):
        assert page.rows()[-1] == f"Sivu {number}/{count}"


def test_ac14_small_blocks_follow_each_other_on_one_page() -> None:
    pdf = monthly()
    assert len(pdf.pages) == 1


def test_ac15_a_block_taller_than_a_page_continues_with_the_mark() -> None:
    pdf = many(80, [date(2026, 10, 6)], "2026-10", "2026-10")
    assert len(pdf.pages) == 2
    first, second = pdf.pages
    assert "10/2026" in first.rows()
    assert second.rows()[:2] == ["10/2026 (jatkuu)", "Kategoria | Summa"]
    assert not any(row.startswith("Yhteensä |") for row in first.rows())
    assert "Yhteensä | 80,00 €" in second.rows()


def _check_layout(page: Page) -> None:
    assert min(char.size for char in page.chars) >= 9 - 0.01
    assert min(char.x0 for char in page.chars) >= MARGIN
    assert max(char.x1 for char in page.chars) <= page.width - MARGIN


def test_ac17_text_is_at_least_9_pt_and_inside_the_margins() -> None:
    pdf = many(80, [date(2026, 10, 6)], "2026-10", "2026-10")
    for page in [*pdf.pages, *monthly().pages]:
        _check_layout(page)


def test_ac18_metadata_title() -> None:
    assert monthly().metadata["Title"] == "Kuukausisummat"

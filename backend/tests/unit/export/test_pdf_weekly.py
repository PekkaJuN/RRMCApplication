"""The weekly totals PDF (PDF export spec PC4, PC6, PC7, PC11, P6)."""

import re
from collections.abc import Sequence
from datetime import date

import pytest

from app.calculation.period_totals import RowCategory, TotalLine
from app.export.exporter import ExportFile, ReportExporter
from app.export.pdf_exporter import PdfExporter
from tests.pdf_reader import Pdf, read_pdf
from tests.unit.export.pdf_data import (
    CATALOG,
    LEIVAT,
    LINES,
    one_line_each,
    standalone_catalog,
    totals_report,
)

A4_LONG, A4_SHORT = 841.89, 595.28
# 15 mm margins; text may sit a little inside a cell's padding, never outside the margin.
MARGIN = 42.0
PRODUCT_AND_STORE_NAMES = ("Ruisleipä", "Limu", "Tuntematon", "Testikauppa")
OCTOBER_6 = [date(2026, 10, 6)]


def weekly_file(
    unit: str = "month",
    first: str = "2026-10",
    last: str = "2026-10",
    *,
    lines: Sequence[TotalLine] = LINES,
    catalog: Sequence[RowCategory] = CATALOG,
    unreviewed: int = 1,
    undated: int = 0,
) -> ExportFile:
    exporter: ReportExporter = PdfExporter()
    report = totals_report(
        unit, first, last, lines=lines, catalog=catalog, unreviewed=unreviewed, undated=undated
    )
    return exporter.totals_report(report, "week")


def weekly(*args: str, **kwargs: object) -> Pdf:
    return read_pdf(weekly_file(*args, **kwargs).content)  # pyright: ignore[reportArgumentType]


def many_rows(count: int = 60) -> Pdf:
    catalog = standalone_catalog(count)
    return weekly(lines=one_line_each(catalog, OCTOBER_6), catalog=catalog, unreviewed=0)


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def test_ac1_file_name_and_media_type() -> None:
    file = weekly_file()
    assert file.name == "summat_viikot_2026-10_2026-10.pdf"
    assert file.media_type == "application/pdf"
    assert file.content.startswith(b"%PDF-")


def test_ac1_one_landscape_a4_page() -> None:
    pdf = weekly()
    assert len(pdf.pages) == 1
    assert pdf.pages[0].width == pytest.approx(A4_LONG, abs=0.5)
    assert pdf.pages[0].height == pytest.approx(A4_SHORT, abs=0.5)


def test_ac1_header_lines() -> None:
    rows = weekly().pages[0].rows()
    assert rows[:3] == ["Viikkosummat", "Jakso: 1.10.2026–31.10.2026", "Luotu 9.11.2026"]
    assert "Tarkistamattomia kuitteja jaksolla: 1" in rows
    assert not any(row.startswith("Kuitteja ilman päivää") for row in rows)


def test_ac1_undated_count_shown_when_not_zero() -> None:
    rows = weekly(unreviewed=0, undated=2).pages[0].rows()
    assert "Kuitteja ilman päivää (ei mukana): 2" in rows
    assert not any(row.startswith("Tarkistamattomia") for row in rows)


def test_ac1_week_headings() -> None:
    text = flat(weekly().text)
    assert "vk 40/2026 (osittainen) 1.10.–4.10.2026" in text
    for week in (41, 42, 43):
        assert f"vk {week}/2026" in text
    assert "vk 44/2026 (osittainen) 26.10.–31.10.2026" in text
    assert "Kategoria" in text


def test_ac1_ac2_table_rows_in_order_with_their_amounts() -> None:
    rows = weekly().pages[0].rows()
    zeros = " | ".join(["0,00 €"] * 3)
    expected = [
        f"Ruoka | 1,25 € | 3,00 € | {zeros}",
        f"Leivät | 0,00 € | 3,00 € | {zeros}",
        f"Maitotuotteet | 1,25 € | 0,00 € | {zeros}",
        f"Juomat | 0,00 € | 2,50 € | {zeros}",
        f"Ei kategoriaa | 0,00 € | 1,99 € | {zeros}",
        f"Yhteensä | 1,25 € | 7,49 € | {zeros}",
    ]
    assert [row for row in rows if row in expected] == expected


def test_ac2_categories_inside_a_group_are_indented() -> None:
    page = weekly().pages[0]
    assert page.row_x("Leivät |") > page.row_x("Ruoka |") + 5
    assert page.row_x("Juomat |") == pytest.approx(page.row_x("Ruoka |"), abs=0.5)


def test_ac4_deposit_refunds_are_not_shown() -> None:
    assert "-0,40 €" not in weekly().text


def test_ac5_week_crossing_the_year() -> None:
    lines = [
        TotalLine(date(2026, 12, 30), 500, LEIVAT, is_deposit_refund=False),
        TotalLine(date(2027, 1, 2), 700, LEIVAT, is_deposit_refund=False),
    ]
    pdf = weekly("range", "2026-12-15", "2027-01-14", lines=lines, unreviewed=0)
    rows = pdf.pages[0].rows()
    assert "Jakso: 15.12.2026–14.1.2027" in rows
    assert "vk 53/2026" in flat(pdf.text)
    # Columns: weeks 51, 52, 53 (28.12.–3.1., both lines), 1 and 2.
    assert "Leivät | 0,00 € | 0,00 € | 12,00 € | 0,00 € | 0,00 €" in rows


def test_ac5_file_name_of_a_date_range() -> None:
    file = weekly_file("range", "2026-12-15", "2027-01-14")
    assert file.name == "summat_viikot_2026-12-15_2027-01-14.pdf"


def test_ac10_empty_period_shows_the_text_and_no_table() -> None:
    pdf = weekly("month", "2026-12", "2026-12", unreviewed=0)
    assert "Ei ostoksia valitulla jaksolla." in pdf.pages[0].rows()
    assert "Kategoria" not in pdf.text


def test_ac16_long_table_continues_with_repeated_headings() -> None:
    pdf = many_rows()
    assert len(pdf.pages) >= 2
    for page in pdf.pages:
        text = flat(page.text)
        assert "Kategoria" in text
        assert "vk 41/2026" in text
    with_total = [
        index
        for index, page in enumerate(pdf.pages)
        if any(row.startswith("Yhteensä |") for row in page.rows())
    ]
    assert with_total == [len(pdf.pages) - 1]


def test_pc4_page_numbers_on_every_page() -> None:
    pdf = many_rows()
    count = len(pdf.pages)
    for number, page in enumerate(pdf.pages, start=1):
        assert f"Sivu {number}/{count}" in page.rows()


def test_ac17_text_is_at_least_9_pt_and_inside_the_margins() -> None:
    for page in [*many_rows().pages, *weekly().pages]:
        assert min(char.size for char in page.chars) >= 9 - 0.01
        assert min(char.x0 for char in page.chars) >= MARGIN
        assert max(char.x1 for char in page.chars) <= page.width - MARGIN
        assert min(char.y0 for char in page.chars) >= MARGIN / 2


def test_ac17_long_category_name_wraps_inside_its_column() -> None:
    name = "Erittäin pitkä kategorian nimi joka ei mahdu yhdelle riville taulukossa"
    catalog = [RowCategory(100, name, "category", None)]
    page = weekly(lines=one_line_each(catalog, OCTOBER_6), catalog=catalog).pages[0]
    assert max(char.x1 for char in page.chars) <= page.width - MARGIN
    assert name in flat(page.text)


def test_ac18_metadata_holds_the_title_only() -> None:
    metadata = weekly().metadata
    assert metadata["Title"] == "Viikkosummat"
    for key in ("Author", "Creator", "Producer", "Subject", "Keywords"):
        assert metadata.get(key, "") == ""


def test_ac18_no_product_or_store_names() -> None:
    pdf = weekly()
    text = pdf.text + " ".join(pdf.metadata.values())
    for name in PRODUCT_AND_STORE_NAMES:
        assert name not in text

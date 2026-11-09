"""The budget comparison PDF (PDF export spec PC5–PC7, PC11, P6)."""

from collections.abc import Mapping, Sequence

import pytest

from app.calculation.period_totals import TotalLine
from app.export.exporter import ExportFile
from app.export.pdf_exporter import PdfExporter
from tests.pdf_reader import Pdf, read_pdf
from tests.unit.export.pdf_data import BUDGETS, REVIEWED_LINES, comparison_report

A4_LONG, A4_SHORT = 841.89, 595.28
MARGIN = 42.0


def comparison_file(
    month: str = "2026-10",
    kind: str = "calendar",
    *,
    lines: Sequence[TotalLine] = REVIEWED_LINES,
    budgets: Mapping[int, int] = BUDGETS,
    unreviewed: int = 1,
    undated: int = 0,
) -> ExportFile:
    report = comparison_report(
        month, kind, lines=lines, budgets=budgets, unreviewed=unreviewed, undated=undated
    )
    return PdfExporter().comparison_report(report)


def comparison(*args: str, **kwargs: object) -> Pdf:
    return read_pdf(comparison_file(*args, **kwargs).content)  # pyright: ignore[reportArgumentType]


def test_ac11_file_name_media_type_and_portrait_a4() -> None:
    file = comparison_file()
    assert file.name == "vertailu_2026-10.pdf"
    assert file.media_type == "application/pdf"
    pdf = read_pdf(file.content)
    assert len(pdf.pages) == 1
    assert pdf.pages[0].width == pytest.approx(A4_SHORT, abs=0.5)
    assert pdf.pages[0].height == pytest.approx(A4_LONG, abs=0.5)


def test_ac11_header() -> None:
    rows = comparison().pages[0].rows()
    assert rows[:4] == [
        "Budjettivertailu",
        "Jakso: 1.10.2026–31.10.2026",
        "Jakson tyyppi: Kalenterikuukausi",
        "Luotu 9.11.2026",
    ]
    assert "Tarkistamattomia kuitteja, ei mukana: 1" in rows
    assert not any(row.startswith("Kuitteja ilman päivää") for row in rows)


def test_ac11_undated_count_shown_when_not_zero() -> None:
    rows = comparison(unreviewed=0, undated=3).pages[0].rows()
    assert "Kuitteja ilman päivää (ei mukana): 3" in rows
    assert not any(row.startswith("Tarkistamattomia") for row in rows)


def test_ac11_table_rows() -> None:
    rows = comparison().pages[0].rows()
    expected = [
        "Kategoria | Budjetti | Toteutunut | Jäljellä",
        "Ruoka | 400,00 € | 3,00 € | 397,00 €",
        "Juomat | 50,00 € | 2,50 € | 47,50 €",
        "Ei kategoriaa | 0,00 € | 1,99 € | -1,99 € Ylitetty",
        "Yhteensä | 450,00 € | 7,49 € | 442,51 €",
    ]
    assert [row for row in rows if row in expected] == expected


def test_ac12_mid_period() -> None:
    file = comparison_file("2026-10", "mid")
    assert file.name == "vertailu_15-14_2026-10.pdf"
    rows = read_pdf(file.content).pages[0].rows()
    assert "Jakso: 15.10.2026–14.11.2026" in rows
    assert "Jakson tyyppi: 15.–14." in rows
    # Receipt C only: receipt B is before the 15th.
    assert "Ruoka | 400,00 € | 9,99 € | 390,01 €" in rows


def test_ac17_text_is_at_least_9_pt_and_inside_the_margins() -> None:
    page = comparison().pages[0]
    assert min(char.size for char in page.chars) >= 9 - 0.01
    assert min(char.x0 for char in page.chars) >= MARGIN
    assert max(char.x1 for char in page.chars) <= page.width - MARGIN


def test_ac18_metadata_holds_the_title_only() -> None:
    metadata = comparison().metadata
    assert metadata["Title"] == "Budjettivertailu"
    for key in ("Author", "Creator", "Producer", "Subject", "Keywords"):
        assert metadata.get(key, "") == ""

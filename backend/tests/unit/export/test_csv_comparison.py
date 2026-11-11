"""The comparison CSV file (comparison CSV export spec PC3–PC7, P3, P4)."""

from datetime import date

import pytest

from app.calculation.period_totals import RowCategory, TotalLine
from app.export.csv_exporter import CsvExporter
from app.export.exporter import Exporter
from tests.unit.export.comparison_data import comparison

BOM = b"\xef\xbb\xbf"
HEADER = "Jakso;Alkaa;Päättyy;Osittainen;Tyyppi;Nimi;Budjetti;Toteutunut;Jäljellä"
WHOLE_OCTOBER = [
    "Koko jakso;01.10.2026;31.10.2026;ei;ryhmä;Ruoka;400,00;125,00;275,00",
    "Koko jakso;01.10.2026;31.10.2026;ei;kategoria;Juomat;50,00;12,50;37,50",
    "Koko jakso;01.10.2026;31.10.2026;ei;kategoria;Ei kategoriaa;0,00;1,99;-1,99",
]


def body_rows(content: bytes) -> list[str]:
    assert content.startswith(BOM)
    text = content[len(BOM) :].decode("utf-8")
    assert text.endswith("\r\n")
    return text.split("\r\n")[:-1]


def test_pc7_the_comparison_file_is_part_of_the_exporter_interface() -> None:
    exporter: Exporter = CsvExporter()

    assert exporter.comparison_file(comparison(), "calendar", weeks=False).name


def test_ac1_file_without_weeks() -> None:
    file = CsvExporter().comparison_file(comparison(), "calendar", weeks=False)

    assert file.media_type == "text/csv; charset=utf-8"
    assert file.name == "vertailu_2026-10.csv"
    assert file.content == BOM + ("\r\n".join([HEADER, *WHOLE_OCTOBER]) + "\r\n").encode()


def test_ac3_file_with_weeks() -> None:
    file = CsvExporter().comparison_file(comparison(), "calendar", weeks=True)
    rows = body_rows(file.content)

    assert rows[:4] == [HEADER, *WHOLE_OCTOBER]
    assert rows[4:7] == [
        "2026-W40;01.10.2026;04.10.2026;kyllä;ryhmä;Ruoka;51,61;125,00;-73,39",
        "2026-W40;01.10.2026;04.10.2026;kyllä;kategoria;Juomat;6,45;0,00;6,45",
        "2026-W40;01.10.2026;04.10.2026;kyllä;kategoria;Ei kategoriaa;0,00;0,00;0,00",
    ]
    assert [row.split(";")[0] for row in rows[4::3]] == [
        "2026-W40",
        "2026-W41",
        "2026-W42",
        "2026-W43",
        "2026-W44",
    ]
    assert rows[7].startswith("2026-W41;05.10.2026;11.10.2026;ei;")
    assert rows[-1].startswith("2026-W44;26.10.2026;31.10.2026;kyllä;")


def test_ac1_dates_keep_their_leading_zeros() -> None:
    lines = [TotalLine(date(2026, 10, 9), 100, None, is_deposit_refund=False)]
    rows = body_rows(
        CsvExporter().comparison_file(comparison(lines=lines), "calendar", weeks=True).content
    )

    assert rows[-1].startswith("2026-W44;26.10.2026;31.10.2026;")
    assert "2026-W41;05.10.2026;11.10.2026;ei;kategoria;Ei kategoriaa;0,00;1,00;-1,00" in rows


@pytest.mark.parametrize(
    ("kind", "weeks", "name"),
    [
        ("calendar", False, "vertailu_2026-10.csv"),
        ("mid", False, "vertailu_15-14_2026-10.csv"),
        ("calendar", True, "vertailu_viikot_2026-10.csv"),
        ("mid", True, "vertailu_viikot_15-14_2026-10.csv"),
    ],
)
def test_ac6_file_names(kind: str, weeks: bool, name: str) -> None:
    file = CsvExporter().comparison_file(comparison(kind=kind), kind, weeks=weeks)

    assert file.name == name


def test_ac6_mid_period_dates() -> None:
    rows = body_rows(
        CsvExporter().comparison_file(comparison(kind="mid"), "mid", weeks=True).content
    )

    assert rows[1].startswith("Koko jakso;15.10.2026;14.11.2026;ei;")
    assert rows[4].startswith("2026-W42;15.10.2026;18.10.2026;kyllä;")
    assert rows[-1].startswith("2026-W46;09.11.2026;14.11.2026;kyllä;")


def test_ac7_zero_rows_without_lines() -> None:
    rows = body_rows(
        CsvExporter().comparison_file(comparison("2026-11"), "calendar", weeks=False).content
    )

    assert rows == [
        HEADER,
        "Koko jakso;01.11.2026;30.11.2026;ei;ryhmä;Ruoka;400,00;0,00;400,00",
        "Koko jakso;01.11.2026;30.11.2026;ei;kategoria;Juomat;50,00;0,00;50,00",
    ]


def test_ac8_header_only_for_an_empty_catalog() -> None:
    empty = comparison("2026-11", lines=[], catalog=[])

    file = CsvExporter().comparison_file(empty, "calendar", weeks=True)

    assert file.content == BOM + (HEADER + "\r\n").encode()


def test_ac9_formula_guard_and_quoting_on_names_only() -> None:
    catalog = [
        RowCategory(1, "=Ruoka", "group", None),
        RowCategory(30, "Juomat; kahvi", "category", None),
    ]
    lines = [TotalLine(date(2026, 10, 6), 199, None, is_deposit_refund=False)]

    rows = body_rows(
        CsvExporter()
        .comparison_file(comparison(catalog=catalog, lines=lines), "calendar", weeks=False)
        .content
    )

    assert rows[1] == "Koko jakso;01.10.2026;31.10.2026;ei;ryhmä;'=Ruoka;400,00;0,00;400,00"
    assert rows[2] == (
        'Koko jakso;01.10.2026;31.10.2026;ei;kategoria;"Juomat; kahvi";50,00;0,00;50,00'
    )
    assert rows[3].endswith(";Ei kategoriaa;0,00;1,99;-1,99")

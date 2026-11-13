"""The CSV file of an archived year (archiving spec PC13, AC31)."""

from datetime import date

from app.calculation.archive_totals import ArchiveLine, archive_totals
from app.export.csv_exporter import CsvExporter


def line(
    day: str, amount: int, product: str, category: str | None = None, group: str | None = None
) -> ArchiveLine:
    return ArchiveLine(date.fromisoformat(day), amount, product, category, group, False)


AC26 = archive_totals(
    2025,
    [
        line("2025-01-10", 250, "Maito 1l", "Maito", "Maitotuotteet"),
        line("2025-01-25", 250, "Maito 1l", "Maito", "Maitotuotteet"),
        line("2025-01-20", 400, "Edam", "Juusto", "Maitotuotteet"),
        line("2025-03-05", 500, "Kahvi 500g", "Kahvi"),
        line("2025-03-06", 100, "TUNTEMATON"),
        ArchiveLine(date(2025, 3, 6), -40, "PANTTI", None, None, True),
    ],
)


def test_ac31_the_exact_file() -> None:
    file = CsvExporter().archive_totals_file(AC26)

    assert file.name == "arkisto_2025.csv"
    assert file.media_type == "text/csv; charset=utf-8"
    assert file.content.decode("utf-8") == (
        "﻿Jakso;Alkaa;Päättyy;Ryhmä;Kategoria;Tuote;Summa\r\n"
        "2025-01;01.01.2025;31.01.2025;Maitotuotteet;Juusto;Edam;4,00\r\n"
        "2025-01;01.01.2025;31.01.2025;Maitotuotteet;Maito;Maito 1l;5,00\r\n"
        "2025-03;01.03.2025;31.03.2025;;Kahvi;Kahvi 500g;5,00\r\n"
        "2025-03;01.03.2025;31.03.2025;;Ei kategoriaa;TUNTEMATON;1,00\r\n"
        "2025;01.01.2025;31.12.2025;;Kahvi;Kahvi 500g;5,00\r\n"
        "2025;01.01.2025;31.12.2025;Maitotuotteet;Juusto;Edam;4,00\r\n"
        "2025;01.01.2025;31.12.2025;Maitotuotteet;Maito;Maito 1l;5,00\r\n"
        "2025;01.01.2025;31.12.2025;;Ei kategoriaa;TUNTEMATON;1,00\r\n"
    )


def test_pc13_february_of_a_leap_year_ends_on_the_29th() -> None:
    totals = archive_totals(2024, [line("2024-02-29", 100, "Leipä", "Leivät")])

    rows = CsvExporter().archive_totals_file(totals).content.decode("utf-8").split("\r\n")

    assert rows[1] == "2024-02;01.02.2024;29.02.2024;;Leivät;Leipä;1,00"


def test_pc13_a_month_whose_lines_add_up_to_zero_still_has_its_row() -> None:
    totals = archive_totals(
        2025,
        [line("2025-04-01", 100, "Leipä", "Leivät"), line("2025-04-02", -100, "Leipä", "Leivät")],
    )

    rows = CsvExporter().archive_totals_file(totals).content.decode("utf-8").split("\r\n")

    assert rows[1] == "2025-04;01.04.2025;30.04.2025;;Leivät;Leipä;0,00"
    assert rows[2] == "2025;01.01.2025;31.12.2025;;Leivät;Leipä;0,00"


def test_pc13_user_text_is_protected_from_excel_formulas() -> None:
    totals = archive_totals(2025, [line("2025-05-01", 100, "=SUM(A1)", "Juomat; kahvi")])

    rows = CsvExporter().archive_totals_file(totals).content.decode("utf-8").split("\r\n")

    assert rows[1] == '2025-05;01.05.2025;31.05.2025;;"Juomat; kahvi";\'=SUM(A1);1,00'

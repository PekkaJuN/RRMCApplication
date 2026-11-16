"""The CSV file of the current year (year with products spec PC5, AC9, AC10)."""

from datetime import date

from app.calculation.archive_totals import ArchiveLine, archive_totals
from app.export.csv_exporter import CsvExporter


def line(
    day: str, amount: int, product: str, category: str | None = None, group: str | None = None
) -> ArchiveLine:
    return ArchiveLine(date.fromisoformat(day), amount, product, category, group, False)


AC1 = archive_totals(
    2026,
    [
        line("2026-01-10", 250, "Maito 1l", "Maito", "Maitotuotteet"),
        line("2026-01-25", 250, "Maito 1l", "Maito", "Maitotuotteet"),
        line("2026-01-20", 400, "Edam", "Juusto", "Maitotuotteet"),
        line("2026-03-05", 500, "Kahvi 500g", "Kahvi"),
        line("2026-03-06", 100, "TUNTEMATON"),
        ArchiveLine(date(2026, 3, 6), -40, "Panttipalautus", None, None, True),
    ],
)


def test_year_ac10_the_exact_file() -> None:
    file = CsvExporter().year_totals_file(AC1)

    assert file.name == "vuosi_2026.csv"
    assert file.media_type == "text/csv; charset=utf-8"
    assert file.content.decode("utf-8") == (
        "﻿Jakso;Alkaa;Päättyy;Ryhmä;Kategoria;Tuote;Summa\r\n"
        "2026-01;01.01.2026;31.01.2026;Maitotuotteet;Juusto;Edam;4,00\r\n"
        "2026-01;01.01.2026;31.01.2026;Maitotuotteet;Maito;Maito 1l;5,00\r\n"
        "2026-03;01.03.2026;31.03.2026;;Kahvi;Kahvi 500g;5,00\r\n"
        "2026-03;01.03.2026;31.03.2026;;Ei kategoriaa;TUNTEMATON;1,00\r\n"
        "2026;01.01.2026;31.12.2026;;Kahvi;Kahvi 500g;5,00\r\n"
        "2026;01.01.2026;31.12.2026;Maitotuotteet;Juusto;Edam;4,00\r\n"
        "2026;01.01.2026;31.12.2026;Maitotuotteet;Maito;Maito 1l;5,00\r\n"
        "2026;01.01.2026;31.12.2026;;Ei kategoriaa;TUNTEMATON;1,00\r\n"
    )


def test_year_ac9_an_empty_year_has_the_header_only() -> None:
    file = CsvExporter().year_totals_file(archive_totals(2026, []))

    assert file.name == "vuosi_2026.csv"
    assert file.content.decode("utf-8") == ("﻿Jakso;Alkaa;Päättyy;Ryhmä;Kategoria;Tuote;Summa\r\n")

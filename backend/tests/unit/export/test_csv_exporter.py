"""The CSV exporter (export spec PC1–PC5, P1, P2)."""

import csv
import io
from datetime import date

import pytest

from app.calculation.period import parse_period
from app.calculation.period_totals import RowCategory, TotalLine, period_totals
from app.export.csv_exporter import CsvExporter
from app.export.exporter import Exporter, ExportLine

RUOKA, LEIVAT, MAITO, JUOMAT = 1, 12, 13, 30
CATALOG = [
    RowCategory(RUOKA, "Ruoka", "group", None),
    RowCategory(LEIVAT, "Leivät", "category", RUOKA),
    RowCategory(MAITO, "Maitotuotteet", "category", RUOKA),
    RowCategory(JUOMAT, "Juomat", "category", None),
]
OCTOBER = parse_period("month", "2026-10", "2026-10")
BOM = b"\xef\xbb\xbf"
LINES_HEADER = "Päivä;Viikko;Kuukausi;Kauppa;Tuote;Summa;Ryhmä;Kategoria;Pantinpalautus;Kuitin tila"
TOTALS_HEADER = "Jakso;Alkaa;Päättyy;Osittainen;Ryhmä;Kategoria;Summa"


def export_line(
    name: str,
    amount: int,
    *,
    day: date = date(2026, 10, 6),
    store: str | None = "Testikauppa",
    group: str | None = None,
    category: str | None = None,
    refund: bool = False,
    reviewed: bool = True,
) -> ExportLine:
    return ExportLine(
        purchase_date=day,
        store=store,
        name=name,
        amount_cents=amount,
        is_deposit_refund=refund,
        group_name=group,
        category_name=category,
        reviewed=reviewed,
    )


FIXTURE_LINES = [
    export_line(
        "Maito",
        125,
        day=date(2026, 10, 2),
        group="Ruoka",
        category="Maitotuotteet",
        reviewed=False,
    ),
    export_line("Ruisleipä", 300, group="Ruoka", category="Leivät"),
    export_line("Limu", 250, category="Juomat"),
    export_line("Tuntematon", 199),
    export_line("Panttipalautus", -40, refund=True),
]
FIXTURE_TOTALS = [
    TotalLine(date(2026, 10, 2), 125, MAITO, is_deposit_refund=False),
    TotalLine(date(2026, 10, 6), 300, LEIVAT, is_deposit_refund=False),
    TotalLine(date(2026, 10, 6), 250, JUOMAT, is_deposit_refund=False),
    TotalLine(date(2026, 10, 6), 199, None, is_deposit_refund=False),
    TotalLine(date(2026, 10, 6), -40, None, is_deposit_refund=True),
]


def text(content: bytes) -> str:
    """The content without the byte order mark, with `\n` line ends."""
    assert content.startswith(BOM)
    decoded = content[len(BOM) :].decode("utf-8")
    assert decoded.endswith("\r\n")
    return decoded.replace("\r\n", "\n")


def cells(content: bytes) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text(content)), delimiter=";"))


def test_ac12_csv_exporter_is_an_exporter() -> None:
    exporter: Exporter = CsvExporter()
    assert exporter.lines_file(OCTOBER, []).media_type == "text/csv; charset=utf-8"


def test_ac1_lines_file() -> None:
    file = CsvExporter().lines_file(OCTOBER, FIXTURE_LINES)
    assert text(file.content) == (
        f"{LINES_HEADER}\n"
        "2026-10-02;2026-W40;2026-10;Testikauppa;Maito;1,25;Ruoka;Maitotuotteet;ei;Tarkistamaton\n"
        "2026-10-06;2026-W41;2026-10;Testikauppa;Ruisleipä;3,00;Ruoka;Leivät;ei;Vahvistettu\n"
        "2026-10-06;2026-W41;2026-10;Testikauppa;Limu;2,50;;Juomat;ei;Vahvistettu\n"
        "2026-10-06;2026-W41;2026-10;Testikauppa;Tuntematon;1,99;;;ei;Vahvistettu\n"
        "2026-10-06;2026-W41;2026-10;Testikauppa;Panttipalautus;-0,40;;;kyllä;Vahvistettu\n"
    )


def test_ac2_weekly_totals_file() -> None:
    file = CsvExporter().totals_file(period_totals(OCTOBER, FIXTURE_TOTALS, CATALOG), "week")
    assert text(file.content) == (
        f"{TOTALS_HEADER}\n"
        "2026-W40;2026-10-01;2026-10-04;kyllä;Ruoka;Maitotuotteet;1,25\n"
        "2026-W41;2026-10-05;2026-10-11;ei;Ruoka;Leivät;3,00\n"
        "2026-W41;2026-10-05;2026-10-11;ei;;Juomat;2,50\n"
        "2026-W41;2026-10-05;2026-10-11;ei;;Ei kategoriaa;1,99\n"
    )


def test_ac16_monthly_totals_file() -> None:
    file = CsvExporter().totals_file(period_totals(OCTOBER, FIXTURE_TOTALS, CATALOG), "month")
    assert text(file.content) == (
        f"{TOTALS_HEADER}\n"
        "2026-10;2026-10-01;2026-10-31;ei;Ruoka;Leivät;3,00\n"
        "2026-10;2026-10-01;2026-10-31;ei;Ruoka;Maitotuotteet;1,25\n"
        "2026-10;2026-10-01;2026-10-31;ei;;Juomat;2,50\n"
        "2026-10;2026-10-01;2026-10-31;ei;;Ei kategoriaa;1,99\n"
    )


def test_ac6_file_names_and_media_type() -> None:
    exporter = CsvExporter()
    weeks = parse_period("week", "2026-W40", "2026-W41")
    months = parse_period("month", "2026-10", "2026-12")
    lines = exporter.lines_file(OCTOBER, [])
    by_week = exporter.totals_file(period_totals(weeks, [], CATALOG), "week")
    by_month = exporter.totals_file(period_totals(months, [], CATALOG), "month")
    assert lines.name == "kuittirivit_2026-10_2026-10.csv"
    assert by_week.name == "summat_viikot_2026-W40_2026-W41.csv"
    assert by_month.name == "summat_kuukaudet_2026-10_2026-12.csv"
    assert {by_week.media_type, by_month.media_type} == {"text/csv; charset=utf-8"}


def test_ac7_header_only_without_data() -> None:
    exporter = CsvExporter()
    totals = period_totals(OCTOBER, [], CATALOG)
    assert exporter.lines_file(OCTOBER, []).content == BOM + f"{LINES_HEADER}\r\n".encode()
    for by in ("week", "month"):
        assert exporter.totals_file(totals, by).content == BOM + f"{TOTALS_HEADER}\r\n".encode()


def test_ac9_quoting_reads_back() -> None:
    lines = [
        export_line('Kahvi; tumma "Extra"', 100, store=" Kauppa "),
        export_line("rivi\nkaksi", 100, store="Kauppa\r"),
    ]
    content = CsvExporter().lines_file(OCTOBER, lines).content
    assert '" Kauppa ";"Kahvi; tumma ""Extra"""' in text(content)
    rows = cells(content)
    assert (rows[1][3], rows[1][4]) == (" Kauppa ", 'Kahvi; tumma "Extra"')
    assert (rows[2][3], rows[2][4]) == ("Kauppa\r", "rivi\nkaksi")


@pytest.mark.parametrize("name", ["=1+1", "+5", "-20% ale", "@SUMMA"])
def test_ac10_formula_guard_on_text_cells_only(name: str) -> None:
    line = export_line(name, -150, store=name, group=name, category=name)
    [_, row] = cells(CsvExporter().lines_file(OCTOBER, [line]).content)
    assert row[3:8] == [f"'{name}", f"'{name}", "-1,50", f"'{name}", f"'{name}"]


@pytest.mark.parametrize(
    ("cents", "money"),
    [(125, "1,25"), (-40, "-0,40"), (0, "0,00"), (123456, "1234,56"), (-150, "-1,50"), (5, "0,05")],
)
def test_money_has_a_decimal_comma(cents: int, money: str) -> None:
    [_, row] = cells(CsvExporter().lines_file(OCTOBER, [export_line("x", cents)]).content)
    assert row[5] == money


def test_week_and_month_of_a_line_use_iso_weeks() -> None:
    line = export_line("x", 1, day=date(2027, 1, 2))
    [_, row] = cells(CsvExporter().lines_file(OCTOBER, [line]).content)
    assert row[:3] == ["2027-01-02", "2026-W53", "2027-01"]

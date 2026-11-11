"""CSV export of the lines and totals of a period (export spec)."""

import csv
import io
import logging
import re
import sqlite3
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field

import httpx2
import pytest
from fastapi.testclient import TestClient

from app.calculation.budget_comparison import Comparison
from app.calculation.period import Period, Unit
from app.calculation.period_totals import PeriodTotals
from app.categorization.names import normalize_key
from app.export.exporter import ExportFile, ExportLine
from app.main import create_app
from app.settings import Settings
from app.storage.catalog_repository import CatalogRepository
from app.storage.db import connect
from app.storage.receipt_repository import LineCategory, ReceiptRepository
from tests.integration.conftest import BASE_URL

TIME = "2026-11-02T10:00:01Z"
OCTOBER = "unit=month&from=2026-10&to=2026-10"
BOM = b"\xef\xbb\xbf"
LINES_HEADER = "Päivä;Viikko;Kuukausi;Kauppa;Tuote;Summa;Ryhmä;Kategoria;Pantinpalautus;Kuitin tila"
TOTALS_HEADER = "Jakso;Alkaa;Päättyy;Osittainen;Ryhmä;Kategoria;Summa"
INVALID_PERIOD = {"error": "invalid_period", "message": "Jakso on virheellinen."}
INVALID_REQUEST = {"error": "invalid_request", "message": "Pyyntö on virheellinen."}


@pytest.fixture
def db(api: TestClient, settings: Settings) -> Iterator[sqlite3.Connection]:
    """A connection to the app's database after its startup (migrations, default list)."""
    connection = connect(settings.db_path)
    yield connection
    connection.close()


def category(db: sqlite3.Connection, name: str) -> LineCategory:
    row = CatalogRepository(db).get_category_by_key(normalize_key(name))
    assert row is not None
    return LineCategory(row.id, "user", None)


_numbers = iter(range(1, 10_000))


def add_receipt(
    db: sqlite3.Connection,
    purchase_date: str | None,
    lines: Sequence[tuple[str, int, str | None] | tuple[str, int, str | None, int]],
    *,
    store: str | None = "Testikauppa",
    reviewed: bool = False,
) -> int:
    """A receipt with lines (name, amount, category name[, position]); a name
    `Panttipalautus` is a deposit refund."""
    receipts = ReceiptRepository(db)
    with receipts.transaction():
        row = receipts.add(
            f"{next(_numbers):064d}",
            "kuitti.jpg",
            TIME,
            store=store,
            purchase_date=purchase_date,
        )
        for index, line in enumerate(lines, start=1):
            name, amount, category_name = line[0], line[1], line[2]
            receipts.add_line(
                row.id,
                line[3] if len(line) == 4 else index,
                name,
                amount,
                is_deposit_refund=name == "Panttipalautus",
                category=category(db, category_name) if category_name else None,
            )
        receipts.set_reviewed(row.id, reviewed=reviewed)
    return row.id


def add_fixture(db: sqlite3.Connection) -> None:
    add_receipt(db, "2026-10-02", [("Maito", 125, "Maitotuotteet")])
    add_receipt(
        db,
        "2026-10-06",
        [
            ("Ruisleipä", 300, "Leivät"),
            ("Limu", 250, "Juomat"),
            ("Tuntematon", 199, None),
            ("Panttipalautus", -40, None),
        ],
        reviewed=True,
    )
    add_receipt(db, "2026-11-01", [("Ruisleipä", 999, "Leivät")], store=None)


def text(response: httpx2.Response) -> str:
    """The content without the byte order mark, with `\\n` line ends."""
    assert response.content.startswith(BOM)
    return response.content[len(BOM) :].decode("utf-8").replace("\r\n", "\n")


def rows(response: httpx2.Response) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text(response)), delimiter=";"))[1:]


def lines_file(api: TestClient, query: str) -> httpx2.Response:
    return api.get(f"/api/export/lines?{query}")


def totals_file(api: TestClient, query: str, by: str = "week") -> httpx2.Response:
    return api.get(f"/api/export/totals?{query}&by={by}")


def test_ac1_lines_file_of_a_month(api: TestClient, db: sqlite3.Connection) -> None:
    add_fixture(db)

    response = lines_file(api, OCTOBER)

    assert response.status_code == 200
    assert text(response) == (
        f"{LINES_HEADER}\n"
        "2026-10-02;2026-W40;2026-10;Testikauppa;Maito;1,25;Ruoka;Maitotuotteet;ei;Tarkistamaton\n"
        "2026-10-06;2026-W41;2026-10;Testikauppa;Ruisleipä;3,00;Ruoka;Leivät;ei;Vahvistettu\n"
        "2026-10-06;2026-W41;2026-10;Testikauppa;Limu;2,50;;Juomat;ei;Vahvistettu\n"
        "2026-10-06;2026-W41;2026-10;Testikauppa;Tuntematon;1,99;;;ei;Vahvistettu\n"
        "2026-10-06;2026-W41;2026-10;Testikauppa;Panttipalautus;-0,40;;;kyllä;Vahvistettu\n"
    )


def test_ac2_weekly_totals_file_of_a_month(api: TestClient, db: sqlite3.Connection) -> None:
    add_fixture(db)

    response = totals_file(api, OCTOBER, "week")

    assert response.status_code == 200
    assert text(response) == (
        f"{TOTALS_HEADER}\n"
        "2026-W40;2026-10-01;2026-10-04;kyllä;Ruoka;Maitotuotteet;1,25\n"
        "2026-W41;2026-10-05;2026-10-11;ei;Ruoka;Leivät;3,00\n"
        "2026-W41;2026-10-05;2026-10-11;ei;;Juomat;2,50\n"
        "2026-W41;2026-10-05;2026-10-11;ei;;Ei kategoriaa;1,99\n"
    )


def test_ac16_monthly_totals_file_of_a_month(api: TestClient, db: sqlite3.Connection) -> None:
    add_fixture(db)

    response = totals_file(api, OCTOBER, "month")

    assert response.status_code == 200
    assert text(response) == (
        f"{TOTALS_HEADER}\n"
        "2026-10;2026-10-01;2026-10-31;ei;Ruoka;Leivät;3,00\n"
        "2026-10;2026-10-01;2026-10-31;ei;Ruoka;Maitotuotteet;1,25\n"
        "2026-10;2026-10-01;2026-10-31;ei;;Juomat;2,50\n"
        "2026-10;2026-10-01;2026-10-31;ei;;Ei kategoriaa;1,99\n"
    )


def cents(money: str) -> int:
    euros, hundredths = money.lstrip("-").split(",")
    value = int(euros) * 100 + int(hundredths)
    return -value if money.startswith("-") else value


def test_ac3_totals_files_match_the_totals_view(api: TestClient, db: sqlite3.Connection) -> None:
    add_fixture(db)
    view = api.get(f"/api/totals?{OCTOBER}").json()
    leaves: dict[str | None, dict[str, list[int]]] = {}
    for row in view["rows"]:
        for leaf in row["categories"] or [row]:
            leaves[leaf["name"]] = leaf

    for by, columns, column_totals, amounts in (
        ("week", view["weeks"], view["week_totals"], "weeks"),
        ("month", view["months"], view["month_totals"], "months"),
    ):
        file_rows = rows(totals_file(api, OCTOBER, by))
        for index, column in enumerate(columns):
            in_column = [row for row in file_rows if row[0] == column["key"]]
            assert sum(cents(row[6]) for row in in_column) == column_totals[index]
            for row in in_column:
                name = None if row[5] == "Ei kategoriaa" else row[5]
                assert cents(row[6]) == leaves[name][amounts][index]


def test_ac4_week_period_with_partial_months(api: TestClient, db: sqlite3.Connection) -> None:
    add_receipt(db, "2026-09-30", [("Ruisleipä", 100, "Leivät")])
    add_receipt(db, "2026-10-01", [("Ruisleipä", 200, "Leivät")])
    week_40 = "unit=week&from=2026-W40&to=2026-W40"

    assert rows(totals_file(api, week_40, "week")) == [
        ["2026-W40", "2026-09-28", "2026-10-04", "ei", "Ruoka", "Leivät", "3,00"]
    ]
    assert rows(totals_file(api, week_40, "month")) == [
        ["2026-09", "2026-09-28", "2026-09-30", "kyllä", "Ruoka", "Leivät", "1,00"],
        ["2026-10", "2026-10-01", "2026-10-04", "kyllä", "Ruoka", "Leivät", "2,00"],
    ]
    assert [row[0] for row in rows(lines_file(api, week_40))] == ["2026-09-30", "2026-10-01"]


def test_ac5_a_category_summing_to_zero(api: TestClient, db: sqlite3.Connection) -> None:
    add_receipt(db, "2026-10-05", [("Ruisleipä", 300, "Leivät"), ("Hyvitys", -300, "Leivät")])

    assert rows(totals_file(api, OCTOBER, "week")) == [
        ["2026-W41", "2026-10-05", "2026-10-11", "ei", "Ruoka", "Leivät", "0,00"]
    ]
    assert rows(totals_file(api, OCTOBER, "month")) == [
        ["2026-10", "2026-10-01", "2026-10-31", "ei", "Ruoka", "Leivät", "0,00"]
    ]


@pytest.mark.parametrize(
    ("path", "name"),
    [
        ("/api/export/lines?unit=month&from=2026-10&to=2026-10", "kuittirivit_2026-10_2026-10.csv"),
        (
            "/api/export/totals?unit=week&from=2026-W40&to=2026-W41&by=week",
            "summat_viikot_2026-W40_2026-W41.csv",
        ),
        (
            "/api/export/totals?unit=month&from=2026-10&to=2026-12&by=month",
            "summat_kuukaudet_2026-10_2026-12.csv",
        ),
    ],
)
def test_ac6_headers_and_file_names(
    api: TestClient, db: sqlite3.Connection, path: str, name: str
) -> None:
    add_fixture(db)

    response = api.get(path)

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-disposition"] == f'attachment; filename="{name}"'
    assert response.content.startswith(BOM)
    body = response.content[len(BOM) :]
    assert body.endswith(b"\r\n")
    assert body.count(b"\n") == body.count(b"\r\n")


def test_ac7_empty_period(api: TestClient, db: sqlite3.Connection) -> None:
    add_fixture(db)
    march = "unit=month&from=2026-03&to=2026-03"

    assert text(lines_file(api, march)) == f"{LINES_HEADER}\n"
    assert text(totals_file(api, march, "week")) == f"{TOTALS_HEADER}\n"
    assert text(totals_file(api, march, "month")) == f"{TOTALS_HEADER}\n"


INVALID_QUERIES = [
    "unit=day&from=2026-10&to=2026-10",
    "unit=month&from=2026-13&to=2026-13",
    "unit=month&from=2026-11&to=2026-10",
    "unit=week&from=2027-W53&to=2027-W53",
    "unit=month&to=2026-10",
    "unit=month&from=2024-10&to=2026-10",
    "unit=week&from=2025-W01&to=2026-W53",
]


@pytest.mark.parametrize("query", INVALID_QUERIES)
def test_ac8_invalid_period(api: TestClient, query: str) -> None:
    for response in (lines_file(api, query), totals_file(api, query, "week")):
        assert response.status_code == 422
        assert response.json() == INVALID_PERIOD


def test_ac17_invalid_by(api: TestClient) -> None:
    for response in (
        api.get(f"/api/export/totals?{OCTOBER}"),
        totals_file(api, OCTOBER, "day"),
        totals_file(api, OCTOBER, "WEEK"),
    ):
        assert response.status_code == 422
        assert response.json() == INVALID_REQUEST
    response = totals_file(api, "unit=day&from=2026-10&to=2026-10", "day")
    assert (response.status_code, response.json()) == (422, INVALID_PERIOD)


def test_ac9_quoting(api: TestClient, db: sqlite3.Connection) -> None:
    add_receipt(db, "2026-10-05", [('Kahvi; tumma "Extra"', 450, None)], store=" Kauppa ")

    response = lines_file(api, OCTOBER)

    assert '" Kauppa ";"Kahvi; tumma ""Extra"""' in text(response)
    [row] = rows(response)
    assert row[3:5] == [" Kauppa ", 'Kahvi; tumma "Extra"']


def test_ac10_formulas_are_not_run(api: TestClient, db: sqlite3.Connection) -> None:
    names = ["=1+1", "+5", "-20% ale", "@SUMMA"]
    add_receipt(db, "2026-10-05", [(name, -150, None) for name in names])

    file_rows = rows(lines_file(api, OCTOBER))

    assert [row[4] for row in file_rows] == [f"'{name}" for name in names]
    assert [row[5] for row in file_rows] == ["-1,50"] * 4


def test_ac11_lines_order(api: TestClient, db: sqlite3.Connection) -> None:
    add_receipt(db, "2026-10-06", [("B3", 1, None, 3), ("B1", 1, None, 1)])
    add_receipt(db, "2026-10-02", [("A1", 1, None)])
    add_receipt(db, "2026-10-06", [("D3", 1, None, 3), ("D1", 1, None, 1)])

    assert [row[4] for row in rows(lines_file(api, OCTOBER))] == ["A1", "B1", "B3", "D1", "D3"]


@dataclass
class FixedExporter:
    """A test exporter that returns a fixed file and remembers what it got (AC12)."""

    lines: list[ExportLine] = field(default_factory=lambda: list[ExportLine]())
    totals: list[tuple[PeriodTotals, Unit]] = field(
        default_factory=lambda: list[tuple[PeriodTotals, Unit]]()
    )
    comparisons: list[tuple[Comparison, str, bool]] = field(
        default_factory=lambda: list[tuple[Comparison, str, bool]]()
    )

    def lines_file(self, period: Period, lines: Sequence[ExportLine]) -> ExportFile:
        self.lines.extend(lines)
        return ExportFile("rivit.test", "application/x-test", b"lines")

    def totals_file(self, totals: PeriodTotals, by: Unit) -> ExportFile:
        self.totals.append((totals, by))
        return ExportFile("summat.test", "application/x-test", b"totals")

    # The comparison CSV export spec, P4.
    def comparison_file(self, comparison: Comparison, kind: str, *, weeks: bool) -> ExportFile:
        self.comparisons.append((comparison, kind, weeks))
        return ExportFile("vertailu.test", "application/x-test", b"comparison")


def test_ac12_exporter_interface(settings: Settings) -> None:
    exporter = FixedExporter()
    with TestClient(create_app(settings, exporter=exporter), base_url=BASE_URL) as client:
        connection = connect(settings.db_path)
        try:
            add_receipt(connection, "2026-10-06", [("Ruisleipä", 300, "Leivät")])
        finally:
            connection.close()

        lines = lines_file(client, OCTOBER)
        totals = totals_file(client, OCTOBER, "month")

    assert (lines.content, lines.headers["content-type"]) == (b"lines", "application/x-test")
    assert lines.headers["content-disposition"] == 'attachment; filename="rivit.test"'
    assert totals.content == b"totals"
    assert totals.headers["content-disposition"] == 'attachment; filename="summat.test"'
    assert [line.name for line in exporter.lines] == ["Ruisleipä"]
    [(period_totals, by)] = exporter.totals
    assert (period_totals.month_totals, by) == ([300], "month")


def test_ac15_privacy(
    api: TestClient, db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    add_receipt(db, "2026-10-05", [("Salainen Tuote", 300, "Leivät")], store="Salakauppa")
    caplog.set_level(logging.DEBUG)

    lines_file(api, OCTOBER)
    totals_file(api, OCTOBER, "month")

    # Only the app's own loggers; the test client logs the full URL itself.
    logged = [record.getMessage() for record in caplog.records if record.name.startswith("app")]
    # Each request line ends with its duration, e.g. `GET /api/export/lines 200 3ms`.
    assert [re.sub(r" [0-9]+ms$", "", message) for message in logged] == [
        "GET /api/export/lines 200",
        "GET /api/export/totals 200",
    ]


# Date range (date range spec).

RANGE = "unit=range&from=2026-10-15&to=2026-11-14"


def add_range_fixture(db: sqlite3.Connection) -> None:
    for day, amount in [
        ("2026-10-14", 100),
        ("2026-10-15", 200),
        ("2026-11-14", 400),
        ("2026-11-15", 800),
    ]:
        add_receipt(db, day, [("Ruisleipä", amount, "Leivät")])


def test_date_range_ac10_lines_file(api: TestClient, db: sqlite3.Connection) -> None:
    add_range_fixture(db)

    response = lines_file(api, RANGE)

    assert response.status_code == 200
    assert (
        response.headers["Content-Disposition"]
        == 'attachment; filename="kuittirivit_2026-10-15_2026-11-14.csv"'
    )
    assert [row[0] for row in rows(response)] == ["2026-10-15", "2026-11-14"]


def test_date_range_ac11_totals_files(api: TestClient, db: sqlite3.Connection) -> None:
    add_range_fixture(db)

    weeks = totals_file(api, RANGE, "week")
    months = totals_file(api, RANGE, "month")

    assert (
        weeks.headers["Content-Disposition"]
        == 'attachment; filename="summat_viikot_2026-10-15_2026-11-14.csv"'
    )
    assert (
        months.headers["Content-Disposition"]
        == 'attachment; filename="summat_kuukaudet_2026-10-15_2026-11-14.csv"'
    )
    assert rows(weeks)[-1] == [
        "2026-W46",
        "2026-11-09",
        "2026-11-14",
        "kyllä",
        "Ruoka",
        "Leivät",
        "4,00",
    ]
    assert rows(months)[-1] == [
        "2026-11",
        "2026-11-01",
        "2026-11-14",
        "kyllä",
        "Ruoka",
        "Leivät",
        "4,00",
    ]


@pytest.mark.parametrize(
    "query",
    [
        "unit=range&from=2026-02-30&to=2026-03-01",
        "unit=range&from=2026-10-02&to=2026-10-01",
        "unit=range&from=2027-01-01&to=2029-01-01",
        "unit=range&from=2026-10&to=2026-11",
    ],
)
def test_date_range_ac12_invalid_range(api: TestClient, query: str) -> None:
    for response in (lines_file(api, query), totals_file(api, query, "week")):
        assert response.status_code == 422
        assert response.json() == INVALID_PERIOD


def test_date_range_ac12_a_bad_range_comes_before_a_bad_by(api: TestClient) -> None:
    response = totals_file(api, "unit=range&from=2026-02-30&to=2026-03-01", "range")

    assert response.json() == INVALID_PERIOD


def test_date_range_ac12_a_file_cannot_be_by_range(api: TestClient) -> None:
    response = totals_file(api, RANGE, "range")

    assert response.status_code == 422
    assert response.json() == INVALID_REQUEST

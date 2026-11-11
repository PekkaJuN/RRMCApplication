"""CSV file of the budget comparison (comparison CSV export spec)."""

import logging
import re
import sqlite3
from collections.abc import Iterator

import httpx2
import pytest
from fastapi.testclient import TestClient

from app.settings import Settings
from app.storage.catalog_repository import CatalogRepository
from app.storage.db import connect
from tests.integration.test_export_api import add_receipt

BOM = b"\xef\xbb\xbf"
HEADER = "Jakso;Alkaa;Päättyy;Osittainen;Tyyppi;Nimi;Budjetti;Toteutunut;Jäljellä"
WHOLE_OCTOBER = [
    "Koko jakso;01.10.2026;31.10.2026;ei;ryhmä;Ruoka;400,00;125,00;275,00",
    "Koko jakso;01.10.2026;31.10.2026;ei;kategoria;Juomat;50,00;12,50;37,50",
    "Koko jakso;01.10.2026;31.10.2026;ei;kategoria;Ei kategoriaa;0,00;1,99;-1,99",
]
INVALID_PERIOD = {"error": "invalid_period", "message": "Jakso on virheellinen."}
INVALID_REQUEST = {"error": "invalid_request", "message": "Pyyntö on virheellinen."}


@pytest.fixture
def db(api: TestClient, settings: Settings) -> Iterator[sqlite3.Connection]:
    connection = connect(settings.db_path)
    yield connection
    connection.close()


def keep_only(db: sqlite3.Connection, names: tuple[str, ...]) -> None:
    """Remove the rest of the default list, so the file has the spec's catalog only."""
    with db:
        db.execute("DELETE FROM products")
        # Categories before groups: a group with categories cannot be deleted.
        for kind in ("category", "group"):
            rows = db.execute("SELECT id, name FROM categories WHERE kind = ?", (kind,))
            for item_id, name in rows.fetchall():
                if name not in names:
                    db.execute("DELETE FROM categories WHERE id = ?", (item_id,))


def add_example(db: sqlite3.Connection) -> None:
    """The catalog, budgets and reviewed lines of the spec's examples."""
    keep_only(db, ("Ruoka", "Maitotuotteet", "Juomat"))
    catalog = CatalogRepository(db)
    with catalog.transaction():
        for item in catalog.list_categories():
            if item.name in ("Ruoka", "Juomat"):
                catalog.set_budget(item.id, 40000 if item.name == "Ruoka" else 5000)
    add_receipt(db, "2026-10-01", [("Maito", 12500, "Maitotuotteet")], reviewed=True)
    add_receipt(db, "2026-10-06", [("Limu", 1250, "Juomat"), ("Outo", 199, None)], reviewed=True)


def comparison_csv(api: TestClient, query: str) -> httpx2.Response:
    return api.get(f"/api/export/comparison?{query}")


def body_rows(response: httpx2.Response) -> list[str]:
    assert response.status_code == 200, response.text
    assert response.content.startswith(BOM)
    text = response.content[len(BOM) :].decode("utf-8")
    assert text.endswith("\r\n")
    return text.split("\r\n")[:-1]


def test_ac1_file_without_weeks(api: TestClient, db: sqlite3.Connection) -> None:
    add_example(db)

    response = comparison_csv(api, "month=2026-10")

    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert response.headers["content-disposition"] == 'attachment; filename="vertailu_2026-10.csv"'
    assert response.headers["cache-control"] == "no-store"
    assert response.content == BOM + ("\r\n".join([HEADER, *WHOLE_OCTOBER]) + "\r\n").encode()


def test_ac2_weeks_false_is_the_default(api: TestClient, db: sqlite3.Connection) -> None:
    add_example(db)

    default = comparison_csv(api, "month=2026-10")
    without = comparison_csv(api, "month=2026-10&weeks=false")

    assert without.status_code == 200
    assert without.content == default.content
    assert without.headers["content-disposition"] == default.headers["content-disposition"]


def test_ac3_file_with_weeks(api: TestClient, db: sqlite3.Connection) -> None:
    add_example(db)

    response = comparison_csv(api, "month=2026-10&weeks=true")

    assert response.headers["content-disposition"] == (
        'attachment; filename="vertailu_viikot_2026-10.csv"'
    )
    rows = body_rows(response)
    assert rows[:4] == [HEADER, *WHOLE_OCTOBER]
    assert rows[4:7] == [
        "2026-W40;01.10.2026;04.10.2026;kyllä;ryhmä;Ruoka;51,61;125,00;-73,39",
        "2026-W40;01.10.2026;04.10.2026;kyllä;kategoria;Juomat;6,45;0,00;6,45",
        "2026-W40;01.10.2026;04.10.2026;kyllä;kategoria;Ei kategoriaa;0,00;0,00;0,00",
    ]
    assert len(rows) == 1 + 3 * 6
    assert [row.split(";")[:4] for row in rows[4::3]] == [
        ["2026-W40", "01.10.2026", "04.10.2026", "kyllä"],
        ["2026-W41", "05.10.2026", "11.10.2026", "ei"],
        ["2026-W42", "12.10.2026", "18.10.2026", "ei"],
        ["2026-W43", "19.10.2026", "25.10.2026", "ei"],
        ["2026-W44", "26.10.2026", "31.10.2026", "kyllä"],
    ]


def cents(text: str) -> int:
    euros, rest = text.split(",")
    sign = -1 if euros.startswith("-") else 1
    return sign * (abs(int(euros)) * 100 + int(rest))


def test_ac4_figures_agree_with_the_page(api: TestClient, db: sqlite3.Connection) -> None:
    add_example(db)

    rows = [row.split(";") for row in body_rows(comparison_csv(api, "month=2026-10&weeks=true"))]
    page = api.get("/api/budget/comparison?month=2026-10").json()

    expected: list[tuple[int, int]] = [
        (row["budget_cents"], row["actual_cents"]) for row in page["rows"]
    ]
    for week in range(len(page["weeks"])):
        expected += [
            (row["weeks"][week]["budget_cents"], row["weeks"][week]["actual_cents"])
            for row in page["rows"]
        ]
    assert [(cents(row[6]), cents(row[7])) for row in rows[1:]] == expected
    assert all(cents(row[8]) == cents(row[6]) - cents(row[7]) for row in rows[1:])


def test_ac5_only_reviewed_receipts_count(api: TestClient, db: sqlite3.Connection) -> None:
    add_example(db)
    add_receipt(db, "2026-10-02", [("Limu", 1000, "Juomat")], reviewed=False)

    rows = body_rows(comparison_csv(api, "month=2026-10"))

    assert rows[2] == WHOLE_OCTOBER[1]


def test_ac6_mid_period(api: TestClient, db: sqlite3.Connection) -> None:
    add_example(db)

    with_weeks = comparison_csv(api, "month=2026-10&period=mid&weeks=true")
    without = comparison_csv(api, "month=2026-10&period=mid")

    assert with_weeks.headers["content-disposition"] == (
        'attachment; filename="vertailu_viikot_15-14_2026-10.csv"'
    )
    assert without.headers["content-disposition"] == (
        'attachment; filename="vertailu_15-14_2026-10.csv"'
    )
    rows = body_rows(with_weeks)
    assert rows[1].startswith("Koko jakso;15.10.2026;14.11.2026;ei;")
    assert rows[4].startswith("2026-W42;15.10.2026;18.10.2026;kyllä;")
    assert rows[-1].startswith("2026-W46;09.11.2026;14.11.2026;kyllä;")


def test_ac7_every_budget_row_without_lines(api: TestClient, db: sqlite3.Connection) -> None:
    add_example(db)

    rows = body_rows(comparison_csv(api, "month=2026-11"))

    assert rows == [
        HEADER,
        "Koko jakso;01.11.2026;30.11.2026;ei;ryhmä;Ruoka;400,00;0,00;400,00",
        "Koko jakso;01.11.2026;30.11.2026;ei;kategoria;Juomat;50,00;0,00;50,00",
    ]


def test_ac8_empty_catalog(api: TestClient, db: sqlite3.Connection) -> None:
    keep_only(db, ("",))

    response = comparison_csv(api, "month=2026-11&weeks=true")

    assert response.status_code == 200
    assert response.content == BOM + (HEADER + "\r\n").encode()


@pytest.mark.parametrize("query", ["", "month=2026-13", "month=2026-10&period=week"])
def test_ac10_bad_period(api: TestClient, query: str) -> None:
    response = comparison_csv(api, query)

    assert response.status_code == 422
    assert response.json() == INVALID_PERIOD


@pytest.mark.parametrize(
    ("query", "error"),
    [("month=2026-10&weeks=yes", INVALID_REQUEST), ("month=2026-13&weeks=yes", INVALID_PERIOD)],
)
def test_ac11_bad_weeks(api: TestClient, query: str, error: dict[str, str]) -> None:
    response = comparison_csv(api, query)

    assert response.status_code == 422
    assert response.json() == error


def test_ac12_request_log_holds_no_query_or_names(
    api: TestClient, db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    add_example(db)
    caplog.set_level(logging.DEBUG)

    comparison_csv(api, "month=2026-10&weeks=true")

    # Only the app's own loggers; the test client logs the full URL itself.
    logged = [record.getMessage() for record in caplog.records if record.name.startswith("app")]
    assert [re.sub(r" [0-9]+ms$", "", message) for message in logged] == [
        "GET /api/export/comparison 200"
    ]

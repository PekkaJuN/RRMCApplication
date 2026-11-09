"""PDF files of the totals and the budget comparison (PDF export spec)."""

import logging
import re
import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime

import httpx2
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings
from app.storage.catalog_repository import CatalogRepository
from app.storage.db import connect
from tests.integration.conftest import BASE_URL
from tests.integration.test_export_api import add_receipt
from tests.pdf_reader import Pdf, read_pdf

# 00:30 on 9 November in Finland: the creation day follows Finnish time.
NOW = datetime(2026, 11, 8, 22, 30, tzinfo=UTC)
OCTOBER = "unit=month&from=2026-10&to=2026-10"
INVALID_PERIOD = {"error": "invalid_period", "message": "Jakso on virheellinen."}
INVALID_REQUEST = {"error": "invalid_request", "message": "Pyyntö on virheellinen."}
TOO_LONG = {"error": "period_too_long", "message": "Jakso on liian pitkä PDF-tiedostoon."}


@pytest.fixture
def api(settings: Settings) -> Iterator[TestClient]:
    """A started app with a fixed clock."""
    app = create_app(settings, clock=lambda: NOW)
    with TestClient(app, raise_server_exceptions=False, base_url=BASE_URL) as client:
        yield client


@pytest.fixture
def db(api: TestClient, settings: Settings) -> Iterator[sqlite3.Connection]:
    connection = connect(settings.db_path)
    yield connection
    connection.close()


def add_fixture(db: sqlite3.Connection) -> None:
    """Receipts A (unreviewed), B and C (confirmed) of the spec."""
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
    add_receipt(db, "2026-11-01", [("Ruisleipä", 999, "Leivät")], reviewed=True)


def set_budgets(db: sqlite3.Connection) -> None:
    catalog = CatalogRepository(db)
    with catalog.transaction():
        for item in catalog.list_categories():
            if item.name in ("Ruoka", "Juomat"):
                catalog.set_budget(item.id, 40000 if item.name == "Ruoka" else 5000)


def totals_pdf(api: TestClient, query: str, by: str | None = "week") -> httpx2.Response:
    suffix = f"&by={by}" if by is not None else ""
    return api.get(f"/api/export/totals/pdf?{query}{suffix}")


def comparison_pdf(api: TestClient, query: str) -> httpx2.Response:
    return api.get(f"/api/export/comparison/pdf?{query}")


def pdf(response: httpx2.Response) -> Pdf:
    assert response.status_code == 200, response.text
    return read_pdf(response.content)


def all_rows(document: Pdf) -> list[str]:
    return [row for page in document.pages for row in page.rows()]


def test_ac1_weekly_pdf_of_a_month(api: TestClient, db: sqlite3.Connection) -> None:
    add_fixture(db)

    response = totals_pdf(api, OCTOBER)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == (
        'attachment; filename="summat_viikot_2026-10_2026-10.pdf"'
    )
    assert response.headers["cache-control"] == "no-store"
    rows = all_rows(pdf(response))
    assert rows[:3] == ["Viikkosummat", "Jakso: 1.10.2026–31.10.2026", "Luotu 9.11.2026"]
    assert "Tarkistamattomia kuitteja jaksolla: 1" in rows
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


def test_ac3_ac4_monthly_pdf(api: TestClient, db: sqlite3.Connection) -> None:
    add_fixture(db)

    response = totals_pdf(api, "unit=month&from=2026-10&to=2026-11", "month")

    assert response.headers["content-disposition"] == (
        'attachment; filename="summat_kuukaudet_2026-10_2026-11.pdf"'
    )
    document = pdf(response)
    rows = all_rows(document)
    assert "Jakso: 1.10.2026–30.11.2026" in rows
    assert [row for row in rows if row in ("10/2026", "11/2026", "Koko jakso")] == [
        "10/2026",
        "11/2026",
        "Koko jakso",
    ]
    assert [row for row in rows if row.startswith("Yhteensä |")] == [
        "Yhteensä | 8,74 €",
        "Yhteensä | 9,99 €",
        "Yhteensä | 18,73 €",
    ]
    assert "-0,40 €" not in document.text


def test_ac4_one_month_has_no_period_block(api: TestClient, db: sqlite3.Connection) -> None:
    add_fixture(db)

    rows = all_rows(pdf(totals_pdf(api, OCTOBER, "month")))

    assert "Koko jakso" not in rows


def test_ac5_date_range_crossing_the_year(api: TestClient, db: sqlite3.Connection) -> None:
    add_receipt(db, "2026-12-30", [("Ruisleipä", 500, "Leivät")])
    add_receipt(db, "2027-01-02", [("Ruisleipä", 700, "Leivät")])

    response = totals_pdf(api, "unit=range&from=2026-12-15&to=2027-01-14")

    assert response.headers["content-disposition"] == (
        'attachment; filename="summat_viikot_2026-12-15_2027-01-14.pdf"'
    )
    document = pdf(response)
    assert "Jakso: 15.12.2026–14.1.2027" in all_rows(document)
    assert "Leivät | 0,00 € | 0,00 € | 12,00 € | 0,00 € | 0,00 €" in all_rows(document)


@pytest.mark.parametrize(
    ("query", "by", "status"),
    [
        ("unit=range&from=2026-10-01&to=2026-10-31", "week", 200),
        ("unit=range&from=2026-10-01&to=2026-11-01", "week", 422),
        ("unit=week&from=2026-W40&to=2026-W43", "week", 200),
        ("unit=week&from=2026-W40&to=2026-W44", "week", 422),
        ("unit=month&from=2026-01&to=2026-12", "month", 200),
        ("unit=range&from=2026-01-15&to=2027-01-14", "month", 200),
        ("unit=range&from=2026-01-01&to=2027-01-01", "month", 200),
        ("unit=range&from=2026-01-01&to=2027-01-02", "month", 422),
        ("unit=month&from=2026-01&to=2027-01", "month", 422),
    ],
)
def test_ac6_ac7_ac8_length_limits(api: TestClient, query: str, by: str, status: int) -> None:
    response = totals_pdf(api, query, by)

    assert response.status_code == status
    if status == 422:
        assert response.json() == TOO_LONG


def test_ac9_invalid_requests(api: TestClient) -> None:
    assert totals_pdf(api, "unit=month&from=2026-13&to=2026-13").json() == INVALID_PERIOD
    assert totals_pdf(api, OCTOBER, None).json() == INVALID_REQUEST
    assert totals_pdf(api, OCTOBER, "day").json() == INVALID_REQUEST
    both = totals_pdf(api, "unit=month&from=2026-13&to=2026-13", "day")
    assert both.status_code == 422
    assert both.json() == INVALID_PERIOD


def test_ac9_a_bad_by_comes_before_the_length(api: TestClient) -> None:
    response = totals_pdf(api, "unit=month&from=2026-01&to=2027-01", "day")

    assert response.json() == INVALID_REQUEST


def test_ac10_empty_period(api: TestClient) -> None:
    document = pdf(totals_pdf(api, OCTOBER))

    assert "Ei ostoksia valitulla jaksolla." in all_rows(document)
    assert "Kategoria" not in document.text


def test_ac11_comparison_pdf_of_a_calendar_month(api: TestClient, db: sqlite3.Connection) -> None:
    add_fixture(db)
    set_budgets(db)

    response = comparison_pdf(api, "month=2026-10")

    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == (
        'attachment; filename="vertailu_2026-10.pdf"'
    )
    assert response.headers["cache-control"] == "no-store"
    rows = all_rows(pdf(response))
    assert rows[:4] == [
        "Budjettivertailu",
        "Jakso: 1.10.2026–31.10.2026",
        "Jakson tyyppi: Kalenterikuukausi",
        "Luotu 9.11.2026",
    ]
    assert "Tarkistamattomia kuitteja, ei mukana: 1" in rows
    expected = [
        "Ruoka | 400,00 € | 3,00 € | 397,00 €",
        "Juomat | 50,00 € | 2,50 € | 47,50 €",
        "Ei kategoriaa | 0,00 € | 1,99 € | -1,99 € Ylitetty",
        "Yhteensä | 450,00 € | 7,49 € | 442,51 €",
    ]
    assert [row for row in rows if row in expected] == expected


def test_ac12_comparison_pdf_of_a_mid_period(api: TestClient, db: sqlite3.Connection) -> None:
    add_fixture(db)
    set_budgets(db)

    response = comparison_pdf(api, "month=2026-10&period=mid")

    assert response.headers["content-disposition"] == (
        'attachment; filename="vertailu_15-14_2026-10.pdf"'
    )
    rows = all_rows(pdf(response))
    assert "Jakso: 15.10.2026–14.11.2026" in rows
    assert "Jakson tyyppi: 15.–14." in rows
    assert "Ruoka | 400,00 € | 9,99 € | 390,01 €" in rows


@pytest.mark.parametrize("query", ["month=2026-13", "", "month=2026-10&period=x"])
def test_ac13_comparison_pdf_errors(api: TestClient, query: str) -> None:
    response = comparison_pdf(api, query)

    assert response.status_code == 422
    assert response.json() == INVALID_PERIOD


def test_ac18_request_log_holds_method_path_and_status_only(
    api: TestClient, db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    add_fixture(db)
    caplog.set_level(logging.DEBUG)

    totals_pdf(api, OCTOBER)
    comparison_pdf(api, "month=2026-10")

    # Only the app's own loggers; the test client logs the full URL itself.
    logged = [record.getMessage() for record in caplog.records if record.name.startswith("app")]
    assert [re.sub(r" [0-9]+ms$", "", message) for message in logged] == [
        "GET /api/export/totals/pdf 200",
        "GET /api/export/comparison/pdf 200",
    ]

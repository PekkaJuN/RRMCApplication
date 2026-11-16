"""Totals of the current year per group, category and product, and their CSV file (year
with products spec T3, T5, T6)."""

import logging
import sqlite3
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings
from app.storage.catalog_repository import CatalogRepository
from app.storage.db import connect
from app.storage.receipt_repository import LineCategory, ReceiptRepository
from tests.integration.conftest import BASE_URL

NOW = datetime(2026, 6, 15, 9, 0, tzinfo=UTC)
TIME = "2026-06-15T09:00:00Z"

ClientFactory = Callable[..., TestClient]


@pytest.fixture
def open_client(settings: Settings) -> Iterator[ClientFactory]:
    clients: list[TestClient] = []

    def open_one(clock: Callable[[], datetime] = lambda: NOW) -> TestClient:
        client = TestClient(create_app(settings, clock=clock), base_url=BASE_URL)
        client.__enter__()
        clients.append(client)
        return client

    yield open_one
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def api(open_client: ClientFactory) -> TestClient:
    return open_client()


class Data:
    """Reviewed receipts with one line each, in a catalog emptied of the default list, so
    the synthetic names cannot clash with it."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.catalog = CatalogRepository(connection)
        self.receipts = ReceiptRepository(connection)
        self.number = 0
        self.ids: dict[str, int] = {}
        with self.catalog.transaction():
            connection.execute("DELETE FROM products")
            connection.execute("DELETE FROM categories WHERE kind = 'category'")
            connection.execute("DELETE FROM categories")

    def category(self, name: str, group: str | None) -> int:
        if name not in self.ids:
            parent = None
            if group is not None:
                if group not in self.ids:
                    self.ids[group] = self.catalog.add_category(group, group.lower(), "group", None)
                parent = self.ids[group]
            self.ids[name] = self.catalog.add_category(name, name.lower(), "category", parent)
        return self.ids[name]

    def line(
        self,
        day: str | None,
        amount: int,
        name: str,
        category: str | None = None,
        group: str | None = None,
        *,
        reviewed: bool = True,
        deposit: bool = False,
    ) -> tuple[int, int]:
        self.number += 1
        with self.receipts.transaction():
            receipt = self.receipts.add(
                f"{self.number:064d}", "kuitti.jpg", TIME, store="Kauppa", purchase_date=day
            )
            line_category = None
            if category is not None:
                category_id = self.category(category, group)
                key = f"{category}/{name}"
                if key not in self.ids:
                    self.ids[key] = self.catalog.add_product(name, name.lower(), category_id)
                line_category = LineCategory(category_id, "user", self.ids[key])
            line_id = self.receipts.add_line(
                receipt.id, 1, name, amount, is_deposit_refund=deposit, category=line_category
            )
            self.receipts.set_reviewed(receipt.id, reviewed=reviewed)
        return receipt.id, line_id


@pytest.fixture
def data(api: TestClient, settings: Settings) -> Iterator[Data]:
    connection = connect(settings.db_path)
    yield Data(connection)
    connection.close()


def ac1(data: Data) -> dict[str, tuple[int, int]]:
    return {
        "milk": data.line("2026-01-10", 250, "Maito 1l", "Maito", "Maitotuotteet"),
        "milk2": data.line("2026-01-25", 250, "Maito 1l", "Maito", "Maitotuotteet"),
        "edam": data.line("2026-01-20", 400, "Edam", "Juusto", "Maitotuotteet"),
        "coffee": data.line("2026-03-05", 500, "Kahvi 500g", "Kahvi"),
        "unknown": data.line("2026-03-06", 100, "TUNTEMATON"),
        "refund": data.line("2026-03-06", -40, "Panttipalautus", deposit=True),
    }


def months(**amounts: int) -> list[int]:
    return [amounts.get(f"m{number}", 0) for number in range(1, 13)]


def product(name: str, sums: list[int]) -> dict[str, Any]:
    return {"kind": "product", "name": name, "months": sums, "total": sum(sums), "children": []}


def node(kind: str, name: str | None, sums: list[int], *children: Any) -> dict[str, Any]:
    return {
        "kind": kind,
        "name": name,
        "months": sums,
        "total": sum(sums),
        "children": list(children),
    }


AC1_ROWS = [
    node("category", "Kahvi", months(m3=500), product("Kahvi 500g", months(m3=500))),
    node(
        "group",
        "Maitotuotteet",
        months(m1=900),
        node("category", "Juusto", months(m1=400), product("Edam", months(m1=400))),
        node("category", "Maito", months(m1=500), product("Maito 1l", months(m1=500))),
    ),
    node("none", None, months(m3=100), product("TUNTEMATON", months(m3=100))),
]


def test_year_ac1_current_year_totals(api: TestClient, data: Data) -> None:
    ac1(data)

    response = api.get("/api/year/totals")

    assert response.status_code == 200
    assert response.json() == {
        "year": 2026,
        "months": [f"2026-{number:02d}" for number in range(1, 13)],
        "rows": AC1_ROWS,
        "month_totals": months(m1=900, m3=600),
        "total": 1500,
        "unreviewed": 0,
    }


def test_year_ac2_only_reviewed_receipts_are_counted(api: TestClient, data: Data) -> None:
    ac1(data)
    data.line("2026-02-01", 300, "Maito 1l", "Maito", "Maitotuotteet", reviewed=False)
    data.line("2026-04-01", 999, "Limu", reviewed=False)

    body = api.get("/api/year/totals").json()

    assert body["rows"] == AC1_ROWS
    assert body["month_totals"] == months(m1=900, m3=600)
    assert body["total"] == 1500
    assert body["unreviewed"] == 2


def test_year_ac3_only_the_current_year_is_counted(api: TestClient, data: Data) -> None:
    for day, amount in [
        ("2025-12-31", 100),
        ("2026-01-01", 200),
        ("2026-12-31", 300),
        ("2027-01-01", 400),
        (None, 500),
    ]:
        data.line(day, amount, f"Kahvi {amount}", "Kahvi")

    body = api.get("/api/year/totals").json()

    assert [(row["name"], row["months"], row["total"]) for row in body["rows"]] == [
        ("Kahvi", months(m1=200, m12=300), 500)
    ]
    assert body["total"] == 500


def test_year_ac4_finnish_time_decides_the_current_year(
    open_client: ClientFactory, settings: Settings
) -> None:
    api = open_client(lambda: datetime(2025, 12, 31, 22, 30, tzinfo=UTC))
    connection = connect(settings.db_path)
    try:
        data = Data(connection)
        data.line("2025-12-31", 100, "Kahvi 500g", "Kahvi")
        data.line("2026-01-01", 200, "Kahvi 500g", "Kahvi")
    finally:
        connection.close()

    body = api.get("/api/year/totals").json()

    assert body["year"] == 2026
    assert [(row["name"], row["total"]) for row in body["rows"]] == [("Kahvi", 200)]


def test_year_ac5_current_names_are_used(api: TestClient, data: Data) -> None:
    _, line_id = data.line("2026-03-01", 100, "Maito 1l", "Maito", "Maitotuotteet")
    data.connection.execute(
        "UPDATE receipt_lines SET name = 'MAITO 1L VALIO' WHERE id = ?", (line_id,)
    )
    product_id = data.ids["Maito/Maito 1l"]
    with data.catalog.transaction():
        data.catalog.update_product(product_id, "Maito 1 l", "maito 1 l", data.ids["Maito"])
        data.catalog.update_category(
            data.ids["Maito"], "Maidot", "maidot", "category", data.ids["Maitotuotteet"]
        )

    body = api.get("/api/year/totals").json()

    assert body["rows"] == [
        node(
            "group",
            "Maitotuotteet",
            months(m3=100),
            node("category", "Maidot", months(m3=100), product("Maito 1 l", months(m3=100))),
        )
    ]


def test_year_ac8_an_edit_shows_at_once(api: TestClient, data: Data) -> None:
    lines = ac1(data)
    receipt_id, edam = lines["edam"]

    edited = api.patch(f"/api/receipts/{receipt_id}/lines/{edam}", json={"amount_cents": 600})
    body = api.get("/api/year/totals").json()

    assert edited.status_code == 200
    group = body["rows"][1]
    assert group["children"][0]["name"] == "Juusto"
    assert group["children"][0]["months"] == months(m1=600)
    assert body["total"] == 1700


def test_year_ac9_empty_year(api: TestClient, data: Data) -> None:
    data.line("2026-05-01", 100, "Limu", reviewed=False)

    body = api.get("/api/year/totals").json()

    assert body["rows"] == []
    assert body["month_totals"] == [0] * 12
    assert body["total"] == 0
    assert body["unreviewed"] == 1


def test_year_ac10_year_csv(api: TestClient, data: Data) -> None:
    ac1(data)

    response = api.get("/api/export/year")

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert 'filename="vuosi_2026.csv"' in response.headers["content-disposition"]
    rows = response.content.decode("utf-8").split("\r\n")
    assert rows[0] == "﻿Jakso;Alkaa;Päättyy;Ryhmä;Kategoria;Tuote;Summa"
    assert rows[1:] == [
        "2026-01;01.01.2026;31.01.2026;Maitotuotteet;Juusto;Edam;4,00",
        "2026-01;01.01.2026;31.01.2026;Maitotuotteet;Maito;Maito 1l;5,00",
        "2026-03;01.03.2026;31.03.2026;;Kahvi;Kahvi 500g;5,00",
        "2026-03;01.03.2026;31.03.2026;;Ei kategoriaa;TUNTEMATON;1,00",
        "2026;01.01.2026;31.12.2026;;Kahvi;Kahvi 500g;5,00",
        "2026;01.01.2026;31.12.2026;Maitotuotteet;Juusto;Edam;4,00",
        "2026;01.01.2026;31.12.2026;Maitotuotteet;Maito;Maito 1l;5,00",
        "2026;01.01.2026;31.12.2026;;Ei kategoriaa;TUNTEMATON;1,00",
        "",
    ]


def test_year_ac9_empty_year_csv(api: TestClient, data: Data) -> None:
    data.line("2026-05-01", 100, "Limu", reviewed=False)

    response = api.get("/api/export/year")

    assert response.status_code == 200
    assert response.content.decode("utf-8") == (
        "﻿Jakso;Alkaa;Päättyy;Ryhmä;Kategoria;Tuote;Summa\r\n"
    )


def test_year_ac18_no_names_in_the_log(
    api: TestClient, data: Data, caplog: pytest.LogCaptureFixture
) -> None:
    ac1(data)
    caplog.set_level(logging.DEBUG)

    totals = api.get("/api/year/totals")
    csv = api.get("/api/export/year")

    assert totals.status_code == 200
    assert csv.status_code == 200
    # The request lines are captured, so the check below reads the real log.
    assert "GET /api/year/totals 200" in caplog.text
    assert "GET /api/export/year 200" in caplog.text
    for name in ("Maito", "Edam", "Juusto", "Kahvi", "TUNTEMATON", "Maitotuotteet", "Kauppa"):
        assert name not in caplog.text

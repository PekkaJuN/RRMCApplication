"""Totals of an archived year and their CSV file (archiving spec PC11, PC13; AC26, AC27,
AC31)."""

import sqlite3
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.settings import Settings
from app.storage.db import connect

# AC26: (date, amount, product, category, group, deposit refund)
AC26_LINES = [
    ("2025-01-10", 250, "Maito 1l", "Maito", "Maitotuotteet", 0),
    ("2025-01-25", 250, "Maito 1l", "Maito", "Maitotuotteet", 0),
    ("2025-01-20", 400, "Edam", "Juusto", "Maitotuotteet", 0),
    ("2025-03-05", 500, "Kahvi 500g", "Kahvi", None, 0),
    ("2025-03-06", 100, "TUNTEMATON", None, None, 0),
    ("2025-03-06", -40, "PANTTI", None, None, 1),
]


@pytest.fixture
def db(api: TestClient, settings: Settings) -> Iterator[sqlite3.Connection]:
    connection = connect(settings.db_path)
    yield connection
    connection.close()


def archive(db: sqlite3.Connection, lines: list[tuple[Any, ...]]) -> None:
    """One archived receipt per line, written straight into the archive tables."""
    for index, (day, amount, product, category, group, deposit) in enumerate(lines, start=1):
        db.execute(
            "INSERT INTO archived_receipts (id, year, purchase_date, store, total_cents,"
            " imported_at, archived_at) VALUES (?, ?, ?, 'Kauppa', ?, 't', 't')",
            (index, int(day[:4]), day, amount),
        )
        db.execute(
            "INSERT INTO archived_lines (receipt_id, position, name, product_name, amount_cents,"
            " is_deposit_refund, category_name, group_name) VALUES (?, 1, ?, ?, ?, ?, ?, ?)",
            (index, product, product, amount, deposit, category, group),
        )


def months(**amounts: int) -> list[int]:
    return [amounts.get(f"m{number}", 0) for number in range(1, 13)]


def product(name: str, sums: list[int]) -> dict[str, Any]:
    return {"kind": "product", "name": name, "months": sums, "total": sum(sums), "children": []}


def test_ac26_archived_year_totals(api: TestClient, db: sqlite3.Connection) -> None:
    archive(db, AC26_LINES)

    response = api.get("/api/archive/2025/totals")

    assert response.status_code == 200
    body = response.json()
    assert body["year"] == 2025
    assert body["months"] == [f"2025-{number:02d}" for number in range(1, 13)]
    assert body["rows"] == [
        {
            "kind": "category",
            "name": "Kahvi",
            "months": months(m3=500),
            "total": 500,
            "children": [product("Kahvi 500g", months(m3=500))],
        },
        {
            "kind": "group",
            "name": "Maitotuotteet",
            "months": months(m1=900),
            "total": 900,
            "children": [
                {
                    "kind": "category",
                    "name": "Juusto",
                    "months": months(m1=400),
                    "total": 400,
                    "children": [product("Edam", months(m1=400))],
                },
                {
                    "kind": "category",
                    "name": "Maito",
                    "months": months(m1=500),
                    "total": 500,
                    "children": [product("Maito 1l", months(m1=500))],
                },
            ],
        },
        {
            "kind": "none",
            "name": None,
            "months": months(m3=100),
            "total": 100,
            "children": [product("TUNTEMATON", months(m3=100))],
        },
    ]
    assert body["month_totals"] == months(m1=900, m3=600)
    assert body["total"] == 1500


def test_ac27_totals_of_a_year_not_archived(api: TestClient, db: sqlite3.Connection) -> None:
    archive(db, AC26_LINES)

    response = api.get("/api/archive/2023/totals")

    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


def test_ac9_totals_of_a_bad_year(api: TestClient) -> None:
    response = api.get("/api/archive/abcd/totals")

    assert response.status_code == 422
    assert response.json()["error"] == "invalid_year"


def test_ac31_archived_totals_csv(api: TestClient, db: sqlite3.Connection) -> None:
    archive(db, AC26_LINES)

    response = api.get("/api/export/archive/2025")

    assert response.status_code == 200
    assert response.headers["content-disposition"] == 'attachment; filename="arkisto_2025.csv"'
    assert response.content.decode("utf-8") == (
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


def test_ac31_csv_of_a_year_not_archived(api: TestClient) -> None:
    assert api.get("/api/export/archive/2023").status_code == 404
    assert api.get("/api/export/archive/abcd").json()["error"] == "invalid_year"

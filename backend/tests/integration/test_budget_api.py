"""Monthly budgets and their comparison with reviewed spending (budget spec)."""

import logging
import sqlite3
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.calculation.money import AMOUNT_LIMIT
from app.categorization.names import normalize_key
from app.settings import Settings
from app.storage.catalog_repository import CatalogRepository
from app.storage.db import connect
from app.storage.receipt_repository import LineCategory, ReceiptRepository

TIME = "2026-11-02T10:00:01Z"
OCTOBER = "/api/budget/comparison?month=2026-10"
OCTOBER_MID = f"{OCTOBER}&period=mid"

_numbers = iter(range(1, 10_000))


@pytest.fixture
def db(api: TestClient, settings: Settings) -> Iterator[sqlite3.Connection]:
    """A connection to the app's database after its startup (migrations, default list)."""
    connection = connect(settings.db_path)
    yield connection
    connection.close()


def item_id(db: sqlite3.Connection, name: str) -> int:
    row = CatalogRepository(db).get_category_by_key(normalize_key(name))
    assert row is not None
    return row.id


def category(db: sqlite3.Connection, name: str) -> LineCategory:
    return LineCategory(item_id(db, name), "user", None)


def add_receipt(
    db: sqlite3.Connection,
    purchase_date: str | None,
    lines: list[tuple[str, int, LineCategory | None]],
    *,
    reviewed: bool = True,
) -> None:
    """A receipt with lines (name, amount, category); a name `Panttipalautus` is a refund."""
    receipts = ReceiptRepository(db)
    with receipts.transaction():
        row = receipts.add(
            f"{next(_numbers):064d}", "kuitti.jpg", TIME, purchase_date=purchase_date
        )
        for position, (name, amount, line_category) in enumerate(lines, start=1):
            receipts.add_line(
                row.id,
                position,
                name,
                amount,
                is_deposit_refund=name == "Panttipalautus",
                category=line_category,
            )
        receipts.set_reviewed(row.id, reviewed=reviewed)


def fixture_budgets(api: TestClient, db: sqlite3.Connection) -> None:
    """The fixture of the spec: `Ruoka` 40000 and `Juomat` 5000."""
    for name, amount in (("Ruoka", 40000), ("Juomat", 5000)):
        response = api.put(f"/api/budget/{item_id(db, name)}", json={"amount_cents": amount})
        assert response.status_code == 200


def row_named(body: dict[str, Any], name: str | None) -> dict[str, Any]:
    return next(row for row in body["rows"] if row["name"] == name)


def amounts(body: dict[str, Any]) -> dict[str, int]:
    return {row["name"]: row["amount_cents"] for row in body["rows"]}


# Budget rows


def test_ac1_rows_of_the_default_catalog(api: TestClient) -> None:
    response = api.get("/api/budget")

    assert response.status_code == 200
    body = response.json()
    assert len(body["rows"]) == 10
    assert [row["kind"] for row in body["rows"]] == ["group"] * 2 + ["category"] * 8
    assert all(row["amount_cents"] == 0 for row in body["rows"])
    assert "Maitotuotteet" not in amounts(body)
    assert body["total_cents"] == 0


def test_ac2_saving_a_budget_updates_the_total(api: TestClient, db: sqlite3.Connection) -> None:
    fixture_budgets(api, db)

    response = api.put(f"/api/budget/{item_id(db, 'Auto')}", json={"amount_cents": 15000})

    assert response.status_code == 200
    body = response.json()
    assert amounts(body)["Auto"] == 15000
    assert body["total_cents"] == 60000
    assert api.get("/api/budget").json() == body


def test_ac3_a_category_inside_a_group_has_no_budget(
    api: TestClient, db: sqlite3.Connection
) -> None:
    response = api.put(f"/api/budget/{item_id(db, 'Maitotuotteet')}", json={"amount_cents": 100})

    assert response.status_code == 422
    assert response.json()["error"] == "not_a_budget_row"
    assert CatalogRepository(db).budgets() == {}


@pytest.mark.parametrize("amount", [-1, AMOUNT_LIMIT + 1])
def test_ac4_an_amount_out_of_range_is_refused(
    api: TestClient, db: sqlite3.Connection, amount: int
) -> None:
    response = api.put(f"/api/budget/{item_id(db, 'Juomat')}", json={"amount_cents": amount})

    assert response.status_code == 422
    assert response.json()["error"] == "invalid_amount"
    assert CatalogRepository(db).budgets() == {}


@pytest.mark.parametrize("amount", [1.5, "100"])
def test_ac4_an_amount_of_the_wrong_type_is_refused(
    api: TestClient, db: sqlite3.Connection, amount: float | str
) -> None:
    response = api.put(f"/api/budget/{item_id(db, 'Juomat')}", json={"amount_cents": amount})

    assert response.status_code == 422
    assert CatalogRepository(db).budgets() == {}


def test_ac4_an_unknown_id_is_not_found(api: TestClient, db: sqlite3.Connection) -> None:
    response = api.put("/api/budget/99999", json={"amount_cents": 100})

    assert response.status_code == 404
    assert response.json()["error"] == "not_found"
    assert CatalogRepository(db).budgets() == {}


@pytest.mark.parametrize("amount", [0, AMOUNT_LIMIT])
def test_ac4_the_limits_are_accepted(api: TestClient, db: sqlite3.Connection, amount: int) -> None:
    response = api.put(f"/api/budget/{item_id(db, 'Juomat')}", json={"amount_cents": amount})

    assert response.status_code == 200
    assert amounts(response.json())["Juomat"] == amount


def test_ac1_rows_follow_the_category_list_order(api: TestClient) -> None:
    # Insertion order would put the group Ruoka first and a new category last.
    api.post("/api/categories", json={"name": "Aakkoset", "kind": "category"})

    names = [row["name"] for row in api.get("/api/budget").json()["rows"]]

    assert names[:3] == ["Auto", "Ruoka", "Aakkoset"]


# Catalog changes


def test_ac16_a_deleted_row_loses_its_budget(api: TestClient, db: sqlite3.Connection) -> None:
    created = api.post("/api/categories", json={"name": "Testi", "kind": "category"}).json()
    api.put(f"/api/budget/{created['id']}", json={"amount_cents": 1000})
    fixture_budgets(api, db)

    assert api.delete(f"/api/categories/{created['id']}").status_code == 204

    body = api.get("/api/budget").json()
    assert "Testi" not in amounts(body)
    assert body["total_cents"] == 45000
    api.post("/api/categories", json={"name": "Testi", "kind": "category"})
    assert amounts(api.get("/api/budget").json())["Testi"] == 0


def test_ac16_a_renamed_row_keeps_its_budget(api: TestClient, db: sqlite3.Connection) -> None:
    fixture_budgets(api, db)

    api.patch(f"/api/categories/{item_id(db, 'Juomat')}", json={"name": "Virvokkeet"})

    assert amounts(api.get("/api/budget").json())["Virvokkeet"] == 5000


def test_ac23_a_budgeted_category_moves_into_a_group(
    api: TestClient, db: sqlite3.Connection
) -> None:
    fixture_budgets(api, db)
    drinks = category(db, "Juomat")
    add_receipt(db, "2026-10-05", [("Limu", 300, drinks)])

    response = api.patch(
        f"/api/categories/{drinks.category_id}", json={"parent_id": item_id(db, "Ruoka")}
    )

    assert response.status_code == 200
    body = api.get("/api/budget").json()
    assert amounts(body)["Ruoka"] == 45000
    assert "Juomat" not in amounts(body)
    assert body["total_cents"] == 45000
    assert row_named(api.get(OCTOBER).json(), "Ruoka")["actual_cents"] == 300


def test_ac24_a_category_leaves_a_group(api: TestClient, db: sqlite3.Connection) -> None:
    fixture_budgets(api, db)
    dairy = category(db, "Maitotuotteet")
    add_receipt(db, "2026-10-05", [("Maito", 125, dairy)])

    response = api.patch(f"/api/categories/{dairy.category_id}", json={"parent_id": None})

    assert response.status_code == 200
    body = api.get("/api/budget").json()
    assert amounts(body)["Maitotuotteet"] == 0
    assert amounts(body)["Ruoka"] == 40000
    comparison = api.get(OCTOBER).json()
    assert row_named(comparison, "Maitotuotteet")["actual_cents"] == 125
    assert row_named(comparison, "Ruoka")["actual_cents"] == 0


# Comparison


def test_ac7_only_reviewed_receipts_count(api: TestClient, db: sqlite3.Connection) -> None:
    fixture_budgets(api, db)
    dairy = category(db, "Maitotuotteet")
    add_receipt(db, "2026-10-05", [("Maito", 125, dairy)])
    add_receipt(db, "2026-10-06", [("Maito", 300, dairy)], reviewed=False)

    response = api.get(OCTOBER)

    assert response.status_code == 200
    body = response.json()
    ruoka = row_named(body, "Ruoka")
    assert (ruoka["actual_cents"], ruoka["remaining_cents"]) == (125, 39875)
    assert body["unreviewed_receipts"] == 1


def test_ac9_the_same_budget_every_month(api: TestClient, db: sqlite3.Connection) -> None:
    fixture_budgets(api, db)
    months = [OCTOBER, "/api/budget/comparison?month=2027-03"]

    assert [row_named(api.get(url).json(), "Ruoka")["budget_cents"] for url in months] == [
        40000,
        40000,
    ]

    api.put(f"/api/budget/{item_id(db, 'Ruoka')}", json={"amount_cents": 30000})

    assert [row_named(api.get(url).json(), "Ruoka")["budget_cents"] for url in months] == [
        30000,
        30000,
    ]


def test_ac10_weeks_of_a_month(api: TestClient, db: sqlite3.Connection) -> None:
    fixture_budgets(api, db)
    drinks = category(db, "Juomat")
    add_receipt(db, "2026-10-02", [("Limu", 100, drinks)])
    add_receipt(db, "2026-11-01", [("Limu", 999, drinks)])

    body = api.get(OCTOBER).json()

    assert body["month"] == "2026-10"
    assert body["weeks"][0] == {
        "key": "2026-W40",
        "start_date": "2026-10-01",
        "end_date": "2026-10-04",
        "partial": True,
    }
    assert [week["key"] for week in body["weeks"]] == [
        "2026-W40",
        "2026-W41",
        "2026-W42",
        "2026-W43",
        "2026-W44",
    ]
    assert body["weeks"][4]["end_date"] == "2026-10-31"
    weeks = row_named(body, "Juomat")["weeks"]
    assert [week["budget_cents"] for week in weeks] == [645, 1129, 1129, 1129, 968]
    assert [week["actual_cents"] for week in weeks] == [100, 0, 0, 0, 0]


def test_ac12_deposit_refunds_undated_receipts_and_purchase_date(
    api: TestClient, db: sqlite3.Connection
) -> None:
    fixture_budgets(api, db)
    dairy = category(db, "Maitotuotteet")
    add_receipt(db, "2026-10-05", [("Maito", 229, dairy), ("Panttipalautus", -40, None)])
    add_receipt(db, None, [("Maito", 300, dairy)])

    body = api.get(OCTOBER).json()

    assert row_named(body, "Ruoka")["actual_cents"] == 229
    assert body["undated_receipts"] == 1
    assert all(row["kind"] != "none" for row in body["rows"])


def test_ac13_lines_without_a_category(api: TestClient, db: sqlite3.Connection) -> None:
    fixture_budgets(api, db)
    add_receipt(
        db, "2026-10-05", [("Limu", 300, category(db, "Juomat")), ("Tuntematon", 199, None)]
    )

    body = api.get(OCTOBER).json()

    last = body["rows"][-1]
    assert (last["kind"], last["id"], last["name"]) == ("none", None, None)
    assert (last["budget_cents"], last["actual_cents"], last["remaining_cents"]) == (0, 199, -199)
    assert body["total"]["actual_cents"] == 499


def test_ac14_an_empty_month(api: TestClient, db: sqlite3.Connection) -> None:
    fixture_budgets(api, db)

    response = api.get("/api/budget/comparison?month=2026-03")

    assert response.status_code == 200
    body = response.json()
    assert len(body["rows"]) == 10
    assert all(row["actual_cents"] == 0 for row in body["rows"])
    assert body["total"]["remaining_cents"] == 45000


@pytest.mark.parametrize(
    "query", ["", "?month=2026-13", "?month=2026-W40", "?month=2026-10&period=bad", "?period=mid"]
)
def test_ac15_ac30_an_invalid_period_is_refused(api: TestClient, query: str) -> None:
    response = api.get(f"/api/budget/comparison{query}")

    assert response.status_code == 422
    assert response.json()["error"] == "invalid_period"


@pytest.mark.parametrize("url", [OCTOBER, f"{OCTOBER}&period=calendar"])
def test_ac30_a_calendar_period(api: TestClient, url: str) -> None:
    response = api.get(url)

    assert response.status_code == 200
    body = response.json()
    assert body["period"] == "calendar"
    assert (body["start_date"], body["end_date"]) == ("2026-10-01", "2026-10-31")


def add_period_bound_receipts(db: sqlite3.Connection) -> None:
    drinks = category(db, "Juomat")
    for day, amount in (
        ("2026-10-14", 999),
        ("2026-10-15", 100),
        ("2026-11-14", 200),
        ("2026-11-15", 999),
    ):
        add_receipt(db, day, [("Limu", amount, drinks)])


def test_ac26_a_mid_period_holds_its_first_and_last_day(
    api: TestClient, db: sqlite3.Connection
) -> None:
    fixture_budgets(api, db)
    add_period_bound_receipts(db)

    body = api.get(OCTOBER_MID).json()

    assert body["period"] == "mid"
    assert (body["start_date"], body["end_date"]) == ("2026-10-15", "2026-11-14")
    juomat = row_named(body, "Juomat")
    assert (juomat["budget_cents"], juomat["actual_cents"], juomat["remaining_cents"]) == (
        5000,
        300,
        4700,
    )


def test_ac27_weeks_of_a_mid_period(api: TestClient, db: sqlite3.Connection) -> None:
    fixture_budgets(api, db)
    add_period_bound_receipts(db)

    body = api.get(OCTOBER_MID).json()

    assert [(week["key"], week["partial"]) for week in body["weeks"]] == [
        ("2026-W42", True),
        ("2026-W43", False),
        ("2026-W44", False),
        ("2026-W45", False),
        ("2026-W46", True),
    ]
    weeks = row_named(body, "Juomat")["weeks"]
    assert [week["budget_cents"] for week in weeks] == [645, 1129, 1129, 1129, 968]
    assert [week["actual_cents"] for week in weeks] == [100, 0, 0, 0, 200]


def test_ac29_counts_follow_the_period(api: TestClient, db: sqlite3.Connection) -> None:
    add_receipt(db, "2026-11-03", [("Limu", 100, category(db, "Juomat"))], reviewed=False)

    assert api.get(OCTOBER_MID).json()["unreviewed_receipts"] == 1
    assert api.get(OCTOBER).json()["unreviewed_receipts"] == 0


def test_ac21_no_product_names_in_the_answer_or_the_log(
    api: TestClient, db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    add_receipt(db, "2026-10-05", [("Salainen Tuote", 300, category(db, "Juomat"))])
    caplog.set_level(logging.DEBUG)

    response = api.get(OCTOBER)

    assert "Salainen" not in response.text
    # Only the app's own loggers; the test client logs the full URL itself.
    logged = "\n".join(
        record.getMessage() for record in caplog.records if record.name.startswith("app")
    )
    assert "GET /api/budget/comparison 200" in logged
    assert "Salainen" not in logged
    assert "2026-10" not in logged


def test_ac22_yhteenveto_still_counts_unreviewed_receipts(
    api: TestClient, db: sqlite3.Connection
) -> None:
    add_receipt(db, "2026-10-05", [("Limu", 300, category(db, "Juomat"))], reviewed=False)

    body = api.get("/api/totals?unit=month&from=2026-10&to=2026-10").json()

    assert body["month_totals"] == [300]

"""Category totals per week and month of a period (totals spec)."""

import logging
import sqlite3
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.categorization.names import normalize_key
from app.settings import Settings
from app.storage.catalog_repository import CatalogRepository
from app.storage.db import connect
from app.storage.receipt_repository import LineCategory, ReceiptRepository

TIME = "2026-11-02T10:00:01Z"
OCTOBER = "/api/totals?unit=month&from=2026-10&to=2026-10"


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


def item_id(db: sqlite3.Connection, name: str) -> int:
    row = CatalogRepository(db).get_category_by_key(normalize_key(name))
    assert row is not None
    return row.id


_numbers = iter(range(1, 10_000))


def add_receipt(
    db: sqlite3.Connection,
    purchase_date: str | None,
    lines: list[tuple[str, int, LineCategory | None]],
    *,
    reviewed: bool = False,
) -> list[int]:
    """A receipt with lines (name, amount, category); a name `Panttipalautus` is a refund."""
    receipts = ReceiptRepository(db)
    with receipts.transaction():
        row = receipts.add(
            f"{next(_numbers):064d}", "kuitti.jpg", TIME, purchase_date=purchase_date
        )
        ids = [
            receipts.add_line(
                row.id,
                position,
                name,
                amount,
                is_deposit_refund=name == "Panttipalautus",
                category=line_category,
            )
            for position, (name, amount, line_category) in enumerate(lines, start=1)
        ]
        receipts.set_reviewed(row.id, reviewed=reviewed)
    return [row.id, *ids]


def rows_by_name(body: dict[str, Any]) -> dict[str, Any]:
    """Every row and category row of an answer by name (`None` for the no-category row)."""
    found: dict[str, Any] = {}
    for row in body["rows"]:
        found[row["name"]] = row
        for child in row["categories"]:
            found[child["name"]] = child
    return found


def test_ac1_month_totals_per_category_and_group(api: TestClient, db: sqlite3.Connection) -> None:
    dairy, bread = category(db, "Maitotuotteet"), category(db, "Leivät")
    add_receipt(db, "2026-10-05", [("Maito", 125, dairy), ("Ruisleipä", 300, bread)])
    add_receipt(db, "2026-10-20", [("Maito", 200, dairy)])

    response = api.get(OCTOBER)

    assert response.status_code == 200
    body = response.json()
    assert body["months"] == [
        {"key": "2026-10", "start_date": "2026-10-01", "end_date": "2026-10-31", "partial": False}
    ]
    assert body["rows"] == [
        {
            "kind": "group",
            "id": item_id(db, "Ruoka"),
            "name": "Ruoka",
            "weeks": [0, 425, 0, 200, 0],
            "months": [625],
            # Category list order: Finnish alphabetical inside the group.
            "categories": [
                {
                    "kind": "category",
                    "id": bread.category_id,
                    "name": "Leivät",
                    "weeks": [0, 300, 0, 0, 0],
                    "months": [300],
                    "categories": [],
                },
                {
                    "kind": "category",
                    "id": dairy.category_id,
                    "name": "Maitotuotteet",
                    "weeks": [0, 125, 0, 200, 0],
                    "months": [325],
                    "categories": [],
                },
            ],
        }
    ]
    assert body["month_totals"] == [625]
    assert body["week_totals"] == [0, 425, 0, 200, 0]
    assert (body["unit"], body["from"], body["to"]) == ("month", "2026-10", "2026-10")
    assert (body["start_date"], body["end_date"]) == ("2026-10-01", "2026-10-31")


def test_ac2_partial_weeks_of_a_month(api: TestClient, db: sqlite3.Connection) -> None:
    dairy, bread = category(db, "Maitotuotteet"), category(db, "Leivät")
    add_receipt(db, "2026-10-05", [("Maito", 125, dairy), ("Ruisleipä", 300, bread)])
    add_receipt(db, "2026-10-20", [("Maito", 200, dairy)])
    add_receipt(db, "2026-10-02", [("Ruisleipä", 100, bread)])
    add_receipt(db, "2026-11-01", [("Ruisleipä", 999, bread)])

    body = api.get(OCTOBER).json()

    assert body["weeks"] == [
        {"key": "2026-W40", "start_date": "2026-10-01", "end_date": "2026-10-04", "partial": True},
        {"key": "2026-W41", "start_date": "2026-10-05", "end_date": "2026-10-11", "partial": False},
        {"key": "2026-W42", "start_date": "2026-10-12", "end_date": "2026-10-18", "partial": False},
        {"key": "2026-W43", "start_date": "2026-10-19", "end_date": "2026-10-25", "partial": False},
        {"key": "2026-W44", "start_date": "2026-10-26", "end_date": "2026-10-31", "partial": True},
    ]
    assert rows_by_name(body)["Leivät"]["weeks"] == [100, 300, 0, 0, 0]
    assert body["month_totals"] == [725]


def test_ac3_week_period_with_partial_months(api: TestClient, db: sqlite3.Connection) -> None:
    bread = category(db, "Leivät")
    add_receipt(db, "2026-09-30", [("Ruisleipä", 100, bread)])
    add_receipt(db, "2026-10-01", [("Ruisleipä", 200, bread)])

    body = api.get("/api/totals?unit=week&from=2026-W40&to=2026-W40").json()

    assert (body["start_date"], body["end_date"]) == ("2026-09-28", "2026-10-04")
    assert [column["key"] for column in body["weeks"]] == ["2026-W40"]
    assert body["months"] == [
        {"key": "2026-09", "start_date": "2026-09-28", "end_date": "2026-09-30", "partial": True},
        {"key": "2026-10", "start_date": "2026-10-01", "end_date": "2026-10-04", "partial": True},
    ]
    assert rows_by_name(body)["Leivät"]["weeks"] == [300]
    assert rows_by_name(body)["Leivät"]["months"] == [100, 200]


def test_ac4_iso_week_across_the_year_boundary(api: TestClient, db: sqlite3.Connection) -> None:
    bread = category(db, "Leivät")
    add_receipt(db, "2025-12-30", [("Ruisleipä", 100, bread)])
    add_receipt(db, "2026-01-02", [("Ruisleipä", 200, bread)])

    body = api.get("/api/totals?unit=month&from=2026-01&to=2026-01").json()

    assert body["weeks"][0] == {
        "key": "2026-W01",
        "start_date": "2026-01-01",
        "end_date": "2026-01-04",
        "partial": True,
    }
    assert rows_by_name(body)["Leivät"]["weeks"][0] == 200
    assert body["month_totals"] == [200]


def test_ac5_week_53(api: TestClient, db: sqlite3.Connection) -> None:
    bread = category(db, "Leivät")
    add_receipt(db, "2027-01-02", [("Ruisleipä", 100, bread)])

    body = api.get("/api/totals?unit=week&from=2026-W53&to=2026-W53").json()

    assert (body["start_date"], body["end_date"]) == ("2026-12-28", "2027-01-03")
    assert [column["key"] for column in body["weeks"]] == ["2026-W53"]
    assert [(column["key"], column["partial"]) for column in body["months"]] == [
        ("2026-12", True),
        ("2027-01", True),
    ]
    assert rows_by_name(body)["Leivät"]["weeks"] == [100]
    assert rows_by_name(body)["Leivät"]["months"] == [0, 100]


def test_ac6_deposit_refunds_are_not_counted(api: TestClient, db: sqlite3.Connection) -> None:
    dairy = category(db, "Maitotuotteet")
    add_receipt(db, "2026-10-05", [("Maito", 229, dairy), ("Panttipalautus", -40, None)])

    body = api.get(OCTOBER).json()

    assert rows_by_name(body)["Maitotuotteet"]["months"] == [229]
    assert body["month_totals"] == [229]
    assert [row["kind"] for row in body["rows"]] == ["group"]


def test_ac7_lines_without_a_category(api: TestClient, db: sqlite3.Connection) -> None:
    add_receipt(db, "2026-10-05", [("Ruisleipä", 300, category(db, "Leivät")), ("X", 199, None)])

    body = api.get(OCTOBER).json()

    assert body["rows"][-1] == {
        "kind": "none",
        "id": None,
        "name": None,
        "weeks": [0, 199, 0, 0, 0],
        "months": [199],
        "categories": [],
    }
    assert body["month_totals"] == [499]


def test_ac8_purchase_date_not_import_date(api: TestClient, db: sqlite3.Connection) -> None:
    # Imported on 2026-11-02 (TIME), bought in October.
    add_receipt(db, "2026-10-05", [("Ruisleipä", 300, category(db, "Leivät"))])

    october = api.get(OCTOBER).json()
    november = api.get("/api/totals?unit=month&from=2026-11&to=2026-11").json()

    assert rows_by_name(october)["Leivät"]["months"] == [300]
    assert november["rows"] == []


def test_ac9_receipts_without_a_date(api: TestClient, db: sqlite3.Connection) -> None:
    add_receipt(db, None, [("Ruisleipä", 300, category(db, "Leivät"))])

    for query in (OCTOBER, "/api/totals?unit=week&from=2026-W01&to=2026-W02"):
        body = api.get(query).json()
        assert body["rows"] == []
        assert body["undated_receipts"] == 1


def test_ac10_rows_and_their_order(api: TestClient, db: sqlite3.Connection) -> None:
    add_receipt(db, "2026-10-05", [("Vesi", 150, category(db, "Juomat"))])
    add_receipt(db, "2026-10-06", [("Ruisleipä", 300, category(db, "Leivät"))])

    body = api.get(OCTOBER).json()

    assert [(row["kind"], row["name"]) for row in body["rows"]] == [
        ("group", "Ruoka"),
        ("category", "Juomat"),
    ]
    assert [child["name"] for child in body["rows"][0]["categories"]] == ["Leivät"]


def test_ac11_totals_follow_edits(api: TestClient, db: sqlite3.Connection) -> None:
    receipt_id, line_id = add_receipt(
        db, "2026-10-05", [("Ruisleipä", 300, category(db, "Leivät"))]
    )
    assert rows_by_name(api.get(OCTOBER).json())["Leivät"]["months"] == [300]

    url = f"/api/receipts/{receipt_id}/lines/{line_id}"
    assert api.patch(url, json={"amount_cents": 350}).status_code == 200
    dairy = item_id(db, "Maitotuotteet")
    assert api.patch(url, json={"category_id": dairy}).status_code == 200

    rows = rows_by_name(api.get(OCTOBER).json())
    assert "Leivät" not in rows
    assert rows["Maitotuotteet"]["months"] == [350]


@pytest.mark.parametrize(
    "query",
    [
        "unit=day&from=2026-10&to=2026-10",
        "unit=month&from=2026-13&to=2026-13",
        "unit=month&from=2026-11&to=2026-10",
        "unit=week&from=2027-W53&to=2027-W53",
        "unit=month&to=2026-10",
        "from=2026-10&to=2026-10",
        "unit=month&from=2024-10&to=2026-10",
        "unit=week&from=2025-W01&to=2026-W53",
    ],
)
def test_ac12_invalid_period(api: TestClient, query: str) -> None:
    response = api.get(f"/api/totals?{query}")

    assert response.status_code == 422
    assert response.json() == {"error": "invalid_period", "message": "Jakso on virheellinen."}


@pytest.mark.parametrize(
    "query", ["unit=month&from=2024-11&to=2026-10", "unit=week&from=2025-W01&to=2026-W52"]
)
def test_ac12_the_limits_are_accepted(api: TestClient, query: str) -> None:
    assert api.get(f"/api/totals?{query}").status_code == 200


def test_ac13_empty_period(api: TestClient) -> None:
    response = api.get("/api/totals?unit=month&from=2026-03&to=2026-03")

    assert response.status_code == 200
    body = response.json()
    assert body["rows"] == []
    assert len(body["weeks"]) == 6
    assert body["week_totals"] == [0] * 6
    assert body["month_totals"] == [0]
    assert (body["unreviewed_receipts"], body["undated_receipts"]) == (0, 0)


def test_ac20_unreviewed_count(api: TestClient, db: sqlite3.Connection) -> None:
    bread = category(db, "Leivät")
    add_receipt(db, "2026-10-05", [("Ruisleipä", 100, bread)], reviewed=True)
    add_receipt(db, "2026-10-06", [("Ruisleipä", 200, bread)])
    add_receipt(db, "2026-10-07", [("Ruisleipä", 400, bread)])
    add_receipt(db, "2026-11-01", [("Ruisleipä", 800, bread)])

    body = api.get(OCTOBER).json()

    assert body["unreviewed_receipts"] == 2
    assert body["month_totals"] == [700]


def test_ac19_no_product_names_in_the_answer_or_the_log(
    api: TestClient, db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    add_receipt(db, "2026-10-05", [("Salainen Tuote", 300, category(db, "Leivät"))])
    caplog.set_level(logging.DEBUG)

    response = api.get(OCTOBER)

    assert "Salainen" not in response.text
    # Only the app's own loggers; the test client logs the full URL itself.
    logged = "\n".join(
        record.getMessage() for record in caplog.records if record.name.startswith("app")
    )
    assert "GET /api/totals 200" in logged
    assert "Salainen" not in logged
    assert "2026-10" not in logged


# Date range (date range spec).

RANGE = "/api/totals?unit=range&from=2026-10-15&to=2026-11-14"


def test_date_range_ac1_a_range_is_totalled_by_its_days(
    api: TestClient, db: sqlite3.Connection
) -> None:
    bread = category(db, "Leivät")
    for day, amount in [
        ("2026-10-14", 100),
        ("2026-10-15", 200),
        ("2026-11-14", 400),
        ("2026-11-15", 800),
    ]:
        add_receipt(db, day, [("Ruisleipä", amount, bread)])

    response = api.get(RANGE)

    assert response.status_code == 200
    body = response.json()
    assert (body["unit"], body["from"], body["to"]) == ("range", "2026-10-15", "2026-11-14")
    assert body["month_totals"] == [200, 400]


def test_date_range_ac4_a_whole_month_gives_the_months_totals(
    api: TestClient, db: sqlite3.Connection
) -> None:
    bread = category(db, "Leivät")
    add_receipt(db, "2026-10-01", [("Ruisleipä", 100, bread)])
    add_receipt(db, "2026-10-31", [("Ruisleipä", 200, bread)])

    by_range = api.get("/api/totals?unit=range&from=2026-10-01&to=2026-10-31").json()
    by_month = api.get(OCTOBER).json()

    for key in ("weeks", "months", "rows", "week_totals", "month_totals"):
        assert by_range[key] == by_month[key]


def test_date_range_ac5_across_a_year_boundary(api: TestClient, db: sqlite3.Connection) -> None:
    bread = category(db, "Leivät")
    for day, amount in [
        ("2026-12-29", 1),
        ("2026-12-30", 10),
        ("2027-01-02", 20),
        ("2027-01-03", 2),
    ]:
        add_receipt(db, day, [("Ruisleipä", amount, bread)])

    body = api.get("/api/totals?unit=range&from=2026-12-30&to=2027-01-02").json()

    assert body["week_totals"] == [30]
    assert body["month_totals"] == [10, 20]
    assert [column["key"] for column in body["weeks"]] == ["2026-W53"]
    assert [column["partial"] for column in body["months"]] == [True, True]


def test_date_range_ac6_the_rules_stay_the_same(api: TestClient, db: sqlite3.Connection) -> None:
    add_receipt(
        db,
        "2026-10-20",
        [("Maito", 229, category(db, "Maitotuotteet")), ("Panttipalautus", -40, None)],
    )
    add_receipt(db, "2026-10-21", [("Tuntematon", 100, None)], reviewed=True)
    add_receipt(db, None, [("Limu", 300, None)])

    body = api.get(RANGE).json()

    assert body["month_totals"] == [329, 0]
    assert body["rows"][-1]["kind"] == "none"
    assert (body["unreviewed_receipts"], body["undated_receipts"]) == (1, 1)


def test_date_range_ac7_the_longest_range(api: TestClient) -> None:
    accepted = api.get("/api/totals?unit=range&from=2027-01-01&to=2028-12-31")
    refused = api.get("/api/totals?unit=range&from=2027-01-01&to=2029-01-01")

    assert accepted.status_code == 200
    assert refused.status_code == 422
    assert refused.json()["error"] == "invalid_period"


@pytest.mark.parametrize(
    "query",
    [
        "unit=range&to=2026-10-15",
        "unit=range&from=2026-10-15",
        "unit=range&from=2026-02-30&to=2026-03-01",
        "unit=range&from=2026-2-3&to=2026-03-01",
        "unit=range&from=20261015&to=20261016",
        "unit=range&from=2026-10&to=2026-11",
        "unit=range&from=2026-W40&to=2026-W41",
        "unit=range&from=0000-01-01&to=0000-01-02",
        "unit=range&from=9999-01-01&to=9999-01-02",
        "unit=range&from=٢٠٢٦-١٠-١٥&to=٢٠٢٦-١٠-١٦",
        "unit=range&from=2026-10-02&to=2026-10-01",
        "unit=month&from=2026-10-15&to=2026-10-15",
        "unit=week&from=2026-10-15&to=2026-10-15",
    ],
)
def test_date_range_ac8_ac9_invalid_values(api: TestClient, query: str) -> None:
    response = api.get(f"/api/totals?{query}")

    assert response.status_code == 422
    assert response.json() == {"error": "invalid_period", "message": "Jakso on virheellinen."}

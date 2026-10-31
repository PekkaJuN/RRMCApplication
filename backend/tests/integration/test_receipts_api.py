"""Receipt list, receipt view, image, category choice and review state (receipt-review spec)."""

import logging
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.categorization.names import normalize_key
from app.main import create_app
from app.settings import Settings
from app.storage.catalog_repository import CatalogRepository
from app.storage.db import connect
from app.storage.migrate import MIGRATIONS_DIR, migrate
from app.storage.receipt_repository import LineCategory, ReceiptRepository

TIME = "2026-10-28T10:00:01Z"
JPEG = b"\xff\xd8\xff\xe0synthetic jpeg"
PNG = b"\x89PNG\r\n\x1a\nsynthetic png"


@pytest.fixture
def db(api: TestClient, settings: Settings) -> Iterator[sqlite3.Connection]:
    """A connection to the app's database after its startup (migrations, default list)."""
    connection = connect(settings.db_path)
    yield connection
    connection.close()


def category_id(db: sqlite3.Connection, name: str) -> int:
    row = CatalogRepository(db).get_category_by_key(normalize_key(name))
    assert row is not None
    return row.id


def add_receipt(
    db: sqlite3.Connection,
    lines: list[tuple[str, int, LineCategory | None]],
    *,
    number: int,
    total: int | None = 349,
    purchase_date: str | None = "2026-10-05",
    store: str | None = "Testikauppa",
    file_name: str = "kuitti.jpg",
) -> tuple[int, list[int]]:
    """A receipt with lines (name, amount, category); a name `Panttipalautus` is a refund."""
    receipts = ReceiptRepository(db)
    with receipts.transaction():
        row = receipts.add(
            f"{number:064d}",
            file_name,
            TIME,
            store=store,
            purchase_date=purchase_date,
            total_cents=total,
            ocr_text="SYNTHETIC",
        )
        ids = [
            receipts.add_line(
                row.id,
                position,
                name,
                amount,
                is_deposit_refund=name == "Panttipalautus",
                category=category,
            )
            for position, (name, amount, category) in enumerate(lines, start=1)
        ]
    return row.id, ids


def receipt_a(db: sqlite3.Connection) -> tuple[int, list[int]]:
    dairy = category_id(db, "Maitotuotteet")
    catalog = CatalogRepository(db)
    with catalog.transaction():
        milk = catalog.add_product("Maito", "maito", dairy)
    return add_receipt(
        db,
        [
            ("Maito", 125, LineCategory(dairy, "remembered", milk)),
            ("Limu", 224, LineCategory(category_id(db, "Juomat"), "model", None)),
        ],
        number=1,
    )


def receipt_b(db: sqlite3.Connection) -> tuple[int, list[int]]:
    return add_receipt(
        db,
        [("Kahvi", 450, None)],
        number=2,
        total=500,
        purchase_date="2026-10-06",
        store="Kauppa B",
    )


def lines_snapshot(db: sqlite3.Connection) -> list[tuple[Any, ...]]:
    return [tuple(row) for row in db.execute("SELECT * FROM receipt_lines ORDER BY id")]


# List (PC1)


def test_ac1_list_shows_every_receipt(api: TestClient, db: sqlite3.Connection) -> None:
    a, _ = receipt_a(db)
    b, _ = receipt_b(db)
    assert api.patch(f"/api/receipts/{a}", json={"reviewed": True}).status_code == 200

    response = api.get("/api/receipts")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": b,
            "purchase_date": "2026-10-06",
            "store": "Kauppa B",
            "total_cents": 500,
            "warning": True,
            "reviewed": False,
        },
        {
            "id": a,
            "purchase_date": "2026-10-05",
            "store": "Testikauppa",
            "total_cents": 349,
            "warning": False,
            "reviewed": True,
        },
    ]


def test_ac2_list_order(api: TestClient, db: sqlite3.Connection) -> None:
    dates = ["2026-10-05", None, "2026-10-07", "2026-10-05", None]
    r1, r2, r3, r4, r5 = (
        add_receipt(db, [], number=number, purchase_date=day)[0]
        for number, day in enumerate(dates, start=1)
    )

    assert [item["id"] for item in api.get("/api/receipts").json()] == [r5, r2, r3, r4, r1]


def test_ac3_empty_list(api: TestClient) -> None:
    response = api.get("/api/receipts")

    assert response.status_code == 200
    assert response.json() == []


# Receipt (PC2)


def test_ac4_receipt_with_its_lines(api: TestClient, db: sqlite3.Connection) -> None:
    a, (milk, soda) = receipt_a(db)

    response = api.get(f"/api/receipts/{a}")

    assert response.status_code == 200
    body = response.json()
    assert "ocr_text" not in body
    assert body["lines"] == [
        {
            "id": milk,
            "position": 1,
            "name": "Maito",
            "amount_cents": 125,
            "is_deposit_refund": False,
            "category_id": category_id(db, "Maitotuotteet"),
            "category_name": "Maitotuotteet",
            "group_name": "Ruoka",
            "category_source": "remembered",
        },
        {
            "id": soda,
            "position": 2,
            "name": "Limu",
            "amount_cents": 224,
            "is_deposit_refund": False,
            "category_id": category_id(db, "Juomat"),
            "category_name": "Juomat",
            "group_name": None,
            "category_source": "model",
        },
    ]
    assert {key: body[key] for key in body if key not in ("lines", "subtotals")} == {
        "id": a,
        "file_name": "kuitti.jpg",
        "imported_at": TIME,
        "store": "Testikauppa",
        "purchase_date": "2026-10-05",
        "total_cents": 349,
        "reviewed": False,
        "line_sum_cents": 349,
        "difference_cents": 0,
        "warning": False,
    }


def test_ac5_line_sum_includes_deposit_refunds(api: TestClient, db: sqlite3.Connection) -> None:
    drinks = LineCategory(category_id(db, "Juomat"), "model", None)
    receipt_id, _ = add_receipt(
        db, [("Olut", 340, drinks), ("Panttipalautus", -40, None)], number=3, total=300
    )

    body = api.get(f"/api/receipts/{receipt_id}").json()

    assert (body["line_sum_cents"], body["difference_cents"], body["warning"]) == (300, 0, False)
    assert body["lines"][1]["is_deposit_refund"] is True


def test_ac6_warning_when_the_lines_do_not_add_up(api: TestClient, db: sqlite3.Connection) -> None:
    b, _ = receipt_b(db)

    body = api.get(f"/api/receipts/{b}").json()

    assert (body["line_sum_cents"], body["difference_cents"], body["warning"]) == (450, 50, True)


def test_ac7_receipt_imported_before_reading(api: TestClient, db: sqlite3.Connection) -> None:
    receipts = ReceiptRepository(db)
    with receipts.transaction():
        row = receipts.add("c" * 64, "vanha.jpg", TIME)

    body = api.get(f"/api/receipts/{row.id}").json()
    listed = api.get("/api/receipts").json()

    assert {
        key: body[key]
        for key in (
            "store",
            "purchase_date",
            "total_cents",
            "difference_cents",
            "lines",
            "line_sum_cents",
            "subtotals",
            "warning",
        )
    } == {
        "store": None,
        "purchase_date": None,
        "total_cents": None,
        "difference_cents": None,
        "lines": [],
        "line_sum_cents": 0,
        "subtotals": [],
        "warning": True,
    }
    assert listed[0]["warning"] is True


def test_ac8_category_subtotals(api: TestClient, db: sqlite3.Connection) -> None:
    dairy, drinks = category_id(db, "Maitotuotteet"), category_id(db, "Juomat")
    receipt_id, _ = add_receipt(
        db,
        [
            ("Maito", 125, LineCategory(dairy, "model", None)),
            ("Limu", 224, LineCategory(drinks, "model", None)),
            ("Jogurtti", 99, LineCategory(dairy, "model", None)),
            ("Outo", 50, None),
            ("Panttipalautus", -40, None),
        ],
        number=4,
        total=500,
    )

    body = api.get(f"/api/receipts/{receipt_id}").json()

    assert body["subtotals"] == [
        {
            "category_id": dairy,
            "category_name": "Maitotuotteet",
            "group_name": "Ruoka",
            "amount_cents": 224,
        },
        {"category_id": drinks, "category_name": "Juomat", "group_name": None, "amount_cents": 224},
        {"category_id": None, "category_name": None, "group_name": None, "amount_cents": 50},
    ]


def test_ac9_unknown_receipt(api: TestClient) -> None:
    responses = [
        api.get("/api/receipts/999"),
        api.get("/api/receipts/999/image"),
        api.patch("/api/receipts/999", json={"reviewed": True}),
    ]

    assert [response.status_code for response in responses] == [404, 404, 404]
    assert {response.json()["error"] for response in responses} == {"not_found"}


# Image (PC3)


def test_ac10_receipt_image(api: TestClient, db: sqlite3.Connection, settings: Settings) -> None:
    settings.done_dir.mkdir(exist_ok=True)
    (settings.done_dir / "kuitti.jpg").write_bytes(JPEG)
    (settings.done_dir / "kuitti.png").write_bytes(PNG)
    a, _ = receipt_a(db)
    png, _ = add_receipt(db, [], number=5, file_name="kuitti.png")

    jpeg_response = api.get(f"/api/receipts/{a}/image")
    png_response = api.get(f"/api/receipts/{png}/image")

    assert jpeg_response.status_code == 200
    assert jpeg_response.headers["content-type"] == "image/jpeg"
    assert jpeg_response.headers["cache-control"] == "no-store"
    assert jpeg_response.content == JPEG
    assert png_response.headers["content-type"] == "image/png"
    assert png_response.content == PNG


def test_ac11_image_missing_from_the_done_folder(api: TestClient, db: sqlite3.Connection) -> None:
    a, _ = receipt_a(db)

    response = api.get(f"/api/receipts/{a}/image")

    assert response.status_code == 404
    assert response.json() == {
        "error": "image_missing",
        "message": "Kuvaa ei löydy valmiiden kansiosta.",
    }


def test_ac12_image_path_cannot_leave_the_done_folder(
    api: TestClient, db: sqlite3.Connection, settings: Settings
) -> None:
    settings.done_dir.mkdir(exist_ok=True)
    (settings.done_dir.parent / "secret.jpg").write_bytes(JPEG)
    receipt_id, _ = add_receipt(db, [], number=6, file_name="../secret.jpg")

    response = api.get(f"/api/receipts/{receipt_id}/image")

    assert response.status_code == 404
    assert response.json()["error"] == "image_missing"


# Category choice (PC4)


def test_ac13_choosing_a_category_for_a_line(api: TestClient, db: sqlite3.Connection) -> None:
    a, (_, soda) = receipt_a(db)
    dairy = category_id(db, "Maitotuotteet")

    response = api.patch(f"/api/receipts/{a}/lines/{soda}", json={"category_id": dairy})

    assert response.status_code == 200
    body = response.json()
    assert (body["lines"][1]["category_name"], body["lines"][1]["category_source"]) == (
        "Maitotuotteet",
        "user",
    )
    assert [(item["category_name"], item["amount_cents"]) for item in body["subtotals"]] == [
        ("Maitotuotteet", 349)
    ]
    products = api.get("/api/products", params={"q": "Limu"}).json()
    assert [(item["name"], item["category_name"]) for item in products] == [
        ("Limu", "Maitotuotteet")
    ]


def test_ac14_choice_moves_the_same_product_on_the_receipt(
    api: TestClient, db: sqlite3.Connection
) -> None:
    dairy = category_id(db, "Maitotuotteet")
    catalog = CatalogRepository(db)
    with catalog.transaction():
        milk = catalog.add_product("Maito", "maito", dairy)
    remembered = LineCategory(dairy, "remembered", milk)
    receipt_id, (first, _) = add_receipt(
        db, [("Maito", 125, remembered), ("Maito", 125, remembered)], number=7, total=250
    )

    body = api.patch(
        f"/api/receipts/{receipt_id}/lines/{first}", json={"category_id": category_id(db, "Juomat")}
    ).json()

    assert [(line["category_name"], line["category_source"]) for line in body["lines"]] == [
        ("Juomat", "user"),
        ("Juomat", "remembered"),
    ]


def test_ac15_category_choice_errors(api: TestClient, db: sqlite3.Connection) -> None:
    a, (milk, _) = receipt_a(db)
    refund_receipt, (refund,) = add_receipt(db, [("Panttipalautus", -40, None)], number=8)
    drinks = category_id(db, "Juomat")
    before = lines_snapshot(db)
    cases: list[tuple[int, int, dict[str, object], str]] = [
        (a, milk, {"category_id": 999}, "unknown_category"),
        (a, milk, {"category_id": category_id(db, "Ruoka")}, "not_a_category"),
        (refund_receipt, refund, {"category_id": drinks}, "deposit_refund_line"),
        (a, milk, {"category_id": None}, "invalid_request"),
        (a, milk, {}, "invalid_request"),
        (a, milk, {"category_id": "12"}, "invalid_request"),
        (a, milk, {"category_id": True}, "invalid_request"),
    ]

    for receipt_id, line_id, body, error in cases:
        response = api.patch(f"/api/receipts/{receipt_id}/lines/{line_id}", json=body)
        assert (response.status_code, response.json()["error"]) == (422, error), body

    assert lines_snapshot(db) == before


def test_ac16_line_on_another_receipt(api: TestClient, db: sqlite3.Connection) -> None:
    a, _ = receipt_a(db)
    _, (b_line,) = receipt_b(db)
    before = lines_snapshot(db)
    body = {"category_id": category_id(db, "Juomat")}

    responses = [
        api.patch(f"/api/receipts/{a}/lines/{b_line}", json=body),
        api.patch(f"/api/receipts/{a}/lines/999", json=body),
    ]

    assert [(response.status_code, response.json()["error"]) for response in responses] == [
        (404, "not_found"),
        (404, "not_found"),
    ]
    assert lines_snapshot(db) == before


# Review state (PC5, PC6)


def test_ac17_confirming_and_cancelling(api: TestClient, db: sqlite3.Connection) -> None:
    b, _ = receipt_b(db)

    confirmed = api.patch(f"/api/receipts/{b}", json={"reviewed": True})
    listed = api.get("/api/receipts").json()
    cancelled = api.patch(f"/api/receipts/{b}", json={"reviewed": False})

    assert (confirmed.status_code, confirmed.json()["reviewed"]) == (200, True)
    assert confirmed.json()["warning"] is True
    assert listed[0]["reviewed"] is True
    assert (cancelled.status_code, cancelled.json()["reviewed"]) == (200, False)


def test_ac18_confirmation_survives_a_category_choice(
    api: TestClient, db: sqlite3.Connection
) -> None:
    a, (_, soda) = receipt_a(db)
    api.patch(f"/api/receipts/{a}", json={"reviewed": True})

    chosen = api.patch(
        f"/api/receipts/{a}/lines/{soda}", json={"category_id": category_id(db, "Maitotuotteet")}
    )
    bad = [
        api.patch(f"/api/receipts/{a}", json={}),
        api.patch(f"/api/receipts/{a}", json={"reviewed": "yes"}),
        api.patch(f"/api/receipts/{a}", json={"reviewed": None}),
    ]

    assert chosen.json()["reviewed"] is True
    assert [(response.status_code, response.json()["error"]) for response in bad] == [
        (422, "invalid_request")
    ] * 3
    assert api.get(f"/api/receipts/{a}").json()["reviewed"] is True


def test_ac19_migration_keeps_existing_receipts(settings: Settings, tmp_path: Path) -> None:
    # Given a database at version 4 with two receipts
    older = tmp_path / "older"
    older.mkdir()
    for path in sorted(MIGRATIONS_DIR.glob("000[1-4]_*.sql")):
        (older / path.name).write_text(path.read_text("utf-8"), "utf-8")
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = connect(settings.db_path)
    migrate(connection, older)
    add_receipt(connection, [], number=1)
    add_receipt(connection, [], number=2)
    connection.close()

    # When the backend starts
    with TestClient(create_app(settings)) as api:
        listed = api.get("/api/receipts").json()

    # Then the schema version is 5 and both receipts are unreviewed
    connection = connect(settings.db_path)
    version = connection.execute("SELECT max(version) FROM schema_version").fetchone()[0]
    connection.close()
    assert version == 5
    assert [item["reviewed"] for item in listed] == [False, False]


# Privacy (PC11)


def test_pc11_no_names_in_the_logs(
    api: TestClient, db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    a, (_, soda) = receipt_a(db)
    caplog.set_level(logging.DEBUG)

    api.get(f"/api/receipts/{a}")
    api.patch(f"/api/receipts/{a}/lines/{soda}", json={"category_id": 999})
    api.patch(
        f"/api/receipts/{a}/lines/{soda}", json={"category_id": category_id(db, "Maitotuotteet")}
    )

    logged = "\n".join(record.getMessage() for record in caplog.records)
    for name in ("Limu", "Maito", "Maitotuotteet", "Juomat", "Testikauppa"):
        assert name not in logged

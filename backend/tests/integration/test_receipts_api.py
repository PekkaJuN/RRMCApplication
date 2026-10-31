"""Receipt list, receipt view, image, category choice and review state (receipt-review spec);
line and receipt edits (line-editing spec)."""

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


def add_line(
    db: sqlite3.Connection,
    receipt_id: int,
    position: int,
    name: str,
    amount: int,
    *,
    refund: bool = False,
    category: LineCategory | None = None,
) -> int:
    receipts = ReceiptRepository(db)
    with receipts.transaction():
        return receipts.add_line(
            receipt_id, position, name, amount, is_deposit_refund=refund, category=category
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
    refund = add_line(db, a, 3, "Panttipalautus", -40, refund=True)
    drinks = category_id(db, "Juomat")
    before = lines_snapshot(db)
    cases: list[tuple[int, int, dict[str, object], str]] = [
        (a, milk, {"category_id": 999}, "unknown_category"),
        (a, milk, {"category_id": category_id(db, "Ruoka")}, "not_a_category"),
        (a, refund, {"category_id": drinks}, "deposit_refund_line"),
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


# Line editing spec (T14). Receipt A has the products Maito; Jogurtti is added where an AC
# needs it.


def snapshot(db: sqlite3.Connection) -> tuple[list[tuple[Any, ...]], list[tuple[Any, ...]]]:
    receipts = [tuple(row) for row in db.execute("SELECT * FROM receipts ORDER BY id")]
    products = [tuple(row) for row in db.execute("SELECT * FROM products ORDER BY id")]
    return lines_snapshot(db) + receipts, products


def product(db: sqlite3.Connection, name: str) -> tuple[int, int] | None:
    """The id and category of the product with this name, or None."""
    row = CatalogRepository(db).get_product_by_key(normalize_key(name))
    return None if row is None else (row.id, row.category_id)


def line_product(db: sqlite3.Connection, line_id: int) -> int | None:
    return db.execute("SELECT product_id FROM receipt_lines WHERE id = ?", (line_id,)).fetchone()[0]


def add_product(db: sqlite3.Connection, name: str, category: str) -> int:
    catalog = CatalogRepository(db)
    with catalog.transaction():
        return catalog.add_product(name, normalize_key(name), category_id(db, category))


def patch_line(api: TestClient, receipt_id: int, line_id: int, body: dict[str, Any]) -> Any:
    return api.patch(f"/api/receipts/{receipt_id}/lines/{line_id}", json=body)


def line_fields(body: dict[str, Any], index: int, *fields: str) -> tuple[Any, ...]:
    return tuple(body["lines"][index][field] for field in fields)


def test_ac1_rename_without_a_match_makes_a_product(
    api: TestClient, db: sqlite3.Connection
) -> None:
    a, (_, soda) = receipt_a(db)

    response = patch_line(api, a, soda, {"name": "  Kivennäisvesi  "})

    assert response.status_code == 200
    assert line_fields(response.json(), 1, "name", "category_name", "category_source") == (
        "Kivennäisvesi",
        "Juomat",
        "user",
    )
    water = product(db, "Kivennäisvesi")
    assert water == (line_product(db, soda), category_id(db, "Juomat"))


def test_ac2_rename_to_a_name_match(api: TestClient, db: sqlite3.Connection) -> None:
    a, (_, soda) = receipt_a(db)
    yoghurt = add_product(db, "Jogurtti", "Maitotuotteet")

    body = patch_line(api, a, soda, {"name": "JOGURTTI"}).json()

    assert line_fields(body, 1, "name", "category_name", "group_name", "category_source") == (
        "JOGURTTI",
        "Maitotuotteet",
        "Ruoka",
        "remembered",
    )
    assert line_product(db, soda) == yoghurt
    assert [(item["category_name"], item["amount_cents"]) for item in body["subtotals"]] == [
        ("Maitotuotteet", 349)
    ]
    assert db.execute("SELECT count(*) FROM products").fetchone()[0] == 2


def test_ac3_rename_leaves_the_old_product_alone(api: TestClient, db: sqlite3.Connection) -> None:
    a, (milk_line, _) = receipt_a(db)
    milk = product(db, "Maito")
    assert milk is not None
    dairy = category_id(db, "Maitotuotteet")
    _, (b_line,) = add_receipt(
        db, [("Maito", 125, LineCategory(dairy, "remembered", milk[0]))], number=2
    )

    body = patch_line(api, a, milk_line, {"name": "Kaurajuoma"}).json()

    assert body["lines"][0]["category_source"] == "user"
    assert product(db, "Kaurajuoma") == (line_product(db, milk_line), dairy)
    assert product(db, "Maito") == milk
    assert line_product(db, b_line) == milk[0]


def test_ac4_case_change_renames_only(api: TestClient, db: sqlite3.Connection) -> None:
    a, (milk_line, _) = receipt_a(db)
    products = snapshot(db)[1]

    body = patch_line(api, a, milk_line, {"name": "MAITO"}).json()

    assert line_fields(body, 0, "name", "category_name", "category_source") == (
        "MAITO",
        "Maitotuotteet",
        "remembered",
    )
    assert snapshot(db)[1] == products


def test_ac5_rename_without_a_category(api: TestClient, db: sqlite3.Connection) -> None:
    a, _ = receipt_a(db)
    odd = add_line(db, a, 3, "Outo", 50)

    body = patch_line(api, a, odd, {"name": "Outo tuote"}).json()

    assert line_fields(body, 2, "name", "category_id", "category_source") == (
        "Outo tuote",
        None,
        None,
    )
    assert product(db, "Outo tuote") is None


def test_ac6_rename_a_deposit_refund(api: TestClient, db: sqlite3.Connection) -> None:
    a, _ = receipt_a(db)
    refund = add_line(db, a, 3, "Panttipalautus", -40, refund=True)

    body = patch_line(api, a, refund, {"name": "Maito"}).json()

    assert line_fields(body, 2, "name", "is_deposit_refund", "category_id") == (
        "Maito",
        True,
        None,
    )
    assert line_product(db, refund) is None


def test_ac7_amount_change(api: TestClient, db: sqlite3.Connection) -> None:
    a, (_, soda) = receipt_a(db)

    body = patch_line(api, a, soda, {"amount_cents": 300}).json()

    assert line_fields(body, 1, "amount_cents", "category_name", "category_source") == (
        300,
        "Juomat",
        "model",
    )
    assert (body["line_sum_cents"], body["difference_cents"], body["warning"]) == (425, -76, True)
    assert [item["amount_cents"] for item in body["subtotals"]] == [125, 300]


def test_ac8_zero_and_negative_amounts(api: TestClient, db: sqlite3.Connection) -> None:
    a, (_, soda) = receipt_a(db)

    zero = patch_line(api, a, soda, {"amount_cents": 0})
    negative = patch_line(api, a, soda, {"amount_cents": -50})

    assert (zero.status_code, zero.json()["lines"][1]["amount_cents"]) == (200, 0)
    body = negative.json()
    assert line_fields(body, 1, "amount_cents", "category_name") == (-50, "Juomat")
    assert (body["subtotals"][-1]["category_name"], body["subtotals"][-1]["amount_cents"]) == (
        "Juomat",
        -50,
    )


def test_ac9_mark_as_a_deposit_refund(api: TestClient, db: sqlite3.Connection) -> None:
    a, (_, soda) = receipt_a(db)

    body = patch_line(api, a, soda, {"is_deposit_refund": True, "amount_cents": -40}).json()

    assert line_fields(
        body,
        1,
        "is_deposit_refund",
        "amount_cents",
        "category_id",
        "category_name",
        "category_source",
    ) == (True, -40, None, None, None)
    assert body["line_sum_cents"] == 85
    assert [item["category_name"] for item in body["subtotals"]] == ["Maitotuotteet"]


def test_ac10_deposit_refund_must_be_negative(api: TestClient, db: sqlite3.Connection) -> None:
    a, (_, soda) = receipt_a(db)
    refund = add_line(db, a, 3, "Panttipalautus", -40, refund=True)
    before = snapshot(db)
    cases: list[tuple[int, dict[str, Any]]] = [
        (soda, {"is_deposit_refund": True}),
        (refund, {"amount_cents": 0}),
        (refund, {"amount_cents": 40}),
        (soda, {"is_deposit_refund": True, "amount_cents": 10}),
    ]

    for line_id, body in cases:
        response = patch_line(api, a, line_id, body)
        assert response.status_code == 422, body
        assert response.json() == {
            "error": "deposit_refund_amount",
            "message": "Pantinpalautuksen summan on oltava negatiivinen.",
        }

    assert snapshot(db) == before


def test_ac11_unmarking_a_refund_resolves_the_line(api: TestClient, db: sqlite3.Connection) -> None:
    a, _ = receipt_a(db)
    milk = product(db, "Maito")
    assert milk is not None
    bottles = add_line(db, a, 3, "Panttipalautus", -40, refund=True)
    small_milk = add_line(db, a, 4, "maito", -40, refund=True)

    patch_line(api, a, bottles, {"is_deposit_refund": False})
    body = patch_line(api, a, small_milk, {"is_deposit_refund": False}).json()

    assert [
        (line["is_deposit_refund"], line["category_name"], line["category_source"])
        for line in body["lines"][2:]
    ] == [(False, None, None), (False, "Maitotuotteet", "remembered")]
    assert line_product(db, small_milk) == milk[0]
    assert [(item["category_name"], item["amount_cents"]) for item in body["subtotals"]] == [
        ("Maitotuotteet", 85),
        ("Juomat", 224),
        (None, -40),
    ]


def test_ac12_name_and_category_in_one_request(api: TestClient, db: sqlite3.Connection) -> None:
    a, (_, soda) = receipt_a(db)
    dairy = category_id(db, "Maitotuotteet")

    body = patch_line(api, a, soda, {"name": "Kivennäisvesi", "category_id": dairy}).json()

    assert line_fields(body, 1, "name", "category_name", "category_source") == (
        "Kivennäisvesi",
        "Maitotuotteet",
        "user",
    )
    count = db.execute(
        "SELECT count(*) FROM products WHERE name_key = 'kivennäisvesi' AND category_id = ?",
        (dairy,),
    ).fetchone()[0]
    assert count == 1


def test_ac13_refund_with_a_category_in_one_request(
    api: TestClient, db: sqlite3.Connection
) -> None:
    a, (_, soda) = receipt_a(db)
    refund = add_line(db, a, 3, "Panttipalautus", -40, refund=True)
    drinks = category_id(db, "Juomat")
    before = snapshot(db)

    responses = [
        patch_line(
            api, a, soda, {"is_deposit_refund": True, "amount_cents": -40, "category_id": drinks}
        ),
        patch_line(api, a, refund, {"name": "Pullot", "category_id": drinks}),
    ]

    assert [(r.status_code, r.json()["error"]) for r in responses] == [
        (422, "deposit_refund_line"),
        (422, "deposit_refund_line"),
    ]
    assert snapshot(db) == before


def test_ac14_line_edit_errors(api: TestClient, db: sqlite3.Connection) -> None:
    a, (_, soda) = receipt_a(db)
    before = snapshot(db)
    cases: list[tuple[dict[str, Any], str]] = [
        ({"name": ""}, "invalid_name"),
        ({"name": "   "}, "invalid_name"),
        ({"name": "a" * 101}, "invalid_name"),
        ({"amount_cents": 100_000_000}, "invalid_amount"),
        ({"amount_cents": -100_000_000}, "invalid_amount"),
        ({}, "invalid_request"),
        ({"name": None}, "invalid_request"),
        ({"amount_cents": "1"}, "invalid_request"),
        ({"amount_cents": 1.5}, "invalid_request"),
        ({"is_deposit_refund": 1}, "invalid_request"),
        ({"name": "Limu", "color": "red"}, "invalid_request"),
    ]

    for body, error in cases:
        response = patch_line(api, a, soda, body)
        assert (response.status_code, response.json()["error"]) == (422, error), body

    assert snapshot(db) == before
    assert patch_line(api, a, soda, {"name": "a" * 100}).status_code == 200
    assert patch_line(api, a, soda, {"amount_cents": 99_999_999}).status_code == 200


def test_ac15_adding_lines(api: TestClient, db: sqlite3.Connection) -> None:
    a, _ = receipt_a(db)
    c, _ = add_receipt(db, [], number=3)
    milk = product(db, "Maito")
    assert milk is not None

    responses = [
        api.post(f"/api/receipts/{a}/lines", json={"name": "Banaani", "amount_cents": 99}),
        api.post(f"/api/receipts/{a}/lines", json={"name": " maito ", "amount_cents": 125}),
        api.post(
            f"/api/receipts/{a}/lines",
            json={"name": "Panttipalautus", "amount_cents": -40, "is_deposit_refund": True},
        ),
        api.post(f"/api/receipts/{c}/lines", json={"name": "Banaani", "amount_cents": 99}),
    ]

    assert [response.status_code for response in responses] == [201, 201, 201, 201]
    body = responses[2].json()
    assert [
        (
            line["position"],
            line["name"],
            line["is_deposit_refund"],
            line["category_name"],
            line["category_source"],
        )
        for line in body["lines"]
    ] == [
        (1, "Maito", False, "Maitotuotteet", "remembered"),
        (2, "Limu", False, "Juomat", "model"),
        (3, "Banaani", False, None, None),
        (4, "maito", False, "Maitotuotteet", "remembered"),
        (5, "Panttipalautus", True, None, None),
    ]
    assert line_product(db, body["lines"][3]["id"]) == milk[0]
    assert body["line_sum_cents"] == 533
    assert [line["position"] for line in responses[3].json()["lines"]] == [1]
    assert product(db, "Banaani") is None


def test_ac16_adding_a_line_errors(api: TestClient, db: sqlite3.Connection) -> None:
    a, _ = receipt_a(db)
    before = snapshot(db)
    cases: list[tuple[int, dict[str, Any], int, str]] = [
        (a, {"amount_cents": 99}, 422, "invalid_request"),
        (a, {"name": "Banaani"}, 422, "invalid_request"),
        (a, {"name": "", "amount_cents": 99}, 422, "invalid_name"),
        (
            a,
            {"name": "Pullot", "amount_cents": 40, "is_deposit_refund": True},
            422,
            "deposit_refund_amount",
        ),
        (a, {"name": "Banaani", "amount_cents": 99, "category_id": 12}, 422, "invalid_request"),
        (999, {"name": "Banaani", "amount_cents": 99}, 404, "not_found"),
    ]

    for receipt_id, body, status, error in cases:
        response = api.post(f"/api/receipts/{receipt_id}/lines", json=body)
        assert (response.status_code, response.json()["error"]) == (status, error), body

    assert snapshot(db) == before


def test_ac17_deleting_a_line(api: TestClient, db: sqlite3.Connection) -> None:
    a, (_, soda) = receipt_a(db)
    _, (b_line,) = receipt_b(db)
    products = snapshot(db)[1]

    first = api.delete(f"/api/receipts/{a}/lines/{soda}")
    again = api.delete(f"/api/receipts/{a}/lines/{soda}")
    other = api.delete(f"/api/receipts/{a}/lines/{b_line}")
    added = api.post(f"/api/receipts/{a}/lines", json={"name": "Banaani", "amount_cents": 99})

    assert first.status_code == 200
    assert [line["name"] for line in first.json()["lines"]] == ["Maito"]
    assert first.json()["line_sum_cents"] == 125
    assert [(r.status_code, r.json()["error"]) for r in (again, other)] == [
        (404, "not_found"),
        (404, "not_found"),
    ]
    assert db.execute("SELECT count(*) FROM receipt_lines WHERE id = ?", (b_line,)).fetchone()[0]
    assert snapshot(db)[1] == products
    assert added.json()["lines"][1]["position"] == 2


def test_ac18_deleting_keeps_the_other_positions(api: TestClient, db: sqlite3.Connection) -> None:
    receipt_id, (_, second, _) = add_receipt(
        db, [("Maito", 125, None), ("Limu", 224, None), ("Outo", 50, None)], number=4
    )

    api.delete(f"/api/receipts/{receipt_id}/lines/{second}")
    body = api.post(
        f"/api/receipts/{receipt_id}/lines", json={"name": "Banaani", "amount_cents": 99}
    ).json()

    assert [line["position"] for line in body["lines"]] == [1, 3, 4]


def test_ac19_editing_store_date_and_total(api: TestClient, db: sqlite3.Connection) -> None:
    a, _ = receipt_a(db)

    first = api.patch(
        f"/api/receipts/{a}",
        json={"store": "  Uusi   kauppa ", "purchase_date": "2026-10-06", "total_cents": 400},
    )
    listed = api.get("/api/receipts").json()[0]
    second = api.patch(f"/api/receipts/{a}", json={"store": ""})

    body = first.json()
    assert first.status_code == 200
    assert (body["store"], body["purchase_date"], body["total_cents"]) == (
        "Uusi kauppa",
        "2026-10-06",
        400,
    )
    assert (body["difference_cents"], body["warning"]) == (51, True)
    assert (listed["store"], listed["purchase_date"], listed["total_cents"]) == (
        "Uusi kauppa",
        "2026-10-06",
        400,
    )
    assert second.json()["store"] == ""


def test_ac20_filling_a_receipt_imported_before_reading(
    api: TestClient, db: sqlite3.Connection
) -> None:
    receipt_id, _ = add_receipt(db, [], number=5, total=None, purchase_date=None, store=None)

    body = api.patch(
        f"/api/receipts/{receipt_id}", json={"purchase_date": "2026-01-15", "total_cents": 0}
    ).json()

    assert (body["purchase_date"], body["total_cents"], body["store"]) == ("2026-01-15", 0, None)
    assert (body["line_sum_cents"], body["difference_cents"], body["warning"]) == (0, 0, False)


def test_ac21_receipt_field_errors(api: TestClient, db: sqlite3.Connection) -> None:
    a, _ = receipt_a(db)
    before = snapshot(db)
    cases: list[tuple[dict[str, Any], str]] = [
        ({"store": "a" * 101}, "invalid_store"),
        ({"purchase_date": "2026-02-30"}, "invalid_date"),
        ({"purchase_date": "5.10.2026"}, "invalid_date"),
        ({"purchase_date": ""}, "invalid_date"),
        ({"total_cents": -1}, "invalid_amount"),
        ({"total_cents": 100_000_000}, "invalid_amount"),
        ({"store": "X", "total_cents": -1}, "invalid_amount"),
        ({}, "invalid_request"),
        ({"store": None}, "invalid_request"),
        ({"purchase_date": None}, "invalid_request"),
        ({"total_cents": None}, "invalid_request"),
        ({"total_cents": "349"}, "invalid_request"),
        ({"reviewed": True, "note": "x"}, "invalid_request"),
    ]

    for body, error in cases:
        response = api.patch(f"/api/receipts/{a}", json=body)
        assert (response.status_code, response.json()["error"]) == (422, error), body

    assert snapshot(db) == before
    assert api.patch(f"/api/receipts/{a}", json={"store": "a" * 100}).status_code == 200


def test_ac22_edits_keep_the_review_state(api: TestClient, db: sqlite3.Connection) -> None:
    a, (milk_line, soda) = receipt_a(db)
    api.patch(f"/api/receipts/{a}", json={"reviewed": True})

    responses = [
        patch_line(api, a, soda, {"name": "Vesi"}),
        patch_line(api, a, milk_line, {"amount_cents": 130}),
        api.post(f"/api/receipts/{a}/lines", json={"name": "Banaani", "amount_cents": 99}),
        api.delete(f"/api/receipts/{a}/lines/{soda}"),
        api.patch(f"/api/receipts/{a}", json={"total_cents": 500}),
    ]
    last = api.patch(f"/api/receipts/{a}", json={"total_cents": 349, "reviewed": False})

    assert [r.status_code for r in responses] == [200, 200, 201, 200, 200]
    assert [r.json()["reviewed"] for r in responses] == [True] * 5
    assert (last.json()["total_cents"], last.json()["reviewed"]) == (349, False)


def test_ac23_ids_out_of_range(api: TestClient, db: sqlite3.Connection) -> None:
    a, (_, soda) = receipt_a(db)
    before = snapshot(db)

    responses = [
        api.get("/api/receipts/9223372036854775808"),
        patch_line(api, a, 9223372036854775808, {"name": "X"}),
        api.delete(f"/api/receipts/{a}/lines/-9223372036854775809"),
        patch_line(api, a, soda, {"category_id": 9223372036854775808}),
    ]

    assert [(r.status_code, r.json()["error"]) for r in responses] == [
        (404, "not_found"),
        (404, "not_found"),
        (404, "not_found"),
        (422, "unknown_category"),
    ]
    assert snapshot(db) == before


def test_pc16_no_names_in_the_logs_of_edits(
    api: TestClient, db: sqlite3.Connection, caplog: pytest.LogCaptureFixture
) -> None:
    a, (_, soda) = receipt_a(db)
    caplog.set_level(logging.DEBUG)

    patch_line(api, a, soda, {"name": "Kivennäisvesi"})
    patch_line(api, a, soda, {"name": ""})
    api.post(f"/api/receipts/{a}/lines", json={"name": "Banaani", "amount_cents": 99})
    api.patch(f"/api/receipts/{a}", json={"store": "Uusi kauppa"})
    api.patch(f"/api/receipts/{a}", json={"store": "a" * 101})

    logged = "\n".join(record.getMessage() for record in caplog.records)
    for name in ("Kivennäisvesi", "Banaani", "Uusi kauppa", "Limu", "Maito", "Testikauppa"):
        assert name not in logged

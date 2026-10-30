from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.settings import Settings
from app.storage.db import connect
from app.storage.receipt_repository import LineCategory, ReceiptRepository
from tests.integration.conftest import make_client

INVALID_REQUEST = {"error": "invalid_request", "message": "Pyyntö on virheellinen."}


def items(api: TestClient) -> list[dict[str, Any]]:
    response = api.get("/api/categories")
    assert response.status_code == 200
    return response.json()


def item_id(api: TestClient, name: str) -> int:
    return item(api, name)["id"]


def item(api: TestClient, name: str) -> dict[str, Any]:
    return next(row for row in items(api) if row["name"] == name)


def add_product(api: TestClient, name: str, category: str) -> None:
    body = {"name": name, "category_id": item_id(api, category)}
    assert api.post("/api/products", json=body).status_code == 201


def add(api: TestClient, name: str, kind: str, parent_id: int | None = None) -> dict[str, Any]:
    response = api.post(
        "/api/categories", json={"name": name, "kind": kind, "parent_id": parent_id}
    )
    assert response.status_code == 201
    return response.json()


def patch(api: TestClient, name: str, body: dict[str, Any]) -> Any:
    return api.patch(f"/api/categories/{item_id(api, name)}", json=body)


def test_ac1_default_list_on_first_start(api: TestClient) -> None:
    rows = items(api)

    groups = [row for row in rows if row["kind"] == "group"]
    assert [(row["name"], row["category_count"], row["product_count"]) for row in groups] == [
        ("Auto", 3, None),
        ("Ruoka", 10, None),
    ]
    categories = [row for row in rows if row["kind"] == "category"]
    assert len(categories) == 21
    assert {row["product_count"] for row in categories} == {0}
    assert {row["category_count"] for row in categories} == {None}
    ungrouped = [row["name"] for row in categories if row["parent_id"] is None]
    assert ungrouped == [
        "Alkoholi",
        "Herkut",
        "Hygienia",
        "Juomat",
        "Kodin tarvikkeet",
        "Lemmikit",
        "Muut",
        "Ulkona syöminen",
    ]


def test_ac2_default_list_is_not_recreated_after_restart(settings: Settings) -> None:
    with make_client(settings) as first:
        for row in sorted(items(first), key=lambda row: row["kind"] != "category"):
            assert first.delete(f"/api/categories/{row['id']}").status_code == 204

    with make_client(settings) as second:
        assert items(second) == []


def test_ac3_add_category(api: TestClient) -> None:
    response = api.post("/api/categories", json={"name": "  Harrastukset  ", "kind": "category"})

    assert response.status_code == 201
    body = response.json()
    assert {key: body[key] for key in ("name", "kind", "parent_id", "product_count")} == {
        "name": "Harrastukset",
        "kind": "category",
        "parent_id": None,
        "product_count": 0,
    }


@pytest.mark.parametrize(("name", "kind"), [("ruoka", "category"), ("JUOMAT", "group")])
def test_ac4_duplicate_across_kinds(api: TestClient, name: str, kind: str) -> None:
    response = api.post("/api/categories", json={"name": name, "kind": kind})

    assert response.status_code == 409
    assert response.json()["error"] == "duplicate_name"
    assert len(items(api)) == 23


def test_ac5_invalid_name(api: TestClient) -> None:
    create = api.post("/api/categories", json={"name": "   ", "kind": "category"})
    rename = patch(api, "Juomat", {"name": "a" * 51})

    assert (create.status_code, create.json()["error"]) == (422, "invalid_name")
    assert (rename.status_code, rename.json()["error"]) == (422, "invalid_name")
    assert len(items(api)) == 23
    assert item(api, "Juomat")["name"] == "Juomat"


def test_ac6_rename_used_category(api: TestClient) -> None:
    add_product(api, "Mehu", "Juomat")
    add_product(api, "Limonadi", "Juomat")

    response = patch(api, "Juomat", {"name": "Virvoitusjuomat"})

    assert response.status_code == 200
    assert response.json()["product_count"] == 2
    products = api.get("/api/products").json()
    assert {product["category_name"] for product in products} == {"Virvoitusjuomat"}


def test_ac8_new_group_and_category(api: TestClient) -> None:
    koti = add(api, "Koti", "group")
    sisustus = add(api, "Sisustus", "category", koti["id"])

    assert sisustus["parent_id"] == koti["id"]
    assert item(api, "Koti")["category_count"] == 1


def test_ac9_move_category(api: TestClient) -> None:
    koti = add(api, "Koti", "group")
    add_product(api, "Pakastepizza", "Pakasteet")
    add_product(api, "Tiskiaine", "Kodin tarvikkeet")
    before = api.get("/api/products").json()

    into = patch(api, "Kodin tarvikkeet", {"parent_id": koti["id"]})
    out = patch(api, "Pakasteet", {"parent_id": None})

    assert (into.status_code, out.status_code) == (200, 200)
    assert item(api, "Koti")["category_count"] == 1
    assert item(api, "Ruoka")["category_count"] == 9
    assert item(api, "Pakasteet")["parent_id"] is None
    after = api.get("/api/products").json()
    assert [(p["name"], p["category_id"]) for p in after] == [
        (p["name"], p["category_id"]) for p in before
    ]


def test_ac9_patch_without_parent_keeps_the_group(api: TestClient) -> None:
    parent_id = item(api, "Liha")["parent_id"]

    response = patch(api, "Liha", {"name": "Lihat"})

    assert response.json()["parent_id"] == parent_id


@pytest.mark.parametrize(("name", "parent"), [("Auto", "Ruoka"), ("Liha", "Juomat")])
def test_ac10_nesting_is_refused(api: TestClient, name: str, parent: str) -> None:
    before = items(api)

    response = patch(api, name, {"parent_id": item_id(api, parent)})

    assert (response.status_code, response.json()["error"]) == (422, "invalid_parent")
    assert items(api) == before


def test_ac10_unknown_parent_is_refused(api: TestClient) -> None:
    response = patch(api, "Juomat", {"parent_id": 9999})

    assert (response.status_code, response.json()["error"]) == (422, "invalid_parent")
    assert item(api, "Juomat")["parent_id"] is None


def test_ac10_group_cannot_be_created_with_a_parent(api: TestClient) -> None:
    body = {"name": "Koti", "kind": "group", "parent_id": item_id(api, "Ruoka")}

    response = api.post("/api/categories", json=body)

    assert (response.status_code, response.json()["error"]) == (422, "invalid_parent")


def test_ac11_convert_empty_items(api: TestClient) -> None:
    add(api, "Harrastukset", "category")
    add(api, "Koti", "group")

    to_group = patch(api, "Harrastukset", {"kind": "group"})
    to_category = patch(api, "Koti", {"kind": "category"})

    assert (to_group.status_code, to_group.json()["kind"]) == (200, "group")
    assert (to_category.status_code, to_category.json()["kind"]) == (200, "category")


def test_ac12_conversion_refused(api: TestClient) -> None:
    add_product(api, "Mehu", "Juomat")
    add_product(api, "Limonadi", "Juomat")

    juomat = patch(api, "Juomat", {"kind": "group"})
    liha = patch(api, "Liha", {"kind": "group"})
    auto = patch(api, "Auto", {"kind": "category"})

    assert (juomat.status_code, juomat.json()["error"]) == (409, "category_has_products")
    assert (liha.status_code, liha.json()["error"]) == (422, "invalid_parent")
    assert (auto.status_code, auto.json()["error"], auto.json()["category_count"]) == (
        409,
        "group_not_empty",
        3,
    )
    kinds = [item(api, name)["kind"] for name in ("Juomat", "Liha", "Auto")]
    assert kinds == ["category", "category", "group"]


def test_ac13_delete_used_category(api: TestClient) -> None:
    for name in ("Mehu", "Limonadi", "Vesi"):
        add_product(api, name, "Juomat")

    response = api.delete(f"/api/categories/{item_id(api, 'Juomat')}")

    assert response.status_code == 409
    assert response.json() == {
        "error": "category_in_use",
        "message": "Kategoriaa käyttää 3 tuotetta.",
        "product_count": 3,
    }
    assert item(api, "Juomat")


def test_ac14_delete_group_with_categories(api: TestClient) -> None:
    response = api.delete(f"/api/categories/{item_id(api, 'Auto')}")

    assert response.status_code == 409
    assert (response.json()["error"], response.json()["category_count"]) == ("group_not_empty", 3)
    assert item(api, "Auto")["category_count"] == 3


def test_ac15_delete_empty_items(api: TestClient) -> None:
    harrastukset = add(api, "Harrastukset", "category")
    koti = add(api, "Koti", "group")

    first = api.delete(f"/api/categories/{harrastukset['id']}")
    second = api.delete(f"/api/categories/{koti['id']}")

    assert (first.status_code, first.content) == (204, b"")
    assert second.status_code == 204
    assert {"Harrastukset", "Koti"}.isdisjoint(row["name"] for row in items(api))


def test_ac25_data_survives_a_restart(settings: Settings) -> None:
    with make_client(settings) as first:
        koti = add(first, "Koti", "group")
        sisustus = add(first, "Sisustus", "category", koti["id"])
        first.post("/api/products", json={"name": "Matto", "category_id": sisustus["id"]})
        before = (items(first), first.get("/api/products").json())

    with make_client(settings) as second:
        assert (items(second), second.get("/api/products").json()) == before
    assert [product["name"] for product in before[1]] == ["Matto"]


def test_ac26_missing_category(api: TestClient) -> None:
    renamed = api.patch("/api/categories/9999", json={"name": "Uusi"})
    deleted = api.delete("/api/categories/9999")

    for response in (renamed, deleted):
        assert (response.status_code, response.json()["error"]) == (404, "not_found")


@pytest.mark.parametrize(
    "body",
    [{"kind": "category"}, {"name": "Koti", "kind": "folder"}, {"name": 123, "kind": "category"}],
)
def test_ac32_malformed_category_body(api: TestClient, body: dict[str, Any]) -> None:
    response = api.post("/api/categories", json=body)

    assert response.status_code == 422
    assert response.json() == INVALID_REQUEST
    assert len(items(api)) == 23


def test_ac10_item_cannot_be_its_own_parent(api: TestClient) -> None:
    koti = add(api, "Koti", "group")

    response = api.patch(
        f"/api/categories/{koti['id']}", json={"kind": "category", "parent_id": koti["id"]}
    )

    assert (response.status_code, response.json()["error"]) == (422, "invalid_parent")
    assert item(api, "Koti")["kind"] == "group"


def test_ac20b_delete_category_used_by_products_and_lines(
    api: TestClient, settings: Settings
) -> None:
    for name in ("Suklaa", "Karkki"):
        add_product(api, name, "Herkut")
    herkut = item_id(api, "Herkut")
    connection = connect(settings.db_path)
    try:
        receipts = ReceiptRepository(connection)
        with receipts.transaction():
            receipt = receipts.add("c" * 64, "a.jpg", "2026-10-30T10:00:00Z")
            for position in (1, 2, 3):
                receipts.add_line(
                    receipt.id,
                    position,
                    "Sipsit",
                    299,
                    is_deposit_refund=False,
                    category=LineCategory(herkut, "model", None),
                )
    finally:
        connection.close()

    response = api.delete(f"/api/categories/{herkut}")

    assert response.status_code == 409
    assert response.json() == {
        "error": "category_in_use",
        "message": "Kategoriaa käyttää 2 tuotetta ja 3 kuittiriviä.",
        "product_count": 2,
        "line_count": 3,
    }

from typing import Any

import pytest
from fastapi.testclient import TestClient

INVALID_REQUEST = {"error": "invalid_request", "message": "Pyyntö on virheellinen."}


def category_id(api: TestClient, name: str) -> int:
    rows = api.get("/api/categories").json()
    return next(row["id"] for row in rows if row["name"] == name)


def product_count(api: TestClient, name: str) -> int:
    rows = api.get("/api/categories").json()
    return next(row["product_count"] for row in rows if row["name"] == name)


def add(api: TestClient, name: str, category: str) -> dict[str, Any]:
    response = api.post(
        "/api/products", json={"name": name, "category_id": category_id(api, category)}
    )
    assert response.status_code == 201
    return response.json()


def names(response: Any) -> list[str]:
    assert response.status_code == 200
    return [product["name"] for product in response.json()]


def test_ac16_add_product(api: TestClient) -> None:
    response = api.post(
        "/api/products",
        json={"name": "  Kevytmaito   1L ", "category_id": category_id(api, "Maitotuotteet")},
    )

    assert response.status_code == 201
    body = response.json()
    assert (body["name"], body["category_name"], body["group_name"]) == (
        "Kevytmaito 1L",
        "Maitotuotteet",
        "Ruoka",
    )
    assert body["category_id"] == category_id(api, "Maitotuotteet")
    assert product_count(api, "Maitotuotteet") == 1


def test_ac17_duplicate_product(api: TestClient) -> None:
    add(api, "Kevytmaito 1L", "Maitotuotteet")

    response = api.post(
        "/api/products", json={"name": "KEVYTMAITO  1l", "category_id": category_id(api, "Juomat")}
    )

    assert (response.status_code, response.json()["error"]) == (409, "duplicate_name")
    assert names(api.get("/api/products")) == ["Kevytmaito 1L"]


@pytest.mark.parametrize("name", ["", "c" * 101])
def test_ac18_invalid_name(api: TestClient, name: str) -> None:
    response = api.post(
        "/api/products", json={"name": name, "category_id": category_id(api, "Juomat")}
    )

    assert (response.status_code, response.json()["error"]) == (422, "invalid_name")
    assert names(api.get("/api/products")) == []


def test_ac18_unknown_category(api: TestClient) -> None:
    response = api.post("/api/products", json={"name": "Mehu", "category_id": 9999})

    assert (response.status_code, response.json()["error"]) == (422, "unknown_category")


def test_ac19_group_as_category(api: TestClient) -> None:
    ruisleipa = add(api, "Ruisleipä", "Leivät")
    ruoka = category_id(api, "Ruoka")

    created = api.post("/api/products", json={"name": "Kaurahiutaleet", "category_id": ruoka})
    changed = api.patch(f"/api/products/{ruisleipa['id']}", json={"category_id": ruoka})

    for response in (created, changed):
        assert (response.status_code, response.json()["error"]) == (422, "not_a_category")
    assert [row["category_name"] for row in api.get("/api/products").json()] == ["Leivät"]


def test_ac20_recategorize(api: TestClient) -> None:
    product = add(api, "Kevytmaito 1L", "Maitotuotteet")

    response = api.patch(
        f"/api/products/{product['id']}", json={"category_id": category_id(api, "Juomat")}
    )

    assert response.status_code == 200
    assert (response.json()["category_name"], response.json()["group_name"]) == ("Juomat", None)
    assert (product_count(api, "Maitotuotteet"), product_count(api, "Juomat")) == (0, 1)


def test_ac21_rename_and_rename_to_duplicate(api: TestClient) -> None:
    product = add(api, "Kevytmaito 1L", "Maitotuotteet")
    add(api, "Rasvaton maito 1L", "Maitotuotteet")

    renamed = api.patch(f"/api/products/{product['id']}", json={"name": "Kevytmaito 1,5L"})
    duplicate = api.patch(f"/api/products/{product['id']}", json={"name": "rasvaton maito 1l"})

    assert (renamed.status_code, renamed.json()["name"]) == (200, "Kevytmaito 1,5L")
    assert (duplicate.status_code, duplicate.json()["error"]) == (409, "duplicate_name")
    assert names(api.get("/api/products")) == ["Kevytmaito 1,5L", "Rasvaton maito 1L"]


def test_ac22_delete_product(api: TestClient) -> None:
    product = add(api, "Kevytmaito 1L", "Maitotuotteet")

    response = api.delete(f"/api/products/{product['id']}")

    assert (response.status_code, response.content) == (204, b"")
    assert names(api.get("/api/products")) == []
    assert product_count(api, "Maitotuotteet") == 0


@pytest.fixture
def products(api: TestClient) -> None:
    add(api, "Rasvaton maito 1L", "Maitotuotteet")
    add(api, "Kevytmaito 1L", "Maitotuotteet")
    add(api, "Ruisleipä", "Leivät")
    add(api, "Moottoriöljy", "Autotarvikkeet")


@pytest.mark.usefixtures("products")
def test_ac23_search(api: TestClient) -> None:
    assert names(api.get("/api/products", params={"q": "MAITO"})) == [
        "Kevytmaito 1L",
        "Rasvaton maito 1L",
    ]


@pytest.mark.usefixtures("products")
def test_ac24_filters(api: TestClient) -> None:
    leivat, ruoka = category_id(api, "Leivät"), category_id(api, "Ruoka")

    assert names(api.get("/api/products", params={"category_id": leivat})) == ["Ruisleipä"]
    assert names(api.get("/api/products", params={"category_id": ruoka})) == [
        "Kevytmaito 1L",
        "Rasvaton maito 1L",
        "Ruisleipä",
    ]
    assert names(api.get("/api/products", params={"category_id": ruoka, "q": "öljy"})) == []


def test_ac26_missing_product(api: TestClient) -> None:
    renamed = api.patch("/api/products/9999", json={"name": "Mehu"})
    deleted = api.delete("/api/products/9999")

    for response in (renamed, deleted):
        assert (response.status_code, response.json()["error"]) == (404, "not_found")


@pytest.mark.parametrize("body", [{"name": "Mehu"}, {"name": "Mehu", "category_id": "x"}])
def test_ac32_malformed_product_body(api: TestClient, body: dict[str, Any]) -> None:
    response = api.post("/api/products", json=body)

    assert response.status_code == 422
    assert response.json() == INVALID_REQUEST


def test_ac33_unknown_filter(api: TestClient) -> None:
    response = api.get("/api/products", params={"category_id": 9999})

    assert (response.status_code, response.json()["error"]) == (422, "unknown_category")

import sqlite3

import pytest

from app.storage.catalog_repository import CatalogRepository, CategoryRow, ProductRow
from app.storage.receipt_repository import LineCategory, ReceiptRepository


@pytest.fixture
def repo(db: sqlite3.Connection) -> CatalogRepository:
    return CatalogRepository(db)


# Categories and groups


def test_ac3_add_and_get_category(repo: CatalogRepository) -> None:
    item_id = repo.add_category("Harrastukset", "harrastukset", "category", None)

    assert repo.get_category(item_id) == CategoryRow(
        id=item_id,
        name="Harrastukset",
        name_key="harrastukset",
        kind="category",
        parent_id=None,
        product_count=0,
        category_count=0,
    )


def test_ac26_get_missing_category_returns_none(repo: CatalogRepository) -> None:
    assert repo.get_category(9999) is None


def test_ac4_get_category_by_key(repo: CatalogRepository) -> None:
    item_id = repo.add_category("Ruoka", "ruoka", "group", None)

    found = repo.get_category_by_key("ruoka")

    assert found is not None
    assert found.id == item_id
    assert repo.get_category_by_key("auto") is None


def test_ac8_list_categories_counts_children_and_products(repo: CatalogRepository) -> None:
    ruoka = repo.add_category("Ruoka", "ruoka", "group", None)
    leivat = repo.add_category("Leivät", "leivät", "category", ruoka)
    repo.add_category("Liha", "liha", "category", ruoka)
    repo.add_product("Ruisleipä", "ruisleipä", leivat)
    repo.add_product("Paahtoleipä", "paahtoleipä", leivat)

    counts = {row.name: (row.category_count, row.product_count) for row in repo.list_categories()}

    assert counts == {"Ruoka": (2, 0), "Leivät": (0, 2), "Liha": (0, 0)}


def test_ac9_update_category(repo: CatalogRepository) -> None:
    koti = repo.add_category("Koti", "koti", "group", None)
    item_id = repo.add_category("Kodin tarvikkeet", "kodin tarvikkeet", "category", None)

    repo.update_category(item_id, "Sisustus", "sisustus", "category", koti)

    row = repo.get_category(item_id)
    assert row is not None
    assert (row.name, row.name_key, row.kind, row.parent_id) == (
        "Sisustus",
        "sisustus",
        "category",
        koti,
    )


def test_ac15_delete_category(repo: CatalogRepository) -> None:
    item_id = repo.add_category("Harrastukset", "harrastukset", "category", None)

    repo.delete_category(item_id)

    assert repo.get_category(item_id) is None


# Seed marker


def test_ac2_app_state_is_absent_until_set(repo: CatalogRepository) -> None:
    assert repo.get_app_state("catalog_seeded_at") is None

    repo.set_app_state("catalog_seeded_at", "2026-10-27T00:00:00+00:00")

    assert repo.get_app_state("catalog_seeded_at") == "2026-10-27T00:00:00+00:00"


# Products


@pytest.fixture
def catalog(repo: CatalogRepository) -> dict[str, int]:
    """Groups Ruoka and Auto, three categories and three products (AC24)."""
    ruoka = repo.add_category("Ruoka", "ruoka", "group", None)
    auto = repo.add_category("Auto", "auto", "group", None)
    ids = {
        "Ruoka": ruoka,
        "Auto": auto,
        "Maitotuotteet": repo.add_category("Maitotuotteet", "maitotuotteet", "category", ruoka),
        "Leivät": repo.add_category("Leivät", "leivät", "category", ruoka),
        "Autotarvikkeet": repo.add_category("Autotarvikkeet", "autotarvikkeet", "category", auto),
        "Juomat": repo.add_category("Juomat", "juomat", "category", None),
    }
    ids["Kevytmaito 1L"] = repo.add_product("Kevytmaito 1L", "kevytmaito 1l", ids["Maitotuotteet"])
    ids["Ruisleipä"] = repo.add_product("Ruisleipä", "ruisleipä", ids["Leivät"])
    ids["Moottoriöljy"] = repo.add_product("Moottoriöljy", "moottoriöljy", ids["Autotarvikkeet"])
    return ids


def names(rows: list[ProductRow]) -> set[str]:
    return {row.name for row in rows}


def test_ac16_get_product_with_category_and_group(
    repo: CatalogRepository, catalog: dict[str, int]
) -> None:
    assert repo.get_product(catalog["Kevytmaito 1L"]) == ProductRow(
        id=catalog["Kevytmaito 1L"],
        name="Kevytmaito 1L",
        name_key="kevytmaito 1l",
        category_id=catalog["Maitotuotteet"],
        category_name="Maitotuotteet",
        group_name="Ruoka",
    )


def test_ac20_product_without_group_has_no_group_name(
    repo: CatalogRepository, catalog: dict[str, int]
) -> None:
    product_id = repo.add_product("Mehu", "mehu", catalog["Juomat"])

    row = repo.get_product(product_id)

    assert row is not None
    assert row.group_name is None


def test_ac26_get_missing_product_returns_none(repo: CatalogRepository) -> None:
    assert repo.get_product(9999) is None


def test_ac17_get_product_by_key(repo: CatalogRepository, catalog: dict[str, int]) -> None:
    found = repo.get_product_by_key("ruisleipä")

    assert found is not None
    assert found.id == catalog["Ruisleipä"]
    assert repo.get_product_by_key("kaurahiutaleet") is None


def test_ac20_ac21_update_product(repo: CatalogRepository, catalog: dict[str, int]) -> None:
    repo.update_product(
        catalog["Kevytmaito 1L"], "Kevytmaito 1,5L", "kevytmaito 1,5l", catalog["Juomat"]
    )

    row = repo.get_product(catalog["Kevytmaito 1L"])
    assert row is not None
    assert (row.name, row.name_key, row.category_name) == (
        "Kevytmaito 1,5L",
        "kevytmaito 1,5l",
        "Juomat",
    )


def test_ac22_delete_product(repo: CatalogRepository, catalog: dict[str, int]) -> None:
    repo.delete_product(catalog["Ruisleipä"])

    assert repo.get_product(catalog["Ruisleipä"]) is None


def test_ac33_list_all_products(repo: CatalogRepository, catalog: dict[str, int]) -> None:
    assert names(repo.list_products()) == {"Kevytmaito 1L", "Ruisleipä", "Moottoriöljy"}


def test_ac23_list_products_by_substring_of_the_key(
    repo: CatalogRepository, catalog: dict[str, int]
) -> None:
    repo.add_product("Rasvaton maito 1L", "rasvaton maito 1l", catalog["Maitotuotteet"])

    assert names(repo.list_products(query_key="maito")) == {"Kevytmaito 1L", "Rasvaton maito 1L"}


def test_ac23_wildcards_in_the_query_match_literally(
    repo: CatalogRepository, catalog: dict[str, int]
) -> None:
    repo.add_product("Mehu 100%", "mehu 100%", catalog["Juomat"])

    assert names(repo.list_products(query_key="%")) == {"Mehu 100%"}
    assert names(repo.list_products(query_key="_")) == set()


def test_ac24_list_products_of_a_category(repo: CatalogRepository, catalog: dict[str, int]) -> None:
    assert names(repo.list_products(category_or_group_id=catalog["Leivät"])) == {"Ruisleipä"}


def test_ac24_list_products_of_a_group(repo: CatalogRepository, catalog: dict[str, int]) -> None:
    assert names(repo.list_products(category_or_group_id=catalog["Ruoka"])) == {
        "Kevytmaito 1L",
        "Ruisleipä",
    }


def test_ac24_group_filter_and_query_combine(
    repo: CatalogRepository, catalog: dict[str, int]
) -> None:
    rows = repo.list_products(query_key="öljy", category_or_group_id=catalog["Ruoka"])

    assert rows == []


def test_repository_transaction_rolls_back_on_error(repo: CatalogRepository) -> None:
    with pytest.raises(ValueError, match="stop"), repo.transaction():
        repo.add_category("Harrastukset", "harrastukset", "category", None)
        raise ValueError("stop")

    assert repo.list_categories() == []


# Categorization spec P3: lines that use a category, and lines that follow a product.


def add_line(
    db: sqlite3.Connection, position: int, category: LineCategory | None, image_hash: str = "e"
) -> None:
    receipts = ReceiptRepository(db)
    receipt = receipts.get_by_hash(image_hash * 64) or receipts.add(
        image_hash * 64, "a.jpg", "2026-10-30T10:00:00Z"
    )
    receipts.add_line(
        receipt.id, position, "Ruisleipä", 189, is_deposit_refund=False, category=category
    )


def test_category_counts_its_lines(db: sqlite3.Connection, repo: CatalogRepository) -> None:
    used = repo.add_category("Leivät", "leivät", "category", None)
    unused = repo.add_category("Kala", "kala", "category", None)
    for position in (1, 2, 3):
        add_line(db, position, LineCategory(used, "model", None))

    counts = [repo.get_category(item) for item in (used, unused)]
    assert [row.line_count if row else None for row in counts] == [3, 0]


def test_move_product_lines_moves_only_the_products_lines(
    db: sqlite3.Connection, repo: CatalogRepository
) -> None:
    old = repo.add_category("Leivät", "leivät", "category", None)
    new = repo.add_category("Kuivatuotteet", "kuivatuotteet", "category", None)
    product = repo.add_product("Ruisleipä", "ruisleipä", old)
    add_line(db, 1, LineCategory(old, "user", product))
    add_line(db, 2, LineCategory(old, "remembered", product))
    add_line(db, 3, LineCategory(old, "model", None))

    repo.move_product_lines(product, new)

    receipt = ReceiptRepository(db).get_by_hash("e" * 64)
    assert receipt is not None
    lines = ReceiptRepository(db).lines(receipt.id)
    assert [(line.category_id, line.category_source, line.product_id) for line in lines] == [
        (new, "remembered", product),
        (new, "remembered", product),
        (old, "model", None),
    ]

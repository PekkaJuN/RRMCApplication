import sqlite3
from datetime import UTC, datetime

import pytest

from app.categorization.defaults import seed_defaults
from app.categorization.errors import (
    DuplicateNameError,
    InvalidNameError,
    NotACategoryError,
    NotFoundError,
    UnknownCategoryError,
)
from app.categorization.service import CategoryService, ProductService
from app.storage.catalog_repository import CatalogRepository


@pytest.fixture
def repo(db: sqlite3.Connection) -> CatalogRepository:
    repository = CatalogRepository(db)
    seed_defaults(repository, datetime(2026, 10, 27, tzinfo=UTC))
    return repository


@pytest.fixture
def ids(repo: CatalogRepository) -> dict[str, int]:
    return {row.name: row.id for row in CategoryService(repo).list()}


@pytest.fixture
def service(repo: CatalogRepository) -> ProductService:
    return ProductService(repo)


def count(repo: CatalogRepository, category_id: int) -> int:
    row = repo.get_category(category_id)
    assert row is not None
    return row.product_count


# T11: writes


def test_ac16_add_product(
    service: ProductService, repo: CatalogRepository, ids: dict[str, int]
) -> None:
    product = service.create("  Kevytmaito   1L ", ids["Maitotuotteet"])

    assert (product.name, product.category_name, product.group_name) == (
        "Kevytmaito 1L",
        "Maitotuotteet",
        "Ruoka",
    )
    assert count(repo, ids["Maitotuotteet"]) == 1


def test_ac17_duplicate_after_normalization(service: ProductService, ids: dict[str, int]) -> None:
    service.create("Kevytmaito 1L", ids["Maitotuotteet"])

    with pytest.raises(DuplicateNameError):
        service.create("KEVYTMAITO  1l", ids["Juomat"])

    assert len(service.list()) == 1


@pytest.mark.parametrize("name", ["", "c" * 101])
def test_ac18_invalid_name(service: ProductService, ids: dict[str, int], name: str) -> None:
    with pytest.raises(InvalidNameError):
        service.create(name, ids["Juomat"])

    assert service.list() == []


def test_ac18_unknown_category(service: ProductService) -> None:
    with pytest.raises(UnknownCategoryError):
        service.create("Mehu", 9999)

    assert service.list() == []


def test_ac19_product_cannot_belong_to_a_group(
    service: ProductService, ids: dict[str, int]
) -> None:
    ruisleipa = service.create("Ruisleipä", ids["Leivät"])

    with pytest.raises(NotACategoryError):
        service.create("Kaurahiutaleet", ids["Ruoka"])
    with pytest.raises(NotACategoryError):
        service.update(ruisleipa.id, category_id=ids["Ruoka"])

    assert [product.category_name for product in service.list()] == ["Leivät"]


def test_ac20_change_category(
    service: ProductService, repo: CatalogRepository, ids: dict[str, int]
) -> None:
    product = service.create("Kevytmaito 1L", ids["Maitotuotteet"])

    changed = service.update(product.id, category_id=ids["Juomat"])

    assert (changed.category_name, changed.group_name) == ("Juomat", None)
    assert (count(repo, ids["Maitotuotteet"]), count(repo, ids["Juomat"])) == (0, 1)


def test_ac21_rename(service: ProductService, ids: dict[str, int]) -> None:
    product = service.create("Kevytmaito 1L", ids["Maitotuotteet"])
    service.create("Rasvaton maito 1L", ids["Maitotuotteet"])

    assert service.update(product.id, name="Kevytmaito 1,5L").name == "Kevytmaito 1,5L"
    with pytest.raises(DuplicateNameError):
        service.update(product.id, name="rasvaton maito 1l")

    assert {row.name for row in service.list()} == {"Kevytmaito 1,5L", "Rasvaton maito 1L"}


def test_ac21_rename_to_a_case_variant_of_the_own_name(
    service: ProductService, ids: dict[str, int]
) -> None:
    product = service.create("kevytmaito 1l", ids["Maitotuotteet"])

    assert service.update(product.id, name="Kevytmaito 1L").name == "Kevytmaito 1L"


def test_ac22_delete(service: ProductService, repo: CatalogRepository, ids: dict[str, int]) -> None:
    product = service.create("Kevytmaito 1L", ids["Maitotuotteet"])

    service.delete(product.id)

    assert service.list() == []
    assert count(repo, ids["Maitotuotteet"]) == 0


def test_ac26_missing_product(service: ProductService) -> None:
    with pytest.raises(NotFoundError):
        service.update(9999, name="Mehu")
    with pytest.raises(NotFoundError):
        service.delete(9999)


# T12: list


@pytest.fixture
def products(service: ProductService, ids: dict[str, int]) -> None:
    service.create("Rasvaton maito 1L", ids["Maitotuotteet"])
    service.create("Kevytmaito 1L", ids["Maitotuotteet"])
    service.create("Ruisleipä", ids["Leivät"])
    service.create("Moottoriöljy", ids["Autotarvikkeet"])


@pytest.mark.usefixtures("products")
def test_ac23_search_is_normalized_and_sorted(service: ProductService) -> None:
    assert [row.name for row in service.list(query="  MAITO ")] == [
        "Kevytmaito 1L",
        "Rasvaton maito 1L",
    ]


@pytest.mark.usefixtures("products")
def test_ac23_empty_query_lists_all_sorted(service: ProductService) -> None:
    assert [row.name for row in service.list(query="")] == [
        "Kevytmaito 1L",
        "Moottoriöljy",
        "Rasvaton maito 1L",
        "Ruisleipä",
    ]


@pytest.mark.usefixtures("products")
def test_ac24_filter_by_category_group_and_query(
    service: ProductService, ids: dict[str, int]
) -> None:
    assert [row.name for row in service.list(category_id=ids["Leivät"])] == ["Ruisleipä"]
    assert [row.name for row in service.list(category_id=ids["Ruoka"])] == [
        "Kevytmaito 1L",
        "Rasvaton maito 1L",
        "Ruisleipä",
    ]
    assert service.list(query="öljy", category_id=ids["Ruoka"]) == []


def test_ac33_unknown_filter(service: ProductService) -> None:
    with pytest.raises(UnknownCategoryError):
        service.list(category_id=9999)

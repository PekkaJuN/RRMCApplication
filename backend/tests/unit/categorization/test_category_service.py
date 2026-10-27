import sqlite3
from datetime import UTC, datetime

import pytest

from app.categorization.defaults import seed_defaults
from app.categorization.errors import (
    CategoryHasProductsError,
    CategoryInUseError,
    DuplicateNameError,
    GroupNotEmptyError,
    InvalidNameError,
    InvalidParentError,
    NotFoundError,
)
from app.categorization.service import CategoryService
from app.storage.catalog_repository import CatalogRepository, CategoryRow


@pytest.fixture
def repo(db: sqlite3.Connection) -> CatalogRepository:
    repository = CatalogRepository(db)
    seed_defaults(repository, datetime(2026, 10, 27, tzinfo=UTC))
    return repository


@pytest.fixture
def service(repo: CatalogRepository) -> CategoryService:
    return CategoryService(repo)


def find(service: CategoryService, name: str) -> CategoryRow:
    return next(row for row in service.list() if row.name == name)


def add_products(repo: CatalogRepository, category: CategoryRow, count: int) -> None:
    for number in range(count):
        repo.add_product(f"Tuote {number}", f"tuote {category.id} {number}", category.id)


# T8: create and rename


def test_ac3_create_category_without_group(service: CategoryService) -> None:
    row = service.create("  Harrastukset  ", "category", None)

    assert (row.name, row.kind, row.parent_id, row.product_count) == (
        "Harrastukset",
        "category",
        None,
        0,
    )


@pytest.mark.parametrize(("name", "kind"), [("ruoka", "category"), ("JUOMAT", "group")])
def test_ac4_names_are_unique_across_groups_and_categories(
    service: CategoryService, name: str, kind: str
) -> None:
    before = service.list()

    with pytest.raises(DuplicateNameError):
        service.create(name, "category" if kind == "category" else "group", None)

    assert service.list() == before


@pytest.mark.parametrize("name", ["", "   ", "a" * 51])
def test_ac5_invalid_names_are_rejected_on_create_and_rename(
    service: CategoryService, name: str
) -> None:
    juomat = find(service, "Juomat")
    before = service.list()

    with pytest.raises(InvalidNameError):
        service.create(name, "category", None)
    with pytest.raises(InvalidNameError):
        service.update(juomat.id, name=name)

    assert service.list() == before


def test_ac6_rename_keeps_the_products(service: CategoryService, repo: CatalogRepository) -> None:
    juomat = find(service, "Juomat")
    add_products(repo, juomat, 2)

    row = service.update(juomat.id, name="Virvoitusjuomat")

    assert (row.name, row.product_count) == ("Virvoitusjuomat", 2)


def test_ac7_rename_to_a_case_variant_of_the_own_name(service: CategoryService) -> None:
    item = service.create("juomat2", "category", None)

    assert service.update(item.id, name="Juomat2").name == "Juomat2"


def test_ac4_rename_to_another_items_name_is_a_duplicate(service: CategoryService) -> None:
    juomat = find(service, "Juomat")

    with pytest.raises(DuplicateNameError):
        service.update(juomat.id, name="ruoka")


def test_ac8_create_group_and_a_category_in_it(service: CategoryService) -> None:
    koti = service.create("Koti", "group", None)
    sisustus = service.create("Sisustus", "category", koti.id)

    assert sisustus.parent_id == koti.id
    assert find(service, "Koti").category_count == 1


# T9: move, nesting and conversion


def test_ac9_move_category_into_a_group_and_out_of_a_group(
    service: CategoryService, repo: CatalogRepository
) -> None:
    koti = service.create("Koti", "group", None)
    tarvikkeet = find(service, "Kodin tarvikkeet")
    pakasteet = find(service, "Pakasteet")
    add_products(repo, pakasteet, 1)

    service.update(tarvikkeet.id, parent_id=koti.id)
    service.update(pakasteet.id, parent_id=None)

    assert find(service, "Koti").category_count == 1
    assert find(service, "Ruoka").category_count == 9
    assert find(service, "Pakasteet").parent_id is None
    assert find(service, "Pakasteet").product_count == 1


def test_ac9_update_without_parent_keeps_the_group(service: CategoryService) -> None:
    liha = find(service, "Liha")

    assert service.update(liha.id, name="Lihat").parent_id == liha.parent_id


def test_ac10_group_cannot_get_a_parent(service: CategoryService) -> None:
    auto = find(service, "Auto")
    ruoka = find(service, "Ruoka")

    with pytest.raises(InvalidParentError):
        service.update(auto.id, parent_id=ruoka.id)


def test_ac10_category_cannot_be_the_parent(service: CategoryService) -> None:
    liha = find(service, "Liha")
    juomat = find(service, "Juomat")

    with pytest.raises(InvalidParentError):
        service.update(liha.id, parent_id=juomat.id)
    with pytest.raises(InvalidParentError):
        service.create("Mehut", "category", juomat.id)


def test_ac10_group_cannot_be_created_with_a_parent(service: CategoryService) -> None:
    ruoka = find(service, "Ruoka")

    with pytest.raises(InvalidParentError):
        service.create("Koti", "group", ruoka.id)


def test_ac10_missing_parent_is_invalid(service: CategoryService) -> None:
    juomat = find(service, "Juomat")
    before = service.list()

    with pytest.raises(InvalidParentError):
        service.update(juomat.id, parent_id=9999)

    assert service.list() == before


def test_ac11_convert_empty_category_to_group_and_empty_group_to_category(
    service: CategoryService,
) -> None:
    harrastukset = service.create("Harrastukset", "category", None)
    koti = service.create("Koti", "group", None)

    assert service.update(harrastukset.id, kind="group").kind == "group"
    assert service.update(koti.id, kind="category").kind == "category"


def test_ac12_category_with_products_cannot_become_a_group(
    service: CategoryService, repo: CatalogRepository
) -> None:
    juomat = find(service, "Juomat")
    add_products(repo, juomat, 2)

    with pytest.raises(CategoryHasProductsError):
        service.update(juomat.id, kind="group")

    assert find(service, "Juomat").kind == "category"


def test_ac12_category_in_a_group_cannot_become_a_group(service: CategoryService) -> None:
    liha = find(service, "Liha")

    with pytest.raises(InvalidParentError):
        service.update(liha.id, kind="group")


def test_ac12_category_taken_out_of_its_group_can_become_a_group(
    service: CategoryService,
) -> None:
    liha = find(service, "Liha")

    row = service.update(liha.id, kind="group", parent_id=None)

    assert (row.kind, row.parent_id) == ("group", None)


def test_ac12_group_with_categories_cannot_become_a_category(service: CategoryService) -> None:
    auto = find(service, "Auto")

    with pytest.raises(GroupNotEmptyError) as error:
        service.update(auto.id, kind="category")

    assert error.value.extra == {"category_count": 3}


def test_ac26_update_missing_item(service: CategoryService) -> None:
    with pytest.raises(NotFoundError):
        service.update(9999, name="Uusi")


# T10: delete and list


def test_ac13_category_in_use_cannot_be_deleted(
    service: CategoryService, repo: CatalogRepository
) -> None:
    juomat = find(service, "Juomat")
    add_products(repo, juomat, 3)

    with pytest.raises(CategoryInUseError) as error:
        service.delete(juomat.id)

    assert error.value.extra == {"product_count": 3}
    assert find(service, "Juomat")


def test_ac14_group_with_categories_cannot_be_deleted(service: CategoryService) -> None:
    auto = find(service, "Auto")

    with pytest.raises(GroupNotEmptyError) as error:
        service.delete(auto.id)

    assert error.value.extra == {"category_count": 3}
    assert find(service, "Auto").category_count == 3


def test_ac15_unused_category_and_empty_group_are_deleted(service: CategoryService) -> None:
    harrastukset = service.create("Harrastukset", "category", None)
    koti = service.create("Koti", "group", None)

    service.delete(harrastukset.id)
    service.delete(koti.id)

    assert {"Harrastukset", "Koti"}.isdisjoint(row.name for row in service.list())


def test_ac26_delete_missing_item(service: CategoryService) -> None:
    with pytest.raises(NotFoundError):
        service.delete(9999)


def test_ac1_list_puts_groups_with_their_categories_first_then_ungrouped(
    service: CategoryService,
) -> None:
    service.create("Äänikirjat", "category", None)
    service.create("Öljyt", "category", find(service, "Auto").id)

    names = [row.name for row in service.list()]

    assert names == [
        "Auto",
        "Autohuolto",
        "Autotarvikkeet",
        "Polttoaineet",
        "Öljyt",
        "Ruoka",
        "Hedelmät",
        "Kala",
        "Kananmunat",
        "Kuivatuotteet",
        "Leivät",
        "Liha",
        "Lihan korvaajat",
        "Maitotuotteet",
        "Pakasteet",
        "Vihannekset",
        "Alkoholi",
        "Herkut",
        "Hygienia",
        "Juomat",
        "Kodin tarvikkeet",
        "Lemmikit",
        "Muut",
        "Ulkona syöminen",
        "Äänikirjat",
    ]


def test_ac10_group_cannot_become_a_category_inside_itself(service: CategoryService) -> None:
    koti = service.create("Koti", "group", None)

    with pytest.raises(InvalidParentError):
        service.update(koti.id, kind="category", parent_id=koti.id)

    assert find(service, "Koti").kind == "group"

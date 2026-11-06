import sqlite3

import pytest

from app.storage.catalog_repository import CatalogRepository


@pytest.fixture
def repository(db: sqlite3.Connection) -> CatalogRepository:
    return CatalogRepository(db)


def add(repository: CatalogRepository, name: str) -> int:
    return repository.add_category(name, name.casefold(), "category", None)


def test_ac1_no_saved_budgets(repository: CatalogRepository) -> None:
    assert repository.budgets() == {}


def test_ac2_saving_twice_keeps_the_latest_amount(repository: CatalogRepository) -> None:
    item = add(repository, "Auto")

    repository.set_budget(item, 15000)
    repository.set_budget(item, 20000)

    assert repository.budgets() == {item: 20000}


def test_ac23_a_move_adds_to_the_target_and_removes_the_source(
    repository: CatalogRepository,
) -> None:
    source, target = add(repository, "Juomat"), add(repository, "Ruoka")
    repository.set_budget(source, 5000)
    repository.set_budget(target, 40000)

    repository.move_budget(source, target)

    assert repository.budgets() == {target: 45000}


def test_ac23_a_move_to_a_target_without_a_budget(repository: CatalogRepository) -> None:
    source, target = add(repository, "Juomat"), add(repository, "Ruoka")
    repository.set_budget(source, 5000)

    repository.move_budget(source, target)

    assert repository.budgets() == {target: 5000}


def test_ac24_a_move_without_a_source_budget_changes_nothing(
    repository: CatalogRepository,
) -> None:
    source, target = add(repository, "Juomat"), add(repository, "Ruoka")
    repository.set_budget(target, 40000)

    repository.move_budget(source, target)

    assert repository.budgets() == {target: 40000}


def test_ac23_a_moved_sum_may_exceed_the_amount_limit(repository: CatalogRepository) -> None:
    source, target = add(repository, "Juomat"), add(repository, "Ruoka")
    repository.set_budget(source, 99_999_999)
    repository.set_budget(target, 99_999_999)

    repository.move_budget(source, target)

    assert repository.budgets() == {target: 199_999_998}

import sqlite3
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

import pytest

from app.categorization.defaults import seed_defaults
from app.categorization.line_categorizer import LineCategorizer
from app.categorization.names import normalize_key
from app.receipt_reading.receipt import ReadLine
from app.storage.catalog_repository import CatalogRepository
from app.storage.receipt_repository import LineCategory


class SuggesterDouble:
    """Suggests the option named in `answers` for each name, and records each call."""

    def __init__(self, answers: Mapping[str, str] | None = None) -> None:
        self.answers = answers or {}
        self.calls: list[tuple[list[str], list[str]]] = []

    def suggest(self, names: Sequence[str], options: Sequence[str]) -> list[int | None]:
        self.calls.append((list(names), list(options)))
        return [
            options.index(self.answers[name]) if name in self.answers else None for name in names
        ]


@pytest.fixture
def repository(db: sqlite3.Connection) -> CatalogRepository:
    repository = CatalogRepository(db)
    seed_defaults(repository, datetime(2026, 10, 30, tzinfo=UTC))
    return repository


def category_id(repository: CatalogRepository, name: str) -> int:
    row = repository.get_category_by_key(normalize_key(name))
    assert row is not None
    return row.id


def add_product(repository: CatalogRepository, name: str, category: str) -> int:
    return repository.add_product(name, normalize_key(name), category_id(repository, category))


def line(name: str, amount: int = 100, *, refund: bool = False) -> ReadLine:
    return ReadLine(name, amount, refund)


def categorize(
    repository: CatalogRepository, suggester: SuggesterDouble, lines: list[ReadLine]
) -> list[LineCategory | None]:
    categorizer = LineCategorizer(repository, suggester)
    return categorizer.resolve(lines, categorizer.suggest(lines))


def test_ac1_remembered_product_gives_category_without_call(
    repository: CatalogRepository,
) -> None:
    product = add_product(repository, "Kevytmaito 1L", "Maitotuotteet")
    suggester = SuggesterDouble()

    result = categorize(repository, suggester, [line("KEVYTMAITO  1L", 129)])

    assert result == [LineCategory(category_id(repository, "Maitotuotteet"), "remembered", product)]
    assert suggester.calls == []


def test_ac2_only_unknown_names_in_one_call(repository: CatalogRepository) -> None:
    product = add_product(repository, "Ruisleipä", "Leivät")
    suggester = SuggesterDouble({"Banaani": "Ruoka > Hedelmät", "Tomaatti": "Ruoka > Vihannekset"})

    result = categorize(
        repository, suggester, [line("Ruisleipä"), line("Banaani"), line("Tomaatti")]
    )

    assert [names for names, _ in suggester.calls] == [["Banaani", "Tomaatti"]]
    assert result == [
        LineCategory(category_id(repository, "Leivät"), "remembered", product),
        LineCategory(category_id(repository, "Hedelmät"), "model", None),
        LineCategory(category_id(repository, "Vihannekset"), "model", None),
    ]
    assert len(repository.list_products()) == 1


def test_ac6_one_line_receipt(repository: CatalogRepository) -> None:
    suggester = SuggesterDouble({"Bensiini 95E10": "Auto > Polttoaineet"})

    result = categorize(repository, suggester, [line("Bensiini 95E10", 6000)])

    assert result == [LineCategory(category_id(repository, "Polttoaineet"), "model", None)]


def test_ac4_repeated_name_asked_once(repository: CatalogRepository) -> None:
    suggester = SuggesterDouble({"Banaani": "Ruoka > Hedelmät", "Omena": "Herkut"})

    result = categorize(repository, suggester, [line("Banaani"), line("BANAANI"), line("Omena")])

    assert [names for names, _ in suggester.calls] == [["Banaani", "Omena"]]
    fruit = LineCategory(category_id(repository, "Hedelmät"), "model", None)
    assert result[:2] == [fruit, fruit]


def test_ac5_refund_has_no_category_and_no_call(repository: CatalogRepository) -> None:
    add_product(repository, "Kevytmaito 1L", "Maitotuotteet")
    suggester = SuggesterDouble({"Panttipalautus": "Muut"})

    result = categorize(
        repository,
        suggester,
        [line("Kevytmaito 1L", 129), line("Panttipalautus", -40, refund=True)],
    )

    assert result[1] is None
    assert suggester.calls == []
    assert repository.get_product_by_key("panttipalautus") is None


def test_ac11_no_categories_no_call(db: sqlite3.Connection) -> None:
    repository = CatalogRepository(db)
    repository.add_category("Ruoka", "ruoka", "group", None)
    suggester = SuggesterDouble()

    assert categorize(repository, suggester, [line("Banaani")]) == [None]
    assert suggester.calls == []


def test_ac12_deleted_category_and_product_are_not_used(repository: CatalogRepository) -> None:
    add_product(repository, "Ruisleipä", "Leivät")
    categorizer = LineCategorizer(repository, SuggesterDouble({"Banaani": "Ruoka > Hedelmät"}))
    lines = [line("Banaani"), line("Ruisleipä")]
    suggestions = categorizer.suggest(lines)

    # The user deletes the category and the product while the run waits for the commit
    repository.delete_category(category_id(repository, "Hedelmät"))
    product = repository.get_product_by_key("ruisleipä")
    assert product is not None
    repository.delete_product(product.id)

    assert categorizer.resolve(lines, suggestions) == [None, None]


def test_ac12_category_turned_into_a_group_is_not_used(repository: CatalogRepository) -> None:
    categorizer = LineCategorizer(repository, SuggesterDouble({"Banaani": "Herkut"}))
    lines = [line("Banaani")]
    suggestions = categorizer.suggest(lines)

    herkut = category_id(repository, "Herkut")
    repository.update_category(herkut, "Herkut", "herkut", "group", None)

    assert categorizer.resolve(lines, suggestions) == [None]


def test_ac5_refund_ignores_a_product_of_the_same_name(repository: CatalogRepository) -> None:
    add_product(repository, "Panttipalautus", "Muut")

    result = categorize(repository, SuggesterDouble(), [line("Panttipalautus", -40, refund=True)])

    assert result == [None]


class FixedSuggester:
    def __init__(self, indexes: list[int | None]) -> None:
        self.indexes = indexes

    def suggest(self, names: Sequence[str], options: Sequence[str]) -> list[int | None]:
        return self.indexes


def test_ac8_index_outside_the_options_gives_no_category(repository: CatalogRepository) -> None:
    # The protocol does not promise a valid index; -1 must not mean the last option
    lines = [line("Banaani"), line("Tomaatti"), line("Omena")]
    categorizer = LineCategorizer(repository, FixedSuggester([-1, 21, 0]))

    result = categorizer.resolve(lines, categorizer.suggest(lines))

    assert result[:2] == [None, None]
    assert result[2] is not None

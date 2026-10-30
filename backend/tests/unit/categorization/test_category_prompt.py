import sqlite3
from datetime import UTC, datetime

import pytest

from app.categorization.defaults import seed_defaults
from app.categorization.prompt import (
    answer_schema,
    category_options,
    category_prompt,
    parse_answer,
)
from app.categorization.service import CategoryService
from app.storage.catalog_repository import CatalogRepository


def default_options(db: sqlite3.Connection) -> list[str]:
    repository = CatalogRepository(db)
    seed_defaults(repository, datetime(2026, 10, 30, tzinfo=UTC))
    return category_options(CategoryService(repository).list())


def test_ac3_options_have_groups_and_no_bare_group(db: sqlite3.Connection) -> None:
    options = default_options(db)

    assert len(options) == 21
    assert {"Ruoka > Maitotuotteet", "Auto > Polttoaineet", "Juomat"} <= set(options)
    assert "Ruoka" not in options
    assert "Auto" not in options
    # Groups first in Finnish order, each followed by its categories, then the ungrouped ones
    assert options[0].startswith("Auto > ")
    assert options[-1] == "Ulkona syöminen"


def test_ac3_prompt_lists_numbered_categories_before_numbered_names() -> None:
    prompt = category_prompt(["Ruoka > Hedelmät", "Juomat"], ["Banaani", "Limu"])

    categories = prompt.index("Categories:\n1 Ruoka > Hedelmät\n2 Juomat\n")
    products = prompt.index("Products:\n1 Banaani\n2 Limu\n")
    assert categories < products


def test_ac3_schema_allows_only_listed_numbers_and_one_per_name() -> None:
    schema = answer_schema(option_count=21, name_count=2)

    numbers = schema["properties"]["c"]
    assert numbers["items"] == {"type": "integer", "enum": list(range(1, 22))}
    assert (numbers["minItems"], numbers["maxItems"]) == (2, 2)
    assert schema["required"] == ["c"]


@pytest.mark.parametrize(
    "raw",
    ["no json", '{"x": [1, 2]}', '{"c": [1]}', '{"c": [1, 2.5]}', '{"c": [1, true]}', '{"c": 1}'],
    ids=["not JSON", "no c", "wrong count", "decimal", "boolean", "not a list"],
)
def test_ac7_invalid_answers_are_none(raw: str) -> None:
    assert parse_answer(raw, option_count=21, name_count=2) is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [('{"c": [0, 5]}', [None, 4]), ('{"c": [22, 5]}', [None, 4]), ('{"c": [1, 21]}', [0, 20])],
)
def test_ac8_numbers_outside_the_list_are_none(raw: str, expected: list[int | None]) -> None:
    assert parse_answer(raw, option_count=21, name_count=2) == expected

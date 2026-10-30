"""The categorization prompt, its answer schema and answer parsing (categorization spec)."""

from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from app.storage.catalog_repository import CategoryRow

# The categories come before the names, so the start of the prompt stays the same between
# receipts and Ollama can reuse it from its prompt cache.
INSTRUCTIONS = """\
You choose a shopping category for each product name from a Finnish shop receipt.
Answer with JSON only: {"c": [...]}, one category number per product, in product order.
"""


def category_options(rows: Sequence[CategoryRow]) -> list[str]:
    """The categories of `CategoryService.list()` in its order, each with its group as
    "Ryhmä > Kategoria". Groups are not options: the model can choose only a category."""
    groups = {row.id: row.name for row in rows if row.kind == "group"}
    return [
        f"{groups[row.parent_id]} > {row.name}" if row.parent_id in groups else row.name
        for row in rows
        if row.kind == "category"
    ]


def category_prompt(options: Sequence[str], names: Sequence[str]) -> str:
    categories = "".join(f"{number} {option}\n" for number, option in enumerate(options, 1))
    products = "".join(f"{number} {name}\n" for number, name in enumerate(names, 1))
    return f"{INSTRUCTIONS}\nCategories:\n{categories}\nProducts:\n{products}"


def answer_schema(option_count: int, name_count: int) -> dict[str, Any]:
    """One listed category number per name. Ollama turns the schema into a grammar."""
    return {
        "type": "object",
        "properties": {
            "c": {
                "type": "array",
                "items": {"type": "integer", "enum": list(range(1, option_count + 1))},
                "minItems": name_count,
                "maxItems": name_count,
            }
        },
        "required": ["c"],
    }


class _Answer(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    c: list[int]


def parse_answer(raw: str, option_count: int, name_count: int) -> list[int | None] | None:
    """The option index (from 0) for each name, None for a number outside the list; or
    None for the whole answer when it is not JSON of the schema or has the wrong count.

    The schema's grammar should prevent both, but it is Ollama's behavior, not a guarantee.
    """
    try:
        numbers = _Answer.model_validate_json(raw).c
    except ValidationError:
        return None
    if len(numbers) != name_count:
        return None
    return [number - 1 if 1 <= number <= option_count else None for number in numbers]

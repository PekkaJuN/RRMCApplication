"""A category for each line of a read receipt: remembered product first, then the model
(categorization spec PC2-PC5)."""

from collections.abc import Mapping, Sequence

from app.categorization.names import normalize_key
from app.categorization.prompt import category_options
from app.categorization.service import CategoryService
from app.categorization.suggester import CategorySuggester
from app.receipt_reading.receipt import ReadLine
from app.storage.catalog_repository import CatalogRepository
from app.storage.receipt_repository import LineCategory

# The model's suggestions: normalized line name -> category id.
type Suggestions = Mapping[str, int]


class LineCategorizer:
    """`suggest` runs before the commit, because the model takes seconds; `resolve` runs
    inside it, so products and categories changed meanwhile are seen as they are (PC5)."""

    def __init__(self, repository: CatalogRepository, suggester: CategorySuggester) -> None:
        self._repository = repository
        self._suggester = suggester

    def suggest(self, lines: Sequence[ReadLine]) -> Suggestions:
        """Ask the model, in one call, about the names that match no product.

        Raises:
            ModelUnavailableError: from the suggester; the import run must stop.
        """
        unknown: dict[str, str] = {}  # key -> the name of its first line
        for line in lines:
            key = normalize_key(line.name)
            if line.is_deposit_refund or key in unknown:
                continue
            if self._repository.get_product_by_key(key) is None:
                unknown[key] = line.name
        if not unknown:
            return {}
        rows = CategoryService(self._repository).list()
        categories = [row for row in rows if row.kind == "category"]
        if not categories:
            return {}
        indexes = self._suggester.suggest(list(unknown.values()), category_options(rows))
        return {
            key: categories[index].id
            for key, index in zip(unknown, indexes, strict=True)
            if index is not None and 0 <= index < len(categories)
        }

    def resolve(
        self, lines: Sequence[ReadLine], suggestions: Suggestions
    ) -> list[LineCategory | None]:
        return [self._resolve(line, suggestions) for line in lines]

    def _resolve(self, line: ReadLine, suggestions: Suggestions) -> LineCategory | None:
        if line.is_deposit_refund:
            return None
        key = normalize_key(line.name)
        product = self._repository.get_product_by_key(key)
        if product is not None:
            return LineCategory(product.category_id, "remembered", product.id)
        suggested = suggestions.get(key)
        category = None if suggested is None else self._repository.get_category(suggested)
        if category is None or category.kind != "category":
            return None
        return LineCategory(category.id, "model", None)

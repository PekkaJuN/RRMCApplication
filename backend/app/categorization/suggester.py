"""Category suggestions for product names: from the model, or a fake (categorization spec)."""

from collections.abc import Sequence
from typing import Protocol

from app.categorization.prompt import answer_schema, category_prompt, parse_answer
from app.engines.model import ModelAnswerError, ModelTimeoutError, ReceiptModel


class CategorySuggester(Protocol):
    def suggest(self, names: Sequence[str], options: Sequence[str]) -> list[int | None]:
        """One option index (from 0) per name, None where there is no usable suggestion.

        Raises:
            ModelUnavailableError: the model cannot be used; the import run must stop.
        """
        ...


class ModelSuggester:
    def __init__(self, model: ReceiptModel) -> None:
        self._model = model

    def suggest(self, names: Sequence[str], options: Sequence[str]) -> list[int | None]:
        # A bad answer leaves the lines without category; it never fails the image (PC4).
        none: list[int | None] = [None] * len(names)
        try:
            raw = self._model.generate(
                category_prompt(options, names), answer_schema(len(options), len(names))
            )
        except (ModelTimeoutError, ModelAnswerError):
            return none
        return parse_answer(raw, len(options), len(names)) or none


class FakeSuggester:
    """Deterministic suggestions for tests and E2E runs (NFR-13); never calls the model.
    Every name gets the first option."""

    def suggest(self, names: Sequence[str], options: Sequence[str]) -> list[int | None]:
        return [0] * len(names)

from pathlib import Path
from typing import Any

import pytest

from app.categorization.factory import create_suggester
from app.categorization.prompt import answer_schema, category_prompt
from app.categorization.suggester import FakeSuggester, ModelSuggester
from app.engines.factory import create_engines
from app.engines.model import (
    ModelAnswerError,
    ModelCheckResult,
    ModelTimeoutError,
    ModelUnavailableError,
)
from app.settings import Settings

OPTIONS = ["Ruoka > Hedelmät", "Ruoka > Vihannekset", "Juomat"]
NAMES = ["Banaani", "Tomaatti"]


class ModelDouble:
    """Answers with a given text or raises a given error, and records each request."""

    def __init__(self, answer: str = "", error: Exception | None = None) -> None:
        self.answer = answer
        self.error = error
        self.requests: list[tuple[str, dict[str, Any]]] = []

    def check(self) -> ModelCheckResult:
        return "ok"

    def load(self) -> None:
        return None

    def generate(self, prompt: str, schema: dict[str, Any]) -> str:
        self.requests.append((prompt, schema))
        if self.error is not None:
            raise self.error
        return self.answer


def test_suggest_sends_one_request_with_the_prompt_and_schema() -> None:
    model = ModelDouble('{"c": [1, 2]}')

    assert ModelSuggester(model).suggest(NAMES, OPTIONS) == [0, 1]
    assert model.requests == [(category_prompt(OPTIONS, NAMES), answer_schema(3, 2))]


def test_ac7_invalid_answer_gives_no_suggestions() -> None:
    assert ModelSuggester(ModelDouble('{"c": [1]}')).suggest(NAMES, OPTIONS) == [None, None]


@pytest.mark.parametrize("error", [ModelTimeoutError("t"), ModelAnswerError("a")])
def test_ac9_timeout_or_error_status_gives_no_suggestions(error: Exception) -> None:
    assert ModelSuggester(ModelDouble(error=error)).suggest(NAMES, OPTIONS) == [None, None]


def test_ac10_unavailable_model_passes_through() -> None:
    model = ModelDouble(error=ModelUnavailableError("gone"))

    with pytest.raises(ModelUnavailableError):
        ModelSuggester(model).suggest(NAMES, OPTIONS)


def test_ac21_fake_suggests_the_first_option() -> None:
    assert FakeSuggester().suggest(["Banaani", "Tomaatti", "Limu"], OPTIONS) == [0, 0, 0]


def test_ac21_factory_chooses_the_fake_or_the_model(tmp_path: Path) -> None:
    fake = Settings(engines="fake", data_dir=tmp_path)
    real = Settings(engines="real", data_dir=tmp_path)

    assert isinstance(create_suggester(fake, create_engines(fake)), FakeSuggester)
    assert isinstance(create_suggester(real, create_engines(real)), ModelSuggester)

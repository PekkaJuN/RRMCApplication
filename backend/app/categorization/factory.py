"""Chooses the model suggester or the fake from the settings."""

from app.categorization.suggester import CategorySuggester, FakeSuggester, ModelSuggester
from app.engines.factory import Engines
from app.settings import Settings


def create_suggester(settings: Settings, engines: Engines) -> CategorySuggester:
    if settings.engines == "fake":
        return FakeSuggester()
    return ModelSuggester(engines.model)

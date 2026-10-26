"""Receipt model interface, the Ollama implementation and a fake for tests."""

from typing import Literal, Protocol

import httpx2
from pydantic import BaseModel, ValidationError

type ModelCheckResult = Literal["ok", "unavailable", "missing_model"]

# The health endpoint must answer within 3 seconds even when Ollama does not (AC14).
CHECK_TIMEOUT_SECONDS = 2.0
# Loading a large model from disk can take minutes on a slow computer.
LOAD_TIMEOUT_SECONDS = 300.0


class ModelLoadError(Exception):
    """Ollama did not load the model."""


class ReceiptModel(Protocol):
    def check(self) -> ModelCheckResult:
        """Tell whether the model can be used."""
        ...

    def load(self) -> None:
        """Ask the model server to load the model and keep it loaded.

        Raises:
            ModelLoadError: the model was not loaded.
        """
        ...


class _TagModel(BaseModel):
    name: str


class _Tags(BaseModel):
    models: list[_TagModel]


class OllamaReceiptModel:
    def __init__(self, base_url: str, model: str, client: httpx2.Client | None = None) -> None:
        self._model = model
        self._client = client or httpx2.Client(base_url=base_url)

    def check(self) -> ModelCheckResult:
        """`ok` when Ollama answers and has the model, `missing_model` when it lacks it."""
        try:
            response = self._client.get("/api/tags", timeout=CHECK_TIMEOUT_SECONDS)
            response.raise_for_status()
            tags = _Tags.model_validate_json(response.content)
        except (httpx2.HTTPError, ValidationError):
            return "unavailable"
        # Ollama lists a model pulled without a tag as `name:latest`.
        accepted = {self._model, f"{self._model}:latest"}
        return "ok" if any(tag.name in accepted for tag in tags.models) else "missing_model"

    def load(self) -> None:
        try:
            response = self._client.post(
                "/api/generate",
                # keep_alive -1 keeps the model in memory until Ollama stops.
                json={"model": self._model, "keep_alive": -1},
                timeout=LOAD_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except httpx2.HTTPError as error:
            raise ModelLoadError(f"Loading model {self._model} failed") from error


class FakeReceiptModel:
    """Deterministic model for tests and E2E runs; never calls Ollama."""

    def check(self) -> ModelCheckResult:
        return "ok"

    def load(self) -> None:
        return None

"""Receipt model interface, the Ollama implementation and a fake for tests."""

from typing import Any, Literal, Protocol

import httpx2
from pydantic import BaseModel, ValidationError

type ModelCheckResult = Literal["ok", "unavailable", "missing_model"]

# The health endpoint must answer within 3 seconds even when Ollama does not (AC14).
CHECK_TIMEOUT_SECONDS = 2.0
# Loading a large model from disk can take minutes on a slow computer.
LOAD_TIMEOUT_SECONDS = 300.0
# Above the 180 s target of NFR-8: the slowest receipt of the evaluation took 188 s (ADR 0003).
GENERATE_TIMEOUT_SECONDS = 300.0
# Ollama's default context can cut a long receipt's OCR text without an error.
CONTEXT_TOKENS = 8192
# Ollama sends a request for these models to its cloud service.
_CLOUD_SUFFIXES = ("-cloud", ":cloud")


class ModelLoadError(Exception):
    """Ollama did not load the model."""


class ModelUnavailableError(Exception):
    """Ollama cannot be reached or does not have the model; later requests would fail too."""


class ModelTimeoutError(Exception):
    """The model did not answer in time."""


class ModelAnswerError(Exception):
    """Ollama answered with an error or with a body that is not a generated answer."""


def is_cloud_model(model: str) -> bool:
    """True for a model Ollama would run in its cloud service (NFR-1)."""
    return model.lower().endswith(_CLOUD_SUFFIXES)


class LoadableModel(Protocol):
    """What health needs of the model: its availability and loading."""

    def check(self) -> ModelCheckResult:
        """Tell whether the model can be used."""
        ...

    def load(self) -> None:
        """Ask the model server to load the model and keep it loaded.

        Raises:
            ModelLoadError: the model was not loaded.
        """
        ...


class ReceiptModel(LoadableModel, Protocol):
    def generate(self, prompt: str, schema: dict[str, Any]) -> str:
        """The model's raw answer to `prompt`, constrained to the JSON `schema`.

        Raises:
            ModelUnavailableError: the model cannot be used now.
            ModelTimeoutError: no answer in time.
            ModelAnswerError: the answer is an error or not an answer.
        """
        ...


class _TagModel(BaseModel):
    name: str


class _Tags(BaseModel):
    models: list[_TagModel]


class _Generated(BaseModel):
    response: str


class OllamaReceiptModel:
    def __init__(
        self,
        base_url: str,
        model: str,
        client: httpx2.Client | None = None,
        transport: httpx2.BaseTransport | None = None,
    ) -> None:
        self._model = model
        # trust_env=False: proxy variables must never route OCR text to another host (NFR-1).
        self._client = client or httpx2.Client(
            base_url=base_url, transport=transport, trust_env=False
        )

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

    def generate(self, prompt: str, schema: dict[str, Any]) -> str:
        if is_cloud_model(self._model):
            raise ModelUnavailableError("Cloud models are not allowed")
        request: dict[str, Any] = {
            "model": self._model,
            "prompt": prompt,
            "format": schema,
            "stream": False,
            "options": {"temperature": 0, "num_ctx": CONTEXT_TOKENS},
            # -1 keeps the model loaded between receipts (FR-30).
            "keep_alive": -1,
        }
        # The messages name no prompt or answer: they are receipt content (NFR-3).
        try:
            # Without streaming Ollama sends nothing until it is done, so the read timeout is
            # the time of the whole answer.
            response = self._client.post(
                "/api/generate", json=request, timeout=GENERATE_TIMEOUT_SECONDS
            )
        except httpx2.ConnectTimeout:
            raise ModelUnavailableError("Ollama did not accept the connection") from None
        except httpx2.TimeoutException:
            raise ModelTimeoutError("The model did not answer in time") from None
        except httpx2.TransportError:
            raise ModelUnavailableError("Ollama cannot be reached") from None
        if response.status_code == 404:
            raise ModelUnavailableError(f"Ollama does not have model {self._model}")
        if response.is_error:
            raise ModelAnswerError(f"Ollama answered with status {response.status_code}")
        try:
            return _Generated.model_validate_json(response.content).response
        except ValidationError:
            raise ModelAnswerError("Ollama's answer has no generated text") from None


FAKE_ANSWER = (
    '{"s": "Testikauppa", "d": "2026-10-05", "t": 349, '
    '"l": [{"n": "Maito", "a": 125, "r": false}, {"n": "Limu", "a": 224, "r": false}]}'
)


class FakeReceiptModel:
    """Deterministic model for tests and E2E runs; never calls Ollama."""

    def check(self) -> ModelCheckResult:
        return "ok"

    def load(self) -> None:
        return None

    def generate(self, prompt: str, schema: dict[str, Any]) -> str:
        return FAKE_ANSWER

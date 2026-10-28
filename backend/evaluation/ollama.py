"""Calls to the local Ollama: model check, warm-up and reading (PC4, AC10, AC12, AC19)."""

import base64
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

import httpx2
from pydantic import BaseModel, ValidationError

from evaluation.prompt import ANSWER_SCHEMA

type ReadError = Literal["timeout", "model_error"]

CHECK_TIMEOUT_SECONDS = 10.0
# Loading a model and reading one receipt on the CPU each take minutes.
READ_TIMEOUT_SECONDS = 600.0
# Ollama's default context can cut a long receipt's OCR text without an error.
CONTEXT_TOKENS = 8192
KEEP_ALIVE = "10m"
# Ollama's counts and durations (nanoseconds) explain slow receipts in the detail files.
_STAT_KEYS = (
    "prompt_eval_count",
    "eval_count",
    "total_duration",
    "load_duration",
    "prompt_eval_duration",
    "eval_duration",
)


@dataclass(frozen=True)
class ReadResult:
    text: str | None
    error: ReadError | None = None
    stats: dict[str, int] = field(default_factory=dict[str, int])


class Reader(Protocol):
    def check(self, models: Sequence[str]) -> list[str]:
        """Messages for every problem that stops the run; empty when all models can run."""
        ...

    def warm_up(self, model: str) -> None:
        """Load the model before the timed reads."""
        ...

    def read(self, model: str, prompt: str, image: bytes | None) -> ReadResult:
        """The model's raw answer, or the error that prevented it."""
        ...


class _TagModel(BaseModel):
    name: str


class _Tags(BaseModel):
    models: list[_TagModel]


class _Generated(BaseModel):
    response: str


class OllamaReader:
    def __init__(
        self,
        base_url: str,
        client: httpx2.Client | None = None,
        transport: httpx2.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        # trust_env=False: proxy variables must never route prompts or images to another
        # host (AC19).
        self._client = client or httpx2.Client(
            base_url=self.base_url, transport=transport, trust_env=False
        )

    def check(self, models: Sequence[str]) -> list[str]:
        try:
            response = self._client.get("/api/tags", timeout=CHECK_TIMEOUT_SECONDS)
            response.raise_for_status()
            tags = _Tags.model_validate_json(response.content)
        except (httpx2.HTTPError, ValidationError):
            return [f"Ollama is not reachable at {self.base_url}"]
        pulled = {tag.name for tag in tags.models}
        # Ollama lists a model pulled without a tag as `name:latest`.
        missing = [m for m in models if m not in pulled and f"{m}:latest" not in pulled]
        return [f"Model {m} is not pulled. Run: ollama pull {m}" for m in dict.fromkeys(missing)]

    def warm_up(self, model: str) -> None:
        try:
            self._client.post(
                "/api/generate",
                json={"model": model, "keep_alive": KEEP_ALIVE},
                timeout=READ_TIMEOUT_SECONDS,
            )
        except httpx2.HTTPError:
            # A model that does not load fails its reads, which record the error.
            return

    def read(self, model: str, prompt: str, image: bytes | None) -> ReadResult:
        request: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "format": ANSWER_SCHEMA,
            "stream": False,
            "options": {"temperature": 0, "num_ctx": CONTEXT_TOKENS},
            "keep_alive": KEEP_ALIVE,
        }
        if image is not None:
            request["images"] = [base64.b64encode(image).decode("ascii")]
        try:
            response = self._client.post(
                "/api/generate", json=request, timeout=READ_TIMEOUT_SECONDS
            )
            response.raise_for_status()
            generated = _Generated.model_validate_json(response.content)
            raw: dict[str, Any] = response.json()
        except httpx2.TimeoutException:
            return ReadResult(text=None, error="timeout")
        except (httpx2.HTTPError, ValidationError):
            return ReadResult(text=None, error="model_error")
        stats = {key: raw[key] for key in _STAT_KEYS if isinstance(raw.get(key), int)}
        return ReadResult(text=generated.response, stats=stats)

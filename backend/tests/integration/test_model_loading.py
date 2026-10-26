import json
import threading

import httpx2
import pytest
from fastapi.testclient import TestClient

from app.engines.factory import Engines
from app.engines.model import OllamaReceiptModel
from app.engines.ocr import FakeOcrEngine
from app.main import create_app
from app.settings import Settings

OLLAMA_URL = "http://ollama.test:11434"


class MockOllama:
    """Answers /api/tags with the model while `is_up`, and counts load requests."""

    def __init__(self, is_up: bool) -> None:
        self.is_up = is_up
        self.load_requests: list[dict[str, object]] = []
        self.loaded = threading.Event()

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        if not self.is_up:
            raise httpx2.ConnectError("Connection refused", request=request)
        if request.url.path == "/api/tags":
            return httpx2.Response(200, json={"models": [{"name": "qwen2.5:7b"}]})
        self.load_requests.append(json.loads(request.content))
        self.loaded.set()
        return httpx2.Response(200, json={"done": True})

    def engines(self) -> Engines:
        client = httpx2.Client(base_url=OLLAMA_URL, transport=httpx2.MockTransport(self.handle))
        return Engines(
            ocr=FakeOcrEngine(),
            model=OllamaReceiptModel(OLLAMA_URL, "qwen2.5:7b", client=client),
        )


@pytest.fixture
def real_settings(settings: Settings) -> Settings:
    return settings.model_copy(update={"engines": "real"})


def test_ac17_model_is_loaded_at_start(real_settings: Settings) -> None:
    # Given Ollama has the model
    ollama = MockOllama(is_up=True)

    # When the backend starts and the health is checked
    with TestClient(create_app(real_settings, engines=ollama.engines())) as client:
        client.get("/api/health")
        # Loading runs in the background; wait for its request instead of sleeping.
        assert ollama.loaded.wait(timeout=5)

    # Then exactly one load request that keeps the model loaded was sent
    assert ollama.load_requests == [{"model": "qwen2.5:7b", "keep_alive": -1}]


def test_ac18_model_is_loaded_when_ollama_starts_later(real_settings: Settings) -> None:
    # Given Ollama is not reachable when the backend starts
    ollama = MockOllama(is_up=False)
    with TestClient(create_app(real_settings, engines=ollama.engines())) as client:
        assert ollama.load_requests == []

        # When Ollama becomes reachable and the health is checked twice
        ollama.is_up = True
        first = client.get("/api/health")
        assert ollama.loaded.wait(timeout=5)
        client.get("/api/health")

    # Then the first answer has the model ok and only one load request was sent
    assert first.json()["checks"]["model"] == "ok"
    assert len(ollama.load_requests) == 1

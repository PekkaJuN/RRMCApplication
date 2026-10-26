import json
import socket
import time
from collections.abc import Callable, Iterator

import httpx2
import pytest

from app.engines.model import FakeReceiptModel, ModelLoadError, OllamaReceiptModel

BASE_URL = "http://ollama.test:11434"
TAGS = {"models": [{"name": "qwen2.5:7b"}, {"name": "llama3:latest"}]}

type Handler = Callable[[httpx2.Request], httpx2.Response]


def ollama(handler: Handler, model: str = "qwen2.5:7b") -> OllamaReceiptModel:
    client = httpx2.Client(base_url=BASE_URL, transport=httpx2.MockTransport(handler))
    return OllamaReceiptModel(BASE_URL, model, client=client)


def answer_tags(request: httpx2.Request) -> httpx2.Response:
    assert (request.method, request.url.path) == ("GET", "/api/tags")
    return httpx2.Response(200, json=TAGS)


def refuse(request: httpx2.Request) -> httpx2.Response:
    raise httpx2.ConnectError("Connection refused", request=request)


@pytest.mark.parametrize(
    ("model", "expected"),
    [("qwen2.5:7b", "ok"), ("llama3", "ok"), ("llama3:latest", "ok"), ("mistral", "missing_model")],
)
def test_ac15_model_name_matching(model: str, expected: str) -> None:
    assert ollama(answer_tags, model).check() == expected


def test_ac14_refused_connection_is_unavailable() -> None:
    assert ollama(refuse).check() == "unavailable"


@pytest.mark.parametrize(
    "response",
    [httpx2.Response(500), httpx2.Response(200, text="not json"), httpx2.Response(200, json={})],
    ids=["server error", "not json", "no model list"],
)
def test_ac14_unexpected_answer_is_unavailable(response: httpx2.Response) -> None:
    assert ollama(lambda request: response).check() == "unavailable"


@pytest.fixture
def silent_server() -> Iterator[str]:
    """A local port that accepts connections but never answers."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        yield f"http://127.0.0.1:{server.getsockname()[1]}"


def test_ac14_no_answer_is_unavailable_within_3_seconds(silent_server: str) -> None:
    # Given an Ollama address that does not answer
    model = OllamaReceiptModel(silent_server, "qwen2.5:7b")

    # When the model is checked
    started = time.monotonic()
    result = model.check()

    # Then it is unavailable, and the answer comes within 3 seconds
    assert result == "unavailable"
    assert time.monotonic() - started < 3


def test_ac17_load_asks_ollama_to_keep_the_model_loaded() -> None:
    requests: list[httpx2.Request] = []

    def answer_generate(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(200, json={"done": True})

    ollama(answer_generate).load()

    assert len(requests) == 1
    assert (requests[0].method, requests[0].url.path) == ("POST", "/api/generate")
    assert json.loads(requests[0].content) == {"model": "qwen2.5:7b", "keep_alive": -1}


def model_not_found(request: httpx2.Request) -> httpx2.Response:
    return httpx2.Response(404, json={"error": "model not found"})


@pytest.mark.parametrize("handler", [refuse, model_not_found])
def test_ac18_failed_load_raises(handler: Handler) -> None:
    with pytest.raises(ModelLoadError):
        ollama(handler).load()


def test_ac12_fake_model_is_ok_without_http(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_http(*args: object, **kwargs: object) -> None:
        raise AssertionError("the fake must not make HTTP requests")

    monkeypatch.setattr(httpx2.Client, "send", no_http)

    model = FakeReceiptModel()
    model.load()
    assert model.check() == "ok"

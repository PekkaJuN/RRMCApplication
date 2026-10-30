import json
import socket
import time
from collections.abc import Callable, Iterator

import httpx2
import pytest

from app.engines.model import (
    FakeReceiptModel,
    ModelAnswerError,
    ModelLoadError,
    ModelTimeoutError,
    ModelUnavailableError,
    OllamaReceiptModel,
    is_cloud_model,
)

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


SCHEMA = {"type": "object"}


class Recorder:
    """Records each request and answers it with `answer`, or raises it."""

    def __init__(self, answer: httpx2.Response | Exception | None = None) -> None:
        self.answer = (
            answer if answer is not None else httpx2.Response(200, json={"response": "{}"})
        )
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def test_ac7_generate_sends_the_reading_request() -> None:
    # Given the model `m`
    recorder = Recorder(httpx2.Response(200, json={"response": '{"s": "x"}', "done": True}))

    # When a prompt is sent
    raw = ollama(recorder, "m").generate("PROMPT", SCHEMA)

    # Then one generate request carries the prompt, the schema and the reading options
    assert raw == '{"s": "x"}'
    assert len(recorder.requests) == 1
    request = recorder.requests[0]
    assert (request.method, str(request.url)) == ("POST", f"{BASE_URL}/api/generate")
    assert json.loads(request.content) == {
        "model": "m",
        "prompt": "PROMPT",
        "format": SCHEMA,
        "stream": False,
        "options": {"temperature": 0, "num_ctx": 8192},
        "keep_alive": -1,
    }


@pytest.mark.parametrize(
    "error",
    [httpx2.ReadTimeout("slow"), httpx2.WriteTimeout("slow"), httpx2.PoolTimeout("slow")],
    ids=["read", "write", "pool"],
)
def test_ac11b_timeout_is_model_timeout(error: Exception) -> None:
    with pytest.raises(ModelTimeoutError):
        ollama(Recorder(error)).generate("PROMPT", SCHEMA)


@pytest.mark.parametrize(
    "answer",
    [
        httpx2.ConnectError("Connection refused"),
        httpx2.ConnectTimeout("no answer"),
        httpx2.RemoteProtocolError("closed"),
        httpx2.Response(404, json={"error": "model 'm' not found"}),
    ],
    ids=["refused", "connect timeout", "connection lost", "model not pulled"],
)
def test_ac20_lost_connection_or_missing_model_is_model_unavailable(
    answer: httpx2.Response | Exception,
) -> None:
    with pytest.raises(ModelUnavailableError):
        ollama(Recorder(answer)).generate("PROMPT", SCHEMA)


@pytest.mark.parametrize(
    "response",
    [httpx2.Response(500), httpx2.Response(200, text="not json"), httpx2.Response(200, json={})],
    ids=["server error", "not json", "no response field"],
)
def test_http_500_or_bad_body_is_model_answer_error(response: httpx2.Response) -> None:
    with pytest.raises(ModelAnswerError):
        ollama(Recorder(response)).generate("PROMPT", SCHEMA)


@pytest.mark.parametrize("model", ["qwen3:cloud", "gpt-oss:120b-cloud", "X:CLOUD"])
def test_ac21_cloud_model_is_refused_without_a_request(model: str) -> None:
    recorder = Recorder()

    assert is_cloud_model(model)
    with pytest.raises(ModelUnavailableError):
        ollama(recorder, model).generate("PROMPT", SCHEMA)
    assert recorder.requests == []


def test_local_model_is_not_a_cloud_model() -> None:
    assert not is_cloud_model("qwen3:30b-a3b-instruct-2507-q4_K_M")


def test_ac23_proxy_settings_are_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given proxy variables that point to another host
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "all_proxy"):
        monkeypatch.setenv(name, "http://proxy.invalid:3128")
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)

    # When the model builds its own client
    model = OllamaReceiptModel(BASE_URL, "m")

    # Then the client does not read them. A mock transport cannot show this: httpx2 sends to
    # a given transport even with trust_env=True, so the client's setting is checked.
    client = model._client  # pyright: ignore[reportPrivateUsage]
    assert client.trust_env is False
    assert str(client.base_url) == f"{BASE_URL}"


def test_fake_model_answers_without_http() -> None:
    assert FakeReceiptModel().generate("PROMPT", SCHEMA) == FakeReceiptModel().generate("", {})

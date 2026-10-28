import base64
import json
from collections.abc import Callable

import httpx2
import pytest

from evaluation.ollama import READ_TIMEOUT_SECONDS, OllamaReader
from evaluation.prompt import ANSWER_SCHEMA

BASE_URL = "http://host.docker.internal:11434"
TAGS = {"models": [{"name": "qwen2.5:7b"}, {"name": "llava:latest"}]}

type Handler = Callable[[httpx2.Request], httpx2.Response]


class Recorder:
    """Answers like Ollama and records every request."""

    def __init__(self, answer: Handler | None = None) -> None:
        self.requests: list[httpx2.Request] = []
        self._answer = answer

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        if self._answer is not None:
            return self._answer(request)
        if request.url.path == "/api/tags":
            return httpx2.Response(200, json=TAGS)
        return httpx2.Response(
            200,
            json={
                "response": '{"s": "X"}',
                "prompt_eval_count": 143,
                "eval_count": 30,
                "total_duration": 5_000_000_000,
                "load_duration": 1_000_000,
                "done": True,
            },
        )


def refuse(request: httpx2.Request) -> httpx2.Response:
    raise httpx2.ConnectError("refused", request=request)


def server_error(request: httpx2.Request) -> httpx2.Response:
    return httpx2.Response(500)


def not_json(request: httpx2.Request) -> httpx2.Response:
    return httpx2.Response(200, content=b"not json")


def reader(handler: Handler) -> OllamaReader:
    client = httpx2.Client(base_url=BASE_URL, transport=httpx2.MockTransport(handler))
    return OllamaReader(BASE_URL, client=client)


def body(request: httpx2.Request) -> dict[str, object]:
    return json.loads(request.content)


def test_ac5_text_request_asks_for_the_schema_at_temperature_zero() -> None:
    recorder = Recorder()

    result = reader(recorder).read("qwen2.5:7b", "PROMPT", image=None)

    assert result.text == '{"s": "X"}'
    assert result.error is None
    [request] = recorder.requests
    assert (request.method, request.url.path) == ("POST", "/api/generate")
    sent = body(request)
    assert sent["model"] == "qwen2.5:7b"
    assert sent["prompt"] == "PROMPT"
    assert sent["format"] == ANSWER_SCHEMA
    assert sent["stream"] is False
    assert sent["options"] == {"temperature": 0, "num_ctx": 8192}
    assert "images" not in sent


def test_ac6_image_request_sends_the_image_as_base64() -> None:
    recorder = Recorder()

    reader(recorder).read("qwen2.5vl:7b", "PROMPT", image=b"\xff\xd8image")

    sent = body(recorder.requests[0])
    assert sent["images"] == [base64.b64encode(b"\xff\xd8image").decode("ascii")]
    assert sent["format"] == ANSWER_SCHEMA
    assert sent["options"] == {"temperature": 0, "num_ctx": 8192}


def test_ac5_read_keeps_ollama_counts_for_the_details() -> None:
    result = reader(Recorder()).read("qwen2.5:7b", "PROMPT", image=None)

    assert result.stats == {
        "prompt_eval_count": 143,
        "eval_count": 30,
        "total_duration": 5_000_000_000,
        "load_duration": 1_000_000,
    }


def test_ac12_read_waits_600_seconds() -> None:
    assert READ_TIMEOUT_SECONDS == 600.0


def test_ac12_timeout_is_recorded() -> None:
    def slow(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadTimeout("timed out", request=request)

    result = reader(slow).read("qwen2.5:7b", "PROMPT", image=None)

    assert (result.text, result.error) == (None, "timeout")


@pytest.mark.parametrize(
    "response",
    [
        httpx2.Response(500, json={"error": "boom"}),
        httpx2.Response(200, content=b"not json"),
        httpx2.Response(200, json={"done": True}),
    ],
)
def test_ac12_failed_call_is_a_model_error(response: httpx2.Response) -> None:
    result = reader(lambda _: response).read("qwen2.5:7b", "PROMPT", image=None)

    assert (result.text, result.error) == (None, "model_error")


def test_ac12_refused_connection_is_a_model_error() -> None:
    assert reader(refuse).read("m", "PROMPT", image=None).error == "model_error"


def test_ac10_pulled_models_pass_the_check() -> None:
    assert reader(Recorder()).check(["qwen2.5:7b", "llava"]) == []


def test_ac10_missing_model_is_named_once() -> None:
    problems = reader(Recorder()).check(["qwen2.5:14b", "qwen2.5:7b", "qwen2.5:14b"])

    assert problems == ["Model qwen2.5:14b is not pulled. Run: ollama pull qwen2.5:14b"]


@pytest.mark.parametrize("answer", [refuse, server_error, not_json])
def test_ac10_unreachable_ollama_is_reported(answer: Handler) -> None:
    problems = reader(Recorder(answer)).check(["qwen2.5:7b"])

    assert problems == [f"Ollama is not reachable at {BASE_URL}"]


def test_ac5_warm_up_loads_the_model_without_a_prompt() -> None:
    recorder = Recorder()

    reader(recorder).warm_up("qwen2.5:7b")

    [request] = recorder.requests
    assert request.url.path == "/api/generate"
    assert body(request) == {"model": "qwen2.5:7b", "keep_alive": "10m"}


def test_ac5_failed_warm_up_is_left_to_the_reads() -> None:
    reader(Recorder(server_error)).warm_up("qwen2.5:7b")


def test_ac19_every_request_goes_to_the_configured_url() -> None:
    recorder = Recorder()
    ollama = reader(recorder)

    ollama.check(["qwen2.5:7b"])
    ollama.warm_up("qwen2.5:7b")
    ollama.read("qwen2.5:7b", "PROMPT", image=b"image")

    assert len(recorder.requests) == 3
    assert {str(r.url.copy_with(path="/")) for r in recorder.requests} == {f"{BASE_URL}/"}


def test_ac19_reader_builds_its_client_on_the_given_url() -> None:
    ollama = OllamaReader(BASE_URL + "/")

    assert ollama.base_url == BASE_URL


def test_ac19_proxy_settings_are_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "all_proxy"):
        monkeypatch.setenv(name, "http://proxy.invalid:3128")
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.delenv("no_proxy", raising=False)
    recorder = Recorder()

    OllamaReader(BASE_URL, transport=httpx2.MockTransport(recorder)).check(["qwen2.5:7b"])

    assert [str(r.url) for r in recorder.requests] == [f"{BASE_URL}/api/tags"]

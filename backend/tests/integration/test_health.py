import time

import httpx2
import pytest
from fastapi.testclient import TestClient

from app.engines.factory import Engines
from app.engines.model import OllamaReceiptModel
from app.engines.ocr import FakeOcrEngine
from app.main import create_app
from app.settings import Settings
from app.storage.migrate import migrate_database

OLLAMA_URL = "http://ollama.test:11434"


def make_folders(settings: Settings) -> None:
    for folder in (settings.import_dir, settings.done_dir, settings.failed_dir):
        folder.mkdir(parents=True)


@pytest.fixture
def ready_settings(settings: Settings) -> Settings:
    """Settings whose three folders and database exist."""
    make_folders(settings)
    migrate_database(settings.db_path)
    return settings


def ollama_engines(transport: httpx2.MockTransport) -> Engines:
    client = httpx2.Client(base_url=OLLAMA_URL, transport=transport)
    return Engines(
        ocr=FakeOcrEngine(), model=OllamaReceiptModel(OLLAMA_URL, "qwen2.5:7b", client=client)
    )


def refuse(request: httpx2.Request) -> httpx2.Response:
    raise httpx2.ConnectError("Connection refused", request=request)


def other_models(request: httpx2.Request) -> httpx2.Response:
    return httpx2.Response(200, json={"models": [{"name": "llama3:latest"}]})


def test_ac12_health_with_fakes(ready_settings: Settings) -> None:
    client = TestClient(create_app(ready_settings))

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "model_name": "qwen3:30b-a3b-instruct-2507-q4_K_M",
        "checks": {"database": "ok", "folders": "ok", "ocr": "ok", "model": "ok"},
    }


def test_ac14_ollama_down_is_degraded_within_3_seconds(ready_settings: Settings) -> None:
    app = create_app(ready_settings, engines=ollama_engines(httpx2.MockTransport(refuse)))

    started = time.monotonic()
    response = TestClient(app).get("/api/health")

    assert time.monotonic() - started < 3
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["checks"]["model"] == "unavailable"


def test_ac15_model_not_pulled_is_missing_model(ready_settings: Settings) -> None:
    app = create_app(ready_settings, engines=ollama_engines(httpx2.MockTransport(other_models)))

    response = TestClient(app).get("/api/health")

    assert response.json()["status"] == "degraded"
    assert response.json()["checks"]["model"] == "missing_model"


def test_ac16_missing_folder_is_degraded(ready_settings: Settings) -> None:
    ready_settings.failed_dir.rmdir()

    response = TestClient(create_app(ready_settings)).get("/api/health")

    assert response.json()["status"] == "degraded"
    assert response.json()["checks"]["folders"] == "unavailable"


def test_ac12_missing_database_is_degraded(settings: Settings) -> None:
    make_folders(settings)

    response = TestClient(create_app(settings)).get("/api/health")

    assert response.json()["checks"]["database"] == "unavailable"

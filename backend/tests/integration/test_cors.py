from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.settings import Settings
from tests.integration.conftest import make_client

PATH = "/api/health"


def test_ac3_ui_origin_is_allowed(client: TestClient) -> None:
    response = client.get(PATH, headers={"Origin": "http://127.0.0.1:5173"})

    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == "http://127.0.0.1:5173"


def test_ac3_other_origin_is_refused(client: TestClient) -> None:
    response = client.get(PATH, headers={"Origin": "http://example.com"})

    assert response.status_code == 200
    assert "Access-Control-Allow-Origin" not in response.headers


def test_ac3_allowed_origin_follows_ui_port(clean_env: pytest.MonkeyPatch, tmp_path: Path) -> None:
    client = make_client(Settings(engines="fake", data_dir=tmp_path, ui_port=5200))

    response = client.get(PATH, headers={"Origin": "http://127.0.0.1:5200"})

    assert response.headers["Access-Control-Allow-Origin"] == "http://127.0.0.1:5200"

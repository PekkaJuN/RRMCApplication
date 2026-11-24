"""The built UI served by the backend (specs/features/app-container.md, PC2 and PC4)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings

BASE_URL = "http://127.0.0.1"
INDEX = '<!doctype html><div id="root"></div>'
SCRIPT = "console.log('synthetic');"
OUTSIDE = "synthetic file outside the static folder"


@pytest.fixture
def settings(clean_env: pytest.MonkeyPatch, tmp_path: Path) -> Settings:
    return Settings(engines="fake", data_dir=tmp_path / "data")


@pytest.fixture
def static_dir(tmp_path: Path) -> Path:
    folder = tmp_path / "static"
    (folder / "assets").mkdir(parents=True)
    (folder / "index.html").write_text(INDEX)
    (folder / "assets" / "a.js").write_text(SCRIPT)
    (tmp_path / "secret.txt").write_text(OUTSIDE)
    return folder


@pytest.fixture
def ui(settings: Settings, static_dir: Path) -> Iterator[TestClient]:
    settings.data_dir.mkdir()
    with TestClient(create_app(settings, static_dir=static_dir), base_url=BASE_URL) as client:
        yield client


def test_ac14_no_static_folder_answers_404(settings: Settings, tmp_path: Path) -> None:
    app = create_app(settings, static_dir=tmp_path / "missing")

    response = TestClient(app, base_url=BASE_URL).get("/")

    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


def test_ac14_the_default_folder_does_not_exist_in_development(settings: Settings) -> None:
    response = TestClient(create_app(settings), base_url=BASE_URL).get("/")

    assert response.status_code == 404


@pytest.mark.parametrize("path", ["/", "/tuonti", "/kuitit/12", "/arkisto/2025", "/apina"])
def test_ac4_client_paths_answer_index_html(ui: TestClient, path: str) -> None:
    response = ui.get(path)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.text == INDEX


def test_ac5_a_file_of_the_ui_is_served(ui: TestClient) -> None:
    response = ui.get("/assets/a.js")

    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]
    assert response.text == SCRIPT


@pytest.mark.parametrize("path", ["/", "/index.html", "/kuitit/12"])
def test_ac35_index_html_is_checked_before_reuse(ui: TestClient, path: str) -> None:
    response = ui.get(path)

    assert response.status_code == 200
    assert response.headers.get("cache-control") == "no-cache"


def test_ac35_other_files_have_no_cache_header(ui: TestClient) -> None:
    assert "cache-control" not in ui.get("/assets/a.js").headers


@pytest.mark.parametrize("path", ["/api", "/api/", "/api/does-not-exist"])
def test_ac6_unknown_api_path_is_a_json_404(ui: TestClient, path: str) -> None:
    response = ui.get(path)

    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


def test_ac15_health_answers_its_own_handler(ui: TestClient) -> None:
    response = ui.get("/api/health")

    assert response.status_code == 200
    assert response.json()["checks"]["ocr"] == "ok"


def test_ac15_no_api_route_answers_the_ui(
    ui: TestClient, settings: Settings, static_dir: Path
) -> None:
    paths = create_app(settings, static_dir=static_dir).openapi()["paths"]
    get_paths = [path for path, methods in paths.items() if "get" in methods]

    assert "/api/health" in get_paths
    assert all(path.startswith("/api/") for path in get_paths)
    for path in get_paths:
        response = ui.get(path.replace("{", "").replace("}", ""))
        assert response.text != INDEX, path


@pytest.mark.parametrize(
    "path",
    ["/..%2Fsecret.txt", "/%2e%2e/secret.txt", "/assets/..%2F..%2Fsecret.txt", "/%2Fetc/passwd"]
    + ["/%00", "/" + "a" * 300],
)
def test_ac4_a_path_outside_the_folder_is_not_served(ui: TestClient, path: str) -> None:
    response = ui.get(path)

    assert response.status_code in (200, 404)
    assert OUTSIDE not in response.text
    if response.status_code == 200:
        assert response.text == INDEX

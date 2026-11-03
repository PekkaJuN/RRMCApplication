"""The failed images list and preview (receipt-management spec, T13)."""

import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.settings import Settings
from tests.receipt_import_data import jpeg, png


def fill_folder_f(settings: Settings) -> Path:
    """Folder F of the spec, and `a.jpg` in the done folder; synthetic images only."""
    failed, done = settings.failed_dir, settings.done_dir
    failed.mkdir(exist_ok=True)
    done.mkdir(exist_ok=True)
    (failed / "b.png").write_bytes(png("b"))
    (failed / "IMG_2.jpg").write_bytes(jpeg("img2"))
    (failed / "notes.txt").write_bytes(b"notes")
    (failed / "fake.jpg").write_bytes(b"not an image")
    (failed / "sub").mkdir()
    (done / "a.jpg").write_bytes(jpeg("a"))
    return failed


def test_ac16_failed_images_list(api: TestClient, settings: Settings) -> None:
    fill_folder_f(settings)

    response = api.get("/api/failed-images")

    assert response.status_code == 200
    assert response.json() == {"file_names": ["b.png", "fake.jpg", "IMG_2.jpg"]}


def test_ac17_empty_then_missing_failed_folder(api: TestClient, settings: Settings) -> None:
    settings.failed_dir.mkdir()
    empty = api.get("/api/failed-images")
    settings.failed_dir.rmdir()
    missing = api.get("/api/failed-images")

    assert (empty.status_code, empty.json()) == (200, {"file_names": []})
    assert missing.status_code == 503
    assert missing.json()["error"] == "folders_unavailable"


def test_ac18_failed_image_preview(
    api: TestClient, settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    fill_folder_f(settings)
    caplog.set_level(logging.INFO)

    response = api.get("/api/failed-images/image?name=b.png")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "no-store"
    assert response.content == png("b")
    # Only the app's own log; the test client logs the whole URL itself.
    logged = "\n".join(
        record.getMessage() for record in caplog.records if record.name.startswith("app")
    )
    assert "/api/failed-images/image" in logged
    assert "b.png" not in logged


@pytest.mark.parametrize(
    "name", ["fake.jpg", "notes.txt", "missing.png", "../import_done/a.jpg", "sub", "a\x00.jpg"]
)
def test_ac19_preview_refused(api: TestClient, settings: Settings, name: str) -> None:
    fill_folder_f(settings)

    response = api.get("/api/failed-images/image", params={"name": name})

    assert response.status_code == 404
    assert response.json() == {
        "error": "image_not_found",
        "message": "Kuvaa ei löydy epäonnistuneiden kansiosta.",
    }


def test_ac19_preview_without_a_name(api: TestClient, settings: Settings) -> None:
    fill_folder_f(settings)

    response = api.get("/api/failed-images/image")

    assert response.status_code == 422
    assert response.json()["error"] == "invalid_request"

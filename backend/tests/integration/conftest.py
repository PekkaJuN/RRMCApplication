from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.receipt_import.service import ImportService
from app.settings import Settings
from tests.integration import endpoints_for_tests


@pytest.fixture
def settings(clean_env: pytest.MonkeyPatch, tmp_path: Path) -> Settings:
    """Default settings with fake engines and every folder under a temporary data folder."""
    return Settings(engines="fake", data_dir=tmp_path)


def make_client(settings: Settings, import_service: ImportService | None = None) -> TestClient:
    app = create_app(
        settings, extra_routers=[endpoints_for_tests.router], import_service=import_service
    )
    # Unexpected errors must become a 500 response, as they do for a real client.
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def client(settings: Settings) -> TestClient:
    return make_client(settings)


@pytest.fixture
def api(settings: Settings) -> Iterator[TestClient]:
    """A client whose app has run its startup: migrations and the default list."""
    with make_client(settings) as client:
        yield client

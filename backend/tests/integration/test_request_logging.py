import re
from pathlib import Path

import pytest

from app.settings import Settings
from tests.integration.conftest import make_client

REQUEST_LOGGER = "app.requests"


def request_lines(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [record.getMessage() for record in caplog.records if record.name == REQUEST_LOGGER]


def test_ac22_request_is_logged_at_info(
    settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    # Given RRMC_LOG_LEVEL=INFO
    client = make_client(settings)

    # When a request with a query string is made
    client.get("/api/health?name=SECRET-LINE-123")

    # Then one line has the method, the path without query, the status and the duration
    lines = request_lines(caplog)
    assert len(lines) == 1
    assert re.fullmatch(r"GET /api/health 200 \d+ms", lines[0])


def test_ac22_no_request_line_at_warning(
    clean_env: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # Given RRMC_LOG_LEVEL=WARNING
    client = make_client(Settings(engines="fake", data_dir=tmp_path, log_level="WARNING"))

    # When a request is made
    client.get("/api/health")

    # Then no request line is written
    assert request_lines(caplog) == []


def test_ac22_failed_request_is_logged_with_status_500(
    settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    client = make_client(settings)

    client.post("/api/test/fail", json={"text": "x"})

    lines = request_lines(caplog)
    assert len(lines) == 1
    assert re.fullmatch(r"POST /api/test/fail 500 \d+ms", lines[0])

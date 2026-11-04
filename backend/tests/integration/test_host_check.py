import pytest
from fastapi.testclient import TestClient

INVALID_HOST = {"error": "invalid_host", "message": "Pyyntö hylättiin: tuntematon osoite."}


@pytest.mark.parametrize(
    "host",
    ["evil.example", "evil.example:8000", "127.0.0.1.evil.example", "backend.evil.example", ""],
)
def test_unknown_host_is_refused(api: TestClient, host: str) -> None:
    # A page that rebinds its own name to 127.0.0.1 sends that name as the Host header.
    response = api.get("/api/categories", headers={"Host": host})

    assert response.status_code == 400
    assert response.json() == INVALID_HOST


@pytest.mark.parametrize(
    "host",
    ["127.0.0.1", "127.0.0.1:8000", "localhost:5173", "LOCALHOST:5173", "backend:8000"]
    + ["backend-e2e:8000"],
)
def test_known_host_is_served(api: TestClient, host: str) -> None:
    response = api.get("/api/categories", headers={"Host": host})

    assert response.status_code == 200

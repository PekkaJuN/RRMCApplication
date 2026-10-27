import logging

import pytest
from fastapi.testclient import TestClient

INVALID_REQUEST = {"error": "invalid_request", "message": "Pyyntö on virheellinen."}


def test_ac19_unknown_path_is_not_found(client: TestClient) -> None:
    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.json() == {"error": "not_found", "message": "Pyydettyä kohdetta ei löydy."}


def test_ac20_invalid_field_is_invalid_request(client: TestClient) -> None:
    response = client.post("/api/test/value", json={"value": "abc"})

    assert response.status_code == 422
    assert response.json() == INVALID_REQUEST


def test_ac20_body_that_is_not_json_is_invalid_request(client: TestClient) -> None:
    response = client.post(
        "/api/test/value", content=b"not json", headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 422
    assert response.json() == INVALID_REQUEST


def test_ac21_unexpected_error_hides_request_content(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    # Given an endpoint that fails after reading a body with a marker
    caplog.set_level(logging.INFO)

    # When it is called
    response = client.post("/api/test/fail", json={"text": "SECRET-LINE-123"})

    # Then the response is the generic error, the log has the stack trace, and the marker
    # appears in neither
    assert response.status_code == 500
    assert response.json() == {
        "error": "internal_error",
        "message": "Odottamaton virhe. Katso lisätiedot palvelimen lokista.",
    }
    assert "Traceback" in caplog.text
    assert "RuntimeError: Test endpoint failure" in caplog.text
    assert "SECRET-LINE-123" not in response.text
    assert "SECRET-LINE-123" not in caplog.text


def test_pc8_app_error_uses_the_error_format(client: TestClient) -> None:
    response = client.get("/api/test/app-error")

    assert response.status_code == 409
    assert response.json() == {"error": "test_conflict", "message": "Testiristiriita."}


def test_ac13_app_error_extra_fields_are_added_to_the_body(client: TestClient) -> None:
    response = client.get("/api/test/app-error-extra")

    assert response.status_code == 409
    assert response.json() == {
        "error": "test_in_use",
        "message": "Testi käytössä.",
        "product_count": 3,
    }

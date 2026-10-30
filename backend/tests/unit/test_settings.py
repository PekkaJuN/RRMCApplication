from pathlib import Path

import pytest
from pydantic import HttpUrl

from app.settings import SettingsError, load_settings


def test_ac6_defaults(clean_env: pytest.MonkeyPatch) -> None:
    # Given an environment without RRMC_* settings
    # When the settings are loaded
    settings = load_settings()

    # Then every value is the PC3 default
    assert settings.engines == "real"
    assert settings.ollama_url == HttpUrl("http://host.docker.internal:11434")
    assert settings.model == "qwen3:30b-a3b-instruct-2507-q4_K_M"
    assert settings.log_level == "INFO"
    assert settings.ui_port == 5173
    assert settings.import_dir == Path("/data/import")
    assert settings.done_dir == Path("/data/import_done")
    assert settings.failed_dir == Path("/data/import_failed")
    assert settings.db_path == Path("/data/db/rrmc.db")


def test_ac7_invalid_engines(clean_env: pytest.MonkeyPatch) -> None:
    clean_env.setenv("RRMC_ENGINES", "both")

    with pytest.raises(SettingsError) as error:
        load_settings()

    assert str(error.value) == "Invalid setting RRMC_ENGINES: expected real or fake"


def test_ac7_invalid_log_level(clean_env: pytest.MonkeyPatch) -> None:
    clean_env.setenv("RRMC_LOG_LEVEL", "LOUD")

    with pytest.raises(SettingsError) as error:
        load_settings()

    assert str(error.value) == (
        "Invalid setting RRMC_LOG_LEVEL: expected DEBUG, INFO, WARNING or ERROR"
    )


def test_ac7_invalid_ollama_url(clean_env: pytest.MonkeyPatch) -> None:
    clean_env.setenv("RRMC_OLLAMA_URL", "not-a-url")

    with pytest.raises(SettingsError) as error:
        load_settings()

    assert str(error.value) == "Invalid setting RRMC_OLLAMA_URL: expected an http or https URL"


def test_ac7_empty_model(clean_env: pytest.MonkeyPatch) -> None:
    clean_env.setenv("RRMC_MODEL", "")

    with pytest.raises(SettingsError) as error:
        load_settings()

    assert str(error.value) == "Invalid setting RRMC_MODEL: expected an Ollama model name"


def test_ac7_invalid_ui_port(clean_env: pytest.MonkeyPatch) -> None:
    clean_env.setenv("RRMC_UI_PORT", "abc")

    with pytest.raises(SettingsError) as error:
        load_settings()

    assert str(error.value) == "Invalid setting RRMC_UI_PORT: expected a port number"

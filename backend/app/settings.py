"""Application settings read from RRMC_* environment variables."""

from pathlib import Path
from typing import Literal

from pydantic import Field, HttpUrl, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class SettingsError(Exception):
    """A setting has an invalid value."""


class Settings(BaseSettings):
    """Backend settings.

    RRMC_IMPORT_DIR, RRMC_DONE_DIR, RRMC_FAILED_DIR and RRMC_BACKEND_PORT are host-side values
    used by Compose; inside the container the folders are always under `data_dir`.
    """

    model_config = SettingsConfigDict(env_prefix="RRMC_", frozen=True)

    engines: Literal["real", "fake"] = "real"
    ollama_url: HttpUrl = HttpUrl("http://host.docker.internal:11434")
    model: str = Field(default="qwen3:30b-a3b-instruct-2507-q4_K_M", min_length=1)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    ui_port: int = 5173
    data_dir: Path = Path("/data")

    @property
    def import_dir(self) -> Path:
        return self.data_dir / "import"

    @property
    def done_dir(self) -> Path:
        return self.data_dir / "import_done"

    @property
    def failed_dir(self) -> Path:
        return self.data_dir / "import_failed"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "db" / "rrmc.db"


_ALLOWED_VALUES = {
    "engines": "real or fake",
    "ollama_url": "an http or https URL",
    "model": "an Ollama model name",
    "log_level": "DEBUG, INFO, WARNING or ERROR",
    "ui_port": "a port number",
}


def load_settings() -> Settings:
    """Read the settings from the environment.

    Raises:
        SettingsError: a setting is invalid. The message names the setting and its allowed
            values, never the given value.
    """
    try:
        return Settings()
    except ValidationError as error:
        field = str(error.errors()[0]["loc"][0])
        raise SettingsError(
            f"Invalid setting RRMC_{field.upper()}: expected {_ALLOWED_VALUES[field]}"
        ) from None

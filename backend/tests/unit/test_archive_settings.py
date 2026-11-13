"""The archive folder setting (archiving spec PC5, AC32)."""

from pathlib import Path

import pytest

from app.settings import Settings, load_settings


def test_ac32_the_archive_folder_is_under_the_data_folder(clean_env: pytest.MonkeyPatch) -> None:
    assert load_settings().archive_dir == Path("/data/archived")


def test_ac32_the_archive_folder_follows_the_data_folder(clean_env: pytest.MonkeyPatch) -> None:
    assert Settings(data_dir=Path("/srv/rrmc")).archive_dir == Path("/srv/rrmc/archived")

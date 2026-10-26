import os

import pytest


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Remove every RRMC_* variable, including those Compose sets from the settings file."""
    for name in list(os.environ):
        if name.startswith("RRMC_"):
            monkeypatch.delenv(name)
    return monkeypatch

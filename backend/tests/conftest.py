import os
from pathlib import Path

import pytest

from tests.data_guard import find_real_data_mount, refusal_line

_MOUNT_TABLE = Path("/proc/self/mounts")


def pytest_configure(config: pytest.Config) -> None:
    """Stop before any test runs when real data may be mounted (test-isolation PC5)."""
    if not _MOUNT_TABLE.exists():  # not Linux, so not a container of this project
        return
    mount_point = find_real_data_mount(_MOUNT_TABLE.read_text())
    if mount_point is not None:
        pytest.exit(refusal_line(mount_point), returncode=2)


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Remove every RRMC_* variable, including those Compose sets from the settings file."""
    for name in list(os.environ):
        if name.startswith("RRMC_"):
            monkeypatch.delenv(name)
    return monkeypatch

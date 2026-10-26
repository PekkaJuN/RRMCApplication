from pathlib import Path

import pytest

from app.health.schemas import HealthChecks
from app.health.service import check_folders, overall_status

ALL_OK = HealthChecks(database="ok", folders="ok", ocr="ok", model="ok")


def make_folders(tmp_path: Path) -> list[Path]:
    folders = [tmp_path / "import", tmp_path / "import_done", tmp_path / "import_failed"]
    for folder in folders:
        folder.mkdir()
    return folders


def test_ac16_existing_writable_folders_are_ok(tmp_path: Path) -> None:
    assert check_folders(make_folders(tmp_path)) == "ok"


def test_ac16_missing_folder_is_unavailable(tmp_path: Path) -> None:
    folders = make_folders(tmp_path)
    folders[2].rmdir()

    assert check_folders(folders) == "unavailable"


def test_ac16_file_instead_of_folder_is_unavailable(tmp_path: Path) -> None:
    folders = make_folders(tmp_path)
    folders[2].rmdir()
    folders[2].write_text("", encoding="utf-8")

    assert check_folders(folders) == "unavailable"


def test_ac16_read_only_folder_is_unavailable(tmp_path: Path) -> None:
    # The tests run as root, for whom permission bits never block writing, so the write
    # check is replaced; a read-only mount makes os.access fail the same way.
    folders = make_folders(tmp_path)

    assert check_folders(folders, can_write=lambda path: path != folders[0]) == "unavailable"


def test_ac12_all_checks_ok_is_ok() -> None:
    assert overall_status(ALL_OK) == "ok"


@pytest.mark.parametrize(
    "checks",
    [
        ALL_OK.model_copy(update={"database": "unavailable"}),
        ALL_OK.model_copy(update={"folders": "unavailable"}),
        ALL_OK.model_copy(update={"ocr": "unavailable"}),
        ALL_OK.model_copy(update={"model": "unavailable"}),
        ALL_OK.model_copy(update={"model": "missing_model"}),
    ],
    ids=["database", "folders", "ocr", "model unavailable", "model missing"],
)
def test_ac14_any_check_not_ok_is_degraded(checks: HealthChecks) -> None:
    assert overall_status(checks) == "degraded"

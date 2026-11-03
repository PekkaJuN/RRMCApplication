import shutil
from pathlib import Path

import pytest

from app.receipt_import.files import LocalFileStore, is_ignored
from tests.receipt_import_data import jpeg


@pytest.mark.parametrize(
    "name", [".hidden.jpg", "desktop.ini", "Desktop.INI", "THUMBS.DB", "Thumbs.db"]
)
def test_ac8_ignored_names(name: str) -> None:
    assert is_ignored(name)


@pytest.mark.parametrize("name", ["a.jpg", "thumbs.db.jpg", "my desktop.ini"])
def test_ac8_other_names_are_not_ignored(name: str) -> None:
    assert not is_ignored(name)


def write(path: Path, data: bytes = b"x") -> Path:
    path.write_bytes(data)
    return path


def test_ac3_ac8_list_files_in_name_order_without_ignored_entries(tmp_path: Path) -> None:
    for name in ["c.jpg", "A.jpg", "b.png", ".hidden.jpg", "desktop.ini", "THUMBS.DB"]:
        write(tmp_path / name)
    (tmp_path / "vanhat").mkdir()
    write(tmp_path / "vanhat" / "x.jpg")

    files = LocalFileStore().list_files(tmp_path)

    assert [path.name for path in files] == ["A.jpg", "b.png", "c.jpg"]


def test_ac8_list_files_skips_symlinks(tmp_path: Path) -> None:
    target = write(tmp_path / "elsewhere.jpg")
    folder = tmp_path / "import"
    folder.mkdir()
    (folder / "link.jpg").symlink_to(target)

    assert LocalFileStore().list_files(folder) == []


def test_ac10_names_in_are_lower_cased(tmp_path: Path) -> None:
    write(tmp_path / "KUITTI (2).jpg")
    (tmp_path / "Kansio").mkdir()

    assert LocalFileStore().names_in(tmp_path) == {"kuitti (2).jpg", "kansio"}


def test_ac1_read_bytes(tmp_path: Path) -> None:
    assert LocalFileStore().read_bytes(write(tmp_path / "a.jpg", jpeg("a"))) == jpeg("a")


def test_ac1_move_copies_the_bytes_and_removes_the_source(tmp_path: Path) -> None:
    source = write(tmp_path / "a.jpg", jpeg("a"))
    target = tmp_path / "done" / "a (2).jpg"
    target.parent.mkdir()

    LocalFileStore().move(source, target)

    assert target.read_bytes() == jpeg("a")
    assert not source.exists()


def test_ac10_move_never_overwrites(tmp_path: Path) -> None:
    source = write(tmp_path / "a.jpg", jpeg("new"))
    target = write(tmp_path / "b.jpg", jpeg("old"))

    with pytest.raises(OSError):
        LocalFileStore().move(source, target)

    assert target.read_bytes() == jpeg("old")
    assert source.read_bytes() == jpeg("new")


def test_ac12_failed_copy_leaves_no_partial_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = write(tmp_path / "a.jpg", jpeg("a"))
    target = tmp_path / "b.jpg"

    def fail_copy(*args: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(shutil, "copyfileobj", fail_copy)

    with pytest.raises(OSError):
        LocalFileStore().move(source, target)

    assert not target.exists()
    assert source.read_bytes() == jpeg("a")


def test_ac12_failed_source_delete_removes_the_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = write(tmp_path / "a.jpg", jpeg("a"))
    target = tmp_path / "b.jpg"
    unlink = Path.unlink

    def fail_for_source(path: Path, missing_ok: bool = False) -> None:
        if path == source:
            raise PermissionError("locked")
        unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", fail_for_source)

    with pytest.raises(OSError):
        LocalFileStore().move(source, target)

    assert not target.exists()
    assert source.read_bytes() == jpeg("a")

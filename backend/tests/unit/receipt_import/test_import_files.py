import shutil
from pathlib import Path

import pytest

from app.receipt_import.files import (
    LocalFileStore,
    check_format,
    free_target_name,
    image_identifier,
    is_ignored,
)
from tests.receipt_import_data import jpeg, png


def test_ac1_image_identifier_is_lowercase_sha256() -> None:
    assert image_identifier(b"abc") == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


@pytest.mark.parametrize(
    ("name", "data"),
    [
        ("a.jpg", jpeg("a")),
        ("c.jpeg", jpeg("c")),
        ("d.JPG", jpeg("d")),
        ("e.JPEG", jpeg("e")),
        ("B.PNG", png("b")),
        ("f.png", png("f")),
    ],
)
def test_ac2_supported_images_in_any_case(name: str, data: bytes) -> None:
    assert check_format(name, data)


@pytest.mark.parametrize(
    ("name", "data"),
    [
        ("notes.txt", b"hello"),
        ("photo.heic", jpeg("heic")),
        ("noextension", jpeg("x")),
        ("text.jpg", b"hello"),
        ("empty.png", b""),
        ("empty.jpg", b""),
        ("png-as.jpg", png("p")),
        ("jpeg-as.png", jpeg("j")),
        ("short.jpg", b"\xff\xd8"),
    ],
)
def test_ac6_ac7_unsupported_files(name: str, data: bytes) -> None:
    assert not check_format(name, data)


@pytest.mark.parametrize(
    "name", [".hidden.jpg", "desktop.ini", "Desktop.INI", "THUMBS.DB", "Thumbs.db"]
)
def test_ac8_ignored_names(name: str) -> None:
    assert is_ignored(name)


@pytest.mark.parametrize("name", ["a.jpg", "thumbs.db.jpg", "my desktop.ini"])
def test_ac8_other_names_are_not_ignored(name: str) -> None:
    assert not is_ignored(name)


def test_ac10_unused_name_is_kept() -> None:
    assert free_target_name("kuitti.jpg", {"muu.jpg"}) == "kuitti.jpg"


def test_ac10_first_free_numbered_suffix_ignoring_case() -> None:
    taken = {"kuitti.jpg", "kuitti (2).jpg"}

    assert free_target_name("kuitti.jpg", taken) == "kuitti (3).jpg"
    assert free_target_name("KUITTI.jpg", taken) == "KUITTI (3).jpg"


def test_ac11_name_without_extension() -> None:
    assert free_target_name("README", {"readme"}) == "README (2)"


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

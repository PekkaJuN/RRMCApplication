"""The failed folder as the new receipt form uses it (receipt-management T11, T12, T14)."""

from pathlib import Path

import pytest

from app.image_files import image_identifier
from app.review.errors import (
    FoldersUnavailableError,
    ImageMoveFailedError,
    ImageNotFoundError,
    UnsupportedFormatError,
)
from app.review.failed_images import FailedFolder
from tests.receipt_import_data import jpeg, png


@pytest.fixture
def folder_f(tmp_path: Path) -> Path:
    """Folder F of the spec: two synthetic images, a text file, a text file named .jpg, a
    folder, and an image in the done folder next to it."""
    failed = tmp_path / "import_failed"
    failed.mkdir()
    (failed / "b.png").write_bytes(png("b"))
    (failed / "IMG_2.jpg").write_bytes(jpeg("img2"))
    (failed / "notes.txt").write_bytes(b"notes")
    (failed / "fake.jpg").write_bytes(b"not an image")
    (failed / "sub").mkdir()
    done = tmp_path / "import_done"
    done.mkdir()
    (done / "a.jpg").write_bytes(jpeg("a"))
    return failed


def failed_folder(failed: Path) -> FailedFolder:
    return FailedFolder(failed, failed.parent / "import_done")


def test_ac16_failed_images_sorted_by_name(folder_f: Path) -> None:
    assert failed_folder(folder_f).names() == ["b.png", "fake.jpg", "IMG_2.jpg"]


def test_ac16_suffixes_in_any_case(tmp_path: Path) -> None:
    for name in ["c.JPEG", "a.Png", "b.jpeg"]:
        (tmp_path / name).write_bytes(b"x")

    assert failed_folder(tmp_path).names() == ["a.Png", "b.jpeg", "c.JPEG"]


def test_ac17_empty_failed_folder(tmp_path: Path) -> None:
    assert failed_folder(tmp_path).names() == []


def test_ac17_missing_failed_folder(tmp_path: Path) -> None:
    with pytest.raises(FoldersUnavailableError):
        failed_folder(tmp_path / "missing").names()


def test_ac18_preview_of_a_failed_image(folder_f: Path) -> None:
    folder = failed_folder(folder_f)

    assert folder.preview("b.png") == (png("b"), "image/png")
    assert folder.preview("IMG_2.jpg") == (jpeg("img2"), "image/jpeg")


@pytest.mark.parametrize(
    "name",
    [
        "fake.jpg",
        "notes.txt",
        "missing.png",
        "../import_done/a.jpg",
        "sub",
        "",
        ".",
        "..",
        "a\x00.jpg",
    ],
)
def test_ac19_preview_refused(folder_f: Path, name: str) -> None:
    with pytest.raises(ImageNotFoundError) as error:
        failed_folder(folder_f).preview(name)

    assert error.value.status == 404


# Taking an image for a new receipt (T14).


def test_ac20_take_a_failed_image(folder_f: Path) -> None:
    taken = failed_folder(folder_f).take("IMG_2.jpg")

    assert taken.path == folder_f / "IMG_2.jpg"
    assert taken.image_hash == image_identifier(jpeg("img2"))
    assert taken.done_name == "IMG_2.jpg"


def test_ac21_done_name_gets_a_free_suffix(folder_f: Path) -> None:
    (folder_f.parent / "import_done" / "b.png").write_bytes(png("other"))

    assert failed_folder(folder_f).take("b.png").done_name == "b (2).png"


@pytest.mark.parametrize(
    "name", ["missing.png", "../import_done/a.jpg", "sub", "notes.txt", "a\x00.jpg"]
)
def test_ac23_take_refuses_what_is_not_a_failed_image(folder_f: Path, name: str) -> None:
    with pytest.raises(ImageNotFoundError) as error:
        failed_folder(folder_f).take(name)

    assert error.value.status == 422


def test_ac23_take_refuses_a_file_that_is_not_an_image(folder_f: Path) -> None:
    with pytest.raises(UnsupportedFormatError):
        failed_folder(folder_f).take("fake.jpg")


def test_ac24_done_folder_that_cannot_be_listed(folder_f: Path) -> None:
    folder = FailedFolder(folder_f, folder_f.parent / "missing_done")

    with pytest.raises(ImageMoveFailedError):
        folder.take("b.png")


def test_ac20_move_to_done(folder_f: Path) -> None:
    folder = failed_folder(folder_f)
    taken = folder.take("IMG_2.jpg")

    folder.move_to_done(taken)

    assert (folder_f.parent / "import_done" / "IMG_2.jpg").read_bytes() == jpeg("img2")
    assert not (folder_f / "IMG_2.jpg").exists()


def test_ac24_move_uses_the_given_mover(folder_f: Path) -> None:
    def failing_move(source: Path, target: Path) -> None:
        raise OSError("simulated")

    folder = FailedFolder(folder_f, folder_f.parent / "import_done", move=failing_move)

    with pytest.raises(OSError):
        folder.move_to_done(folder.take("b.png"))

    assert (folder_f / "b.png").exists()

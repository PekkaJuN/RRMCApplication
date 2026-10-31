from pathlib import Path

import pytest

from app.review.errors import ImageMissingError
from app.review.images import read_image

JPEG = b"\xff\xd8\xff\xe0synthetic jpeg"
PNG = b"\x89PNG\r\n\x1a\nsynthetic png"


@pytest.fixture
def done_dir(tmp_path: Path) -> Path:
    done = tmp_path / "import_done"
    done.mkdir()
    return done


def test_ac10_jpeg_and_png(done_dir: Path) -> None:
    (done_dir / "kuitti.jpg").write_bytes(JPEG)
    (done_dir / "kuitti (2).png").write_bytes(PNG)

    assert read_image(done_dir, "kuitti.jpg") == (JPEG, "image/jpeg")
    assert read_image(done_dir, "kuitti (2).png") == (PNG, "image/png")


def test_ac10_type_comes_from_the_signature_not_the_name(done_dir: Path) -> None:
    (done_dir / "kuitti.jpg").write_bytes(PNG)

    assert read_image(done_dir, "kuitti.jpg") == (PNG, "image/png")


@pytest.mark.parametrize("case", ["no file", "directory", "text"])
def test_ac11_missing_or_unreadable(done_dir: Path, case: str) -> None:
    if case == "directory":
        (done_dir / "kuitti.jpg").mkdir()
    if case == "text":
        (done_dir / "kuitti.jpg").write_bytes(b"not an image")

    with pytest.raises(ImageMissingError) as raised:
        read_image(done_dir, "kuitti.jpg")

    assert raised.value.code == "image_missing"
    assert raised.value.status == 404
    assert raised.value.message == "Kuvaa ei löydy valmiiden kansiosta."


@pytest.mark.parametrize("name", ["../secret.jpg", "sub/kuitti.jpg", "", ".", ".."])
def test_ac12_name_outside_the_done_folder(done_dir: Path, name: str) -> None:
    (done_dir.parent / "secret.jpg").write_bytes(JPEG)
    (done_dir / "sub").mkdir()
    (done_dir / "sub" / "kuitti.jpg").write_bytes(JPEG)

    with pytest.raises(ImageMissingError):
        read_image(done_dir, name)


def test_ac12_absolute_name(done_dir: Path) -> None:
    secret = done_dir.parent / "secret.jpg"
    secret.write_bytes(JPEG)

    with pytest.raises(ImageMissingError):
        read_image(done_dir, str(secret))


def test_ac12_link_out_of_the_done_folder(done_dir: Path) -> None:
    secret = done_dir.parent / "secret.jpg"
    secret.write_bytes(JPEG)
    (done_dir / "kuitti.jpg").symlink_to(secret)

    with pytest.raises(ImageMissingError):
        read_image(done_dir, "kuitti.jpg")

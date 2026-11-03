"""The image file rules shared by import and review (receipt-management Plan P3). The
tests moved here unchanged from the import's file tests."""

import pytest

from app.image_files import check_format, free_target_name, image_identifier, media_type
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


def test_ac10_unused_name_is_kept() -> None:
    assert free_target_name("kuitti.jpg", {"muu.jpg"}) == "kuitti.jpg"


def test_ac10_first_free_numbered_suffix_ignoring_case() -> None:
    taken = {"kuitti.jpg", "kuitti (2).jpg"}

    assert free_target_name("kuitti.jpg", taken) == "kuitti (3).jpg"
    assert free_target_name("KUITTI.jpg", taken) == "KUITTI (3).jpg"


def test_ac11_name_without_extension() -> None:
    assert free_target_name("README", {"readme"}) == "README (2)"


def test_media_type_from_the_signature() -> None:
    assert media_type(jpeg("a")) == "image/jpeg"
    assert media_type(png("a")) == "image/png"
    assert media_type(b"hello") is None
    assert media_type(b"") is None

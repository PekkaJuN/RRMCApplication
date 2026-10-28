from tests.receipt_import_data import JPEG_SIGNATURE, PNG_SIGNATURE, jpeg, png


def test_synthetic_images_have_signatures_and_differ_by_tag() -> None:
    assert jpeg("a").startswith(JPEG_SIGNATURE)
    assert png("a").startswith(PNG_SIGNATURE)
    assert jpeg("a") != jpeg("b")
    assert png("a") != png("b")

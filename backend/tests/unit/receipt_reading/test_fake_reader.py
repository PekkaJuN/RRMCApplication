import subprocess
from datetime import date

import pytest

from app.engines.factory import create_engines
from app.receipt_reading.factory import create_reader
from app.receipt_reading.fake import FAKE_PARSE_FAILED_IMAGE, FakeReceiptReader
from app.receipt_reading.reader import OcrReceiptReader
from app.receipt_reading.receipt import ReadFailedError, ReadLine
from app.settings import Settings


def test_ac24_fake_returns_the_fixed_receipt(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_subprocess(*args: object, **kwargs: object) -> None:
        raise AssertionError("the fake must not start a process")

    monkeypatch.setattr(subprocess, "run", no_subprocess)
    fake = FakeReceiptReader()

    first, second = fake.read(b"\xff\xd8\xff one"), fake.read(b"\x89PNG two")

    assert first == second
    assert first.store == "Testikauppa"
    assert first.purchase_date == date(2026, 10, 5)
    assert first.total_cents == 349
    assert first.ocr_text == "TESTIKAUPPA\nMAITO 1,25\nLIMU 2,24\nYHTEENSÄ 3,49"
    assert first.lines == (
        ReadLine("Maito", 125, is_deposit_refund=False),
        ReadLine("Limu", 224, is_deposit_refund=False),
    )


def test_ac24b_listed_hash_is_parse_failed() -> None:
    assert FAKE_PARSE_FAILED_IMAGE == b"\x89PNG\r\n\x1a\nrrmc fake reader: parse_failed"

    with pytest.raises(ReadFailedError) as error:
        FakeReceiptReader().read(FAKE_PARSE_FAILED_IMAGE)

    assert error.value.reason == "parse_failed"


@pytest.mark.parametrize(
    ("engines", "reader_type"), [("fake", FakeReceiptReader), ("real", OcrReceiptReader)]
)
def test_create_reader_picks_fake_or_ocr(engines: str, reader_type: type) -> None:
    settings = Settings(engines=engines)  # pyright: ignore[reportArgumentType]

    assert isinstance(create_reader(settings, create_engines(settings)), reader_type)

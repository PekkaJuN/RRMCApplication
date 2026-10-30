"""Deterministic reader for tests and E2E runs (NFR-13); never calls Tesseract or Ollama."""

import hashlib
from datetime import date

from app.engines.ocr import FAKE_OCR_TEXT
from app.receipt_reading.receipt import ReadFailedError, ReadFailure, ReadLine, ReadReceipt

FAKE_RECEIPT = ReadReceipt(
    store="Testikauppa",
    purchase_date=date(2026, 10, 5),
    total_cents=349,
    lines=(
        ReadLine("Maito", 125, is_deposit_refund=False),
        ReadLine("Limu", 224, is_deposit_refund=False),
    ),
    ocr_text=FAKE_OCR_TEXT,
)

# Not a real image: the fake never decodes one. The E2E test writes the same bytes.
FAKE_PARSE_FAILED_IMAGE = b"\x89PNG\r\n\x1a\nrrmc fake reader: parse_failed"

_FAILURES: dict[str, ReadFailure] = {
    hashlib.sha256(FAKE_PARSE_FAILED_IMAGE).hexdigest(): "parse_failed",
}


class FakeReceiptReader:
    """`FAKE_RECEIPT` for every image, except the images listed by SHA-256, which fail."""

    def read(self, image: bytes) -> ReadReceipt:
        failure = _FAILURES.get(hashlib.sha256(image).hexdigest())
        if failure is not None:
            raise ReadFailedError(failure)
        return FAKE_RECEIPT

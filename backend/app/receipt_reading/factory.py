"""Chooses the OCR reader or the fake from the settings."""

from app.engines.factory import Engines
from app.receipt_reading.fake import FakeReceiptReader
from app.receipt_reading.reader import OcrReceiptReader, ReceiptReader
from app.settings import Settings


def create_reader(settings: Settings, engines: Engines) -> ReceiptReader:
    if settings.engines == "fake":
        return FakeReceiptReader()
    return OcrReceiptReader(ocr=engines.ocr, model=engines.model)

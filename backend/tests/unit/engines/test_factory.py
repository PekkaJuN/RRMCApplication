from pathlib import Path

from app.engines.factory import create_engines
from app.engines.model import FakeReceiptModel, OllamaReceiptModel
from app.engines.ocr import FakeOcrEngine, TesseractOcrEngine
from app.settings import Settings


def test_ac12_fake_setting_gives_fakes(tmp_path: Path) -> None:
    engines = create_engines(Settings(engines="fake", data_dir=tmp_path))

    assert isinstance(engines.ocr, FakeOcrEngine)
    assert isinstance(engines.model, FakeReceiptModel)


def test_ac13_real_setting_gives_tesseract_and_ollama(tmp_path: Path) -> None:
    engines = create_engines(Settings(engines="real", data_dir=tmp_path))

    assert isinstance(engines.ocr, TesseractOcrEngine)
    assert isinstance(engines.model, OllamaReceiptModel)

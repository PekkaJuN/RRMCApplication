import subprocess
from collections.abc import Sequence

import pytest

from app.engines.ocr import FakeOcrEngine, RunCommand, TesseractOcrEngine

LIST_LANGS_HEADER = 'List of available languages in "/usr/share/tesseract-ocr/5/tessdata/" (3):'


def fake_run(stdout: str = "", returncode: int = 0, error: Exception | None = None) -> RunCommand:
    """A fake subprocess runner that records nothing and returns a fixed result."""

    def run(args: Sequence[str], timeout: float) -> subprocess.CompletedProcess[str]:
        if error is not None:
            raise error
        assert list(args) == ["tesseract", "--list-langs"]
        return subprocess.CompletedProcess(args, returncode, stdout=stdout, stderr="")

    return run


def test_ac13_tesseract_with_fin_and_eng_is_ok() -> None:
    engine = TesseractOcrEngine(run=fake_run(f"{LIST_LANGS_HEADER}\neng\nfin\nosd\n"))

    assert engine.check() == "ok"


def test_ac13_tesseract_without_fin_is_unavailable() -> None:
    engine = TesseractOcrEngine(run=fake_run(f"{LIST_LANGS_HEADER}\neng\nosd\n"))

    assert engine.check() == "unavailable"


@pytest.mark.parametrize(
    "run",
    [
        fake_run(returncode=1),
        fake_run(error=FileNotFoundError("tesseract")),
        fake_run(error=subprocess.TimeoutExpired("tesseract", 5)),
    ],
    ids=["exit code 1", "not installed", "timeout"],
)
def test_ac13_tesseract_that_cannot_run_is_unavailable(run: RunCommand) -> None:
    assert TesseractOcrEngine(run=run).check() == "unavailable"


def test_ac12_fake_ocr_is_ok_without_running_tesseract(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_subprocess(*args: object, **kwargs: object) -> None:
        raise AssertionError("the fake must not start a process")

    monkeypatch.setattr(subprocess, "run", no_subprocess)
    monkeypatch.setattr(subprocess, "Popen", no_subprocess)

    assert FakeOcrEngine().check() == "ok"

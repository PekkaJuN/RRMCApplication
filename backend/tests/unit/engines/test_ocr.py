import io
import subprocess
from collections.abc import Sequence

import pytest
from PIL import Image

from app.engines.ocr import FakeOcrEngine, OcrError, Oriented, RunCommand, TesseractOcrEngine

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


class FakeImageRun:
    """A fake runner for the commands that get the image on stdin; records each call."""

    def __init__(self, result: subprocess.CompletedProcess[bytes] | Exception) -> None:
        self.result = result
        self.calls: list[tuple[list[str], bytes]] = []

    def __call__(self, args: Sequence[str], data: bytes) -> subprocess.CompletedProcess[bytes]:
        self.calls.append((list(args), data))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def done(returncode: int, stdout: bytes) -> subprocess.CompletedProcess[bytes]:
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr=b"")


def osd_output(rotate: int, confidence: str) -> bytes:
    return (
        f"Page number: 0\nOrientation in degrees: {(360 - rotate) % 360}\nRotate: {rotate}\n"
        f"Orientation confidence: {confidence}\nScript: Latin\nScript confidence: 1.50\n"
    ).encode()


def sideways_receipt() -> tuple[Image.Image, bytes]:
    """An upright receipt, and the same receipt stored turned 90 degrees counterclockwise."""
    upright = Image.new("L", (300, 400), 255)
    upright.paste(0, (0, 0, 300, 40))
    buffer = io.BytesIO()
    upright.transpose(Image.Transpose.ROTATE_90).save(buffer, format="PNG")
    return upright, buffer.getvalue()


def test_ac3_sure_osd_turns_the_image() -> None:
    # Given OSD reports Rotate 90 with confidence 2.0, the limit
    upright, stored = sideways_receipt()
    run = FakeImageRun(done(0, osd_output(90, "2.00")))

    # When orientation detection runs
    oriented = TesseractOcrEngine(run_image=run).orient(stored)

    # Then the image is turned 90 degrees clockwise, upright again
    assert run.calls == [(["tesseract", "stdin", "stdout", "--psm", "0"], stored)]
    assert Image.open(io.BytesIO(oriented.image)).tobytes() == upright.tobytes()
    assert (oriented.osd_rotation, oriented.osd_confidence) == (90, 2.0)


@pytest.mark.parametrize(
    "result",
    [
        done(0, osd_output(90, "1.90")),
        done(0, osd_output(0, "5.00")),
        done(0, osd_output(90, "nan")),
        done(1, b""),
        done(0, b"Page number: 0\n"),
        OSError("no tesseract"),
        subprocess.TimeoutExpired("tesseract", 1),
    ],
    ids=["unsure", "no rotation", "nan", "exit code 1", "no fields", "not installed", "timeout"],
)
def test_ac4_unsure_or_failed_osd_keeps_the_image(
    result: subprocess.CompletedProcess[bytes] | Exception,
) -> None:
    _, stored = sideways_receipt()

    oriented = TesseractOcrEngine(run_image=FakeImageRun(result)).orient(stored)

    assert oriented.image == stored
    assert oriented.osd_rotation == 0


def test_tesseract_reads_with_finnish_and_english() -> None:
    run = FakeImageRun(done(0, "MAITO 1,25\nYHTEENSÄ 1,25\n".encode()))

    text = TesseractOcrEngine(run_image=run).read(b"image")

    assert text == "MAITO 1,25\nYHTEENSÄ 1,25\n"
    assert run.calls == [
        (["tesseract", "stdin", "stdout", "-l", "fin+eng", "--psm", "4"], b"image")
    ]


@pytest.mark.parametrize(
    "result",
    [done(1, b""), OSError("no tesseract"), subprocess.TimeoutExpired("tesseract", 1)],
    ids=["exit code 1", "not installed", "timeout"],
)
def test_ac12_tesseract_error_or_timeout_is_ocr_error(
    result: subprocess.CompletedProcess[bytes] | Exception,
) -> None:
    with pytest.raises(OcrError):
        TesseractOcrEngine(run_image=FakeImageRun(result)).read(b"image")


def test_ac24_fake_ocr_keeps_the_image_and_reads_fixed_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_subprocess(*args: object, **kwargs: object) -> None:
        raise AssertionError("the fake must not start a process")

    monkeypatch.setattr(subprocess, "run", no_subprocess)
    fake = FakeOcrEngine()

    assert fake.orient(b"image") == Oriented(b"image", 0, None)
    assert fake.read(b"image") == fake.read(b"other image") != ""

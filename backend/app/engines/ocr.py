"""OCR engine interface, the Tesseract implementation and a fake for tests."""

import io
import math
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from PIL import Image

type OcrCheckResult = Literal["ok", "unavailable"]
type RunCommand = Callable[[Sequence[str], float], subprocess.CompletedProcess[str]]
type RunImageCommand = Callable[[Sequence[str], bytes], subprocess.CompletedProcess[bytes]]

REQUIRED_LANGUAGES = frozenset({"fin", "eng"})
CHECK_TIMEOUT_SECONDS = 5.0
# --psm 4: one column of text of varying sizes, the layout of a receipt.
READ_ARGS = ("tesseract", "stdin", "stdout", "-l", "fin+eng", "--psm", "4")
# --psm 0: orientation and script detection only.
OSD_ARGS = ("tesseract", "stdin", "stdout", "--psm", "0")
# Measured on synthetic receipts: 20 or more lines give 2.5–4.6, eight lines below 1.5.
OSD_MIN_CONFIDENCE = 2.0
READ_TIMEOUT_SECONDS = 120.0


class OcrError(Exception):
    """Tesseract did not read the image."""


@dataclass(frozen=True)
class Oriented:
    image: bytes
    osd_rotation: int
    osd_confidence: float | None


class OcrEngine(Protocol):
    def check(self) -> OcrCheckResult:
        """Tell whether OCR can run."""
        ...

    def orient(self, image: bytes) -> Oriented:
        """The image turned upright by orientation detection; never raises."""
        ...

    def read(self, image: bytes) -> str:
        """The text of an image.

        Raises:
            OcrError: the image was not read.
        """
        ...


def _run(args: Sequence[str], timeout: float) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed command, no user input
        args, capture_output=True, text=True, timeout=timeout, check=False
    )


def _run_image(args: Sequence[str], image: bytes) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(  # noqa: S603 - fixed command, the image goes to stdin
        args, input=image, capture_output=True, timeout=READ_TIMEOUT_SECONDS, check=False
    )


def _osd_values(output: str) -> tuple[int, float] | None:
    """`Rotate` and `Orientation confidence` from Tesseract's OSD output."""
    fields = dict(line.split(":", 1) for line in output.splitlines() if ":" in line)
    try:
        rotation, confidence = int(fields["Rotate"]), float(fields["Orientation confidence"])
    except (KeyError, ValueError):
        return None
    # A NaN would pass the confidence limit.
    return (rotation, confidence) if math.isfinite(confidence) else None


class TesseractOcrEngine:
    def __init__(self, run: RunCommand = _run, run_image: RunImageCommand = _run_image) -> None:
        self._run = run
        self._run_image = run_image

    def check(self) -> OcrCheckResult:
        """`ok` when Tesseract runs and has the Finnish and English language data."""
        try:
            result = self._run(["tesseract", "--list-langs"], CHECK_TIMEOUT_SECONDS)
        except (OSError, subprocess.TimeoutExpired):
            return "unavailable"
        if result.returncode != 0:
            return "unavailable"
        # The first line is a header naming the tessdata folder; one language per line follows.
        languages = set(result.stdout.splitlines()[1:])
        return "ok" if languages.issuperset(REQUIRED_LANGUAGES) else "unavailable"

    def orient(self, image: bytes) -> Oriented:
        """Turn the image upright when OSD is sure enough; a failed detection keeps it.

        OSD catches images whose EXIF tag is missing or wrong (scans, edited images).
        """
        try:
            result = self._run_image(OSD_ARGS, image)
        except (OSError, subprocess.TimeoutExpired):
            return Oriented(image, 0, None)
        values = _osd_values(result.stdout.decode("utf-8", errors="replace"))
        if result.returncode != 0 or values is None:
            return Oriented(image, 0, None)
        rotation, confidence = values
        if rotation not in (90, 180, 270) or confidence < OSD_MIN_CONFIDENCE:
            return Oriented(image, 0, confidence)
        with Image.open(io.BytesIO(image)) as source:
            # `Rotate` is clockwise; Pillow turns counterclockwise.
            turned = source.rotate(-rotation, expand=True)
        buffer = io.BytesIO()
        turned.save(buffer, format="PNG")
        return Oriented(buffer.getvalue(), rotation, confidence)

    def read(self, image: bytes) -> str:
        try:
            result = self._run_image(READ_ARGS, image)
        except (OSError, subprocess.TimeoutExpired):
            raise OcrError("Tesseract did not run") from None
        if result.returncode != 0:
            raise OcrError(f"Tesseract exited with code {result.returncode}")
        return result.stdout.decode("utf-8", errors="replace")


# The text of the fake reader's receipt (receipt-reading AC24).
FAKE_OCR_TEXT = "TESTIKAUPPA\nMAITO 1,25\nLIMU 2,24\nYHTEENSÄ 3,49"


class FakeOcrEngine:
    """Deterministic OCR for tests and E2E runs; never starts Tesseract."""

    def check(self) -> OcrCheckResult:
        return "ok"

    def orient(self, image: bytes) -> Oriented:
        return Oriented(image, 0, None)

    def read(self, image: bytes) -> str:
        return FAKE_OCR_TEXT

"""Preprocessing and Tesseract OCR for `ocr:` variants; upright images for `vision:` (PC4)."""

import io
import math
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from PIL import Image, ImageOps

type RunCommand = Callable[[Sequence[str], bytes], subprocess.CompletedProcess[bytes]]

MIN_WIDTH = 1500
EXIF_ORIENTATION = 0x0112
# --psm 4: one column of text of varying sizes, the layout of a receipt.
TESSERACT_ARGS = ("tesseract", "stdin", "stdout", "-l", "fin+eng", "--psm", "4")
# --psm 0: orientation and script detection only.
OSD_ARGS = ("tesseract", "stdin", "stdout", "--psm", "0")
# Measured on synthetic receipts: 20 or more lines give 2.5–4.6, eight lines below 1.5.
OSD_MIN_CONFIDENCE = 2.0
OCR_TIMEOUT_SECONDS = 120.0


class OcrError(Exception):
    """Tesseract did not read the image."""


@dataclass(frozen=True)
class Oriented:
    image: bytes
    osd_rotation: int
    osd_confidence: float | None


class Ocr(Protocol):
    def orient(self, image: bytes) -> Oriented:
        """The image turned upright by orientation detection; never raises (AC25)."""
        ...

    def read(self, image: bytes) -> str:
        """The text of an image.

        Raises:
            OcrError: the image was not read.
        """
        ...


def exif_orientation(image: bytes) -> int | None:
    """The EXIF orientation tag (1–8), or None when the image has none."""
    with Image.open(io.BytesIO(image)) as source:
        return _orientation(source)


def _orientation(source: Image.Image) -> int | None:
    # Pillow skips broken EXIF; a value outside 1–8 counts as no tag.
    value = source.getexif().get(EXIF_ORIENTATION)
    return value if isinstance(value, int) and 1 <= value <= 8 else None


def upright_original(image: bytes) -> bytes:
    """The image for a `vision:` variant (AC26).

    Upright from EXIF in its own format, or the original bytes when there is nothing to turn.
    """
    with Image.open(io.BytesIO(image)) as source:
        if _orientation(source) in (None, 1):
            return image
        image_format = source.format
        icc_profile = source.info.get("icc_profile")
        turned = ImageOps.exif_transpose(source)
    if icc_profile:
        turned.info["icc_profile"] = icc_profile
    # MPO is a JPEG with more pictures in it (Ultra HDR phone photos).
    if image_format in ("JPEG", "MPO"):
        return _encode(turned, "JPEG", quality=95)
    return _encode(turned, "PNG")


def preprocess(image: bytes) -> bytes:
    """Upright from EXIF, grayscale, at least 1 500 px wide, automatic contrast; as PNG."""
    with Image.open(io.BytesIO(image)) as source:
        # Phones store photos on their side and record the turn in EXIF (AC22).
        result = ImageOps.exif_transpose(source).convert("L")
    if result.width < MIN_WIDTH:
        result = ImageOps.scale(result, MIN_WIDTH / result.width, Image.Resampling.LANCZOS)
    return _encode(ImageOps.autocontrast(result), "PNG")


def _encode(image: Image.Image, image_format: str, **options: int) -> bytes:
    buffer = io.BytesIO()
    icc_profile = image.info.get("icc_profile")
    if icc_profile:
        image.save(buffer, format=image_format, icc_profile=icc_profile, **options)
    else:
        image.save(buffer, format=image_format, **options)
    return buffer.getvalue()


def _osd_values(output: str) -> tuple[int, float] | None:
    """`Rotate` and `Orientation confidence` from Tesseract's OSD output."""
    fields = dict(line.split(":", 1) for line in output.splitlines() if ":" in line)
    try:
        rotation, confidence = int(fields["Rotate"]), float(fields["Orientation confidence"])
    except (KeyError, ValueError):
        return None
    # A NaN would pass the confidence limit and is not valid JSON in the detail file.
    return (rotation, confidence) if math.isfinite(confidence) else None


def _run(args: Sequence[str], data: bytes) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(  # noqa: S603 - fixed command, the image goes to stdin
        args, input=data, capture_output=True, timeout=OCR_TIMEOUT_SECONDS, check=False
    )


class TesseractOcr:
    def __init__(self, run: RunCommand = _run) -> None:
        self._run = run

    def orient(self, image: bytes) -> Oriented:
        """Turn the image upright when OSD is sure enough; a failed detection keeps it (AC25)."""
        try:
            result = self._run(OSD_ARGS, image)
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
        return Oriented(_encode(turned, "PNG"), rotation, confidence)

    def read(self, image: bytes) -> str:
        try:
            result = self._run(TESSERACT_ARGS, image)
        except (OSError, subprocess.TimeoutExpired):
            raise OcrError("Tesseract did not run") from None
        if result.returncode != 0:
            raise OcrError(f"Tesseract exited with code {result.returncode}")
        return result.stdout.decode("utf-8", errors="replace")

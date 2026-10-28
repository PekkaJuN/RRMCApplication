"""An evaluation run: every variant over its receipts, with local detail files (PC6, PC7)."""

import json
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from PIL import Image

from evaluation.ocr import Ocr, OcrError, preprocess
from evaluation.ollama import Reader, ReadError
from evaluation.prompt import image_prompt, parse_answer, text_prompt
from evaluation.scoring import Row, Score, aggregate, score_receipt
from evaluation.truth import Receipt
from evaluation.variants import Variant, select_receipts

type Clock = Callable[[], float]
type Output = Callable[[str], None]
type ReceiptError = ReadError | Literal["image_error", "ocr_error"]


@dataclass(frozen=True)
class _Reading:
    ocr_text: str | None = None
    raw: str | None = None
    error: ReceiptError | None = None
    stats: dict[str, int] = field(default_factory=dict[str, int])


def run_evaluation(
    *,
    results_dir: Path,
    receipts: Sequence[Receipt],
    variants: Sequence[Variant],
    ocr: Ocr,
    reader: Reader,
    clock: Clock,
    out: Output,
) -> list[Row]:
    """Run the variants one after another, so each model is loaded once."""
    results_dir.mkdir(parents=True)
    # The only place that links an index to a file name; it stays in the evaluation folder.
    _write_json(results_dir / "receipts.json", {str(r.index): r.image.name for r in receipts})
    rows: list[Row] = []
    for variant in variants:
        selected = select_receipts(list(receipts), variant)
        folder = results_dir / variant.folder
        folder.mkdir()
        # The model load is not part of a receipt's time: the app loads it at start (FR-30).
        reader.warm_up(variant.model)
        scores: list[Score] = []
        for number, receipt in enumerate(selected, start=1):
            score, detail = _score_receipt(variant, receipt, ocr, reader, clock)
            _write_json(folder / f"{receipt.index}.json", detail)
            scores.append(score)
            out(f"{variant.text} {number}/{len(selected)} {score.seconds:.0f} s")
        rows.append(aggregate(variant.text, scores))
    return rows


def _score_receipt(
    variant: Variant, receipt: Receipt, ocr: Ocr, reader: Reader, clock: Clock
) -> tuple[Score, dict[str, Any]]:
    started = clock()
    reading = _read(variant, receipt, ocr, reader)
    seconds = clock() - started

    answer = parse_answer(reading.raw) if reading.raw is not None else None
    score = score_receipt(receipt.truth, answer, seconds)
    return score, {
        "variant": variant.text,
        "receipt": receipt.index,
        "ocr_text": reading.ocr_text,
        "raw_answer": reading.raw,
        "answer": answer.model_dump() if answer is not None else None,
        "error": reading.error,
        "scores": asdict(score),
        "seconds": seconds,
        "ollama": reading.stats,
    }


def _read(variant: Variant, receipt: Receipt, ocr: Ocr, reader: Reader) -> _Reading:
    """One receipt through one variant. A failure is recorded, never raised (AC12)."""
    try:
        image = receipt.image.read_bytes()
    except OSError:
        return _Reading(error="image_error")
    if variant.kind == "vision":
        result = reader.read(variant.model, image_prompt(), image=image)
        return _Reading(raw=result.text, error=result.error, stats=result.stats)
    try:
        ocr_text = ocr.read(preprocess(image))
    except (OcrError, OSError, Image.DecompressionBombError):
        # Pillow raises an OSError subclass for an image it cannot open.
        return _Reading(error="ocr_error")
    result = reader.read(variant.model, text_prompt(ocr_text), image=None)
    return _Reading(ocr_text=ocr_text, raw=result.text, error=result.error, stats=result.stats)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    # A model can answer the escape of a lone surrogate, which UTF-8 cannot encode.
    path.write_text(text, encoding="utf-8", errors="replace")

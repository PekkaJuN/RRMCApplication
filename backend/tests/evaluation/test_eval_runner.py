import io
import json
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from evaluation.ollama import ReadResult
from evaluation.prompt import image_prompt, text_prompt
from evaluation.runner import run_evaluation
from evaluation.truth import Receipt
from evaluation.variants import Variant, parse_variant
from tests.evaluation.eval_fakes import FakeClock, FakeOcr, FakeReader, make_receipts

EXIF_ORIENTATION = 0x0112


class Output:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def __call__(self, line: str) -> None:
        self.lines.append(line)


def run(
    tmp_path: Path,
    receipts: list[Receipt],
    variants: list[Variant],
    ocr: FakeOcr | None = None,
    reader: FakeReader | None = None,
    out: Output | None = None,
) -> tuple[Path, list[Any]]:
    results = tmp_path / "results" / "20260102-030405"
    rows = run_evaluation(
        results_dir=results,
        receipts=receipts,
        variants=variants,
        ocr=ocr or FakeOcr(),
        reader=reader or FakeReader(),
        clock=FakeClock(step=5.0),
        out=out or Output(),
    )
    return results, rows


def detail(results: Path, folder: str, index: int) -> dict[str, Any]:
    return json.loads((results / folder / f"{index}.json").read_text(encoding="utf-8"))


def test_ac5_ocr_variant_preprocesses_reads_and_writes_details(tmp_path: Path) -> None:
    receipts = make_receipts(tmp_path, 1)
    ocr = FakeOcr(text="MAITO 1,25")
    reader = FakeReader(results=[ReadResult(text="not json", stats={"eval_count": 7})])

    results, _ = run(tmp_path, receipts, [parse_variant("ocr:qwen2.5:7b")], ocr, reader)

    [sent] = ocr.images
    with Image.open(io.BytesIO(sent)) as image:
        assert (image.format, image.mode, image.width) == ("PNG", "L", 1500)
    assert reader.events == ["warm_up qwen2.5:7b", "read qwen2.5:7b"]
    assert reader.reads == [("qwen2.5:7b", text_prompt("MAITO 1,25"), None)]
    saved = detail(results, "ocr-qwen2.5-7b", 1)
    assert saved["variant"] == "ocr:qwen2.5:7b"
    assert saved["ocr_text"] == "MAITO 1,25"
    assert saved["raw_answer"] == "not json"
    assert saved["answer"] is None
    assert saved["error"] is None
    assert saved["scores"]["valid"] is False
    assert saved["seconds"] == 5.0
    assert saved["ollama"] == {"eval_count": 7}


def test_ac6_vision_variant_sends_the_original_image(tmp_path: Path) -> None:
    receipts = make_receipts(tmp_path, 1)
    ocr = FakeOcr()
    reader = FakeReader()

    results, _ = run(tmp_path, receipts, [parse_variant("vision:qwen2.5vl:7b")], ocr, reader)

    assert ocr.images == []
    assert reader.reads == [("qwen2.5vl:7b", image_prompt(), receipts[0].image.read_bytes())]
    saved = detail(results, "vision-qwen2.5vl-7b", 1)
    assert saved["ocr_text"] is None
    assert saved["answer"] == {
        "s": "Kauppa",
        "d": "2026-01-02",
        "t": 125,
        "l": [{"n": "MAITO", "a": 125, "r": False}],
    }
    assert saved["scores"]["total"] is True


def test_ac7_each_variant_reads_its_own_selection(tmp_path: Path) -> None:
    receipts = make_receipts(tmp_path, 5, full=(2, 4))
    reader = FakeReader()
    variants = [Variant("ocr", "m", limit=3), Variant("ocr", "n", full_only=True)]

    results, rows = run(tmp_path, receipts, variants, reader=reader)

    assert [model for model, _, _ in reader.reads] == ["m", "m", "m", "n", "n"]
    assert sorted(p.name for p in (results / "ocr-m").iterdir()) == ["1.json", "2.json", "3.json"]
    assert sorted(p.name for p in (results / "ocr-n").iterdir()) == ["2.json", "4.json"]
    assert [row.receipts for row in rows] == [3, 2]


def test_ac7_variants_run_one_after_another(tmp_path: Path) -> None:
    receipts = make_receipts(tmp_path, 2)
    reader = FakeReader()

    run(tmp_path, receipts, [Variant("ocr", "m"), Variant("vision", "v")], reader=reader)

    assert reader.events == ["warm_up m", "read m", "read m", "warm_up v", "read v", "read v"]


def test_ac11_invalid_answer_is_scored_and_the_run_goes_on(tmp_path: Path) -> None:
    receipts = make_receipts(tmp_path, 2)
    reader = FakeReader(results=[ReadResult(text='{"s": "Kauppa"}')])

    results, rows = run(tmp_path, receipts, [Variant("ocr", "m")], reader=reader)

    assert detail(results, "ocr-m", 1)["scores"]["valid"] is False
    assert detail(results, "ocr-m", 2)["scores"]["valid"] is True
    assert rows[0].valid == 50


def test_ac12_model_error_and_timeout_are_recorded(tmp_path: Path) -> None:
    receipts = make_receipts(tmp_path, 3)
    reader = FakeReader(
        results=[
            ReadResult(text=None, error="timeout"),
            ReadResult(text=None, error="model_error"),
        ]
    )

    results, rows = run(tmp_path, receipts, [Variant("vision", "v")], reader=reader)

    assert detail(results, "vision-v", 1)["error"] == "timeout"
    assert detail(results, "vision-v", 2)["error"] == "model_error"
    assert detail(results, "vision-v", 2)["raw_answer"] is None
    assert detail(results, "vision-v", 3)["error"] is None
    assert detail(results, "vision-v", 1)["seconds"] == 5.0
    assert rows[0].receipts == 3


def test_ac12_ocr_failure_is_recorded_without_a_model_call(tmp_path: Path) -> None:
    receipts = make_receipts(tmp_path, 1)
    reader = FakeReader()

    results, _ = run(tmp_path, receipts, [Variant("ocr", "m")], FakeOcr(fail=True), reader)

    assert reader.reads == []
    saved = detail(results, "ocr-m", 1)
    assert (saved["error"], saved["ocr_text"]) == ("ocr_error", None)
    assert saved["scores"]["valid"] is False


def test_ac12_image_that_cannot_be_opened_is_an_ocr_error(tmp_path: Path) -> None:
    receipts = make_receipts(tmp_path, 1)
    receipts[0].image.write_bytes(b"not an image")
    ocr = FakeOcr()

    results, _ = run(tmp_path, receipts, [Variant("ocr", "m")], ocr)

    assert ocr.images == []
    assert detail(results, "ocr-m", 1)["error"] == "ocr_error"


def test_ac5_progress_names_the_variant_count_and_seconds(tmp_path: Path) -> None:
    receipts = make_receipts(tmp_path, 2)
    out = Output()

    run(tmp_path, receipts, [Variant("ocr", "m")], out=out)

    assert out.lines == ["ocr:m 1/2 5 s", "ocr:m 2/2 5 s"]


def test_ac5_receipt_index_map_is_written_for_the_user(tmp_path: Path) -> None:
    receipts = make_receipts(tmp_path, 2)

    results, _ = run(tmp_path, receipts, [Variant("ocr", "m")])

    saved = json.loads((results / "receipts.json").read_text(encoding="utf-8"))
    assert saved == {"1": "r1.jpg", "2": "r2.jpg"}


def test_ac17_rows_aggregate_each_variant(tmp_path: Path) -> None:
    receipts = make_receipts(tmp_path, 2)

    _, rows = run(tmp_path, receipts, [Variant("ocr", "m"), Variant("vision", "v")])

    assert [(row.variant, row.receipts, row.total, row.median) for row in rows] == [
        ("ocr:m", 2, 100, 5.0),
        ("vision:v", 2, 100, 5.0),
    ]


@pytest.mark.parametrize("variant", [Variant("ocr", "m"), Variant("vision", "m")])
def test_ac12_image_file_that_cannot_be_read_is_an_image_error(
    tmp_path: Path, variant: Variant
) -> None:
    receipts = make_receipts(tmp_path, 2)
    receipts[0].image.unlink()
    reader = FakeReader()

    results, rows = run(tmp_path, receipts, [variant], reader=reader)

    saved = detail(results, variant.folder, 1)
    assert (saved["error"], saved["raw_answer"]) == ("image_error", None)
    assert saved["scores"]["valid"] is False
    assert len(reader.reads) == 1
    assert rows[0].receipts == 2


def test_ac12_image_too_large_for_pillow_is_an_ocr_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipts = make_receipts(tmp_path, 1)
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)

    results, _ = run(tmp_path, receipts, [Variant("ocr", "m")])

    assert detail(results, "ocr-m", 1)["error"] == "ocr_error"


def jpeg_on_its_side(orientation: int | None) -> bytes:
    """600 x 100 as stored; with tag 6 it is 100 x 600 upright."""
    exif = Image.Exif()
    if orientation is not None:
        exif[EXIF_ORIENTATION] = orientation
    buffer = io.BytesIO()
    Image.new("RGB", (600, 100), (200, 100, 50)).save(buffer, format="JPEG", exif=exif)
    return buffer.getvalue()


def test_ac22_ac24_ocr_detail_records_the_orientation(tmp_path: Path) -> None:
    receipts = make_receipts(tmp_path, 1)
    receipts[0].image.write_bytes(jpeg_on_its_side(6))
    ocr = FakeOcr(osd_rotation=90, osd_confidence=5.0)

    results, _ = run(tmp_path, receipts, [Variant("ocr", "m")], ocr)

    [oriented] = ocr.oriented
    with Image.open(io.BytesIO(oriented)) as image:
        assert (image.mode, image.width) == ("L", 1500)
        assert image.height > image.width
    assert ocr.images == [FakeOcr.TURNED]
    assert detail(results, "ocr-m", 1)["orientation"] == {
        "exif": 6,
        "osd_rotation": 90,
        "osd_confidence": 5.0,
    }


def test_ac23_ac25_ocr_detail_without_any_turn(tmp_path: Path) -> None:
    receipts = make_receipts(tmp_path, 1)

    results, _ = run(tmp_path, receipts, [Variant("ocr", "m")])

    assert detail(results, "ocr-m", 1)["orientation"] == {
        "exif": None,
        "osd_rotation": 0,
        "osd_confidence": None,
    }


def test_ac26_vision_image_is_turned_upright_from_exif(tmp_path: Path) -> None:
    receipts = make_receipts(tmp_path, 1)
    receipts[0].image.write_bytes(jpeg_on_its_side(6))
    reader = FakeReader()

    results, _ = run(tmp_path, receipts, [Variant("vision", "v")], reader=reader)

    [(_, _, sent)] = reader.reads
    assert sent is not None
    with Image.open(io.BytesIO(sent)) as image:
        assert (image.format, image.size) == ("JPEG", (100, 600))
    assert detail(results, "vision-v", 1)["orientation"] == {"exif": 6}


def test_ac26_vision_image_without_the_tag_is_sent_unchanged(tmp_path: Path) -> None:
    receipts = make_receipts(tmp_path, 1)
    reader = FakeReader()

    results, _ = run(tmp_path, receipts, [Variant("vision", "v")], reader=reader)

    assert reader.reads[0][2] == receipts[0].image.read_bytes()
    assert detail(results, "vision-v", 1)["orientation"] == {"exif": None}


def test_ac12_vision_image_that_cannot_be_opened_is_an_image_error(tmp_path: Path) -> None:
    receipts = make_receipts(tmp_path, 1)
    receipts[0].image.write_bytes(b"not an image")
    reader = FakeReader()

    results, _ = run(tmp_path, receipts, [Variant("vision", "v")], reader=reader)

    assert reader.reads == []
    assert detail(results, "vision-v", 1)["error"] == "image_error"


def jpeg_with_broken_exif(exif_body: bytes) -> bytes:
    """A valid JPEG with an Exif APP1 segment whose TIFF data is broken."""
    payload = b"Exif\x00\x00" + exif_body
    segment = b"\xff\xe1" + (len(payload) + 2).to_bytes(2, "big") + payload
    good = jpeg_on_its_side(None)
    return good[:2] + segment + good[2:]


@pytest.mark.parametrize("variant", [Variant("ocr", "m"), Variant("vision", "v")])
@pytest.mark.parametrize(
    "exif_body", [b"garbage-not-a-tiff-header", b"MM", b"MM\x00\x2a\xff\xff\xff\xff"]
)
def test_ac23_broken_exif_counts_as_no_tag(
    tmp_path: Path, variant: Variant, exif_body: bytes
) -> None:
    receipts = make_receipts(tmp_path, 1)
    receipts[0].image.write_bytes(jpeg_with_broken_exif(exif_body))

    results, _ = run(tmp_path, receipts, [variant])

    saved = detail(results, variant.folder, 1)
    assert saved["error"] is None
    assert saved["orientation"]["exif"] is None


def test_ac11_answer_with_a_lone_surrogate_is_still_written(tmp_path: Path) -> None:
    receipts = make_receipts(tmp_path, 1)
    # json.loads turns the escape "\ud800" in a model answer into a lone surrogate.
    reader = FakeReader(results=[ReadResult(text=json.loads('"\\ud800"'))])

    results, _ = run(tmp_path, receipts, [Variant("vision", "v")], reader=reader)

    assert detail(results, "vision-v", 1)["scores"]["valid"] is False

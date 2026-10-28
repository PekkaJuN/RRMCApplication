import json
from datetime import date
from pathlib import Path

import pytest

from evaluation.truth import (
    TEMPLATE,
    TruthFileError,
    collect_receipts,
    init_templates,
    load_truth,
)

VALID = {"store": "X", "date": "2026-01-02", "total_cents": 5, "line_count": 1}


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def add_receipt(folder: Path, name: str, truth: object | None = VALID) -> None:
    (folder / name).write_bytes(b"image")
    if truth is not None:
        write_json(folder / f"{name}.truth.json", truth)


def error_text(path: Path) -> str:
    with pytest.raises(TruthFileError) as caught:
        load_truth(path)
    return str(caught.value)


# --- AC1: templates ---------------------------------------------------------------------


def test_ac1_init_creates_a_template_only_for_images_without_a_truth_file(tmp_path: Path) -> None:
    (tmp_path / "a.jpg").write_bytes(b"image")
    (tmp_path / "b.png").write_bytes(b"image")
    (tmp_path / "c.txt").write_text("text")
    existing = tmp_path / "b.png.truth.json"
    write_json(existing, VALID)
    before = existing.read_bytes()

    created = init_templates(tmp_path)

    assert created == 1
    assert json.loads((tmp_path / "a.jpg.truth.json").read_text(encoding="utf-8")) == TEMPLATE
    assert existing.read_bytes() == before
    assert not (tmp_path / "c.txt.truth.json").exists()


def test_ac1_template_is_the_documented_format() -> None:
    assert TEMPLATE == {
        "store": "",
        "date": "YYYY-MM-DD",
        "total_cents": 0,
        "line_count": 0,
        "lines": [],
    }


def test_ac1_image_suffixes_are_case_insensitive(tmp_path: Path) -> None:
    (tmp_path / "A.JPEG").write_bytes(b"image")

    assert init_templates(tmp_path) == 1
    assert (tmp_path / "A.JPEG.truth.json").exists()


def test_ac1_folders_are_not_images(tmp_path: Path) -> None:
    (tmp_path / "results.jpg").mkdir()

    assert init_templates(tmp_path) == 0


# --- AC2: invalid truth files -----------------------------------------------------------


def test_ac2_string_total_is_refused_without_its_value(tmp_path: Path) -> None:
    path = tmp_path / "a.jpg.truth.json"
    write_json(path, {**VALID, "total_cents": "12,50"})

    assert error_text(path) == "Invalid truth file a.jpg.truth.json: total_cents must be an integer"


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({"total_cents": 12.5}, "total_cents must be an integer"),
        ({"total_cents": True}, "total_cents must be an integer"),
        ({"line_count": -1}, "line_count must not be negative"),
        ({"date": "2.1.2026"}, "date must be a date YYYY-MM-DD"),
        ({"store": ""}, "store must not be empty"),
        ({"store": 7}, "store must be text"),
        ({"lines": {}}, "lines must be a list"),
        ({"lines": [{"name": "A"}]}, "lines[0].amount_cents is required"),
        ({"lines": [{"name": "", "amount_cents": 1}]}, "lines[0].name must not be empty"),
        ({"total": 5}, "total is not a known field"),
    ],
)
def test_ac2_each_invalid_field_is_named(
    tmp_path: Path, change: dict[str, object], expected: str
) -> None:
    path = tmp_path / "a.jpg.truth.json"
    write_json(path, {**VALID, **change})

    assert error_text(path) == f"Invalid truth file a.jpg.truth.json: {expected}"


def test_ac2_missing_field_is_named(tmp_path: Path) -> None:
    path = tmp_path / "a.jpg.truth.json"
    write_json(path, {k: v for k, v in VALID.items() if k != "date"})

    assert error_text(path) == "Invalid truth file a.jpg.truth.json: date is required"


def test_ac2_not_json_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "a.jpg.truth.json"
    path.write_text("{store: SECRET-CONTENT", encoding="utf-8")

    assert error_text(path) == "Invalid truth file a.jpg.truth.json: not valid JSON"


def test_ac2_json_that_is_not_an_object_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "a.jpg.truth.json"
    write_json(path, [1, 2])

    assert error_text(path) == "Invalid truth file a.jpg.truth.json: must be a JSON object"


def test_ac2_valid_truth_file_loads(tmp_path: Path) -> None:
    path = tmp_path / "a.jpg.truth.json"
    write_json(path, {**VALID, "lines": [{"name": "PANTTIPALAUTUS", "amount_cents": -40}]})

    truth = load_truth(path)

    assert truth is not None
    assert truth.store == "X"
    assert truth.date == date(2026, 1, 2)
    assert truth.total_cents == 5
    assert truth.line_count == 1
    assert truth.lines is not None
    assert truth.lines[0].amount_cents == -40
    assert truth.is_full


def test_ac2_truth_without_lines_is_not_full(tmp_path: Path) -> None:
    path = tmp_path / "a.jpg.truth.json"
    write_json(path, VALID)

    truth = load_truth(path)

    assert truth is not None
    assert not truth.is_full


def test_ac2_invalid_file_stops_collection(tmp_path: Path) -> None:
    add_receipt(tmp_path, "a.jpg", {**VALID, "total_cents": "12,50"})
    add_receipt(tmp_path, "b.jpg")

    with pytest.raises(TruthFileError, match="a.jpg.truth.json: total_cents"):
        collect_receipts(tmp_path)


# --- AC3, AC4: skipped receipts ---------------------------------------------------------


def test_ac3_image_without_truth_file_is_skipped(tmp_path: Path) -> None:
    add_receipt(tmp_path, "a.jpg")
    add_receipt(tmp_path, "b.jpg", truth=None)

    collected = collect_receipts(tmp_path)

    assert [receipt.image.name for receipt in collected.receipts] == ["a.jpg"]
    assert collected.skipped == 1


def test_ac4_unfilled_template_is_skipped(tmp_path: Path) -> None:
    add_receipt(tmp_path, "a.jpg", TEMPLATE)

    assert load_truth(tmp_path / "a.jpg.truth.json") is None
    collected = collect_receipts(tmp_path)
    assert collected.receipts == []
    assert collected.skipped == 1


def test_ac3_receipts_are_in_name_order_with_indexes(tmp_path: Path) -> None:
    for name in ["c.jpg", "A.png", "b.jpg"]:
        add_receipt(tmp_path, name)

    collected = collect_receipts(tmp_path)

    assert [(r.index, r.image.name) for r in collected.receipts] == [
        (1, "A.png"),
        (2, "b.jpg"),
        (3, "c.jpg"),
    ]

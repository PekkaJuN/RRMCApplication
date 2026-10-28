import datetime
from pathlib import Path

import pytest

from evaluation.truth import Receipt, Truth, TruthLine
from evaluation.variants import Variant, VariantError, parse_variant, select_receipts


def receipt(index: int, *, full: bool = False) -> Receipt:
    lines = [TruthLine(name="A", amount_cents=1)] if full else None
    truth = Truth(
        store="X",
        date=datetime.date(2026, 1, 2),
        total_cents=1,
        line_count=1,
        lines=lines,
    )
    return Receipt(index=index, image=Path(f"{index}.jpg"), truth=truth)


@pytest.mark.parametrize(
    ("text", "kind", "model"),
    [
        ("ocr:qwen2.5:7b", "ocr", "qwen2.5:7b"),
        ("vision:qwen2.5vl:7b", "vision", "qwen2.5vl:7b"),
        ("ocr:m", "ocr", "m"),
    ],
)
def test_ac5_ac6_valid_variants_are_parsed(text: str, kind: str, model: str) -> None:
    variant = parse_variant(text)

    assert (variant.kind, variant.model, variant.text) == (kind, model, text)


def test_ac5_variant_folder_replaces_colons() -> None:
    assert parse_variant("ocr:qwen2.5:7b").folder == "ocr-qwen2.5-7b"


@pytest.mark.parametrize("text", ["ocr:gpt-oss:120b-cloud", "vision:x:cloud", "ocr:X:CLOUD"])
def test_ac8_cloud_models_are_refused(text: str) -> None:
    with pytest.raises(VariantError) as caught:
        parse_variant(text)

    assert str(caught.value) == f"Cloud models are not allowed: {text}"


@pytest.mark.parametrize("text", ["qwen2.5:7b", "audio:x", "ocr:", "ocr", "", "vision: "])
def test_ac9_malformed_variants_are_refused(text: str) -> None:
    with pytest.raises(VariantError) as caught:
        parse_variant(text)

    assert str(caught.value) == (
        f"Invalid variant: {text} (expected ocr:<model> or vision:<model>)"
    )


def test_ac7_limit_takes_the_first_receipts_in_order() -> None:
    receipts = [receipt(i) for i in range(1, 6)]

    selected = select_receipts(receipts, Variant("ocr", "m", limit=3))

    assert [r.index for r in selected] == [1, 2, 3]


def test_ac7_full_subset_takes_receipts_with_lines() -> None:
    receipts = [receipt(1), receipt(2, full=True), receipt(3), receipt(4, full=True), receipt(5)]

    selected = select_receipts(receipts, Variant("ocr", "n", full_only=True))

    assert [r.index for r in selected] == [2, 4]


def test_ac7_without_options_every_receipt_is_taken() -> None:
    receipts = [receipt(i) for i in range(1, 4)]

    assert select_receipts(receipts, Variant("ocr", "m")) == receipts


def test_ac7_subset_is_applied_before_the_limit() -> None:
    receipts = [receipt(1), receipt(2, full=True), receipt(3, full=True)]

    selected = select_receipts(receipts, Variant("ocr", "m", limit=1, full_only=True))

    assert [r.index for r in selected] == [2]

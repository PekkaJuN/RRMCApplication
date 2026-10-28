from dataclasses import replace
from typing import Any

from evaluation.report import render_summary
from evaluation.scoring import Row

BASE_ROW = Row(
    variant="ocr:qwen2.5:7b",
    receipts=10,
    valid=100,
    total=90,
    date=100,
    store=80,
    consistent=70,
    lines=60,
    amounts=0.754,
    names=0.9333,
    median=105.4,
    p90=140.0,
    max=200.0,
    in_time=90,
    meets=True,
)


def make_row(**changes: Any) -> Row:
    return replace(BASE_ROW, **changes)


def table_row(summary: str, variant: str) -> list[str]:
    [line] = [line for line in summary.splitlines() if line.startswith(f"| {variant} |")]
    return [cell.strip() for cell in line.strip("|").split("|")]


def test_ac17_row_shows_the_aggregates_and_the_criteria() -> None:
    summary = render_summary("20260102-030405", [make_row()], skipped=0)

    assert table_row(summary, "ocr:qwen2.5:7b") == [
        "ocr:qwen2.5:7b",
        "10",
        "100 %",
        "90 %",
        "100 %",
        "80 %",
        "70 %",
        "60 %",
        "0.75",
        "0.93",
        "105",
        "140",
        "200",
        "90 %",
        "yes",
    ]


def test_ac17_variant_below_the_criteria_says_no() -> None:
    summary = render_summary("20260102-030405", [make_row(total=80, meets=False)], skipped=0)

    cells = table_row(summary, "ocr:qwen2.5:7b")
    assert cells[3] == "80 %"
    assert cells[-1] == "no"


def test_ac17_missing_values_are_shown_as_a_dash() -> None:
    row = make_row(receipts=0, amounts=None, names=None, median=None, p90=None, max=None)

    cells = table_row(render_summary("x", [row], skipped=0), "ocr:qwen2.5:7b")

    assert cells[8:13] == ["–", "–", "–", "–", "–"]


def test_ac3_summary_counts_the_skipped_receipts() -> None:
    summary = render_summary("20260102-030405", [make_row()], skipped=1)

    assert "Skipped without truth file: 1" in summary
    assert "Run: 20260102-030405" in summary


def test_ac17_summary_states_the_criteria() -> None:
    summary = render_summary("x", [make_row()], skipped=0)

    assert "valid 100 %, total ≥ 90 %, date ≥ 95 %, in_time ≥ 90 %" in summary


def test_ac17_one_row_per_variant_in_order() -> None:
    rows = [make_row(variant="ocr:m"), make_row(variant="vision:v")]

    summary = render_summary("x", rows, skipped=0)

    assert summary.index("| ocr:m |") < summary.index("| vision:v |")

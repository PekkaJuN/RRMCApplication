import datetime
from dataclasses import replace
from difflib import SequenceMatcher

import pytest

from evaluation.prompt import Answer, AnswerLine
from evaluation.scoring import (
    Score,
    aggregate,
    score_lines,
    score_receipt,
)
from evaluation.truth import Truth, TruthLine

TRUTH = Truth(
    store="K-Market Esimerkki",
    date=datetime.date(2026, 1, 2),
    total_cents=1185,
    line_count=4,
)
FOUR_LINES = [AnswerLine(n=f"L{a}", a=a, r=False) for a in (125, 249, 212, 599)]


def answer(**changes: object) -> Answer:
    values: dict[str, object] = {
        "s": "K-MARKET  ESIMERKKI OY",
        "d": "2026-01-02",
        "t": 1185,
        "l": FOUR_LINES,
    }
    return Answer.model_validate({**values, **changes})


def full_truth(lines: list[tuple[str, int]], total: int = 1185) -> Truth:
    return Truth(
        store="X",
        date=datetime.date(2026, 1, 2),
        total_cents=total,
        line_count=len(lines),
        lines=[TruthLine(name=n, amount_cents=a) for n, a in lines],
    )


# --- AC13, AC14 -------------------------------------------------------------------------


def test_ac13_right_fields_are_true() -> None:
    score = score_receipt(TRUTH, answer(), seconds=60.0)

    assert (score.valid, score.total, score.date, score.store, score.consistent, score.lines) == (
        True,
        True,
        True,
        True,
        True,
        True,
    )
    assert (score.seconds, score.in_time) == (60.0, True)


def test_ac14_wrong_fields_are_false() -> None:
    three = [AnswerLine(n="A", a=a, r=False) for a in (300, 300, 400)]
    score = score_receipt(TRUTH, answer(t=1158, d="2026-02-01", s="S-Market", l=three), 60.0)

    assert score.valid
    assert (score.total, score.date, score.store, score.consistent, score.lines) == (
        False,
        False,
        False,
        False,
        False,
    )


@pytest.mark.parametrize(
    ("store", "expected"),
    [("k-market esimerkki", True), ("Esimerkki", True), ("", False), ("   ", False)],
)
def test_ac13_store_is_compared_normalized_by_containment(store: str, expected: bool) -> None:
    assert score_receipt(TRUTH, answer(s=store), 1.0).store is expected


def test_ac13_truth_store_contained_in_answer_matches() -> None:
    truth = TRUTH.model_copy(update={"store": "Esimerkki"})

    assert score_receipt(truth, answer(s="K-Market Esimerkki"), 1.0).store


# --- AC11: invalid answer ---------------------------------------------------------------


def test_ac11_invalid_answer_is_wrong_everywhere_but_time() -> None:
    score = score_receipt(full_truth([("A", 1185)]), None, seconds=200.0)

    assert not any(
        (score.valid, score.total, score.date, score.store, score.consistent, score.lines)
    )
    assert (score.amounts, score.names) == (0.0, 0.0)
    assert (score.seconds, score.in_time) == (200.0, False)


def test_ac11_invalid_answer_without_lines_has_no_line_scores() -> None:
    score = score_receipt(TRUTH, None, seconds=1.0)

    assert (score.amounts, score.names) == (None, None)


# --- AC15, AC16 -------------------------------------------------------------------------


def test_ac15_amounts_f1_and_names_on_normalized_names() -> None:
    truth_lines = [
        TruthLine(name="MAITO 1L", amount_cents=125),
        TruthLine(name="LEIPÄ", amount_cents=249),
        TruthLine(name="OMENA", amount_cents=212),
        TruthLine(name="KAHVI 500G", amount_cents=599),
    ]
    answer_lines = [
        AnswerLine(n="Maito 1l", a=125, r=False),
        AnswerLine(n="LEIPA", a=249, r=False),
        AnswerLine(n="KAHVI 500G", a=599, r=False),
        AnswerLine(n="X", a=300, r=False),
    ]

    amounts, names = score_lines(truth_lines, answer_lines)

    assert amounts == pytest.approx(0.75)
    leipa = SequenceMatcher(None, "leipä", "leipa").ratio()
    assert names == pytest.approx((1.0 + leipa + 1.0) / 3)


def test_ac15_repeated_amounts_count_as_a_multiset() -> None:
    truth_lines = [TruthLine(name="A", amount_cents=100), TruthLine(name="B", amount_cents=100)]
    answer_lines = [AnswerLine(n="A", a=100, r=False)]

    amounts, names = score_lines(truth_lines, answer_lines)

    # precision 1/1, recall 1/2
    assert amounts == pytest.approx(2 / 3)
    assert names == pytest.approx(1.0)


def test_ac15_no_matching_amount_gives_zero_and_no_names() -> None:
    amounts, names = score_lines([TruthLine(name="A", amount_cents=1)], [])

    assert (amounts, names) == (0.0, None)


def test_ac15_line_scores_only_for_the_full_subset() -> None:
    score = score_receipt(TRUTH, answer(), 1.0)

    assert (score.amounts, score.names) == (None, None)


def test_ac15_full_receipt_gets_line_scores() -> None:
    truth = full_truth([("L125", 125), ("L249", 249), ("L212", 212), ("L599", 599)])

    score = score_receipt(truth, answer(), 1.0)

    assert (score.amounts, score.names) == (1.0, 1.0)


def test_ac16_deposit_refund_matches_and_counts_in_the_sum() -> None:
    truth = full_truth([("OLUT", 229), ("PANTTIPALAUTUS", -40)], total=189)
    lines = [AnswerLine(n="OLUT", a=229, r=False), AnswerLine(n="PANTTIPALAUTUS", a=-40, r=True)]

    score = score_receipt(truth, answer(t=189, l=lines), 1.0)

    assert score.amounts == 1.0
    assert score.consistent


# --- AC17: aggregates -------------------------------------------------------------------


def make_score(*, total: bool = True, seconds: float = 60.0, valid: bool = True) -> Score:
    return Score(
        valid=valid,
        total=total and valid,
        date=valid,
        store=valid,
        consistent=valid,
        lines=valid,
        amounts=None,
        names=None,
        seconds=seconds,
        in_time=seconds <= 180,
    )


TIMES = [60.0, 70.0, 80.0, 90.0, 100.0, 110.0, 120.0, 130.0, 140.0, 200.0]


def test_ac17_aggregate_meets_the_criteria() -> None:
    scores = [make_score(total=i != 0, seconds=s) for i, s in enumerate(TIMES)]

    row = aggregate("ocr:m", scores)

    assert (row.receipts, row.valid, row.total, row.date, row.in_time) == (10, 100, 90, 100, 90)
    assert (row.median, row.p90, row.max) == (105.0, 140.0, 200.0)
    assert row.meets


def test_ac17_eight_totals_do_not_meet_the_criteria() -> None:
    scores = [make_score(total=i > 1, seconds=s) for i, s in enumerate(TIMES)]

    row = aggregate("ocr:m", scores)

    assert row.total == 80
    assert not row.meets


def test_ac17_accuracy_is_a_share_of_valid_receipts() -> None:
    scores = [make_score(), make_score(), make_score(total=False), make_score(valid=False)]

    row = aggregate("ocr:m", scores)

    assert (row.valid, row.total, row.date) == (75, 67, 100)
    assert not row.meets


def test_ac17_line_means_skip_receipts_without_values() -> None:
    scores = [
        replace(make_score(), amounts=0.5, names=1.0),
        replace(make_score(), amounts=1.0, names=None),
        make_score(),
    ]

    row = aggregate("ocr:m", scores)

    assert (row.amounts, row.names) == (0.75, 1.0)


def test_ac17_no_receipts_gives_empty_row() -> None:
    row = aggregate("ocr:m", [])

    assert (row.receipts, row.valid, row.total, row.median, row.amounts) == (0, 0, 0, None, None)
    assert not row.meets


def test_ac17_all_invalid_gives_zero_accuracy() -> None:
    row = aggregate("ocr:m", [make_score(valid=False)])

    assert (row.valid, row.total, row.consistent) == (0, 0, 0)


def test_ac17_criteria_use_exact_shares_not_rounded_percentages() -> None:
    scores = [make_score() for _ in range(199)] + [make_score(valid=False)]

    row = aggregate("ocr:m", scores)

    assert row.valid == 100
    assert not row.meets


def test_ac17_total_just_below_90_percent_does_not_meet() -> None:
    # 179 of 200 is 89.5 %: shown as 90 %, but below the criterion.
    scores = [make_score(total=i < 179) for i in range(200)]

    row = aggregate("ocr:m", scores)

    assert row.total == 90
    assert not row.meets

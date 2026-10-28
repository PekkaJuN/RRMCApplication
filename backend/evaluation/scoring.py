"""Scores per receipt, aggregates per variant and the decision criteria (PC5, Metrics)."""

import math
import statistics
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher

from app.categorization.names import normalize_key
from evaluation.prompt import Answer, AnswerLine
from evaluation.truth import Truth, TruthLine

TIME_LIMIT_SECONDS = 180.0
# Decision criteria (whole percent): the only place these numbers live.
MIN_VALID = 100
MIN_TOTAL = 90
MIN_DATE = 95
MIN_IN_TIME = 90


@dataclass(frozen=True)
class Score:
    valid: bool
    total: bool
    date: bool
    store: bool
    consistent: bool
    lines: bool
    # None outside the full subset; names also when no line matched by amount.
    amounts: float | None
    names: float | None
    seconds: float
    in_time: bool


@dataclass(frozen=True)
class Row:
    variant: str
    receipts: int
    valid: int
    total: int
    date: int
    store: int
    consistent: int
    lines: int
    amounts: float | None
    names: float | None
    median: float | None
    p90: float | None
    max: float | None
    in_time: int
    meets: bool


def score_receipt(truth: Truth, answer: Answer | None, seconds: float) -> Score:
    in_time = seconds <= TIME_LIMIT_SECONDS
    if answer is None:
        zero = 0.0 if truth.is_full else None
        return Score(False, False, False, False, False, False, zero, zero, seconds, in_time)
    amounts = names = None
    if truth.lines:
        amounts, names = score_lines(truth.lines, answer.l)
    return Score(
        valid=True,
        total=answer.t == truth.total_cents,
        date=answer.d == truth.date.isoformat(),
        store=_same_store(truth.store, answer.s),
        consistent=sum(line.a for line in answer.l) == answer.t,
        lines=len(answer.l) == truth.line_count,
        amounts=amounts,
        names=names,
        seconds=seconds,
        in_time=in_time,
    )


def score_lines(
    truth_lines: Sequence[TruthLine], answer_lines: Sequence[AnswerLine]
) -> tuple[float, float | None]:
    """F1 of the amounts as multisets, and the mean name similarity of lines paired by amount."""
    truth_amounts = Counter(line.amount_cents for line in truth_lines)
    answer_amounts = Counter(line.a for line in answer_lines)
    matched = (truth_amounts & answer_amounts).total()
    if matched == 0:
        return 0.0, None
    precision = matched / len(answer_lines)
    recall = matched / len(truth_lines)
    f1 = 2 * precision * recall / (precision + recall)

    unused = list(answer_lines)
    similarities: list[float] = []
    for truth_line in truth_lines:
        pair = next((a for a in unused if a.a == truth_line.amount_cents), None)
        if pair is None:
            continue
        unused.remove(pair)
        similarities.append(
            SequenceMatcher(None, normalize_key(truth_line.name), normalize_key(pair.n)).ratio()
        )
    return f1, statistics.fmean(similarities)


def aggregate(variant: str, scores: Sequence[Score]) -> Row:
    valid = [s for s in scores if s.valid]
    times = sorted(s.seconds for s in scores)

    def share_of_valid(metric: Callable[[Score], bool]) -> int:
        return _percent(sum(metric(s) for s in valid), len(valid))

    return Row(
        variant=variant,
        receipts=len(scores),
        valid=_percent(len(valid), len(scores)),
        total=share_of_valid(lambda s: s.total),
        date=share_of_valid(lambda s: s.date),
        store=share_of_valid(lambda s: s.store),
        consistent=share_of_valid(lambda s: s.consistent),
        lines=share_of_valid(lambda s: s.lines),
        amounts=_mean([s.amounts for s in scores]),
        names=_mean([s.names for s in scores]),
        median=statistics.median(times) if times else None,
        p90=times[math.ceil(0.9 * len(times)) - 1] if times else None,
        max=times[-1] if times else None,
        in_time=_percent(sum(s.in_time for s in scores), len(scores)),
        meets=_meets_criteria(scores, valid),
    )


def _meets_criteria(scores: Sequence[Score], valid: Sequence[Score]) -> bool:
    """Compared on exact counts: 199 valid of 200 rounds to 100 % but is not 100 %."""

    def reaches(part: int, whole: int, minimum: int) -> bool:
        return whole > 0 and 100 * part >= minimum * whole

    return (
        reaches(len(valid), len(scores), MIN_VALID)
        and reaches(sum(s.total for s in valid), len(valid), MIN_TOTAL)
        and reaches(sum(s.date for s in valid), len(valid), MIN_DATE)
        and reaches(sum(s.in_time for s in scores), len(scores), MIN_IN_TIME)
    )


def _same_store(truth: str, answer: str) -> bool:
    expected, given = normalize_key(truth), normalize_key(answer)
    # An empty answer is "contained" in every name; it is never a match.
    return bool(given) and (expected in given or given in expected)


def _percent(part: int, whole: int) -> int:
    # Half up, not Python's round-half-to-even.
    return math.floor(100 * part / whole + 0.5) if whole else 0


def _mean(values: Sequence[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return statistics.fmean(present) if present else None

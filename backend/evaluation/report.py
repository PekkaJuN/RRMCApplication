"""The summary printed at the end and saved as `summary.md` (PC6).

It holds aggregates only: never a file name or anything read from a receipt (AC18).
"""

from collections.abc import Sequence

from evaluation.scoring import MIN_DATE, MIN_IN_TIME, MIN_TOTAL, MIN_VALID, Row

_HEADER = (
    "Variant",
    "Receipts",
    "valid",
    "total",
    "date",
    "store",
    "consistent",
    "lines",
    "amounts",
    "names",
    "median s",
    "p90 s",
    "max s",
    "in_time",
    "meets criteria",
)
_MISSING = "–"


def render_summary(run_id: str, rows: Sequence[Row], skipped: int) -> str:
    lines = [
        "# Evaluation summary",
        "",
        f"Run: {run_id}",
        f"Skipped without truth file: {skipped}",
        "",
        _table_line(_HEADER),
        _table_line(["---"] * len(_HEADER)),
        *(_table_line(_cells(row)) for row in rows),
        "",
        f"Criteria: valid {MIN_VALID} %, total ≥ {MIN_TOTAL} %, date ≥ {MIN_DATE} %, "
        f"in_time ≥ {MIN_IN_TIME} %.",
        "",
    ]
    return "\n".join(lines)


def _cells(row: Row) -> list[str]:
    return [
        row.variant,
        str(row.receipts),
        *(_percent(v) for v in (row.valid, row.total, row.date, row.store, row.consistent)),
        _percent(row.lines),
        _decimal(row.amounts),
        _decimal(row.names),
        _seconds(row.median),
        _seconds(row.p90),
        _seconds(row.max),
        _percent(row.in_time),
        "yes" if row.meets else "no",
    ]


def _table_line(cells: Sequence[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _percent(value: int) -> str:
    return f"{value} %"


def _decimal(value: float | None) -> str:
    return _MISSING if value is None else f"{value:.2f}"


def _seconds(value: float | None) -> str:
    return _MISSING if value is None else f"{value:.0f}"

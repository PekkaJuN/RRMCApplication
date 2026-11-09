"""PDF files of the totals and the budget comparison (PDF export spec PC4–PC7, PC11, P6).

reportlab's platypus lays out the pages (ADR 0005): tables repeat their heading rows on a
new page, and text cells are paragraphs, so a long name wraps inside its column.
"""

import io
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    Flowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app import texts
from app.calculation.period import Period, Unit
from app.calculation.period_totals import PeriodTotals
from app.export.exporter import ComparisonReport, ExportFile, TotalsReport
from app.export.finnish import column_heading, day, money
from app.export.report import (
    ReportRow,
    expanded_rows,
    has_lines,
    has_period_block,
    period_rows,
)

PageSize = tuple[float, float]

MEDIA_TYPE = "application/pdf"
MARGIN = 15 * mm
# The padding reportlab's page frame keeps inside the margins.
FRAME_PADDING = 6
FONT, BOLD = "Helvetica", "Helvetica-Bold"
TEXT_SIZE = 10
HEADING_SIZE = 9
FOOTER_SIZE = 9
BLOCK_HEADING_SIZE = 11
INDENT = 12
CELL_PADDING = 3
ROW_PADDING = 2
BLOCK_GAP = 10
# The share of the table width for `Kategoria`: weekly table, monthly block, comparison.
NAME_SHARE = 0.3
BLOCK_NAME_SHARE = 0.7
COMPARISON_NAME_SHARE = 0.4
TOTALS_TITLES: dict[Unit, str] = {"week": texts.WEEKLY_TITLE, "month": texts.MONTHLY_TITLE}
TOTALS_NAMES: dict[Unit, str] = {"week": "summat_viikot", "month": "summat_kuukaudet"}

_TITLE = ParagraphStyle("title", fontName=BOLD, fontSize=14, leading=18, spaceAfter=4)
_LINE = ParagraphStyle("line", fontName=FONT, fontSize=TEXT_SIZE, leading=14)
_HEADING = ParagraphStyle("heading", fontName=BOLD, fontSize=HEADING_SIZE, leading=11)
_HEADING_RIGHT = ParagraphStyle("heading_right", _HEADING, alignment=TA_RIGHT)
_NAME = ParagraphStyle("name", fontName=FONT, fontSize=TEXT_SIZE, leading=12)
_NAME_BOLD = ParagraphStyle("name_bold", _NAME, fontName=BOLD)
_NAME_INDENTED = ParagraphStyle("name_indented", _NAME, leftIndent=INDENT)
_AMOUNT = ParagraphStyle("amount", _NAME, alignment=TA_RIGHT)
_AMOUNT_BOLD = ParagraphStyle("amount_bold", _AMOUNT, fontName=BOLD)


class PdfExporter:
    def totals_report(self, report: TotalsReport, by: Unit) -> ExportFile:
        """Weekly: one landscape table. Monthly: portrait, one block per month (PC4)."""
        totals = report.totals
        page_size = landscape(A4) if by == "week" else A4

        def make_story() -> list[Flowable]:
            story = _header(TOTALS_TITLES[by], totals.period, report.created)
            story += _counts(
                (
                    texts.unreviewed_in_period(report.unreviewed_receipts),
                    report.unreviewed_receipts,
                ),
                (texts.undated_left_out(report.undated_receipts), report.undated_receipts),
            )
            if not has_lines(totals):
                story.append(Paragraph(texts.NO_PURCHASES, _LINE))
            elif by == "week":
                headings = [column_heading(column, by) for column in totals.weeks]
                rows = _money_rows(expanded_rows(totals, by))
                story.append(_amount_table(headings, rows, page_size))
            else:
                story += _month_blocks(totals, page_size)
            return story

        name = f"{TOTALS_NAMES[by]}_{totals.period.first}_{totals.period.last}.pdf"
        return ExportFile(name, MEDIA_TYPE, _build(make_story, page_size, TOTALS_TITLES[by]))

    def comparison_report(self, report: ComparisonReport) -> ExportFile:
        """The Vertailu page's month table on a portrait page (PC5)."""
        comparison = report.comparison
        kind = texts.MID_PERIOD if report.kind == "mid" else texts.CALENDAR_MONTH
        rows = [
            _TextRow(
                row.name if row.name is not None else texts.NO_CATEGORY,
                level=0,
                bold=False,
                cells=_comparison_cells(row.budget_cents, row.actual_cents, row.remaining_cents),
            )
            for row in comparison.rows
        ]
        total = comparison.total
        rows.append(
            _TextRow(
                texts.TOTAL,
                level=0,
                bold=True,
                cells=_comparison_cells(
                    total.budget_cents, total.actual_cents, total.remaining_cents
                ),
            )
        )

        def make_story() -> list[Flowable]:
            story = _header(texts.COMPARISON_TITLE, comparison.period, report.created)
            story.insert(2, Paragraph(escape(f"{texts.PERIOD_KIND} {kind}"), _LINE))
            story += _counts(
                (
                    texts.unreviewed_left_out(report.unreviewed_receipts),
                    report.unreviewed_receipts,
                ),
                (texts.undated_left_out(report.undated_receipts), report.undated_receipts),
            )
            story.append(
                _amount_table(texts.COMPARISON_COLUMNS, rows, A4, name_share=COMPARISON_NAME_SHARE)
            )
            return story

        prefix = "vertailu_15-14" if report.kind == "mid" else "vertailu"
        name = f"{prefix}_{comparison.period.first}.pdf"
        return ExportFile(name, MEDIA_TYPE, _build(make_story, A4, texts.COMPARISON_TITLE))


def _header(title: str, period: Period, created: date) -> list[Flowable]:
    return [
        Paragraph(escape(title), _TITLE),
        Paragraph(escape(f"{texts.PERIOD_LABEL} {day(period.start)}–{day(period.end)}"), _LINE),
        Paragraph(escape(f"{texts.CREATED} {day(created)}"), _LINE),
    ]


def _counts(*counts: tuple[str, int]) -> list[Flowable]:
    """The count lines of the page, each only when it is not 0, then a gap to the table."""
    story: list[Flowable] = [Paragraph(escape(text), _LINE) for text, count in counts if count]
    story.append(Spacer(1, 8))
    return story


def _month_blocks(totals: PeriodTotals, page_size: PageSize) -> list[Flowable]:
    """A block per month column, then `Koko jakso` for a period over a month (PC4)."""
    rows = expanded_rows(totals, "month")
    blocks = [
        (column_heading(column, "month"), [_row_at(row, index) for row in rows])
        for index, column in enumerate(totals.months)
    ]
    if has_period_block(totals.period):
        blocks.append((texts.PERIOD_BLOCK, period_rows(totals)))
    width, height = _content_size(page_size)
    story: list[Flowable] = []
    for heading, block_rows in blocks:
        table = _amount_table(
            [texts.AMOUNT],
            _money_rows(block_rows),
            page_size,
            name_share=BLOCK_NAME_SHARE,
            block=heading,
        )
        _, table_height = table.wrap(width, height)
        # A block that fits on a page moves whole to the next page. A taller one starts at
        # once and continues with the mark: moving it first would leave a page empty.
        story.append(KeepTogether([table]) if table_height <= height else table)
        story.append(Spacer(1, BLOCK_GAP))
    return story


def _content_size(page_size: PageSize) -> PageSize:
    """The space inside the margins and reportlab's frame padding."""
    width, height = page_size
    return width - 2 * (MARGIN + FRAME_PADDING), height - 2 * (MARGIN + FRAME_PADDING)


def _row_at(row: ReportRow, index: int) -> ReportRow:
    return ReportRow(row.name, row.level, row.bold, [row.amounts[index]])


@dataclass(frozen=True)
class _TextRow:
    """A table row as text: the name and one cell per amount column."""

    name: str
    level: int
    bold: bool
    cells: list[str]


def _money_rows(rows: Sequence[ReportRow]) -> list[_TextRow]:
    return [
        _TextRow(row.name, row.level, row.bold, [money(amount) for amount in row.amounts])
        for row in rows
    ]


def _comparison_cells(budget: int, actual: int, remaining: int) -> list[str]:
    """A negative remaining also says `Ylitetty`, so its meaning needs no color (PC5)."""
    over = f" {texts.OVER_BUDGET}" if remaining < 0 else ""
    return [money(budget), money(actual), money(remaining) + over]


def _amount_table(
    headings: Sequence[str],
    rows: Sequence[_TextRow],
    page_size: PageSize,
    *,
    name_share: float = NAME_SHARE,
    block: str | None = None,
) -> Table:
    """`Kategoria` and one amount column per heading; bold rows for groups and totals.

    A `block` heading becomes a first row over the whole width, repeated as
    `<block> (jatkuu)` when the table continues on the next page.
    """
    data: list[list[Any]] = []
    if block is not None:
        data.append([_BlockHeading(block)] + [""] * len(headings))
    heading_row = len(data)
    data.append(
        [Paragraph(texts.CATEGORY, _HEADING)]
        + [Paragraph(escape(heading), _HEADING_RIGHT) for heading in headings]
    )
    for row in rows:
        name_style = _NAME_BOLD if row.bold else _NAME_INDENTED if row.level else _NAME
        amount_style = _AMOUNT_BOLD if row.bold else _AMOUNT
        data.append(
            [Paragraph(escape(row.name), name_style)]
            + [Paragraph(escape(cell), amount_style) for cell in row.cells]
        )
    width, _ = _content_size(page_size)
    name_width = width * name_share
    amount_width = (width - name_width) / len(headings)
    commands: list[Any] = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("VALIGN", (0, heading_row), (-1, heading_row), "BOTTOM"),
        ("LEFTPADDING", (0, 0), (-1, -1), CELL_PADDING),
        ("RIGHTPADDING", (0, 0), (-1, -1), CELL_PADDING),
        ("TOPPADDING", (0, 0), (-1, -1), ROW_PADDING),
        ("BOTTOMPADDING", (0, 0), (-1, -1), ROW_PADDING),
        ("LINEBELOW", (0, heading_row), (-1, heading_row), 0.75, "black"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.75, "black"),
    ]
    if block is not None:
        commands.append(("SPAN", (0, 0), (-1, 0)))
    table = Table(
        data,
        colWidths=[name_width] + [amount_width] * len(headings),
        repeatRows=heading_row + 1,
        hAlign="LEFT",
    )
    table.setStyle(TableStyle(commands))
    return table


class _BlockHeading(Flowable):
    """A month block's heading. The table repeats this same object on each page it runs
    over, so every drawing after the first is a continuation and gets the mark."""

    def __init__(self, text: str) -> None:
        super().__init__()
        self._text = text
        self._drawn = False

    def wrap(self, aW: float, aH: float) -> tuple[float, float]:  # noqa: N803 - reportlab names
        return aW, BLOCK_HEADING_SIZE + 3

    def draw(self) -> None:
        text = f"{self._text} {texts.CONTINUED}" if self._drawn else self._text
        self._drawn = True
        self.canv.setFont(BOLD, BLOCK_HEADING_SIZE)
        self.canv.drawString(0, 3, text)


def _build(
    make_story: Callable[[], list[Flowable]], page_size: tuple[float, float], title: str
) -> bytes:
    """Lays the story out twice: the first pass counts the pages for `Sivu n/total`.

    Layout splits the flowables, so each pass gets a fresh story.
    """
    _, pages = _render(make_story(), page_size, title, total=None)
    content, _ = _render(make_story(), page_size, title, total=pages)
    return content


def _render(
    story: list[Flowable], page_size: tuple[float, float], title: str, total: int | None
) -> tuple[bytes, int]:
    """The file and its number of pages."""
    seen = [0]
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
        # The title only: no author or user name leaves the app in a file (PC11).
        title=title,
        author="",
        creator="",
        producer="",
        subject="",
        keywords=[],
    )

    def footer(canvas: Canvas, _document: SimpleDocTemplate) -> None:
        number = canvas.getPageNumber()
        seen[0] = number
        canvas.setFont(FONT, FOOTER_SIZE)
        canvas.drawRightString(
            page_size[0] - MARGIN, MARGIN * 0.6, texts.page_number(number, total or number)
        )

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue(), seen[0]

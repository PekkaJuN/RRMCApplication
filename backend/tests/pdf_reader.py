"""Reads a PDF file back for tests: pages, text, character sizes and boxes, metadata.

The PDF export tests check the real file, not the code that builds it (ADR 0005).
"""

import io
from collections.abc import Iterable
from dataclasses import dataclass
from typing import cast

from pdfminer.high_level import extract_pages
from pdfminer.layout import LTChar, LTComponent, LTPage, LTTextContainer
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfparser import PDFParser


@dataclass(frozen=True)
class Char:
    text: str
    size: float
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass(frozen=True)
class Page:
    width: float
    height: float
    lines: list[str]
    chars: list[Char]

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    def rows(self) -> list[str]:
        """The characters of each baseline, top to bottom; cells joined with ` | `.

        A gap wider than `CELL_GAP` points starts a new cell, so a table row reads as
        `Ruoka | 1,25 € | 3,00 €`.
        """
        return [text for text, _ in self.rows_with_x()]

    def rows_with_x(self) -> list[tuple[str, float]]:
        """`rows()` with the left edge of each row's first character."""
        baselines: dict[int, list[Char]] = {}
        for char in self.chars:
            if char.text.strip():
                baselines.setdefault(round(char.y0), []).append(char)
        result: list[tuple[str, float]] = []
        for y in sorted(baselines, reverse=True):
            ordered = sorted(baselines[y], key=lambda item: item.x0)
            cells: list[str] = []
            previous: Char | None = None
            for char in ordered:
                if previous is None or char.x0 - previous.x1 > CELL_GAP:
                    cells.append(char.text)
                else:
                    cells[-1] += " " * (char.x0 - previous.x1 > SPACE_GAP) + char.text
                previous = char
            result.append((" | ".join(cells), ordered[0].x0))
        return result

    def row_x(self, start: str) -> float:
        """The left edge of the first row that starts with `start`."""
        return next(x for text, x in self.rows_with_x() if text.startswith(start))


# pdfminer may leave spaces out of the characters, so gaps decide: a word space in 9–14 pt
# Helvetica is 2.5–3.9 pt, the gap between table cells is wider.
SPACE_GAP = 1.5
CELL_GAP = 5.0


@dataclass(frozen=True)
class Pdf:
    pages: list[Page]
    metadata: dict[str, str]

    @property
    def text(self) -> str:
        return "\n".join(page.text for page in self.pages)


def read_pdf(content: bytes) -> Pdf:
    pages = [_page(page) for page in extract_pages(io.BytesIO(content))]
    document = PDFDocument(PDFParser(io.BytesIO(content)))
    metadata: dict[str, str] = {}
    infos = cast(list[dict[str, object]], document.info)  # pyright: ignore[reportUnknownMemberType]
    for info in infos:
        for key, value in info.items():
            metadata[key] = value.decode("latin-1") if isinstance(value, bytes) else str(value)
    return Pdf(pages, metadata)


def _page(page: LTPage) -> Page:
    lines: list[str] = []
    chars: list[Char] = []
    for element in page:
        if isinstance(element, LTTextContainer):
            lines.extend(line for line in element.get_text().splitlines() if line.strip())
            chars.extend(_chars(cast(Iterable[LTComponent], element)))
    _, _, width, height = page.bbox
    return Page(width, height, lines, chars)


def _chars(container: Iterable[LTComponent]) -> list[Char]:
    found: list[Char] = []
    for item in container:
        if isinstance(item, LTChar):
            found.append(Char(item.get_text(), item.size, item.x0, item.y0, item.x1, item.y1))
        elif isinstance(item, Iterable):
            found.extend(_chars(item))  # pyright: ignore[reportUnknownArgumentType]
    return found

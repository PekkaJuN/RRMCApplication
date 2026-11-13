"""API schemas of /api/archive (archiving spec P4)."""

from typing import Literal

from pydantic import BaseModel

from app.archive.service import ArchiveOverview, ArchiveResult, DeletedYear
from app.calculation.archive_totals import ArchiveRow, ArchiveTotals


class ArchivedYearOut(BaseModel):
    year: int
    receipts: int
    lines: int
    images: int


class CandidateOut(BaseModel):
    year: int
    receipts: int
    lines: int
    images: int
    unreviewed: int


class ArchiveOverviewOut(BaseModel):
    archived: list[ArchivedYearOut]
    candidates: list[CandidateOut]

    @classmethod
    def from_overview(cls, overview: ArchiveOverview) -> "ArchiveOverviewOut":
        return cls(
            archived=[
                ArchivedYearOut(
                    year=row.year, receipts=row.receipts, lines=row.lines, images=row.images
                )
                for row in overview.archived
            ],
            candidates=[
                CandidateOut(
                    year=row.year,
                    receipts=row.receipts,
                    lines=row.lines,
                    images=row.images,
                    unreviewed=row.unreviewed,
                )
                for row in overview.candidates
            ],
        )


class ArchiveResultOut(BaseModel):
    year: int
    receipts: int
    lines: int
    images_moved: int
    images_not_moved: list[str]

    @classmethod
    def from_result(cls, result: ArchiveResult) -> "ArchiveResultOut":
        return cls(
            year=result.year,
            receipts=result.receipts,
            lines=result.lines,
            images_moved=result.images_moved,
            images_not_moved=result.images_not_moved,
        )


class DeletedYearOut(BaseModel):
    year: int
    receipts: int
    lines: int

    @classmethod
    def from_deleted(cls, deleted: DeletedYear) -> "DeletedYearOut":
        return cls(year=deleted.year, receipts=deleted.receipts, lines=deleted.lines)


class ArchiveRowOut(BaseModel):
    kind: Literal["group", "category", "product", "none"]
    name: str | None
    months: list[int]
    total: int
    children: list["ArchiveRowOut"]

    @classmethod
    def from_row(cls, row: ArchiveRow) -> "ArchiveRowOut":
        return cls(
            kind=row.kind,
            name=row.name,
            months=row.months,
            total=row.total,
            children=[cls.from_row(child) for child in row.children],
        )


class ArchiveTotalsOut(BaseModel):
    year: int
    months: list[str]
    rows: list[ArchiveRowOut]
    month_totals: list[int]
    total: int

    @classmethod
    def from_totals(cls, totals: ArchiveTotals) -> "ArchiveTotalsOut":
        return cls(
            year=totals.year,
            months=totals.months,
            rows=[ArchiveRowOut.from_row(row) for row in totals.rows],
            month_totals=totals.month_totals,
            total=totals.total,
        )

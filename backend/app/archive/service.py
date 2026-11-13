"""Archiving a finished year, the overview, permanent delete and the year totals (archiving
spec PC2–PC4, PC7, PC8, PC11, P3)."""

import logging
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Protocol

from app.archive.errors import (
    ArchiveImportRunningError,
    InvalidYearError,
    NothingToArchiveError,
    UnreviewedReceiptsError,
    YearNotArchivedError,
    YearNotFinishedError,
)
from app.calculation.archive_totals import ArchiveLine, ArchiveTotals, archive_totals
from app.image_files import free_target_name, move_file
from app.local_time import local_today
from app.storage.archive_repository import ArchivedYearRow, ArchiveRepository, CandidateRow

logger = logging.getLogger(__name__)

_YEAR = re.compile(r"[0-9]{4}")


class ArchiveFiles(Protocol):
    """File access of archiving. Tests replace it to simulate a failing move."""

    def names_in(self, folder: Path) -> set[str]: ...

    def exists(self, path: Path) -> bool: ...

    def move(self, source: Path, target: Path) -> None: ...


class LocalArchiveFiles:
    def names_in(self, folder: Path) -> set[str]:
        """Lower-cased names, as `free_target_name` expects."""
        return {name.casefold() for name in os.listdir(folder)}

    def exists(self, path: Path) -> bool:
        return path.is_file()

    def move(self, source: Path, target: Path) -> None:
        move_file(source, target)


@dataclass(frozen=True)
class ArchiveResult:
    year: int
    receipts: int
    lines: int
    images_moved: int
    images_not_moved: list[str]


@dataclass(frozen=True)
class ArchiveOverview:
    archived: list[ArchivedYearRow]
    candidates: list[CandidateRow]


@dataclass(frozen=True)
class DeletedYear:
    year: int
    receipts: int
    lines: int


def parse_year(text: str) -> int:
    """A four-digit year from 2000 to 9999. Raises: InvalidYearError."""
    if not _YEAR.fullmatch(text) or not 2000 <= int(text) <= 9999:  # noqa: PLR2004 - P3 bounds
        raise InvalidYearError()
    return int(text)


class ArchiveService:
    def __init__(
        self,
        repository: ArchiveRepository,
        done_dir: Path,
        archive_dir: Path,
        *,
        import_running: Callable[[], bool],
        clock: Callable[[], datetime],
        files: ArchiveFiles,
    ) -> None:
        self._repository = repository
        self._done_dir = done_dir
        self._archive_dir = archive_dir
        self._import_running = import_running
        self._clock = clock
        self._files = files

    def overview(self) -> ArchiveOverview:
        current_year = local_today(self._clock).year
        with self._repository.transaction():
            return ArchiveOverview(
                self._repository.archived(), self._repository.candidates(current_year)
            )

    def archive(self, year_text: str) -> ArchiveResult:
        """Raises, in this order (PC3): InvalidYearError, YearNotFinishedError,
        ArchiveImportRunningError, NothingToArchiveError, UnreviewedReceiptsError."""
        year = parse_year(year_text)
        if year >= local_today(self._clock).year:
            raise YearNotFinishedError()
        if self._import_running():
            raise ArchiveImportRunningError()
        with self._repository.transaction():
            counts = self._repository.year_counts(year)
            if counts.receipts == 0:
                raise NothingToArchiveError()
            if counts.unreviewed:
                raise UnreviewedReceiptsError(counts.unreviewed)
            run = self._repository.archive_year(year, _utc_text(self._clock()))
        # Only after the commit (NFR-7): a failed transaction moves no file.
        moved, not_moved = self._move_images(run.images)
        if moved:
            self._store_names(moved)
        logger.info(
            "Archived year=%d receipts=%d lines=%d moved=%d not_moved=%d",
            year,
            run.receipts,
            run.lines,
            len(moved),
            len(not_moved),
        )
        return ArchiveResult(year, run.receipts, run.lines, len(moved), not_moved)

    def delete(self, year_text: str) -> DeletedYear:
        """Raises: InvalidYearError, YearNotArchivedError."""
        year = parse_year(year_text)
        with self._repository.transaction():
            receipts, lines = self._repository.delete_year(year)
            if receipts == 0:
                raise YearNotArchivedError()
        logger.info("Deleted archived year=%d receipts=%d lines=%d", year, receipts, lines)
        return DeletedYear(year, receipts, lines)

    def totals(self, year_text: str) -> ArchiveTotals:
        """Raises: InvalidYearError, YearNotArchivedError."""
        return read_year_totals(self._repository, parse_year(year_text))

    def _move_images(
        self, images: list[tuple[int, str]]
    ) -> tuple[list[tuple[int, str]], list[str]]:
        """Move each image to the archive folder (P3 step 5). Returns the moved (id, new
        name) pairs and the names left in the done folder."""
        moved: list[tuple[int, str]] = []
        not_moved: list[str] = []
        try:
            taken = self._files.names_in(self._archive_dir)
        except OSError:
            return [], [name for _, name in images]
        for receipt_id, name in images:
            source = self._done_dir / name
            target = free_target_name(name, taken)
            try:
                if not self._files.exists(source):
                    raise FileNotFoundError
                self._files.move(source, self._archive_dir / target)
            except OSError:
                not_moved.append(name)
                continue
            taken.add(target.casefold())
            moved.append((receipt_id, target))
        return moved, not_moved

    def _store_names(self, moved: list[tuple[int, str]]) -> None:
        try:
            with self._repository.transaction():
                self._repository.set_file_names(moved)
        except Exception as error:  # noqa: BLE001 - the files are already moved
            # Only the type: file names stay out of the log (NFR-3).
            logger.error("Storing archived image names failed: %s", type(error).__name__)


def read_year_totals(repository: ArchiveRepository, year: int) -> ArchiveTotals:
    """The totals of an archived year, read in one transaction; shared with the archive CSV
    export. Raises: YearNotArchivedError."""
    with repository.transaction():
        if not repository.has_year(year):
            raise YearNotArchivedError()
        rows = repository.year_lines(year)
    lines = [
        ArchiveLine(
            date.fromisoformat(row.purchase_date),
            row.amount_cents,
            row.product_name,
            row.category_name,
            row.group_name,
            row.is_deposit_refund,
        )
        for row in rows
    ]
    return archive_totals(year, lines)


def _utc_text(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

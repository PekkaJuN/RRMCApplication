"""Error codes of archiving (archiving spec PC3, PC8, P4)."""

from app import texts
from app.errors import AppError


class InvalidYearError(AppError):
    def __init__(self) -> None:
        super().__init__("invalid_year", texts.INVALID_YEAR, 422)


class YearNotFinishedError(AppError):
    def __init__(self) -> None:
        super().__init__("year_not_finished", texts.YEAR_NOT_FINISHED, 409)


class ArchiveImportRunningError(AppError):
    def __init__(self) -> None:
        super().__init__("import_running", texts.ARCHIVE_IMPORT_RUNNING, 409)


class NothingToArchiveError(AppError):
    def __init__(self) -> None:
        super().__init__("nothing_to_archive", texts.NOTHING_TO_ARCHIVE, 404)


class UnreviewedReceiptsError(AppError):
    def __init__(self, count: int) -> None:
        super().__init__(
            "unreviewed_receipts", texts.unreviewed_block_archiving(count), 409, {"count": count}
        )


class YearNotArchivedError(AppError):
    def __init__(self) -> None:
        super().__init__("not_found", texts.NOT_FOUND, 404)

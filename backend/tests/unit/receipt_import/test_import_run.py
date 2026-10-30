import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.engines.model import ModelUnavailableError
from app.receipt_import.files import LocalFileStore, image_identifier
from app.receipt_import.run import FileResult, ImportFolders, process_file
from app.receipt_reading.fake import FakeReceiptReader
from app.storage.catalog_repository import CatalogRepository
from app.storage.receipt_repository import LineCategory, ReceiptRepository
from tests.receipt_import_data import FailingRepository, FailingStore, StubCategorizer, jpeg

NOW = datetime(2026, 10, 28, 10, 0, 1, tzinfo=UTC)


@pytest.fixture
def folders(tmp_path: Path) -> ImportFolders:
    folders = ImportFolders(
        import_dir=tmp_path / "import",
        done_dir=tmp_path / "import_done",
        failed_dir=tmp_path / "import_failed",
    )
    for folder in (folders.import_dir, folders.done_dir, folders.failed_dir):
        folder.mkdir()
    return folders


def run_file(
    path: Path,
    folders: ImportFolders,
    repository: ReceiptRepository,
    store: LocalFileStore | None = None,
    categorizer: StubCategorizer | None = None,
) -> FileResult:
    return process_file(
        path,
        store=store or LocalFileStore(),
        repository=repository,
        reader=FakeReceiptReader(),
        categorizer=categorizer or StubCategorizer(),
        folders=folders,
        now=NOW,
    )


def names(folder: Path) -> list[str]:
    return sorted(path.name for path in folder.iterdir())


def test_ac1_new_image_is_stored_and_moved(db: sqlite3.Connection, folders: ImportFolders) -> None:
    repository = ReceiptRepository(db)
    path = folders.import_dir / "a.jpg"
    path.write_bytes(jpeg("a"))

    result = run_file(path, folders, repository)

    assert result == FileResult("a.jpg", "imported")
    row = repository.get_by_hash(image_identifier(jpeg("a")))
    assert row is not None
    # The read fields are the receipt-reading spec's (AC13); this AC is about the image record.
    assert (row.image_hash, row.file_name, row.imported_at) == (
        image_identifier(jpeg("a")),
        "a.jpg",
        "2026-10-28T10:00:01Z",
    )
    assert (folders.done_dir / "a.jpg").read_bytes() == jpeg("a")
    assert names(folders.import_dir) == []


def test_ac4_ac5_same_bytes_again_is_a_duplicate_and_stays(
    db: sqlite3.Connection, folders: ImportFolders
) -> None:
    repository = ReceiptRepository(db)
    (folders.import_dir / "a.jpg").write_bytes(jpeg("a"))
    (folders.import_dir / "b.jpg").write_bytes(jpeg("a"))
    run_file(folders.import_dir / "a.jpg", folders, repository)

    result = run_file(folders.import_dir / "b.jpg", folders, repository)

    assert result == FileResult("b.jpg", "duplicate")
    assert names(folders.import_dir) == ["b.jpg"]
    assert names(folders.done_dir) == ["a.jpg"]
    assert db.execute("SELECT count(*) FROM receipts").fetchone()[0] == 1


def test_ac10_collision_in_done_folder_gets_a_numbered_name(
    db: sqlite3.Connection, folders: ImportFolders
) -> None:
    repository = ReceiptRepository(db)
    (folders.done_dir / "kuitti.jpg").write_bytes(jpeg("old 1"))
    (folders.done_dir / "KUITTI (2).jpg").write_bytes(jpeg("old 2"))
    path = folders.import_dir / "kuitti.jpg"
    path.write_bytes(jpeg("new"))

    run_file(path, folders, repository)

    assert (folders.done_dir / "kuitti (3).jpg").read_bytes() == jpeg("new")
    assert (folders.done_dir / "kuitti.jpg").read_bytes() == jpeg("old 1")
    assert (folders.done_dir / "KUITTI (2).jpg").read_bytes() == jpeg("old 2")
    row = repository.get_by_hash(image_identifier(jpeg("new")))
    assert row is not None
    assert row.file_name == "kuitti (3).jpg"


def receipt_count(db: sqlite3.Connection) -> int:
    return db.execute("SELECT count(*) FROM receipts").fetchone()[0]


@pytest.mark.parametrize(("name", "data"), [("notes.txt", b"hello"), ("text.jpg", b"hello")])
def test_ac6_ac7_unsupported_file_moves_to_failed_folder(
    db: sqlite3.Connection, folders: ImportFolders, name: str, data: bytes
) -> None:
    (folders.import_dir / name).write_bytes(data)

    result = run_file(folders.import_dir / name, folders, ReceiptRepository(db))

    assert result == FileResult(name, "failed", "unsupported_format")
    assert names(folders.failed_dir) == [name]
    assert names(folders.import_dir) == []
    assert receipt_count(db) == 0


def test_ac11_collision_in_failed_folder_keeps_original_name_in_result(
    db: sqlite3.Connection, folders: ImportFolders
) -> None:
    (folders.failed_dir / "notes.txt").write_bytes(b"old")
    (folders.import_dir / "notes.txt").write_bytes(b"new")

    result = run_file(folders.import_dir / "notes.txt", folders, ReceiptRepository(db))

    assert result == FileResult("notes.txt", "failed", "unsupported_format")
    assert (folders.failed_dir / "notes.txt").read_bytes() == b"old"
    assert (folders.failed_dir / "notes (2).txt").read_bytes() == b"new"


def test_ac15_unreadable_file_fails_with_read_failed(
    db: sqlite3.Connection, folders: ImportFolders
) -> None:
    (folders.import_dir / "b.jpg").write_bytes(jpeg("b"))
    store = FailingStore(read_fails="b.jpg")

    result = run_file(folders.import_dir / "b.jpg", folders, ReceiptRepository(db), store)

    assert result == FileResult("b.jpg", "failed", "read_failed")
    assert names(folders.failed_dir) == ["b.jpg"]


def test_ac14_failed_save_moves_file_to_failed_folder(
    db: sqlite3.Connection, folders: ImportFolders
) -> None:
    (folders.import_dir / "a.jpg").write_bytes(jpeg("a"))

    result = run_file(folders.import_dir / "a.jpg", folders, FailingRepository(db, add_fails=True))

    assert result == FileResult("a.jpg", "failed", "save_failed")
    assert names(folders.failed_dir) == ["a.jpg"]
    assert receipt_count(db) == 0


def test_ac12_failed_move_to_done_deletes_the_row_and_leaves_the_file(
    db: sqlite3.Connection, folders: ImportFolders
) -> None:
    (folders.import_dir / "a.jpg").write_bytes(jpeg("a"))
    store = FailingStore(move_fails=folders.done_dir)

    result = run_file(folders.import_dir / "a.jpg", folders, ReceiptRepository(db), store)

    assert result == FileResult("a.jpg", "failed", "move_failed")
    assert names(folders.import_dir) == ["a.jpg"]
    assert names(folders.failed_dir) == []
    assert receipt_count(db) == 0


def test_ac12_unreadable_done_folder_is_move_failed(
    db: sqlite3.Connection, folders: ImportFolders
) -> None:
    (folders.import_dir / "a.jpg").write_bytes(jpeg("a"))
    store = FailingStore(names_fail=True)

    result = run_file(folders.import_dir / "a.jpg", folders, ReceiptRepository(db), store)

    assert result == FileResult("a.jpg", "failed", "move_failed")
    assert names(folders.import_dir) == ["a.jpg"]
    assert receipt_count(db) == 0


def test_ac12_row_that_cannot_be_deleted_is_logged_and_still_move_failed(
    db: sqlite3.Connection, folders: ImportFolders, caplog: pytest.LogCaptureFixture
) -> None:
    (folders.import_dir / "secret-name.jpg").write_bytes(jpeg("a"))
    store = FailingStore(move_fails=folders.done_dir)
    repository = FailingRepository(db, delete_fails=True)

    result = run_file(folders.import_dir / "secret-name.jpg", folders, repository, store)

    assert result == FileResult("secret-name.jpg", "failed", "move_failed")
    assert names(folders.import_dir) == ["secret-name.jpg"]
    assert "OperationalError" in caplog.text
    assert "secret-name" not in caplog.text


def test_ac16_failed_move_to_failed_folder_leaves_file_and_keeps_reason(
    db: sqlite3.Connection, folders: ImportFolders
) -> None:
    (folders.import_dir / "notes.txt").write_bytes(b"hello")
    store = FailingStore(move_fails=folders.failed_dir)

    result = run_file(folders.import_dir / "notes.txt", folders, ReceiptRepository(db), store)

    assert result == FileResult("notes.txt", "failed", "unsupported_format")
    assert names(folders.import_dir) == ["notes.txt"]


def test_ac17_unexpected_error_is_internal_error_and_logged_without_names(
    db: sqlite3.Connection, folders: ImportFolders, caplog: pytest.LogCaptureFixture
) -> None:
    (folders.import_dir / "secret-name.jpg").write_bytes(jpeg("a"))
    store = FailingStore(
        read_fails="secret-name.jpg", error=RuntimeError("/data/import/secret-name.jpg")
    )

    result = run_file(folders.import_dir / "secret-name.jpg", folders, ReceiptRepository(db), store)

    assert result == FileResult("secret-name.jpg", "failed", "internal_error")
    assert names(folders.failed_dir) == ["secret-name.jpg"]
    assert "RuntimeError" in caplog.text
    assert "in read_bytes" in caplog.text  # a traceback frame
    assert "secret-name" not in caplog.text


class BrokenMoveStore(LocalFileStore):
    def __init__(self, done_dir: Path) -> None:
        self._done_dir = done_dir

    def move(self, source: Path, target: Path) -> None:
        if target.parent == self._done_dir:
            raise RuntimeError("simulated")
        super().move(source, target)


def test_ac17_unexpected_error_in_move_to_done_deletes_the_row(
    db: sqlite3.Connection, folders: ImportFolders
) -> None:
    (folders.import_dir / "a.jpg").write_bytes(jpeg("a"))
    store = BrokenMoveStore(folders.done_dir)

    result = run_file(folders.import_dir / "a.jpg", folders, ReceiptRepository(db), store)

    assert result == FileResult("a.jpg", "failed", "internal_error")
    assert receipt_count(db) == 0
    assert names(folders.failed_dir) == ["a.jpg"]


# Categorization spec: the run categorizes the lines and stores them in the commit.


def test_categories_are_stored_with_the_lines(
    db: sqlite3.Connection, folders: ImportFolders
) -> None:
    repository = ReceiptRepository(db)
    category_id = CatalogRepository(db).add_category(
        "Maitotuotteet", "maitotuotteet", "category", None
    )
    path = folders.import_dir / "a.jpg"
    path.write_bytes(jpeg("a"))

    run_file(
        path,
        folders,
        repository,
        categorizer=StubCategorizer([LineCategory(category_id, "model", None)]),
    )

    receipt = repository.get_by_hash(image_identifier(jpeg("a")))
    assert receipt is not None
    lines = repository.lines(receipt.id)
    assert [(line.category_id, line.category_source) for line in lines] == [
        (category_id, "model"),
        (None, None),
    ]


def test_ac10_unavailable_model_in_categorization_stores_nothing(
    db: sqlite3.Connection, folders: ImportFolders
) -> None:
    path = folders.import_dir / "a.jpg"
    path.write_bytes(jpeg("a"))

    with pytest.raises(ModelUnavailableError):
        run_file(
            path,
            folders,
            ReceiptRepository(db),
            categorizer=StubCategorizer(error=ModelUnavailableError("gone")),
        )

    assert names(folders.import_dir) == ["a.jpg"]
    assert db.execute("SELECT count(*) FROM receipts").fetchone()[0] == 0


def test_unexpected_error_in_categorization_is_internal_error(
    db: sqlite3.Connection, folders: ImportFolders
) -> None:
    path = folders.import_dir / "a.jpg"
    path.write_bytes(jpeg("a"))

    result = run_file(
        path, folders, ReceiptRepository(db), categorizer=StubCategorizer(error=RuntimeError())
    )

    assert result == FileResult("a.jpg", "failed", "internal_error")
    assert names(folders.failed_dir) == ["a.jpg"]
    assert db.execute("SELECT count(*) FROM receipts").fetchone()[0] == 0

"""Archived data stays out of active views, and periods that touch an archived year warn
(archiving spec PC9, PC10; AC21–AC25)."""

import sqlite3
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.settings import Settings
from app.storage.archive_repository import ArchiveRepository
from app.storage.db import connect
from app.storage.receipt_repository import ReceiptRepository
from tests.pdf_reader import read_pdf

TIME = "2025-03-10T10:00:00Z"


@pytest.fixture
def db(api: TestClient, settings: Settings) -> Iterator[sqlite3.Connection]:
    connection = connect(settings.db_path)
    yield connection
    connection.close()


def archive_years(db: sqlite3.Connection, *years: int) -> list[int]:
    """One reviewed receipt with one line per year, archived; returns the receipt ids."""
    receipts = ReceiptRepository(db)
    archive = ArchiveRepository(db)
    ids: list[int] = []
    with receipts.transaction():
        for year in years:
            row = receipts.add(None, None, TIME, store="Kauppa", purchase_date=f"{year}-06-01")
            receipts.add_line(row.id, 1, "MAITO", 100, is_deposit_refund=False)
            receipts.set_reviewed(row.id, reviewed=True)
            ids.append(row.id)
        for year in years:
            archive.archive_year(year, TIME)
    return ids


def test_ac21_archived_data_is_not_in_active_views(api: TestClient, db: sqlite3.Connection) -> None:
    [receipt] = archive_years(db, 2025)
    period = "unit=month&from=2025-01&to=2025-12"

    listed = api.get("/api/receipts").json()
    one = api.get(f"/api/receipts/{receipt}")
    totals = api.get(f"/api/totals?{period}").json()
    lines = api.get(f"/api/export/lines?{period}")

    assert listed == []
    assert (one.status_code, one.json()["error"]) == (404, "not_found")
    assert totals["rows"] == []
    assert sum(totals["month_totals"]) == 0
    assert lines.content.decode("utf-8").count("\r\n") == 1


@pytest.mark.parametrize(
    ("query", "years"),
    [
        ("unit=range&from=2025-12-15&to=2026-01-14", [2025]),
        ("unit=week&from=2026-W01&to=2026-W01", [2025]),
        ("unit=month&from=2026-02&to=2026-02", []),
    ],
)
def test_ac22_totals_warn_about_an_archived_year(
    api: TestClient, db: sqlite3.Connection, query: str, years: list[int]
) -> None:
    archive_years(db, 2025)

    assert api.get(f"/api/totals?{query}").json()["archived_years"] == years


def test_ac23_several_archived_years(api: TestClient, db: sqlite3.Connection) -> None:
    archive_years(db, 2024, 2025)

    body = api.get("/api/totals?unit=range&from=2024-12-01&to=2025-01-31").json()

    assert body["archived_years"] == [2024, 2025]


def test_ac24_budget_comparison_warns(api: TestClient, db: sqlite3.Connection) -> None:
    archive_years(db, 2025)

    mid = api.get("/api/budget/comparison?month=2025-12&period=mid").json()
    later = api.get("/api/budget/comparison?month=2026-02&period=calendar").json()

    assert mid["archived_years"] == [2025]
    assert later["archived_years"] == []


def test_ac25_pdf_files_carry_the_warning(api: TestClient, db: sqlite3.Connection) -> None:
    archive_years(db, 2025)
    note = "Arkistoitu vuosi 2025 ei ole mukana."

    totals = api.get("/api/export/totals/pdf?unit=range&from=2025-12-15&to=2026-01-14&by=month")
    comparison = api.get("/api/export/comparison/pdf?month=2025-12&period=mid")
    february = api.get("/api/export/totals/pdf?unit=month&from=2026-02&to=2026-02&by=month")

    assert note in read_pdf(totals.content).text
    assert note in read_pdf(comparison.content).text
    assert note not in read_pdf(february.content).text

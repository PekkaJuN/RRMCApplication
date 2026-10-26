from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings
from app.storage.db import connect


def make_migrations(folder: Path) -> Path:
    folder.mkdir()
    (folder / "0001_create_item.sql").write_text("CREATE TABLE item (id INTEGER);")
    (folder / "0002_add_name.sql").write_text("ALTER TABLE item ADD COLUMN name TEXT;")
    return folder


def applied_versions(settings: Settings) -> list[tuple[int, str]]:
    connection = connect(settings.db_path)
    try:
        rows = connection.execute("SELECT version, applied_at FROM schema_version ORDER BY 1")
        return [(row["version"], row["applied_at"]) for row in rows]
    finally:
        connection.close()


def test_ac8_ac9_startup_migrates_once(settings: Settings, tmp_path: Path) -> None:
    # Given no database
    migrations = make_migrations(tmp_path / "migrations")

    # When the app starts
    with TestClient(create_app(settings, migrations_dir=migrations)):
        pass

    # Then every migration has been applied, and the version is the newest
    first_start = applied_versions(settings)
    assert [version for version, _ in first_start] == [1, 2]

    # When the app starts again, nothing is applied again
    with TestClient(create_app(settings, migrations_dir=migrations)):
        pass
    assert applied_versions(settings) == first_start

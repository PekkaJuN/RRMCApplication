import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings
from app.storage.db import connect
from app.storage.migrate import MIGRATIONS_DIR


def make_migrations(folder: Path) -> tuple[Path, list[int]]:
    """The real migrations, which startup needs, followed by two throwaway ones."""
    shutil.copytree(MIGRATIONS_DIR, folder)
    real = sorted(int(path.name[:4]) for path in folder.glob("[0-9][0-9][0-9][0-9]_*.sql"))
    first, second = real[-1] + 1, real[-1] + 2
    (folder / f"{first:04d}_create_item.sql").write_text("CREATE TABLE item (id INTEGER);")
    (folder / f"{second:04d}_add_name.sql").write_text("ALTER TABLE item ADD COLUMN name TEXT;")
    return folder, [*real, first, second]


def applied_versions(settings: Settings) -> list[tuple[int, str]]:
    connection = connect(settings.db_path)
    try:
        rows = connection.execute("SELECT version, applied_at FROM schema_version ORDER BY 1")
        return [(row["version"], row["applied_at"]) for row in rows]
    finally:
        connection.close()


def test_ac8_ac9_startup_migrates_once(settings: Settings, tmp_path: Path) -> None:
    # Given no database
    migrations, versions = make_migrations(tmp_path / "migrations")

    # When the app starts
    with TestClient(create_app(settings, migrations_dir=migrations)):
        pass

    # Then every migration has been applied, and the version is the newest
    first_start = applied_versions(settings)
    assert [version for version, _ in first_start] == versions

    # When the app starts again, nothing is applied again
    with TestClient(create_app(settings, migrations_dir=migrations)):
        pass
    assert applied_versions(settings) == first_start

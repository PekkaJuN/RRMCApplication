"""Start checks run before Uvicorn: settings and database migrations.

Run as `python -m app.prestart`. A non-zero exit code stops the container; Uvicorn's
reloader would otherwise keep the container running after a failed start.
"""

import logging
from pathlib import Path

from app.logging_setup import configure_logging
from app.settings import SettingsError, load_settings
from app.storage.migrate import MIGRATIONS_DIR, MigrationError, migrate_database

logger = logging.getLogger(__name__)


def main(migrations_dir: Path = MIGRATIONS_DIR) -> int:
    """Validate the settings and migrate the database. Returns the process exit code."""
    try:
        settings = load_settings()
    except SettingsError as error:
        # The log level setting itself may be the invalid one.
        configure_logging("INFO")
        logger.error("%s", error)
        return 1
    configure_logging(settings.log_level)
    try:
        version = migrate_database(settings.db_path, migrations_dir)
    except MigrationError as error:
        logger.error("%s: %s", error, error.__cause__)
        return 1
    logger.info("Database at schema version %d", version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

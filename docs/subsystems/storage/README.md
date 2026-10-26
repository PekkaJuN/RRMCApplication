# Storage

Navigation: ↑ [Architecture](../../architecture.md) | → [Data model](../../datamodel.md) | → [Receipt reading](../receipt-reading/README.md) | → [UI](../ui/README.md)

## Overview

Storage owns the SQLite database: opening connections, applying schema migrations, and all
SQL. Other subsystems never run SQL; they call storage's repositories, which feature specs
add together with their tables. Storage holds no business rules.

Today storage has the connection and the migration runner only. The schema is described in
[datamodel.md](../../datamodel.md).

## Key Files and Entry Points

- @backend/app/storage/db.py — `connect(path)` opens a connection; `is_available(path)`
  tells whether an existing database can be read, for the health check
- @backend/app/storage/migrate.py — `migrate_database(db_path)` creates the database and
  applies pending migrations; `migrate()` and `current_version()` work on an open connection
- @backend/app/storage/migrations/ — the numbered SQL migration files (none yet)

## Interfaces

| Function | Returns | Raises |
|---|---|---|
| `connect(path)` | `sqlite3.Connection` with foreign keys on, WAL journal, rows as `sqlite3.Row` | `sqlite3.Error` |
| `is_available(path)` | `True` when the file exists and its schema can be read | nothing |
| `migrate_database(db_path, migrations_dir)` | the schema version after migrating | `MigrationError` |
| `migrate(connection, migrations_dir)` | the versions applied, in order | `MigrationError` |
| `current_version(connection)` | the newest applied version, 0 for a new database | `sqlite3.Error` |

## Data Flow

1. `python -m app.prestart` runs before Uvicorn and calls `migrate_database`. On
   `MigrationError` it logs `Migration NNNN_name.sql failed: <cause>` and exits 1, which stops
   the container.
2. The app's lifespan calls `migrate_database` again; with nothing pending it applies nothing.
3. `GET /api/health` calls `is_available` on each request.

## Dependencies

- Uses: Python's `sqlite3`; nothing else in the app.
- Used by: the foundation (`prestart`, `main`), [health](../../api-reference.md#get-apihealth);
  later every feature subsystem through its repositories.

## Modules

None yet.

## Known Issues and Gotchas

- Connections are opened with `isolation_level=None`: Python's `sqlite3` does not start
  transactions on its own. Code that writes must start one with `BEGIN` and end it with
  `COMMIT` or `ROLLBACK`.
- `is_available` opens the file with `mode=rw`, so it never creates an empty database, and
  reads the schema, because `SELECT 1` would not notice a damaged file.
- A migration file must not contain `BEGIN` or `COMMIT`; the runner wraps each file in its own
  transaction with its `schema_version` row.
- The database must stay in a Docker volume, not in a Windows folder
  ([ADR 0002](../../adr/0002-docker.md)).

## Related Documents

- [datamodel.md](../../datamodel.md): schema and migration rules
- [Foundation spec](../../../specs/features/foundation.md) PC4

# Storage

Navigation: ↑ [Architecture](../../architecture.md) | → [Data model](../../datamodel.md) | → [Categorization](../categorization/README.md) | → [Import](../import/README.md) | → [Receipt reading](../receipt-reading/README.md) | → [UI](../ui/README.md)

## Overview

Storage owns the SQLite database: opening connections, applying schema migrations, and all
SQL. Other subsystems never run SQL; they call storage's repositories, which feature specs
add together with their tables. Storage holds no business rules.

Today storage has the connection, transactions, the migration runner, and the catalog and
receipt repositories. The schema is described in [datamodel.md](../../datamodel.md).

## Key Files and Entry Points

- @backend/app/storage/db.py — `connect(path)` opens a connection; `transaction(connection)`
  wraps a block in one transaction; `is_available(path)` tells whether an existing database
  can be read, for the health check
- @backend/app/storage/catalog_repository.py — `CatalogRepository`: all SQL for groups,
  categories, products and `app_state`
- @backend/app/storage/receipt_repository.py — `ReceiptRepository`: all SQL for receipts
- @backend/app/storage/migrate.py — `migrate_database(db_path)` creates the database and
  applies pending migrations; `migrate()` and `current_version()` work on an open connection
- @backend/app/storage/migrations/ — the numbered SQL migration files
  (`0001_catalog.sql`, `0002_receipts.sql`)

## Interfaces

| Function | Returns | Raises |
|---|---|---|
| `connect(path)` | `sqlite3.Connection` with foreign keys on, WAL journal, rows as `sqlite3.Row`, usable from another thread | `sqlite3.Error` |
| `transaction(connection)` | context manager: `BEGIN IMMEDIATE`, then `COMMIT`, or `ROLLBACK` and re-raise on any exception | `sqlite3.Error` |
| `is_available(path)` | `True` when the file exists and its schema can be read | nothing |
| `migrate_database(db_path, migrations_dir)` | the schema version after migrating | `MigrationError` |
| `migrate(connection, migrations_dir)` | the versions applied, in order | `MigrationError` |
| `current_version(connection)` | the newest applied version, 0 for a new database | `sqlite3.Error` |

`CatalogRepository(connection)` returns frozen dataclasses: `CategoryRow` (with
`product_count` and `category_count`) and `ProductRow` (with `category_name` and
`group_name`). It has add, get, get by key, list, update and delete for categories and
products, `get_app_state` and `set_app_state`, and `transaction()` on its own connection. It
holds no rules: `list_products(query_key, category_or_group_id)` filters but does not sort,
and callers own the transaction. The rules are in
[categorization](../categorization/README.md#rules).

`ReceiptRepository(connection)` returns the frozen dataclass `ReceiptRow` (`id`,
`image_hash`, `file_name`, `imported_at`). It has `add` (raises `sqlite3.IntegrityError` for
an existing hash), `get_by_hash`, `delete` and `transaction()`. The rules are in
[import](../import/README.md).

## Data Flow

1. `python -m app.prestart` runs before Uvicorn and calls `migrate_database`. On
   `MigrationError` it logs `Migration NNNN_name.sql failed: <cause>` and exits 1, which stops
   the container.
2. The app's lifespan calls `migrate_database` again; with nothing pending it applies nothing.
3. `GET /api/health` calls `is_available` on each request.
4. Each catalog request opens its own connection and closes it after the response.
5. An import run opens one connection in its background thread and closes it when the run
   ends.

## Dependencies

- Uses: Python's `sqlite3`; nothing else in the app.
- Used by: the foundation (`prestart`, `main`), [health](../../api-reference.md#get-apihealth),
  [categorization](../categorization/README.md), [import](../import/README.md); later every
  feature subsystem through its repositories.

## Modules

None yet.

## Known Issues and Gotchas

- Connections are opened with `isolation_level=None`: Python's `sqlite3` does not start
  transactions on its own. Code that writes uses `transaction()`.
- Connections are opened with `check_same_thread=False`, because FastAPI may open a
  request's connection in one threadpool thread and use it in another. A connection is
  never shared between requests ([learnings](../../learnings.md)).
- Product search uses `instr()`, not `LIKE`, so `%` and `_` in a query match literally.
- `is_available` opens the file with `mode=rw`, so it never creates an empty database, and
  reads the schema, because `SELECT 1` would not notice a damaged file.
- A migration file must not contain `BEGIN` or `COMMIT`; the runner wraps each file in its own
  transaction with its `schema_version` row.
- The database must stay in a Docker volume, not in a Windows folder
  ([ADR 0002](../../adr/0002-docker.md)).

## Related Documents

- [datamodel.md](../../datamodel.md): schema and migration rules
- [Foundation spec](../../../specs/features/foundation.md) PC4
- [Product management spec](../../../specs/features/product-management.md)
- [Receipt import spec](../../../specs/features/receipt-import.md)

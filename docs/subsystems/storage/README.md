# Storage

Navigation: ↑ [Architecture](../../architecture.md) | → [Data model](../../datamodel.md) | → [Categorization](../categorization/README.md) | → [Import](../import/README.md) | → [Receipt reading](../receipt-reading/README.md) | → [Review](../review/README.md) | → [Totals](../totals/README.md) | → [Budget](../budget/README.md) | → [Archive](../archive/README.md) | → [UI](../ui/README.md)

## Overview

Storage owns the SQLite database: opening connections, applying schema migrations, and all
SQL. Other subsystems never run SQL; they call storage's repositories, which feature specs
add together with their tables. Storage holds no business rules.

Today storage has the connection, transactions, the migration runner, and the catalog,
receipt and archive repositories. The schema is described in [datamodel.md](../../datamodel.md).

## Key Files and Entry Points

- @backend/app/storage/db.py — `connect(path)` opens a connection; `transaction(connection)`
  wraps a block in one transaction; `is_available(path)` tells whether an existing database
  can be read, for the health check; `fits_integer(value)` tells whether an int fits SQLite's
  signed 64-bit range (`INTEGER_MIN`, `INTEGER_MAX`), so an id from a request cannot raise
  `OverflowError`
- @backend/app/storage/catalog_repository.py — `CatalogRepository`: all SQL for groups,
  categories, products, budgets and `app_state`, and `move_product_lines` (FR-36)
- @backend/app/storage/receipt_repository.py — `ReceiptRepository`: all SQL for receipts and
  their lines (`add` with the read fields, `add_line` with an optional `LineCategory`,
  `lines`, `get_line`, `set_line_category`, `update_line`, `next_position`, `delete_line`,
  `get`, `get_by_hash`, `image_known`, `summaries`, `set_reviewed`, `set_fields`, `delete`, `dated_lines`,
  `export_lines`, `count_unreviewed`, `count_undated`)
- @backend/app/storage/archive_repository.py — `ArchiveRepository`: all SQL for the
  archive tables (`year_counts`, `archive_year`, `set_file_names`, `archived`,
  `candidates`, `delete_year`, `has_year`, `year_lines`, `archived_years`)
- @backend/app/storage/migrate.py — `migrate_database(db_path)` creates the database and
  applies pending migrations; `migrate()` and `current_version()` work on an open connection
- @backend/app/storage/migrations/ — the numbered SQL migration files
  (`0001_catalog.sql`, `0002_receipts.sql`, `0003_receipt_reading.sql`,
  `0004_line_categories.sql`, `0005_receipt_review.sql`, `0006_manual_receipts.sql`,
  `0007_budgets.sql`, `0008_archive.sql`)

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
`product_count`, `category_count` and `line_count`) and `ProductRow` (with `category_name` and
`group_name`). It has add, get, get by key, list, update and delete for categories and
products, `get_app_state` and `set_app_state`, and `transaction()` on its own connection. It
holds no rules: `list_products(query_key, category_or_group_id)` filters but does not sort,
and callers own the transaction. `move_product_lines(product_id, category_id)` gives every
line linked to the product the category and source `remembered`. The rules are in
[categorization](../categorization/README.md#rules).

`ReceiptRepository(connection)` returns the frozen dataclass `ReceiptRow` (`id`,
`image_hash`, `file_name`, `imported_at`, the read fields and `reviewed`; `image_hash` and
`file_name` are both `None` for a receipt typed in without an image). It has `add` (raises
`sqlite3.IntegrityError` for an existing hash; takes `None` for both hash and name), `get`, `get_by_hash`, `image_known` (whether the hash is in `receipts` or `archived_receipts`: the duplicate lookup of import and review, FR-42), `delete` and
`transaction()`. `summaries()` lists every receipt as `ReceiptSummaryRow` with the sum of its
line amounts, computed in SQL, in the review list order (no date first, then newest date,
then newest id); `set_reviewed(id, reviewed=...)` and `set_fields(id, store=...,
purchase_date=..., total_cents=...)` return `False` when the receipt does not exist.
`add_line` returns the new line's id; `next_position(receipt_id)` is the position after the
last line (1 without lines), and positions can have gaps after `delete_line`, which returns
`False` for a missing line. Lines come back as `LineRow` (id, position, name, amount, refund
flag and the three category fields) from `lines`, or as `StoredLine` (with its receipt id,
amount and a `LineCategory` or `None`) from `get_line`; `set_line_category` writes the three
category columns, and `update_line` writes the name, amount, refund flag and category at
once, so the schema's `CHECK`s see one consistent row. `LineCategory` and `CategorySource`
are defined here. The rules are in [import](../import/README.md) and
[categorization](../categorization/README.md#line-categorization).

For the [budget](../budget/README.md), `CatalogRepository` has `budgets()` (amounts by
category id; a missing id has 0), `set_budget(category_id, cents)` and
`move_budget(from_id, to_id)`, which adds the first amount to the second and removes the
first, and does nothing without one. They are on the catalog repository so that a category
update moves a budget in its own transaction.

For the [totals](../totals/README.md), `dated_lines(start, end)` returns the lines of the
receipts dated from `start` to `end` (`YYYY-MM-DD`, inclusive) as `DatedLineRow`
(purchase date, amount, category id, refund flag; no product name), in no order. With
`reviewed_only=True` it returns only the lines of reviewed receipts, for the budget.
`count_unreviewed(start, end)` counts the unreviewed receipts dated in the range, and
`count_undated()` the receipts without a purchase date. The date `CHECK` keeps every
`purchase_date` as `YYYY-MM-DD`, so `BETWEEN` on the text compares dates.

For the [export](../export/README.md), `export_lines(start, end)` returns the lines of the
receipts dated in the range as `ExportLineRow` (purchase date, store, name, amount, refund
flag, group name, category name, review state), ordered by purchase date, receipt id and
position. It joins the line's category and that category's group with `LEFT JOIN`, so a
line without a category, or a category without a group, has `None` names.

`ArchiveRepository(connection)` holds the archive SQL and no rules; callers own the
transaction ([archive](../archive/README.md#archiving-a-year)). `archive_year(year,
archived_at)` copies the year's receipts and lines (with the product, category and group
names) into the archive tables, deletes the active rows, and returns the counts and the
(id, file name) pairs of the images. `year_counts`, `archived`, `candidates(before_year)`
and `delete_year` give and remove whole years; `year_lines` reads an archived year's lines
for the totals; `archived_years(first_year, last_year)` serves the period warning of
totals and budget.

## Data Flow

1. `python -m app.prestart` runs before Uvicorn and calls `migrate_database`. On
   `MigrationError` it logs `Migration NNNN_name.sql failed: <cause>` and exits 1, which stops
   the container.
2. The app's lifespan calls `migrate_database` again; with nothing pending it applies nothing.
3. `GET /api/health` calls `is_available` on each request.
4. Each catalog, review, totals, budget, archive and export request opens its own connection and closes it
   after the response.
5. An import run opens one connection in its background thread and closes it when the run
   ends.

## Dependencies

- Uses: Python's `sqlite3`; nothing else in the app.
- Used by: the foundation (`prestart`, `main`), [health](../../api-reference.md#get-apihealth),
  [categorization](../categorization/README.md), [import](../import/README.md),
  [review](../review/README.md), [totals](../totals/README.md),
  [budget](../budget/README.md), [archive](../archive/README.md),
  [export](../export/README.md).

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
- The runner turns foreign keys off before each migration's `BEGIN` (the pragma does nothing
  inside a transaction) and on again afterwards, also after a failure, and runs
  `PRAGMA foreign_key_check` before the commit. Without this, the `DROP TABLE` of a table
  rebuild would cascade-delete every row that references the table (migration `0006` rebuilds
  `receipts`, whose lines reference it).
- The database must stay in a Docker volume, not in a Windows folder
  ([ADR 0002](../../adr/0002-docker.md)).

## Related Documents

- [datamodel.md](../../datamodel.md): schema and migration rules
- [Foundation spec](../../../specs/features/foundation.md) PC4
- [Product management spec](../../../specs/features/product-management.md)
- [Receipt import spec](../../../specs/features/receipt-import.md)
- [Receipt-reading spec](../../../specs/features/receipt-reading.md)
- [Categorization spec](../../../specs/features/categorization.md): migration 0004
- [Receipt deletion and manual receipts spec](../../../specs/features/receipt-management.md): migration 0006

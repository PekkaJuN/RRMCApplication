# Data Model

- **Status:** Done (catalog, receipts with their read data and review state, and
  receipt lines with their categories, budgets and the archive implemented)
- **Updated:** 2026-11-13

## Overview

The app keeps all its data in one SQLite database. This document describes the schema and
how it changes. Today the schema holds the migration bookkeeping, the catalog (groups,
categories and products), the imported receipts with what was read from them and their
review state, their lines with their categories, the monthly budgets, and the archive of
finished years.

## Where the database is

| Item | Value |
|---|---|
| File inside the backend container | `/data/db/rrmc.db` |
| Storage | Docker volume `rrmc_rrmc-data`, mounted at `/data/db` |
| Created | On the first start, by `python -m app.prestart` |

The database is not in a Windows folder, because SQLite file locking is unreliable on
Windows folders mounted into Linux containers ([ADR 0002](adr/0002-docker.md)). It survives
`docker compose down` and image rebuilds; `docker compose down -v` deletes it.

Every connection has foreign keys on and uses the WAL journal
(@backend/app/storage/db.py).

## Entities

### schema_version

One row per applied migration.

| Column | Type | Meaning |
|---|---|---|
| `version` | `INTEGER PRIMARY KEY` | Number of the migration file (`0001_...` → 1) |
| `applied_at` | `TEXT NOT NULL` | When it was applied, UTC ISO 8601 |

The schema version is the largest `version`, or 0 when the table is empty.

### categories

Groups and categories share one table, so they share one name namespace (PRD FR-35). A
**group** holds categories and never products; a **category** holds products and belongs to
one group or to none. The hierarchy has at most two levels.

| Column | Type | Meaning |
|---|---|---|
| `id` | `INTEGER PRIMARY KEY` | Stable id |
| `name` | `TEXT NOT NULL` | Display name, as the user typed it after trimming and collapsing spaces |
| `name_key` | `TEXT NOT NULL UNIQUE` | Normalized name, used for every comparison ([normalization](subsystems/categorization/README.md#names)) |
| `kind` | `TEXT NOT NULL`, `group` or `category` | What the row is |
| `parent_id` | `INTEGER`, references `categories (id)`, `ON DELETE RESTRICT` | The group of a category; always `NULL` for a group (`CHECK`) |

### products

| Column | Type | Meaning |
|---|---|---|
| `id` | `INTEGER PRIMARY KEY` | Stable id; linked receipt lines reference it (FR-36) |
| `name` | `TEXT NOT NULL` | Display name |
| `name_key` | `TEXT NOT NULL UNIQUE` | Normalized name; two products cannot share it |
| `category_id` | `INTEGER NOT NULL`, references `categories (id)`, `ON DELETE RESTRICT` | The product's category, never a group |

### app_state

One-time facts about the database, as key and value text.

| Key | Value | Meaning |
|---|---|---|
| `catalog_seeded_at` | UTC ISO 8601 time | The default category list was created; it is never created again, even after the user deletes every item |

### receipts

One row per receipt: an imported image ([import](subsystems/import/README.md)) with what
[receipt reading](subsystems/receipt-reading/README.md) read from it, or a receipt the user
typed in ([review](subsystems/review/README.md), FR-47). The read columns are `NULL` for
receipts imported before reading existed (migration `0003`). Migration `0006` rebuilt the
table so that a typed-in receipt can have no image.

| Column | Type | Meaning |
|---|---|---|
| `id` | `INTEGER PRIMARY KEY AUTOINCREMENT` | Stable id; its receipt lines reference it. Never reused after a delete, so an old link cannot open another receipt |
| `image_hash` | `TEXT UNIQUE`, `CHECK (NULL or length = 64)` | The image identifier: SHA-256 of the file's bytes, lowercase hex. The `UNIQUE` index is the duplicate lookup (FR-3). `NULL` for a typed-in receipt without an image; many may be `NULL` |
| `file_name` | `TEXT` | The file's name in the done folder, after any numbered suffix; `NULL` exactly when `image_hash` is `NULL` (`CHECK`) |
| `imported_at` | `TEXT NOT NULL` | When the receipt was stored or typed in, UTC ISO 8601 with seconds (`2026-10-28T10:00:01Z`) |
| `store` | `TEXT` | Store name as read, trimmed; `''` when the model found none |
| `purchase_date` | `TEXT`, `CHECK` shape `YYYY-MM-DD` | Purchase date; `NULL` when the model's date was not a real date (the user fixes it in review) |
| `total_cents` | `INTEGER` | Receipt total in integer cents (NFR-6) |
| `ocr_text` | `TEXT` | The raw Tesseract output, so the receipt can be re-parsed without OCR (FR-10); `NULL` for a typed-in receipt |
| `reviewed` | `INTEGER NOT NULL DEFAULT 0`, `0` or `1` | Review state (FR-21): 0 unreviewed, 1 confirmed by the user. Receipts stored before migration `0005` are unreviewed ([review](subsystems/review/README.md)) |

A failed import stores no row, so the image can be retried (FR-4).

### receipt_lines

One row per item line of a receipt, in printed order (receipt-reading spec).

| Column | Type | Meaning |
|---|---|---|
| `id` | `INTEGER PRIMARY KEY` | Stable id |
| `receipt_id` | `INTEGER NOT NULL`, `REFERENCES receipts ON DELETE CASCADE` | The receipt; deleting the receipt deletes its lines |
| `position` | `INTEGER NOT NULL`, `CHECK (≥ 1)`, `UNIQUE` with `receipt_id` | Printed order, from 1. A line the user adds goes after the last one; a deleted line leaves a gap, and the other lines keep their positions |
| `name` | `TEXT NOT NULL`, `CHECK` not blank | Product name as read, or as the user edited it (1–100 characters) |
| `amount_cents` | `INTEGER NOT NULL` | Amount after any discount and including any deposit (FR-9); negative for a deposit refund |
| `is_deposit_refund` | `INTEGER NOT NULL`, `0` or `1` | 1 for a deposit refund (panttipalautus); `CHECK` that such a line is negative |
| `category_id` | `INTEGER`, references `categories (id)`, `ON DELETE RESTRICT` | The line's category; `NULL` when it has none. Always `NULL` for a deposit refund (FR-44) |
| `category_source` | `TEXT`, `remembered`, `model` or `user` | Where the category came from (FR-15); `NULL` exactly when `category_id` is `NULL` |
| `product_id` | `INTEGER`, references `products (id)`, `ON DELETE SET NULL` | The product the line follows (a linked line); only with a category. Deleting the product keeps the category and the source |

Lines stored before migration `0004` have no category. The rules that set these columns are in
[categorization](subsystems/categorization/README.md#line-categorization). Indexes on
`category_id` and `product_id` keep the category delete check and FR-36 updates fast.

### budgets

The monthly budget of a group or a category without a group. It is the same for every
month and has no history ([budget](subsystems/budget/README.md)).

| Column | Type | Meaning |
|---|---|---|
| `category_id` | `INTEGER PRIMARY KEY`, references `categories (id)`, `ON DELETE CASCADE` | The group or category; deleting it deletes the budget |
| `amount_cents` | `INTEGER NOT NULL`, `CHECK (≥ 0)` | The monthly budget in integer cents. No upper limit here: a budget moved into a group may exceed the limit of a typed amount |

A missing row means 0. "Only a budget row has a budget" needs another row, which `CHECK`
cannot read, so the budget and categorization services enforce it.

### archived_receipts

A receipt of an archived year (FR-40, [archive](subsystems/archive/README.md)). Archiving
copies the reviewed receipts of a finished year here and deletes them from `receipts`. No
column refers to the active tables ([ADR 0007](adr/0007-archive-tables.md)).

| Column | Type | Meaning |
|---|---|---|
| `id` | `INTEGER PRIMARY KEY` | The active receipt's id, copied. Active ids are never reused, so an id is unique across both tables |
| `year` | `INTEGER NOT NULL`, `CHECK` 2000–9999 and equal to the date's year | The archived year; indexed |
| `purchase_date` | `TEXT NOT NULL`, `CHECK` shape `YYYY-MM-DD` | Purchase date |
| `store` | `TEXT` | Store name |
| `total_cents` | `INTEGER` | Receipt total in integer cents |
| `image_hash` | `TEXT UNIQUE`, `CHECK (NULL or length = 64)` | The image identifier; an import still finds it as a duplicate (FR-42) |
| `file_name` | `TEXT` | The image's name in the archive folder after the move; the done folder name when the move failed. `NULL` exactly when `image_hash` is `NULL` |
| `imported_at` | `TEXT NOT NULL` | Copied from the active receipt |
| `archived_at` | `TEXT NOT NULL` | When it was archived, UTC ISO 8601 with seconds |

The OCR text and the review state are not copied: the archive is not re-read, and every
archived receipt was reviewed.

### archived_lines

A line of an archived receipt, with its product, category and group as names.

| Column | Type | Meaning |
|---|---|---|
| `id` | `INTEGER PRIMARY KEY` | The active line's id, copied |
| `receipt_id` | `INTEGER NOT NULL`, `REFERENCES archived_receipts ON DELETE CASCADE` | The archived receipt; deleting an archived year deletes its lines |
| `position` | `INTEGER NOT NULL`, `UNIQUE` with `receipt_id` | Printed order, as in the active line |
| `name` | `TEXT NOT NULL` | The line's own name |
| `product_name` | `TEXT NOT NULL` | The linked product's name, else the line's name; the year totals group lines by it |
| `amount_cents` | `INTEGER NOT NULL` | Amount in integer cents |
| `is_deposit_refund` | `INTEGER NOT NULL`, `0` or `1` | 1 for a deposit refund; such a line has no category (`CHECK`) |
| `category_name` | `TEXT` | The category's name at archiving; `NULL` for a line without a category |
| `group_name` | `TEXT` | The category's group's name; `NULL` without a group. Only with a category (`CHECK`) |

Later catalog changes never touch these rows, and deleting a category or product is not
blocked by archived lines.

### Relationships and rules

```mermaid
erDiagram
  categories ||--o{ categories : "group holds"
  categories ||--o{ products : "category holds"
  receipts ||--o{ receipt_lines : "has"
  categories ||--o{ receipt_lines : "categorizes"
  categories ||--o| budgets : "has"
  products ||--o{ receipt_lines : "is followed by"
  archived_receipts ||--o{ archived_lines : "has"
```

The archive tables have no relation to the other tables.

- `UNIQUE`, `CHECK` and `RESTRICT` are a safety net. "A parent is a group" and "a product's
  category is not a group" need another row, which SQLite `CHECK` cannot read, so the
  [categorization services](subsystems/categorization/README.md#rules) enforce them, and
  they also check every rule first to return the right error code and count.
- Product names are personal purchase data: they stay in this database and are never logged.

## Migrations

- Migrations are SQL files in @backend/app/storage/migrations/ named `NNNN_name.sql`
  (four digits, then a short name). Today there are eight, `0001_catalog.sql`,
  `0002_receipts.sql`, `0003_receipt_reading.sql`, `0004_line_categories.sql`,
  `0005_receipt_review.sql`, `0006_manual_receipts.sql`, `0007_budgets.sql` and
  `0008_archive.sql`, so the schema version is 8.
- On every start, `prestart` and then the app's lifespan apply each file whose number is
  above the schema version, in number order (@backend/app/storage/migrate.py).
- Each file runs in its own transaction together with its `schema_version` row. If it fails,
  that transaction is rolled back, the backend does not start, and the database stays at the
  previous version.
- A migration file must not contain `BEGIN` or `COMMIT`; the runner owns the transaction.
- The runner turns foreign keys off around each migration and runs `PRAGMA foreign_key_check`
  before the commit, so a table rebuild (create, copy, drop, rename) keeps the rows that
  reference the table instead of cascade-deleting them; a broken reference fails the
  migration.
- A committed migration is never edited. A change is a new migration.
- A feature spec that adds tables lists its migration in "Files to Modify" and documents the
  new entities in this file.

## Subsystems

- [storage](subsystems/storage/README.md) — owns the connection, the migration runner and
  all SQL
- [categorization](subsystems/categorization/README.md) — the rules on top of the catalog
  tables, and the line categories
- [import](subsystems/import/README.md) — creates the receipt and line rows
- [review](subsystems/review/README.md) — reads receipts and lines for the review UI, edits,
  adds and deletes lines, and sets the store, date, total and review state
- [receipt-reading](subsystems/receipt-reading/README.md) — produces the read data
- [archive](subsystems/archive/README.md) — moves a finished year into the archive tables,
  deletes an archived year and reads its totals

## Related Documents

- [architecture.md](architecture.md): where storage sits among the subsystems
- [Foundation spec](../specs/features/foundation.md) PC4: database requirements
- [Product management spec](../specs/features/product-management.md): the catalog tables
- [Receipt import spec](../specs/features/receipt-import.md): the `receipts` table
- [Receipt reading spec](../specs/features/receipt-reading.md): the read columns and
  `receipt_lines`
- [Archiving spec](../specs/features/archiving.md): the archive tables
- [Categorization spec](../specs/features/categorization.md): the line category columns
- [Receipt review spec](../specs/features/receipt-review.md): the `reviewed` column
- [Line editing spec](../specs/features/line-editing.md): edited, added and deleted lines;
  no schema change
- [development.md](development.md#running-the-app): where the data lives when the app runs

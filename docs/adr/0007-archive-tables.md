# 0007. Archive in separate tables of the same database, with names instead of ids

- Status: accepted
- Date: 2026-11-13

## Context

Archiving ([spec](../../specs/features/archiving.md), PRD FR-40–FR-42, FR-53) moves the
reviewed receipts of a finished year out of the active data. The active pages, totals,
budget comparison and exports must not see them. The archived year's totals per group,
category and product must stay viewable and exportable, and an archived image must still be
found as a duplicate. The user may later rename, merge or delete categories and products
(FR-36, FR-37), and must not be blocked by archived lines.

The options were:

1. **An `archived` flag** on `receipts`: no copy, but every active query needs the filter,
   and archived lines keep their category and product ids, so catalog changes rewrite
   history and a category with archived lines cannot be deleted.
2. **Separate tables in the same database** with names instead of ids: one copy at
   archiving; active queries stay as they are; one backup covers both.
3. **A separate database file**: the active database shrinks, but a backup and a restore
   handle two files, the duplicate lookup crosses databases, and the move is not one
   transaction.

## Decision

- Archived receipts and lines live in `archived_receipts` and `archived_lines` in the same
  SQLite database (migration `0008_archive.sql`).
- An archived line stores its product, category and group as **names** at archiving. No
  archive column refers to an active table.
- The archived rows keep the active **ids**. Active ids are `AUTOINCREMENT` and never
  reused, so they are unique across both tables, and archiving a year again cannot collide.
- The archive leaves out the OCR text and the review state: the archive is not re-read, and
  every archived receipt was reviewed.
- The move is one transaction (copy, then delete); the image moves follow the commit.

## Consequences

- Active queries need no change and read fewer rows after an archiving.
- Catalog changes never touch archived lines, and deleting a category or product is not
  blocked by them. An archived year shows the names it had at archiving.
- The archive has no catalog order, so its groups and categories sort by name.
- `archived_receipts.image_hash` is `UNIQUE` and the duplicate lookup reads both tables.
- An archived receipt cannot be re-parsed (no OCR text) or shown one by one.
- One database backup covers active and archived data.

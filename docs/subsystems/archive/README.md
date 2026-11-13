# Archive

Navigation: ↑ [Architecture](../../architecture.md) | → [API reference](../../api-reference.md#archive) | → [Data model](../../datamodel.md#archived_receipts) | → [Calculation](../calculation/README.md#archived-year-totals) | → [Storage](../storage/README.md) | → [Export](../export/README.md) | → [UI](../ui/README.md)

## Overview

Archive moves a finished year out of the active data (PRD FR-40–FR-42, FR-53). The user
archives a year on the Arkisto page when its receipts are reviewed. The receipts and lines
move into two archive tables, and the images move from the done folder to the archive
folder. The active pages, totals, budget comparison and exports then read less data, and
the archived year's totals per group, category and product stay viewable and exportable.

The archive keeps names, not ids: each archived line stores its product, category and group
name at archiving ([ADR 0007](../../adr/0007-archive-tables.md)). Later catalog changes
never touch archived lines, and archived lines never block deleting a category or product.

It does not:

- show archived receipts one by one, their lines or images;
- undo an archiving, edit archived data or delete image files;
- archive the current year, part of a year, or a year with unreviewed receipts.

## Key Files and Entry Points

- @backend/app/archive/routes.py — `create_archive_router(settings, import_service, clock,
  files)`: `GET /api/archive`, `POST` and `DELETE /api/archive/{year}`,
  `GET /api/archive/{year}/totals`, one connection per request
- @backend/app/archive/service.py — `ArchiveService`: `overview()`, `archive()`, `delete()`,
  `totals()`; `parse_year`, `read_year_totals`; the `ArchiveFiles` protocol and
  `LocalArchiveFiles`
- @backend/app/archive/schemas.py — the API shape
- @backend/app/archive/errors.py — `InvalidYearError`, `YearNotFinishedError`,
  `ArchiveImportRunningError`, `NothingToArchiveError`, `UnreviewedReceiptsError` (adds
  `count`), `YearNotArchivedError` (`not_found`)
- @backend/app/storage/archive_repository.py — all archive SQL
- @backend/app/storage/migrations/0008_archive.sql — the archive tables
- @backend/app/calculation/archive_totals.py, @backend/app/calculation/names.py — the year
  totals tree and the Finnish name order
- @backend/app/local_time.py — the Finnish time zone and today's date, shared with export

## Interfaces

The endpoints, their shape and error codes are in the
[API reference](../../api-reference.md#archive).

| Method | Does | Raises |
|---|---|---|
| `ArchiveService.overview()` | The archived years and the candidates (years before the current Finnish year with active dated receipts), read in one transaction | nothing |
| `ArchiveService.archive(year_text)` | Checks the year, moves its rows in one transaction, then its images; returns the counts and the names not moved | `InvalidYearError`, `YearNotFinishedError`, `ArchiveImportRunningError`, `NothingToArchiveError`, `UnreviewedReceiptsError`, in that order |
| `ArchiveService.delete(year_text)` | Deletes the year's archived receipts and lines (lines by `ON DELETE CASCADE`); files stay | `InvalidYearError`, `YearNotArchivedError` |
| `ArchiveService.totals(year_text)` | The year totals tree from calculation | `InvalidYearError`, `YearNotArchivedError` |
| `read_year_totals(repository, year)` | The same totals for an already parsed year; used by export for the CSV file | `YearNotArchivedError` |
| `ArchiveRepository.archived_years(first, last)` | The archived years between two years; used by totals and budget for the period warning | nothing |

`ArchiveFiles` (`names_in`, `exists`, `move`) is the file access of the image moves. Tests
pass a fake that fails a move; the app passes `LocalArchiveFiles`, which uses the safe move
of @backend/app/image_files.py.

## Data Flow

### Archiving a year

1. `parse_year` accepts four digits from 2000 to 9999 (`invalid_year`). `year` is a plain
   string path parameter, so a bad value reaches the service.
2. A year that is not before the current Finnish year is refused (`year_not_finished`).
3. A running import is refused (`import_running`), so the done folder does not change under
   the moves.
4. In one transaction: the year's active receipts are counted (none: `nothing_to_archive`;
   unreviewed: `unreviewed_receipts` with the count), then copied with their lines into
   `archived_receipts` and `archived_lines` and deleted from `receipts` (lines by cascade).
   Ids are copied: active ids are never reused, so they cannot collide, also when a year is
   archived again. The line's product name is the linked product's name, else its own name.
5. After the commit (NFR-7), each image moves to a free name in the archive folder. A
   missing source or a failed move leaves the file and names it in `images_not_moved`; the
   row keeps its done folder name. The new names are stored in one short transaction; an
   error there is logged by type only, because the files have moved.
6. The log line has the year and counts only, no store, product or file name (NFR-3).

A receipt dated in an archived year that arrives later stays active, and archiving the year
again adds it.

### Duplicates

`ReceiptRepository.image_known(hash)` looks in `receipts` and `archived_receipts`, so an
archived image is still a duplicate for the [import](../import/README.md) and for a typed-in
receipt's image ([review](../review/README.md)). After a permanent delete, the year's images
are no longer known.

### Period warning

[Totals](../totals/README.md) and [budget](../budget/README.md) read
`ArchiveRepository.archived_years` in their transaction and answer `archived_years`. The
Yhteenveto and Vertailu pages and the two PDF reports show
`Arkistoitu vuosi 2025 ei ole mukana.` (`texts.archived_years_note`). CSV files do not
change.

## Dependencies

- Uses: [storage](../storage/README.md) (`ArchiveRepository`, `connect`),
  [calculation](../calculation/README.md#archived-year-totals) (`archive_totals`),
  `image_files` (`free_target_name`, `move_file`), `local_time`, and the
  [import](../import/README.md) service's state.
- Used by: the [UI](../ui/README.md) Arkisto and archived year pages;
  [export](../export/README.md) for the archive CSV file (`parse_year`,
  `read_year_totals`). This is the one dependency on archive: the CSV file must be built
  from the same reader as the page.

## Modules

None yet.

## Known Issues and Gotchas

- Archiving cannot be undone. The page asks the user to take a backup first
  (`scripts/backup-db.ps1`); a restore brings the rows back, and moved images are moved
  back by hand.
- An import that starts after the `import_running` check is accepted: it only adds new,
  unreviewed receipts and moves other files, so it cannot change what the transaction
  archives.
- An image that was not moved stays in the done folder under its name, and its archived row
  keeps that name. The user moves it by hand.
- Group and category names are the names at archiving. A renamed category shows its old
  name in the archived year, and the same name in two years can mean different things.
- Groups and categories are sorted by name in Finnish order, because the archive has no
  catalog order.

## Related Documents

- [Archiving spec](../../../specs/features/archiving.md)
- [ADR 0007: Archive tables](../../adr/0007-archive-tables.md)
- [Data model: archived_receipts](../../datamodel.md#archived_receipts)

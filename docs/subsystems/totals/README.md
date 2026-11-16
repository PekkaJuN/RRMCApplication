# Totals

Navigation: ↑ [Architecture](../../architecture.md) | → [API reference](../../api-reference.md#totals) | → [Calculation](../calculation/README.md#period-totals) | → [Categorization](../categorization/README.md) | → [Storage](../storage/README.md) | → [Export](../export/README.md) | → [UI](../ui/README.md)

## Overview

Totals serves `GET /api/totals`: spending per category and group, per ISO week and per
calendar month, by purchase date, for a period the user chooses (PRD FR-22–FR-25, FR-44, FR-49).
It reads the data and hands it to calculation; it holds no sum rule of its own:

- [calculation](../calculation/README.md#period-totals) checks the period, builds the week
  and month columns and computes every total;
- [storage](../storage/README.md#interfaces) reads the dated lines and the two counts;
- [categorization](../categorization/README.md) gives the category list order
  (`CategoryService.list()`), which is the row order.

It also serves `GET /api/year/totals`: the current year's totals per group, category and
product, by month, from reviewed receipts only (PRD FR-54), for the Vuosi tuotteineen page
and its CSV file. See [Current year totals](#current-year-totals).

It is a separate package because the totals span receipts and are also used by the CSV
export (FR-26), so they are computed in one place. Totals are never stored: every request
computes them from the database, so they always reflect the latest edits (FR-24).

## Key Files and Entry Points

- @backend/app/totals/routes.py — `create_totals_router(settings, clock)`: `GET /api/totals`
  and `GET /api/year/totals`, one connection per request; `clock` gives the current year in
  Finnish time
- @backend/app/totals/year.py — `read_year_totals(receipts, year)` → `YearTotals(totals,
  unreviewed)`
- @backend/app/totals/service.py — `TotalsService.totals(unit, first, last)` →
  `TotalsView(totals, unreviewed_receipts, undated_receipts, archived_years)`
- @backend/app/totals/schemas.py — the API shape; `from_` is sent as `from`
- @backend/app/totals/errors.py — `InvalidPeriodError` (422 `invalid_period`)

## Interfaces

The endpoint, its shape and its error code are in the
[API reference](../../api-reference.md#totals).

| Method | Does | Raises |
|---|---|---|
| `TotalsService(catalog, receipts, archive).totals(unit, first, last)` | Parses the period, reads the lines dated in it, the unreviewed count of the period, the undated count, the archived years of the period and the category list in one transaction, and returns the period totals | `InvalidPeriodError` |
| `TotalsService.period(unit, first, last)` | Parses the period | `InvalidPeriodError` |
| `TotalsService.read(period)` | Reads the dated lines and the category list and returns `period_totals`; opens no transaction, so the caller holds one ([export](../export/README.md)) | nothing |
| `read_year_totals(receipts, year)` | Reads the year's reviewed lines with their names and the year's unreviewed count in one transaction, and returns the year tree; shared with the year CSV file of [export](../export/README.md) | nothing |

## Data Flow

1. The route passes `unit`, `from` and `to` as plain optional strings. FastAPI validates
   nothing, so every missing or malformed value reaches `parse_period` and becomes
   `invalid_period`, not the generic `invalid_request`.
2. The service reads, in one transaction, `dated_lines(start, end)`,
   `count_unreviewed(start, end)`, `count_undated()`, `CategoryService.list()` and
   `ArchiveRepository.archived_years(start year, end year)`. Archived receipts are not in
   the active tables, so they are in no total; `archived_years` tells the page which years
   of the period are archived ([archive](../archive/README.md#period-warning)).
3. `period_totals(period, lines, catalog)` computes the columns, rows and column totals.
4. The answer holds category and group names and cents only; no product name is read
   (NFR-3). The request log has no query string (@backend/app/logging_setup.py).

### Current year totals

1. `GET /api/year/totals` takes the year from `local_today(clock)` (@backend/app/local_time.py),
   so the year changes at midnight in Finland.
2. `read_year_totals` reads `ReceiptRepository.year_lines` and `count_unreviewed` for
   `<year>-01-01`–`<year>-12-31` in one transaction. Only reviewed receipts are in the lines;
   undated receipts and other years are not.
3. The names are the current catalog names: a linked line has its product's name, else its
   own name. The lines become `ArchiveLine`s, and `archive_totals` of
   [calculation](../calculation/README.md#archived-year-totals) builds the tree: Finnish name
   order, deposit refunds left out, the same shape as an archived year's totals.
4. The answer is the archived year's shape plus `unreviewed`. It holds product names; they
   are never logged (NFR-3).

## Dependencies

- Uses: [calculation](../calculation/README.md),
  [categorization](../categorization/README.md) (the category list order),
  [storage](../storage/README.md) (also `ArchiveRepository.archived_years` and
  `year_lines`), [archive](../archive/README.md) (`ArchiveTotalsOut`, the shape of the year
  totals answer).
- Used by: the [UI](../ui/README.md) Yhteenveto and Vuosi tuotteineen pages; [export](../export/README.md) for
  the totals file and the totals PDF; [budget](../budget/README.md) for `ColumnOut` and `InvalidPeriodError`.

## Modules

None yet.

## Known Issues and Gotchas

- The year totals count reviewed receipts only, unlike `GET /api/totals`, so the two can
  differ for the same months until every receipt is reviewed.
- The year tree is sorted by name, not in the catalog order of `GET /api/totals`, because it
  shares the archived year's tree.
- Every receipt counts in `GET /api/totals`, reviewed or not; `unreviewed_receipts` tells the user which totals
  may still change. A receipt without a purchase date is in no period; `undated_receipts`
  counts them over all receipts, whatever the period.
- `purchase_date` has no index. A full scan of one user's receipts is fast; add an index by
  migration if that changes.

## Related Documents

- [Category totals spec](../../../specs/features/totals.md)
- [Year with products spec](../../../specs/features/year-products.md)
- [Architecture](../../architecture.md#component-map)

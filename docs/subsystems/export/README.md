# Export

Navigation: ↑ [Architecture](../../architecture.md) | → [API reference](../../api-reference.md#export) | → [Totals](../totals/README.md) | → [Storage](../storage/README.md) | → [UI](../ui/README.md)

## Overview

Export serves the CSV downloads of the Yhteenveto page (PRD FR-26, FR-27): the **lines
file** of a period, and the **totals file** of a period by week or by month. The files are
built only through the `Exporter` interface, so a Google Sheets exporter (FR-28) can be
added later without changing the endpoints.

Export computes no sum itself. The totals file uses the same `TotalsService.read` as
`GET /api/totals`, so the file and the Yhteenveto page always agree (PRD risk table). The
lines file reads the period's lines with their store, review state, category and group
names from storage.

## Key Files and Entry Points

- @backend/app/export/routes.py — `create_export_router(settings, exporter)`:
  `GET /api/export/lines` and `GET /api/export/totals`, one connection per request; the
  answer is a download (`Content-Disposition: attachment`, `Cache-Control: no-store`)
- @backend/app/export/service.py — `ExportService(catalog, receipts, exporter)`: checks
  the period, then `by`, reads in one transaction and calls the exporter
- @backend/app/export/exporter.py — the `Exporter` protocol, `ExportFile`, `ExportLine`
- @backend/app/export/csv_exporter.py — `CsvExporter`: the CSV format of FR-26
- @backend/app/export/rows.py — `long_rows(totals, by)`: the totals file's rows

## Interfaces

The endpoints, their files and error codes are in the
[API reference](../../api-reference.md#export).

| Method | Does | Raises |
|---|---|---|
| `ExportService.lines_file(unit, first, last)` | Parses the period, reads `export_lines` and returns the exporter's lines file | `InvalidPeriodError` |
| `ExportService.totals_file(unit, first, last, by)` | Parses the period, checks that `by` is `week` or `month`, reads the totals and returns the exporter's totals file | `InvalidPeriodError`, then `AppError` `invalid_request` |
| `Exporter.lines_file(period, lines)` | Builds the lines file from `ExportLine` items | nothing |
| `Exporter.totals_file(totals, by)` | Builds the totals file of the week columns (`by` `week`) or the month columns (`month`) | nothing |

`create_app(exporter=...)` takes another exporter; tests pass a fixed one. Production uses
`CsvExporter`.

## Data Flow

1. The route passes `unit`, `from`, `to` and `by` as plain optional strings, as the totals
   route does, so a bad period becomes `invalid_period` before a bad `by` becomes
   `invalid_request`.
2. The lines file reads `ReceiptRepository.export_lines(start, end)`: the lines in purchase
   date order, then import order, then position. The totals file calls
   `TotalsService.read(period)`.
3. `long_rows(totals, by)` lists, per week or month column in date order, each category
   that has at least one counted line in that column (`TotalsRow.week_counts` and
   `month_counts`), groups' categories first with the group name, then the categories
   without a group, then `Ei kategoriaa`. So a category whose lines sum to 0 is listed,
   and columns without lines and group sums are not.
4. `CsvExporter` writes the rows (format below) and names the file after the period's
   bounds.
5. The request log holds method, path, status and duration only; the query string and the
   file name are never logged (@backend/app/logging_setup.py).

### CSV format

- `;` between fields, UTF-8 with a byte order mark, a Finnish header row, `\r\n` after
  every row; amounts as `1,25` and `-0,40` (integer arithmetic, no euro sign or thousands
  separator); dates as `YYYY-MM-DD`; `kyllä` and `ei`.
- The exporter writes its own rows instead of `csv.writer`: a cell is quoted when it holds
  `;`, `"`, `\r` or `\n`, or starts or ends with a space (`QUOTE_MINIMAL` does not quote
  spaces), and `"` is doubled.
- User text (store, product, group, category) that starts with `=`, `+`, `-` or `@` gets a
  leading `'`, so Excel shows it as text instead of running it as a formula. Amounts and
  dates are not changed, so `-1,50` stays a number.
- File names: `kuittirivit_<from>_<to>.csv`, `summat_viikot_<from>_<to>.csv`,
  `summat_kuukaudet_<from>_<to>.csv`. `parse_period` has checked the bounds, so they hold
  only digits, `-` and `W`.

## Dependencies

- Uses: [totals](../totals/README.md) (`TotalsService.period` and `read`),
  [calculation](../calculation/README.md) (the period and totals types),
  [storage](../storage/README.md) (`export_lines`).
- Used by: the [UI](../ui/README.md) Yhteenveto page's three download links.

## Modules

None yet.

## Known Issues and Gotchas

- Receipts without a purchase date are in no period, so no file has them; the Yhteenveto
  page shows their count.
- The browser downloads the file through the Vite proxy with a plain link, so an error
  answer (422) would be saved as a file. The page shows the links only while the totals of
  the same period loaded, so the period is valid.

## Related Documents

- [CSV export spec](../../../specs/features/csv-export.md)
- [Architecture](../../architecture.md#component-map)

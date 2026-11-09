# Export

Navigation: ↑ [Architecture](../../architecture.md) | → [API reference](../../api-reference.md#export) | → [Totals](../totals/README.md) | → [Budget](../budget/README.md) | → [Storage](../storage/README.md) | → [UI](../ui/README.md)

## Overview

Export serves the downloads of the Yhteenveto and Vertailu pages:

- **CSV** (PRD FR-26, FR-27): the **lines file** of a period, and the **totals file** of a
  period by week or by month.
- **PDF** (PRD FR-48): the **weekly totals PDF** (A4 landscape), the **monthly totals PDF**
  (A4 portrait, stacked month blocks) and the **comparison PDF** (A4 portrait, the Vertailu
  month table).

The CSV files are built through the `Exporter` interface and the PDF files through the
`ReportExporter` interface, so a Google Sheets exporter (FR-28) or a CSV file of the
comparison can be added later without changing the endpoints. Two small interfaces instead
of one: a report file has no lines file, and the CSV totals file needs no counts.

Export computes no sum itself. The totals files use the same `TotalsService` as
`GET /api/totals`, and the comparison PDF the same `BudgetService.comparison` as
`GET /api/budget/comparison`, so a file and its page always agree (PRD risk table). The
lines file reads the period's lines with their store, review state, category and group
names from storage.

## Key Files and Entry Points

- @backend/app/export/routes.py — `create_export_router(settings, exporter,
  report_exporter, clock)`: `GET /api/export/lines`, `/totals`, `/totals/pdf` and
  `/comparison/pdf`, one connection per request; the answer is a download
  (`Content-Disposition: attachment`, `Cache-Control: no-store`)
- @backend/app/export/service.py — `ExportService`: checks the period, then `by`, then a
  PDF's length, reads in one transaction and calls the exporter
- @backend/app/export/exporter.py — the `Exporter` and `ReportExporter` protocols,
  `ExportFile`, `ExportLine`, `TotalsReport`, `ComparisonReport`
- @backend/app/export/csv_exporter.py — `CsvExporter`: the CSV format of FR-26
- @backend/app/export/rows.py — `long_rows(totals, by)`: the CSV totals file's rows
- @backend/app/export/pdf_exporter.py — `PdfExporter`: the PDF files, with reportlab
  ([ADR 0005](../../adr/0005-pdf-library.md))
- @backend/app/export/report.py — the PDF rows: every group expanded, the period block
- @backend/app/export/finnish.py — money, dates and column headings as the pages show them
- @backend/app/export/limits.py — the PDF length limits; @backend/app/export/errors.py —
  `PeriodTooLongError`

## Interfaces

The endpoints, their files and error codes are in the
[API reference](../../api-reference.md#export).

| Method | Does | Raises |
|---|---|---|
| `ExportService.lines_file(unit, first, last)` | Parses the period, reads `export_lines` and returns the exporter's lines file | `InvalidPeriodError` |
| `ExportService.totals_file(unit, first, last, by)` | Parses the period, checks that `by` is `week` or `month`, reads the totals and returns the exporter's totals file | `InvalidPeriodError`, then `AppError` `invalid_request` |
| `ExportService.totals_pdf(unit, first, last, by)` | As `totals_file`, then checks the length; reads the totals and both counts as `TotalsService.totals` does | `InvalidPeriodError`, `invalid_request`, then `PeriodTooLongError` |
| `ExportService.comparison_pdf(month, period)` | Reads `BudgetService.comparison` | `InvalidPeriodError` |
| `Exporter.lines_file(period, lines)` | Builds the lines file from `ExportLine` items | nothing |
| `Exporter.totals_file(totals, by)` | Builds the totals file of the week columns (`by` `week`) or the month columns (`month`) | nothing |
| `ReportExporter.totals_report(report, by)` | Builds the weekly or monthly totals PDF | nothing |
| `ReportExporter.comparison_report(report)` | Builds the comparison PDF | nothing |

`create_app(exporter=..., report_exporter=..., clock=...)` takes other exporters and a fixed
clock; tests pass fixed ones. Production uses `CsvExporter`, `PdfExporter` and the system
clock.

## Data Flow

1. The route passes `unit`, `from`, `to` and `by` as plain optional strings, as the totals
   route does, so a bad period becomes `invalid_period` before a bad `by` becomes
   `invalid_request`, and both come before `period_too_long`.
2. The lines file reads `ReceiptRepository.export_lines(start, end)`: the lines in purchase
   date order, then import order, then position. The CSV totals file calls
   `TotalsService.read(period)`; the totals PDF calls `TotalsService.totals`, which also
   counts the unreviewed and undated receipts.
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
  `summat_kuukaudet_<from>_<to>.csv`. A date range gives
  `kuittirivit_2026-10-15_2026-11-14.csv`. `parse_period` has checked the bounds, so they
  hold only digits, `-` and `W`.

### PDF layout

- **Limits:** the weekly PDF covers at most 31 days (at most 6 week columns), the monthly
  PDF at most 366 days. Longer periods are refused with `period_too_long`, so columns
  never split over pages.
- **Header:** the title, `Jakso: <first day>–<last day>`, for the comparison
  `Jakson tyyppi: Kalenterikuukausi` or `15.–14.`, `Luotu <day>` and the counts of the page
  when they are not 0. The creation day is the clock's time in `Europe/Helsinki`.
- **Rows:** the totals PDFs show every group expanded: the group row (bold), its
  categories (indented), the standalone categories, `Ei kategoriaa` and `Yhteensä` (bold).
  The comparison shows the budget rows as the Vertailu page; a negative `Jäljellä` also
  reads `Ylitetty`.
- **Month blocks:** the monthly PDF stacks one two-column block (`Kategoria`, `Summa`) per
  month column, then the **period block** `Koko jakso` with each row's sum over the whole
  period. A period of at most 31 days, such as 15.10.–14.11., has no period block. A block
  that fits on a page is kept whole (`KeepTogether`); a taller one starts at once and
  continues on the next page under its heading with the mark `(jatkuu)`.
- **Pages:** 15 mm margins; text at least 9 pt (table 10 pt, column headings 9 pt);
  names are paragraphs, so a long name wraps inside its column; a table that runs over a
  page repeats its heading rows; every page ends with `Sivu n/total`, written in a second
  layout pass once the number of pages is known.
- **Metadata:** the title only; author, creator, producer, subject and keywords are empty.
- File names: `summat_viikot_<from>_<to>.pdf`, `summat_kuukaudet_<from>_<to>.pdf`,
  `vertailu_<month>.pdf`, `vertailu_15-14_<month>.pdf`.

## Dependencies

- Uses: [totals](../totals/README.md) (`TotalsService.period`, `read` and `totals`),
  [budget](../budget/README.md) (`BudgetService.comparison`),
  [calculation](../calculation/README.md) (the period, totals and comparison types),
  [storage](../storage/README.md) (`export_lines`); reportlab for the PDF files.
- Used by: the [UI](../ui/README.md) Yhteenveto page's download links and the Vertailu
  page's PDF link.

## Modules

None yet.

## Known Issues and Gotchas

- Receipts without a purchase date are in no period, so no file has them; the pages and
  the PDF files show their count.
- The browser downloads the file through the Vite proxy with a plain link, so an error
  answer (422) would be saved as a file. The pages show a link only while the data of the
  same period loaded, so the period is valid, and the Yhteenveto page replaces a PDF link
  by a text when the period is over its limit.
- The PDF uses the standard fonts, which cover Finnish, Swedish and `€`. A character
  outside WinAnsi in a name would not show correctly ([ADR 0005](../../adr/0005-pdf-library.md)).
- Tests read the PDF files back with pdfminer.six (@backend/tests/pdf_reader.py):
  `Page.rows()` joins the characters of a baseline into cells, `Ruoka | 1,25 €`.

## Related Documents

- [CSV export spec](../../../specs/features/csv-export.md)
- [PDF export spec](../../../specs/features/pdf-export.md)
- [ADR 0005: PDF library](../../adr/0005-pdf-library.md)
- [Architecture](../../architecture.md#component-map)

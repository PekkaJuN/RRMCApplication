# Feature: CSV export

## Overview
- **Status:** Done
- **Created:** 2026-11-02
- **Updated:** 2026-11-02: user answers before Specify: the export is started on the
  Yhteenveto page for its period; two buttons, one per file; file names hold the period.
  The CSV format is decided in PRD FR-26 (open question 7). Specify approved by the user;
  Plan added. Plan approved by the user; Tasks added. User change before approval: the
  totals file holds either weeks or months, chosen with its own link (`by`); three
  links instead of two; the `Jakson tyyppi` column is dropped (Specify, Plan and Tasks
  updated). Spec approved by the user. Implemented and audited (PASS). Later change
  (2026-11-11): the [Finnish CSV dates spec](finnish-csv-dates.md) changed the date cells of
  both files to `dd.mm.yyyy`; the examples below keep the ISO dates of this spec's time.
- **Depends on:** [Category totals](totals.md)
- **Implements:** PRD FR-26, FR-27, FR-44 (exported totals); NFR-1, NFR-3, NFR-6, NFR-15 for
  the export.
- **Affected subsystems:** **export** (new, see
  [architecture](../../docs/architecture.md#component-map)),
  [totals](../../docs/subsystems/totals/README.md),
  [storage](../../docs/subsystems/storage/README.md),
  [ui](../../docs/subsystems/ui/README.md)

## Problem Statement
The Yhteenveto page shows the totals, but the user cannot take the data elsewhere, for
example to an own budget workbook in Excel (PRD G5, section 5 step 7). This spec adds a CSV
export of the receipt lines and the totals of the period chosen on the Yhteenveto page, in
a format that Finnish Excel opens correctly, behind an exporter interface so that Google
Sheets (FR-28) can be added later.

## Current Behavior
- `GET /api/totals` returns the totals of a period, and the Yhteenveto page keeps the period
  in its address ([totals](../../docs/subsystems/totals/README.md),
  [ui](../../docs/subsystems/ui/README.md)).
- Receipt lines have a name, amount, deposit refund flag and category; receipts have a
  purchase date, store and review state ([datamodel](../../docs/datamodel.md)).
- There is no export. The architecture plans an `export` subsystem with an `Exporter`
  interface ([architecture](../../docs/architecture.md#key-interfaces)).

## Proposed Change

### Concepts

- The **lines file** has one row per receipt line of the receipts whose purchase date is in
  the period, deposit refunds included.
- The **totals file** is in **long format** and holds either weeks or months (`by`), never
  both: one row per column of that kind (ISO week or month, as in the totals spec) and
  category that has at least one counted line in that column.
  Counted lines are the lines of the totals: deposit refunds are left out (FR-44); lines
  without a category are counted under `Ei kategoriaa`. No rows for group sums (a pivot
  table computes them from the Ryhmä column) and no rows for columns without lines.
- Both files use the **CSV format of FR-26**: `;` between fields, UTF-8 with a byte order
  mark, a Finnish header row, `CRLF` line ends. Amounts have a decimal comma and no euro
  sign or thousands separator; dates are `YYYY-MM-DD`.

### Parts

- **PC1 Exporter interface (FR-27).** The export endpoints build their files only through
  one exporter interface: it gets the period's lines and totals and returns a file (name,
  media type, bytes). The CSV exporter is the first implementation; a later one (Google
  Sheets) is added without changing the endpoints' callers.
- **PC2 Lines endpoint (FR-26).** `GET /api/export/lines?unit=...&from=...&to=...` returns
  the lines file of the period. Rows are in purchase date order, then receipt (import
  order), then the line's position on the receipt. Columns:

  | Column | Value |
  |---|---|
  | `Päivä` | purchase date, `2026-10-05` |
  | `Viikko` | ISO week of the purchase date, `2026-W41` |
  | `Kuukausi` | month of the purchase date, `2026-10` |
  | `Kauppa` | store; empty without one |
  | `Tuote` | line name |
  | `Summa` | line amount, `1,25`, `-0,40` |
  | `Ryhmä` | the category's group; empty without a group or category |
  | `Kategoria` | the line's category; empty without one (deposit refunds have none) |
  | `Pantinpalautus` | `kyllä` or `ei` |
  | `Kuitin tila` | `Tarkistamaton` or `Vahvistettu` |

- **PC3 Totals endpoint (FR-26, FR-44).**
  `GET /api/export/totals?unit=...&from=...&to=...&by=week|month` returns the totals file
  of the period with the week columns (`by=week`) or the month columns (`by=month`) of the
  totals view, computed by the same totals service as the Yhteenveto page, so the two
  always agree. `by` is independent of the period's unit: a month period can be exported by
  week, with partial weeks at its edges, and a week period by month. Rows: the columns in
  date order; inside a column, categories in category list order (each group's categories,
  then the categories without a group), `Ei kategoriaa` last. Columns:

  | Column | Value |
  |---|---|
  | `Jakso` | `2026-W40` (`by=week`) or `2026-10` (`by=month`) |
  | `Alkaa`, `Päättyy` | the column's days inside the period, `2026-10-01` |
  | `Osittainen` | `kyllä` or `ei` |
  | `Ryhmä` | the category's group; empty without one |
  | `Kategoria` | the category, or `Ei kategoriaa` |
  | `Summa` | the category's total in the column, `1,25` |

- **PC4 Responses.** Both endpoints answer `200` with `Content-Type: text/csv;
  charset=utf-8`, `Content-Disposition: attachment; filename="<name>"` and `Cache-Control:
  no-store`. Names: `kuittirivit_<from>_<to>.csv`, `summat_viikot_<from>_<to>.csv` and
  `summat_kuukaudet_<from>_<to>.csv`, e.g. `kuittirivit_2026-10_2026-10.csv`,
  `summat_viikot_2026-W40_2026-W41.csv`. A period without lines gives the header row only.
  An invalid period gives `422 invalid_period`, as `GET /api/totals` (totals spec PC3). A
  missing or other `by` on the totals endpoint gives `422 invalid_request` (the
  [API error format](../../docs/api-reference.md#error-format)); the period is checked
  first.
- **PC5 Text cells.** A field that holds `;`, `"`, a line break or starts or ends with a
  space is quoted, with `"` doubled (RFC 4180). A text field (Kauppa, Tuote, Ryhmä,
  Kategoria) that starts with `=`, `+`, `-` or `@` gets a leading `'`, so Excel shows it as
  text and never runs it as a formula. Amounts and dates are not changed.
- **PC6 Export buttons on the Yhteenveto page (FR-26).** Under the period chooser, three
  links that look like buttons, `Vie viikkosummat (CSV)`, `Vie kuukausisummat (CSV)` and
  `Vie rivit (CSV)`, download the files of the period shown: the totals by week, the totals
  by month, and the lines. They are shown when the totals of the period loaded, also when
  the period has no lines; they are hidden while a period is refused or the totals cannot
  be loaded.
- **PC7 Privacy (NFR-1, NFR-3).** The files go only to the user's browser, as a download
  from the local backend. The request log holds method, path and status only (the query
  string and file names are never logged); error messages hold no receipt content.

### UI texts

| Place | Text |
|---|---|
| Weekly totals download link | `Vie viikkosummat (CSV)` |
| Monthly totals download link | `Vie kuukausisummat (CSV)` |
| Lines download link | `Vie rivit (CSV)` |

The header rows and cell values are in PC2 and PC3.

### Out of Scope
- Google Sheets (FR-28): a later release; it adds an exporter behind PC1.
- Wide format and Excel files (`.xlsx`).
- Exporting receipts without a purchase date (they are in no period), receipt-level fields
  other than the store and state (total, file name, import time), the category source and
  ids.
- Quantity, unit price and time: not read or stored (PRD FR-8 note).
- Choosing the separator, encoding or columns in the UI.
- Archived data (FR-40–FR-42).

## Acceptance Criteria

Fixture unless the AC says otherwise: the default catalog (Ruoka holds Leivät and
Maitotuotteet; Juomat has no group), and these receipts. The file content is shown without
the byte order mark and with `\n` for line ends.

- Receipt A, dated 2026-10-02, store `Testikauppa`, unreviewed: `Maito` 125 Maitotuotteet.
- Receipt B, dated 2026-10-06, store `Testikauppa`, confirmed: `Ruisleipä` 300 Leivät,
  `Limu` 250 Juomat, `Tuntematon` 199 no category, `Panttipalautus` -40 deposit refund.
- Receipt C, dated 2026-11-01, `Ruisleipä` 999 Leivät (outside October).

### AC1: Lines file of a month
**Given** the fixture
**When** the client calls `GET /api/export/lines?unit=month&from=2026-10&to=2026-10`
**Then** the answer is 200 and the content, after the byte order mark, is:
```
Päivä;Viikko;Kuukausi;Kauppa;Tuote;Summa;Ryhmä;Kategoria;Pantinpalautus;Kuitin tila
2026-10-02;2026-W40;2026-10;Testikauppa;Maito;1,25;Ruoka;Maitotuotteet;ei;Tarkistamaton
2026-10-06;2026-W41;2026-10;Testikauppa;Ruisleipä;3,00;Ruoka;Leivät;ei;Vahvistettu
2026-10-06;2026-W41;2026-10;Testikauppa;Limu;2,50;;Juomat;ei;Vahvistettu
2026-10-06;2026-W41;2026-10;Testikauppa;Tuntematon;1,99;;;ei;Vahvistettu
2026-10-06;2026-W41;2026-10;Testikauppa;Panttipalautus;-0,40;;;kyllä;Vahvistettu
```

### AC2: Weekly totals file of a month in long format
**Given** the fixture
**When** the client calls
`GET /api/export/totals?unit=month&from=2026-10&to=2026-10&by=week`
**Then** the answer is 200 and the content is:
```
Jakso;Alkaa;Päättyy;Osittainen;Ryhmä;Kategoria;Summa
2026-W40;2026-10-01;2026-10-04;kyllä;Ruoka;Maitotuotteet;1,25
2026-W41;2026-10-05;2026-10-11;ei;Ruoka;Leivät;3,00
2026-W41;2026-10-05;2026-10-11;ei;;Juomat;2,50
2026-W41;2026-10-05;2026-10-11;ei;;Ei kategoriaa;1,99
```
(no rows for weeks 42–44, no month rows, no group rows, no deposit refund, receipt C not
counted)

### AC16: Monthly totals file of a month
**Given** the fixture
**When** the client calls
`GET /api/export/totals?unit=month&from=2026-10&to=2026-10&by=month`
**Then** the answer is 200 and the content is:
```
Jakso;Alkaa;Päättyy;Osittainen;Ryhmä;Kategoria;Summa
2026-10;2026-10-01;2026-10-31;ei;Ruoka;Leivät;3,00
2026-10;2026-10-01;2026-10-31;ei;Ruoka;Maitotuotteet;1,25
2026-10;2026-10-01;2026-10-31;ei;;Juomat;2,50
2026-10;2026-10-01;2026-10-31;ei;;Ei kategoriaa;1,99
```
(no week rows)

### AC3: The totals file matches the totals view
**Given** the fixture
**When** the client gets `GET /api/totals` and `GET /api/export/totals` with `by=week` and
`by=month` for October 2026
**Then** for every week column of the weekly file and every month column of the monthly
file, the sum of the file's `Summa` values equals the view's column total (`week_totals`,
`month_totals`), and each category's value equals its row in the view

### AC4: Week period with partial months
**Given** receipts dated 2026-09-30 (Leivät 100) and 2026-10-01 (Leivät 200)
**When** the client gets the totals file of `unit=week&from=2026-W40&to=2026-W40` with
`by=week` and with `by=month`
**Then** the weekly file's only row is `2026-W40;2026-09-28;2026-10-04;ei;Ruoka;Leivät;3,00`;
the monthly file's rows are `2026-09;2026-09-28;2026-09-30;kyllä;Ruoka;Leivät;1,00` and
`2026-10;2026-10-01;2026-10-04;kyllä;Ruoka;Leivät;2,00`; and the lines file of the same
period has both lines

### AC5: A category whose lines sum to 0 in a column
**Given** receipts dated 2026-10-05 with Leivät 300 and Leivät -300
**When** the client gets the weekly and the monthly totals file for October 2026
**Then** the weekly file has the row `2026-W41;2026-10-05;2026-10-11;ei;Ruoka;Leivät;0,00`
and the monthly file `2026-10;2026-10-01;2026-10-31;ei;Ruoka;Leivät;0,00`

### AC6: Response headers and file names
**Given** any data
**When** the client gets `/api/export/lines?unit=month&from=2026-10&to=2026-10`,
`/api/export/totals?unit=week&from=2026-W40&to=2026-W41&by=week` and
`/api/export/totals?unit=month&from=2026-10&to=2026-12&by=month`
**Then** all have `Content-Type: text/csv; charset=utf-8`, `Cache-Control: no-store`,
content starting with the bytes `EF BB BF`, line ends `\r\n` (also after the last row), and
`Content-Disposition: attachment; filename="kuittirivit_2026-10_2026-10.csv"`,
`attachment; filename="summat_viikot_2026-W40_2026-W41.csv"` and
`attachment; filename="summat_kuukaudet_2026-10_2026-12.csv"`

### AC7: Empty period
**Given** no receipts in March 2026
**When** the client gets the lines file and both totals files for March 2026
**Then** each is 200 with the header row only

### AC8: Invalid period
**Given** any data
**When** the client gets the lines file, and the totals file with `by=week`, with each
invalid period query of the totals spec AC12
**Then** the answer is 422 with `{"error": "invalid_period", "message": "Jakso on virheellinen."}`

### AC17: Invalid `by`
**Given** any data
**When** the client gets the totals file of October 2026 without `by`, with `by=day` and
with `by=WEEK`; and with `by=day` and an invalid period
**Then** the first three answers are 422 with
`{"error": "invalid_request", "message": "Pyyntö on virheellinen."}`, and the last is 422
`invalid_period` (the period is checked first)

### AC9: Quoting
**Given** a line named `Kahvi; tumma "Extra"` on a receipt whose store is ` Kauppa `
(spaces at both ends)
**When** the client gets the lines file of its month
**Then** the row holds `" Kauppa "` and `"Kahvi; tumma ""Extra"""`, and a CSV reader with
`;` as the separator reads them back as ` Kauppa ` and `Kahvi; tumma "Extra"`

### AC10: Formulas are not run
**Given** lines named `=1+1`, `+5`, `-20% ale` and `@SUMMA` with amount -150
**When** the client gets the lines file of their month
**Then** the Tuote cells are `'=1+1`, `'+5`, `'-20% ale` and `'@SUMMA`, and the Summa cells
stay `-1,50`

### AC11: Lines order
**Given** receipt D dated 2026-10-06 imported after receipt B, and receipt A, with lines at
positions 1 and 3 (a deleted line left a gap)
**When** the client gets the lines file for October 2026
**Then** the rows are receipt A's, then B's in position order, then D's in position order

### AC12: Exporter interface
**Given** the app is built with a test exporter in place of the CSV exporter, which returns
a fixed file
**When** the client calls either export endpoint with a valid period
**Then** the answer holds the test exporter's name, media type and bytes, and the exporter
received the period's lines, or its totals and the `by` of the request

### AC13: Export links on the Yhteenveto page
**Given** the Yhteenveto page shows the totals of `unit=week&from=2026-W40&to=2026-W41`
**When** the user looks under the period chooser
**Then** there are, in this order, the links `Vie viikkosummat (CSV)` with
`href="/api/export/totals?unit=week&from=2026-W40&to=2026-W41&by=week"`,
`Vie kuukausisummat (CSV)` with
`href="/api/export/totals?unit=week&from=2026-W40&to=2026-W41&by=month"` and
`Vie rivit (CSV)` with `href="/api/export/lines?unit=week&from=2026-W40&to=2026-W41"`, all
with the `download` attribute; after the user chooses another period they point to it

### AC14: Links with an empty period, hidden on errors
**Given** the totals of the period loaded with `rows` `[]`
**When** the page shows them
**Then** all three links are shown. **And** while the period is refused (`invalid_period`)
or the totals cannot be loaded, no link is shown

### AC15: Privacy
**Given** a receipt with a product name and store
**When** the lines file and a totals file are downloaded
**Then** the backend log holds only `GET /api/export/lines 200` and
`GET /api/export/totals 200` lines, with no product name, store, query string or file name

## Files to Modify

Refined by the Plan.

| File | Change |
|---|---|
| `backend/app/export/__init__.py` | New package |
| `backend/app/export/exporter.py` | `Exporter` protocol, `ExportFile`, `ExportLine` (P1) |
| `backend/app/export/csv_exporter.py` | `CsvExporter`: cells, quoting, formula guard, money and file names (P2) |
| `backend/app/export/rows.py` | `long_rows(totals, by)`: the totals file's rows (P3) |
| `backend/app/export/service.py` | `ExportService`: period, lines and totals for the exporter (P4) |
| `backend/app/export/routes.py` | `create_export_router(settings, exporter)`: the two endpoints (P5) |
| `backend/app/calculation/period_totals.py` | Line counts per column on `TotalsRow` (P3) |
| `backend/app/totals/service.py` | `period()` and `read(period)` split out of `totals()` (P4) |
| `backend/app/storage/receipt_repository.py` | `export_lines(start, end)` and `ExportLineRow` (P4) |
| `backend/app/main.py` | Include the export router; `create_app(exporter=...)` for tests (AC12) |
| `backend/app/texts.py` | `NO_CATEGORY` (`Ei kategoriaa`) for the totals file |
| `backend/tests/unit/totals/test_totals_service.py` | `period()` and `read()` (T5) |
| `backend/tests/unit/export/` | `test_csv_exporter.py`, `test_rows.py` |
| `backend/tests/unit/calculation/test_period_totals.py` | Line counts |
| `backend/tests/unit/storage/test_receipt_repository.py` | `export_lines` |
| `backend/tests/integration/test_export_api.py` | Integration tests |
| `frontend/src/api/export.ts` (+ test) | `exportUrl(kind, period)` |
| `frontend/src/components/TotalsPage.tsx` (+ test) | The three links (PC6) |
| `frontend/src/i18n/fi.ts` | Texts |
| `frontend/e2e/import.spec.ts` | E2E downloads |
| `docs/subsystems/export/README.md` | New Tier 2 doc |
| `docs/api-reference.md` | The two endpoints |
| `docs/architecture.md` | Export implemented; the overview paragraph; folder structure |
| `docs/subsystems/totals/README.md`, `docs/subsystems/calculation/README.md`, `docs/subsystems/storage/README.md`, `docs/subsystems/ui/README.md` | Used by export; line counts; the query; the links |
| `docs/glossary.md` | Lines file, totals file, long format |
| `docs/content-plan.md`, `specs/README.md` | Status, export row |
| `docs/development.md`, `docs/learnings.md` | Restart `backend-e2e` after a backend change (found in T10) |

## Risk
- **What could break:** a file that Excel opens with wrong characters (missing byte order
  mark) or in one column (wrong separator); amounts that Excel reads as text or dates
  (wrong decimal format); totals in the file that differ from the view if they were
  computed separately; a product name that Excel runs as a formula. The change only reads
  data.
- **Excel's own conversions:** Excel may show `2026-10` in the Kuukausi and Jakso columns
  as a date (`loka.26`). The value stays correct for sorting and pivots; it is not changed
  in the file.
- **Rollback:** revert the commit; no migration, no data change.
- **Dependencies:** none new expected (Python's `csv` module).

## Testing Strategy (MANDATORY)

### Unit tests
| AC | Function | Case | Given | When | Then | Mocks |
|---|---|---|---|---|---|---|
| AC1 | CSV lines writer | happy path | lines of the fixture | write | AC1 content | none |
| AC2 | CSV totals writer | by week | totals of the fixture | write | AC2 content | none |
| AC16 | CSV totals writer | by month | totals of the fixture | write | AC16 content | none |
| AC4 | long rows | partial months by month | AC4 totals | rows | AC4 rows | none |
| AC5 | totals rows | zero sum | lines summing to 0 | rows | `0,00` rows listed | none |
| AC6 | CSV writer | format | any rows | write | BOM, `;`, `\r\n`, file names | none |
| AC7 | CSV writers | empty | no lines | write | header only | none |
| AC9 | CSV writer | quoting | fields with `;`, `"`, spaces | write, read back | AC9 values | none |
| AC10 | CSV writer | formulas | AC10 names | write | `'` prefixed text, amounts unchanged | none |

### Integration tests
Real SQLite (temporary file) and real FastAPI app.
| AC | Scenario | Request / input | Expected output | Status |
|---|---|---|---|---|
| AC1 | lines file | `GET /api/export/lines?unit=month&from=2026-10&to=2026-10` | AC1 content | 200 |
| AC2 | weekly totals file | `GET /api/export/totals?...&by=week` October | AC2 content | 200 |
| AC16 | monthly totals file | `GET /api/export/totals?...&by=month` October | AC16 content | 200 |
| AC3 | matches the view | `/api/totals` and both totals files, October | equal sums | 200 |
| AC4 | week period | `unit=week&from=2026-W40&to=2026-W40`, `by=week` and `by=month` | AC4 rows | 200 |
| AC5 | zero sum | October | AC5 rows | 200 |
| AC6 | headers | the three AC6 requests | AC6 headers and bytes | 200 |
| AC7 | empty period | March 2026 | header only | 200 |
| AC8 | invalid period | each invalid query, both endpoints | `invalid_period` | 422 |
| AC17 | invalid `by` | no `by`, `day`, `WEEK`; `day` with a bad period | `invalid_request`; `invalid_period` | 422 |
| AC9 | quoting | AC9 receipt | AC9 cells | 200 |
| AC10 | formulas | AC10 lines | AC10 cells | 200 |
| AC11 | order | AC11 receipts | AC11 order | 200 |
| AC12 | interface | app with a test exporter | the test file; exporter got the data | 200 |
| AC15 | privacy | both endpoints, captured log | AC15 log lines only | 200 |

### Frontend component tests (MSW)
| AC | Case | Expected |
|---|---|---|
| AC13 | three links of the period, in order, then another period | `href` and `download` follow the period |
| AC14 | empty period; refused period; network error | links shown; hidden; hidden |

### E2E tests
| AC | Journey | Steps | Expected outcome |
|---|---|---|---|
| AC1, AC2, AC16, AC13 | import and export | import the synthetic receipt, open Yhteenveto for its month, click the three links | downloads named `summat_viikot_2026-10_2026-10.csv`, `summat_kuukaudet_2026-10_2026-10.csv` and `kuittirivit_2026-10_2026-10.csv`; the lines file holds the receipt's line names; the totals files start with the header row of AC2 and have `2026-W` and `2026-10` rows respectively |

### Coverage target
- Backend: 90 % lines; the CSV writers and the quoting: every branch tested.
- Frontend: 80 % lines for the changed page.

### Test data
- Synthetic fixtures only (no real receipts): invented receipts and lines through the test
  repository; the synthetic E2E receipt image.
- Mocks: MSW for the frontend; a test exporter for AC12.

## Related Documentation (MANDATORY)
- Tier 1: [PRD](../PRD.md) FR-26–FR-28, FR-44;
  [architecture](../../docs/architecture.md#key-interfaces);
  [datamodel](../../docs/datamodel.md); [API reference](../../docs/api-reference.md#totals);
  [glossary](../../docs/glossary.md)
- Tier 2: [totals](../../docs/subsystems/totals/README.md),
  [calculation](../../docs/subsystems/calculation/README.md#period-totals),
  [storage](../../docs/subsystems/storage/README.md),
  [ui](../../docs/subsystems/ui/README.md)
- Specs: [Category totals](totals.md)
- ADRs: [0001 tech stack](../../docs/adr/0001-tech-stack.md)

## Plan

### P0 Overview

```
GET /api/export/lines|totals?unit&from&to
  → export/routes.py   (plain optional strings, as GET /api/totals: bad values → invalid_period)
  → ExportService      (one connection, one read transaction)
      TotalsService.period(unit, from, to)        → Period, or InvalidPeriodError
      TotalsService.read(period)                  → PeriodTotals
      ReceiptRepository.export_lines(start, end)  → lines with store, state, category, group
  → Exporter.lines_file(period, lines) / totals_file(totals, by)  → ExportFile(name, media_type, content)
  → Response(content, media_type, Content-Disposition, Cache-Control: no-store)
```

No migration and no new dependency. Export asks totals for the totals, so the file and the
Yhteenveto page use one computation (AC3, architecture "Totals and export"). Formatting
with a decimal comma happens only in the CSV exporter and the UI (NFR-6).

### P1 Exporter interface (`export/exporter.py`)

- `ExportFile(name: str, media_type: str, content: bytes)`.
- `ExportLine(purchase_date: date, store: str | None, name: str, amount_cents: int,
  is_deposit_refund: bool, group_name: str | None, category_name: str | None, reviewed:
  bool)`.
- `class Exporter(Protocol)`: `lines_file(period: Period, lines: Sequence[ExportLine]) ->
  ExportFile` and `totals_file(totals: PeriodTotals, by: Unit) -> ExportFile`, where `by` is
  `week` or `month` (the `Unit` type of `calculation/period.py`). How a Google Sheets
  exporter answers the browser belongs to its spec (FR-28).

### P2 CSV exporter (`export/csv_exporter.py`)

- Writes its own rows instead of `csv.writer`, because `QUOTE_MINIMAL` does not quote
  leading or trailing spaces (PC5). `_cell(text)` quotes when the text holds `;`, `"`,
  `\r` or `\n`, or starts or ends with a space, and doubles `"`. `_text(text)` puts `'`
  before a text that starts with `=`, `+`, `-` or `@`, then calls `_cell`. Only Kauppa,
  Tuote, Ryhmä and Kategoria go through `_text`; amounts, dates and fixed words go through
  `_cell`.
- `_money(cents)`: `125` → `1,25`, `-40` → `-0,40`, integer arithmetic only.
- Content: the byte order mark, then each row joined by `;` and ended by `\r\n`, encoded
  UTF-8. Media type `text/csv; charset=utf-8`.
- File names `kuittirivit_<first>_<last>.csv`, `summat_viikot_<first>_<last>.csv` and
  `summat_kuukaudet_<first>_<last>.csv` from the period's bounds, which `parse_period`
  has already checked, so they hold only digits, `-` and `W`.
- A line's week and month: `date.isocalendar()` and the date, with four-digit years, the
  same keys as the totals columns.

### P3 Totals rows in long format

- `calculation/period_totals.py`: `TotalsRow` gets `week_counts` and `month_counts`, the
  number of counted lines per column. A group's counts are the sums of its categories'.
  The totals API schema lists its fields one by one, so `GET /api/totals` does not change.
- `export/rows.py`: `long_rows(totals, by) -> list[LongRow(column, group_name,
  category_name, amount_cents)]`: the week columns (`by` `week`) or the month columns
  (`month`), in order; inside a column, the leaf rows in row order (each group's
  categories with the group's name, then the categories without a group, then `none` as
  `Ei kategoriaa`), only where that column's count is above 0. That gives AC5 (a sum of 0 with lines is listed) and no
  rows for columns without lines (AC2). `Ei kategoriaa` comes from `app.texts`.

### P4 Data (`ExportService`, totals, storage)

- `TotalsService` is split without changing its behavior: `period(unit, first, last)`
  parses (raises `InvalidPeriodError`), `read(period)` reads and computes without opening a
  transaction, and `totals()` is `period()`, then `read()` inside a transaction, as today.
- `ReceiptRepository.export_lines(start, end) -> list[ExportLineRow]`: one query joining
  `receipt_lines`, `receipts`, the line's category and its group (`LEFT JOIN categories`
  twice), `WHERE purchase_date BETWEEN ? AND ?`, `ORDER BY purchase_date, receipts.id,
  position` (AC11). Storage holds no rules; the join only reads names.
- `ExportService(catalog, receipts, exporter)`: `lines_file(unit, first, last)` and
  `totals_file(unit, first, last, by)`. Each parses the period first, then the totals file
  checks `by` and raises `AppError("invalid_request", texts.INVALID_REQUEST, 422)` (the
  existing code and text), then reads inside one read transaction: the lines file reads `export_lines`, the totals file calls
  `TotalsService.read`.

### P5 Routes and app

- `create_export_router(settings, exporter)`: `GET /api/export/lines` and
  `GET /api/export/totals` with `unit`, `from` and `to` as in the totals route; the totals
  endpoint also takes `by` as a plain optional string, so the service decides its error
  after the period's (AC17). The answer
  is a `Response` with the exporter's bytes and media type, `Content-Disposition:
  attachment; filename="<name>"` and `Cache-Control: no-store`.
- `create_app(..., exporter: Exporter | None = None)` passes `exporter or CsvExporter()`,
  as it does for the engines; AC12's test passes a fake.
- Logging is unchanged: method, path and status (@backend/app/logging_setup.py).

### P6 Frontend

- `api/export.ts`: `exportUrl(kind: "lines" | "weeks" | "months", period)` →
  `/api/export/lines?unit=week&from=2026-W40&to=2026-W41`, or
  `/api/export/totals?unit=...&from=...&to=...&by=week` (`weeks`) or `&by=month`
  (`months`).
- `TotalsPage`: under the chooser, three `<a download href=...>` links built from the
  period of the loaded totals (not the draft, and not a newer period whose totals have
  not arrived yet, so the links and the tables always show the same period, PC6), shown
  when `totals !== null` and there is no error (AC13, AC14). They
  look like buttons through a small inline style (border, padding), as the app has no
  stylesheet. The browser downloads through the Vite proxy; the file name comes from
  `Content-Disposition`.

### P7 AC check

| AC | Covered by |
|---|---|
| AC1, AC6, AC7, AC9, AC10 | P2 (unit), P5 (integration) |
| AC2, AC4, AC5, AC16 | P3, P2 |
| AC3 | P0: the file uses `TotalsService.read`; the integration test compares |
| AC8, AC17 | P4 `TotalsService.period` and the `by` check, P5 routes |
| AC11 | P4 query order |
| AC12 | P1, P5 `create_app(exporter=...)` |
| AC13, AC14 | P6 |
| AC15 | P5 logging unchanged; integration test |

### P8 Decisions (no ADR needed)

- An own CSV row writer instead of `csv.writer`: PC5 needs quoting of leading and trailing
  spaces, which `QUOTE_MINIMAL` does not do, and a formula guard on text columns only.
- One endpoint per file shape (lines, totals with `by`) instead of one with a `kind`
  parameter: each link is a plain URL, and each shape has its own columns.
- Line counts on `TotalsRow` instead of a second computation in export: the long rows come
  from the same totals as the view.

## Tasks

Each task is one Red → Green → Refactor cycle (or a few small ones) and ends with the
tests, lint, format check and type check of the part it changed.

### Backend

- [x] **T1 Line counts** (AC5). `week_counts` and `month_counts` on `TotalsRow`, a group's
  as the sum of its categories'. Tests in `test_period_totals.py`: counts per column, a
  sum of 0 with two lines counts 2, deposit refunds and lines outside the period not
  counted, group counts; `GET /api/totals` answers unchanged (the existing integration
  tests stay green).
- [x] **T2 Long rows** (AC2, AC4, AC5, AC16). `export/rows.py` `long_rows(totals, by)`.
  Tests `tests/unit/export/test_rows.py`: only weeks for `week` and only months for
  `month`, columns in order, leaf rows in row order with the group name, `Ei kategoriaa`
  last, no rows for empty columns, a 0 sum with lines listed, partial months of a week
  period.
- [x] **T3 CSV exporter** (AC1, AC2, AC4, AC6, AC7, AC9, AC10, AC16). `export/exporter.py` and
  `export/csv_exporter.py`. Tests `tests/unit/export/test_csv_exporter.py`: the AC1 and
  AC2 and AC16 contents from built inputs; byte order mark, `;`, `\r\n` after every row;
  the three file names; header only without data; quoting of `;`, `"`, line breaks and edge spaces, read
  back with `csv.reader`; `'` before `=`, `+`, `-`, `@` in text columns only; money
  `1,25`, `-0,40`, `0,00`, `1234,56`; week and month keys of a line.
- [x] **T4 Storage query** (AC1, AC11). `ReceiptRepository.export_lines`. Tests in
  `tests/unit/storage/`: dates at both edges included, outside and undated excluded;
  store, state, category and group names (none for a refund or a line without category;
  no group for a category without one); order by date, receipt id, position with gaps.
- [x] **T5 Totals service split** (AC3, AC8). `TotalsService.period` and `read`; `totals`
  unchanged. The existing totals tests stay green; a unit or integration test pins that
  `period` raises `InvalidPeriodError`.
- [x] **T6 Export service, routes and app** (AC1–AC12, AC16, AC17). `export/service.py`,
  `export/routes.py`, `create_app(exporter=...)`, router in `main.py`. Tests
  `tests/integration/test_export_api.py`: one test per integration row of the Testing
  Strategy, including AC3 against `GET /api/totals`, every AC8 query on both endpoints,
  every AC17 query, and AC12 with a test exporter.
- [x] **T7 Privacy** (AC15). Integration test: both downloads; the app's log lines are
  `GET /api/export/lines 200` and `GET /api/export/totals 200` only, with no product name,
  store, query string or file name.

### Frontend

- [x] **T8 Export URLs** (AC13). `api/export.ts` `exportUrl`. Test: the three kinds, month
  and week periods.
- [x] **T9 Links on the Yhteenveto page** (AC13, AC14). `TotalsPage.tsx`, `fi.ts`. Tests in
  `TotalsPage.test.tsx`: the three links in order with `href` and `download` for the shown
  period; they
  follow a new period; shown for an empty period; hidden for a refused period and a
  network error.
- [x] **T10 E2E** (AC1, AC2, AC13, AC16). In `e2e/import.spec.ts`: import the synthetic
  receipt, open Yhteenveto for October 2026, click the three links, check the downloads'
  names, that the lines file holds the receipt's line names, and that both totals files
  start with the AC2 header row and hold week and month rows respectively.

### Docs and closing

- [x] **T11 Docs.** Create `docs/subsystems/export/README.md`; update `api-reference.md`,
  `architecture.md` (overview paragraph, folder structure, totals and export flow, key
  interfaces), the totals, calculation, storage and UI READMEs, `glossary.md`,
  `content-plan.md` and `specs/README.md`.
- [x] **T12 Full check.** Every command in the AGENTS.md command table, including the E2E
  and container tests; coverage meets the targets. Then hand over to `review-audit`.

## Audit

Audited 2026-11-02 against this spec, with an independent review: **PASS**.

- Acceptance criteria 17/17 and PC1–PC7 met; every Testing Strategy row has a test.
- Tests: backend 1028 passed, frontend 183 passed, E2E 10 passed (three runs, also on a
  kept database), container tests passed; ruff, pyright, ESLint and tsc clean. Coverage:
  the new backend code (`app/export`, `app/totals`) 100 %, the whole backend 99 %; the new
  frontend code is covered by its tests.
- Security: no findings. Parameterized SQL; the file name is built only from a checked
  period, so no header injection; the request log holds method, path, status and duration
  only (AC15). `pip-audit`: no known vulnerabilities.
- Fixed during the audit (test first): while a new period loaded, the links already
  pointed at it although the tables still showed the previous one (PC6); Plan P6 updated,
  regression test `export AC13: while a new period loads, the links keep the period of the
  shown totals`.
- Found in T10: `backend-e2e` does not reload code; recorded in `docs/learnings.md` and
  `docs/development.md`.
- Format check: files not touched by this spec fail `npm run format:check` because their
  working copies have CRLF line endings (`core.autocrlf=true`); the content in Git is fine.
- Later:
  - The formula guard (PC5) covers `=`, `+`, `-` and `@`. OWASP also lists a leading tab
    and carriage return. No write path stores them today (names are trimmed), but a spec
    change could add them.
  - The export reads use the same `BEGIN IMMEDIATE` transaction as `GET /api/totals`, so
    an export during an import waits for it. A deferred read transaction could be added
    for both.

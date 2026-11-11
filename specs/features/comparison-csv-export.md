# Feature: Budget comparison CSV export

## Overview
- **Status:** Done
- **Created:** 2026-11-11
- **Updated:** 2026-11-11: user answers before Specify: the file is always in long format
  with the columns `Jakso;Alkaa;Päättyy;Osittainen;Tyyppi;Nimi;Budjetti;Toteutunut;Jäljellä`;
  by default it holds the whole period only (the month table), and the user can choose to
  include the weeks; no total row. User change after the Specify draft: the dates of this
  file are `dd.mm.yyyy`; the other CSV files keep `YYYY-MM-DD` and get Finnish dates in a
  separate spec (PC1). Specify approved by the user. Plan added and approved by the user;
  Tasks added. Spec approved by the user; implementation started. Implemented and audited
  2026-11-11 (see Audit).
- **Depends on:** [Monthly budget](budget.md), [CSV export](csv-export.md),
  [PDF export](pdf-export.md)
- **Implements:** PRD FR-52 (new; from the Later candidates: CSV export of the budget
  comparison); FR-27, NFR-3 for the new file.
- **Affected subsystems:** [export](../../docs/subsystems/export/README.md),
  [budget](../../docs/subsystems/budget/README.md),
  [ui](../../docs/subsystems/ui/README.md)

## Problem Statement
The Vertailu page compares the monthly budget with the reviewed spending of a period and its
weeks, and the comparison can be saved as a PDF. The user cannot take the figures into Excel
to filter, chart or keep them. This spec adds a CSV file of the comparison, in the same long
format style as the totals CSV file, with the weeks as an option.

## Current Behavior
- `GET /api/budget/comparison` returns the comparison of a calendar month or a 15–14 period:
  the budget rows with budget, actual and remaining, each row's weekly figures and a total
  ([budget](../../docs/subsystems/budget/README.md),
  [calculation](../../docs/subsystems/calculation/README.md#budget-comparison),
  [API reference](../../docs/api-reference.md#budget)).
- The Vertailu page shows the month table, the week table on request, and the link
  `Vie vertailu (PDF)` ([ui](../../docs/subsystems/ui/README.md)).
- `GET /api/export/comparison/pdf` returns the comparison PDF; the CSV files cover only the
  lines and the totals ([export](../../docs/subsystems/export/README.md)).

## Proposed Change

### Concepts

- The **comparison CSV file** lists the comparison of one comparison period, read from the
  same `BudgetService.comparison` as the Vertailu page, so the file and the page agree.
  Only reviewed receipts count, as on the page.
- It is in **long format**: one row per **block** and budget row. A block is the whole
  period (`Koko jakso`) or one week column of the period.
- **Without weeks** (the default) the file has the `Koko jakso` block only: the month table
  of the page. **With weeks** the `Koko jakso` block is followed by one block per week
  column, in date order.

### Parts

- **PC1 PRD:** add FR-52 (the comparison CSV file, weeks optional, dates `dd.mm.yyyy`),
  remove the candidate from the Later (candidates) row, and add the candidate "dates as
  `dd.mm.yyyy` in the lines and totals CSV files (FR-26)" to that row.
- **PC2 Endpoint:** `GET /api/export/comparison` with `month` and `period` as in
  `GET /api/budget/comparison`, and the optional `weeks`: missing or `false` gives the file
  without weeks, `true` the file with weeks. The answer is a CSV download with the headers of
  the other CSV files.
- **PC3 Columns:** the header row is
  `Jakso;Alkaa;Päättyy;Osittainen;Tyyppi;Nimi;Budjetti;Toteutunut;Jäljellä`.
  - `Jakso`: `Koko jakso`, or the week's key such as `2026-W40`.
  - `Alkaa`, `Päättyy`: the block's first and last day inside the period, `dd.mm.yyyy`
    with leading zeros, such as `01.10.2026` (Finnish Excel reads it as a date).
  - `Osittainen`: `kyllä` for a week clipped by the period's edge, otherwise `ei`;
    `Koko jakso` is always `ei`.
  - `Tyyppi`: `ryhmä` for a group, `kategoria` for a category without a group and for the
    row of lines without a category.
  - `Nimi`: the group or category name; `Ei kategoriaa` for lines without a category.
  - `Budjetti`, `Toteutunut`, `Jäljellä`: the block's budget, reviewed spending and
    budget minus spending, as the page shows them (a week's budget is its share of the
    monthly budget, PRD FR-50).
- **PC4 Rows:** within a block, the rows are in the order of the page: the budget rows in
  catalog order, then `Ei kategoriaa` when it exists. Every budget row is listed, also with
  zeros. No total row, no category rows inside a group.
- **PC5 Format:** the CSV rules of the other files: `;`, UTF-8 with a byte order mark,
  `\r\n`, amounts as `1,25` and `-0,40`, quoting, and the leading `'` before a name that
  starts with `=`, `+`, `-` or `@` ([export](../../docs/subsystems/export/README.md#csv-format)).
- **PC6 File names:** `vertailu_<month>.csv`, `vertailu_15-14_<month>.csv`,
  `vertailu_viikot_<month>.csv`, `vertailu_viikot_15-14_<month>.csv`.
- **PC7 Exporter:** the file is built through the exporter interface (FR-27).
- **PC8 Errors:** a bad `month` or `period` gives 422 `invalid_period`, checked first; a
  `weeks` other than `true` or `false` gives 422 `invalid_request`.
- **PC9 UI:** on the Vertailu page, beside `Vie vertailu (PDF)`, the link
  `Vie vertailu (CSV)` and the checkbox `Viikot mukaan` (unchecked when the page opens).
  The link points at the file of the shown answer's period, with weeks when the box is
  checked.

### Out of Scope
- A total row, category rows inside a group, the unreviewed and undated counts in the file.
- A CSV export of the budget amounts alone (the Budjetti page).
- Changes to the comparison figures, the PDF or the other CSV files; their dates stay
  `YYYY-MM-DD` until their own spec (PC1).
- Google Sheets export (FR-28).

## Acceptance Criteria

The examples use this synthetic catalog and data unless an AC says otherwise: the group
`Ruoka` (budget 400,00 €) with the category `Maitotuotteet`; the category `Juomat` without a
group (budget 50,00 €); reviewed lines in October 2026: 1.10. `Maitotuotteet` 125,00 €,
6.10. `Juomat` 12,50 €, 6.10. a line without a category 1,99 €.

### AC1: File without weeks
**Given** the example data
**When** the user requests `GET /api/export/comparison?month=2026-10`
**Then** the answer is 200 with `Content-Type: text/csv; charset=utf-8`,
`Content-Disposition: attachment; filename="vertailu_2026-10.csv"` and
`Cache-Control: no-store`, and the body is the byte order mark followed by exactly:
```text
Jakso;Alkaa;Päättyy;Osittainen;Tyyppi;Nimi;Budjetti;Toteutunut;Jäljellä
Koko jakso;01.10.2026;31.10.2026;ei;ryhmä;Ruoka;400,00;125,00;275,00
Koko jakso;01.10.2026;31.10.2026;ei;kategoria;Juomat;50,00;12,50;37,50
Koko jakso;01.10.2026;31.10.2026;ei;kategoria;Ei kategoriaa;0,00;1,99;-1,99
```
with `\r\n` after every row.

### AC2: `weeks=false` is the default
**Given** the example data
**When** the user requests `GET /api/export/comparison?month=2026-10&weeks=false`
**Then** the body and file name are the same as in AC1.

### AC3: File with weeks
**Given** the example data
**When** the user requests `GET /api/export/comparison?month=2026-10&weeks=true`
**Then** the file name is `vertailu_viikot_2026-10.csv`, the first four rows are those of
AC1, and they are followed by one block per week column `2026-W40` (1.–4.10., `kyllä`),
`2026-W41`, `2026-W42`, `2026-W43` (`ei`) and `2026-W44` (26.–31.10., `kyllä`), three rows
each in the order of AC1. The `2026-W40` block is:
```text
2026-W40;01.10.2026;04.10.2026;kyllä;ryhmä;Ruoka;51,61;125,00;-73,39
2026-W40;01.10.2026;04.10.2026;kyllä;kategoria;Juomat;6,45;0,00;6,45
2026-W40;01.10.2026;04.10.2026;kyllä;kategoria;Ei kategoriaa;0,00;0,00;0,00
```
and each row's `Budjetti` cells over the five weeks add up to its `Koko jakso` budget.

### AC4: Figures agree with the page
**Given** the example data
**When** the user requests the file with weeks and `GET /api/budget/comparison?month=2026-10`
**Then** every `Budjetti` and `Toteutunut` cell equals the matching `budget_cents` and
`actual_cents` of the answer (row and week), and `Jäljellä` equals budget minus actual.

### AC5: Only reviewed receipts count
**Given** the example data and an unreviewed receipt dated 2.10.2026 with a 10,00 €
`Juomat` line
**When** the user requests `GET /api/export/comparison?month=2026-10`
**Then** the `Juomat` row is `...;Juomat;50,00;12,50;37,50`, as in AC1.

### AC6: 15–14 period
**Given** the example data
**When** the user requests `GET /api/export/comparison?month=2026-10&period=mid&weeks=true`
**Then** the file name is `vertailu_viikot_15-14_2026-10.csv`, the `Koko jakso` rows have
`15.10.2026;14.11.2026`, the first week block is `2026-W42` with `15.10.2026;18.10.2026;kyllä`
and the last is `2026-W46` with `09.11.2026;14.11.2026;kyllä`. Without `weeks` the file
name is `vertailu_15-14_2026-10.csv`.

### AC7: Every budget row is listed, `Ei kategoriaa` only with such lines
**Given** the catalog of the example and no reviewed lines in November 2026
**When** the user requests `GET /api/export/comparison?month=2026-11`
**Then** the body has the header row and two rows: `Ruoka` `400,00;0,00;400,00` and
`Juomat` `50,00;0,00;50,00`; there is no `Ei kategoriaa` row.

### AC8: Empty catalog
**Given** no groups or categories and no receipts
**When** the user requests `GET /api/export/comparison?month=2026-11&weeks=true`
**Then** the answer is 200 and the body is the byte order mark and the header row only.

### AC9: Names that look like formulas, or need quoting
**Given** a group named `=Ruoka` and a category without a group named `Juomat; kahvi`
**When** the user requests the file
**Then** their `Nimi` cells are `'=Ruoka` and `"Juomat; kahvi"`, and the amounts such as
`-1,99` are not changed.

### AC10: Bad period
**Given** any data
**When** the user requests `GET /api/export/comparison` without `month`, with
`month=2026-13`, or with `month=2026-10&period=week`
**Then** the answer is 422 with `error` `invalid_period` and `message`
`Jakso on virheellinen.`

### AC11: Bad `weeks`
**Given** any data
**When** the user requests `GET /api/export/comparison?month=2026-10&weeks=yes`
**Then** the answer is 422 with `error` `invalid_request` and `message`
`Pyyntö on virheellinen.`; with `month=2026-13&weeks=yes` the error is `invalid_period`.

### AC12: No receipt content in the log
**Given** the example data
**When** the user requests the file
**Then** the request log line holds the method, path, status and duration, and no query
string, file name, group or category name.

### AC13: CSV link on the Vertailu page
**Given** the Vertailu page shows the comparison of `2026-10` with the period `15.–14.`
**When** the page is shown
**Then** beside `Vie vertailu (PDF)` there is the download link `Vie vertailu (CSV)` with
`href` `/api/export/comparison?month=2026-10&period=mid`, and the checkbox `Viikot mukaan`,
unchecked.

### AC14: Weeks checkbox
**Given** the page of AC13
**When** the user checks `Viikot mukaan`
**Then** the link's `href` is `/api/export/comparison?month=2026-10&period=mid&weeks=true`;
unchecking it restores the `href` of AC13.

### AC15: Link follows the shown answer
**Given** the page shows `2026-10` and the user changes the month to `2026-11`
**When** the answer of `2026-11` has not arrived yet
**Then** the link still points at `2026-10`; once it arrives, it points at `2026-11`.

### AC16: Download from the page
**Given** synthetic receipts in the E2E database
**When** the user opens Vertailu, checks `Viikot mukaan` and clicks `Vie vertailu (CSV)`
**Then** the browser downloads `vertailu_viikot_<month>.csv` whose header row is that of
AC1, and the page passes the axe check.

## Files to Modify
| File | Change |
|---|---|
| `specs/PRD.md` | FR-52; remove the candidate from the Later (candidates) row (PC1) |
| `backend/app/export/exporter.py` | The comparison file in the `Exporter` interface (PC7) |
| `backend/app/export/csv_exporter.py` | The comparison CSV file (PC3–PC6) |
| `backend/app/export/service.py` | Read the comparison and check `weeks` (PC2, PC8) |
| `backend/app/export/routes.py` | `GET /api/export/comparison` (PC2) |
| `backend/tests/` | Unit and integration tests of the file and the endpoint |
| `frontend/src/api/export.ts` | The comparison CSV URL (PC9) |
| `frontend/src/components/ComparisonPage.tsx` | The link and the checkbox (PC9) |
| `frontend/src/i18n/` | `Vie vertailu (CSV)`, `Viikot mukaan` |
| `frontend/src/**/*.test.ts(x)` | Tests of the URL, the link and the checkbox |
| `frontend/e2e/` | The download journey (AC16) |
| `docs/subsystems/export/README.md` | The comparison CSV file, its format and names |
| `docs/subsystems/budget/README.md` | Export as a user of `BudgetService.comparison` for CSV too |
| `docs/subsystems/ui/README.md` | The CSV link and checkbox on the Vertailu page |
| `docs/api-reference.md` | `GET /api/export/comparison` |
| `docs/glossary.md` | Comparison CSV file |
| `docs/architecture.md` | The export row: the new endpoint |
| `docs/content-plan.md`, `specs/README.md` | Status |

## Risk
- **What could break:** the existing CSV and PDF exports if the shared CSV helpers or the
  exporter interface change; the Vertailu page's PDF link. Their existing tests cover them.
- **Rollback:** revert the change; there is no data model change and no migration.
- **Dependencies:** none new.

## Testing Strategy (MANDATORY)

### Unit tests
| AC | Function | Case | Given | When | Then | Mocks |
|---|---|---|---|---|---|---|
| AC1 | `CsvExporter` comparison file | without weeks | example comparison | build | exact body and name of AC1 | none |
| AC1 | `CsvExporter` comparison file | Finnish dates | a period of 1.–9.10. | build | `01.10.2026;09.10.2026`, leading zeros kept | none |
| AC3 | `CsvExporter` comparison file | with weeks | example comparison | build | blocks in date order; W40 rows of AC3 | none |
| AC3 | `CsvExporter` comparison file | weeks add up | example comparison | build with weeks | each row's week budgets sum to its `Koko jakso` budget | none |
| AC6 | `CsvExporter` comparison file | names | `mid` and `calendar`, with and without weeks | build | the four names of PC6 | none |
| AC7 | `CsvExporter` comparison file | zeros, no `none` row | comparison without lines | build | two rows with zeros | none |
| AC8 | `CsvExporter` comparison file | empty | no rows | build | header only | none |
| AC9 | `CsvExporter` comparison file | formula and quoting | names `=Ruoka`, `Juomat; kahvi` | build | `'=Ruoka`, `"Juomat; kahvi"`; `-1,99` unchanged | none |
| AC11 | `parse_weeks` | bad `weeks` | `"yes"`, `"True"`, `"1"`, `""` | call | `invalid_request` | none |
| AC2, AC3 | `parse_weeks` | good `weeks` | `None`, `"false"`, `"true"` | call | `False`, `False`, `True` | none |

### Integration tests
Real SQLite (temporary file) and real FastAPI app.
| AC | Scenario | Request / input | Expected output | Status |
|---|---|---|---|---|
| AC1 | without weeks | `GET /api/export/comparison?month=2026-10` | body and headers of AC1 | 200 |
| AC2 | `weeks=false` | `...&weeks=false` | same as AC1 | 200 |
| AC3 | with weeks | `...&weeks=true` | five week blocks, name `vertailu_viikot_2026-10.csv` | 200 |
| AC4 | agrees with the page | the file and `GET /api/budget/comparison` | cells equal the answer's cents | 200 |
| AC5 | unreviewed left out | unreviewed receipt added | `Juomat` row unchanged | 200 |
| AC6 | 15–14 | `month=2026-10&period=mid&weeks=true` | dates and names of AC6 | 200 |
| AC7 | no lines | `month=2026-11` | two zero rows | 200 |
| AC8 | empty catalog | `month=2026-11&weeks=true` | header only | 200 |
| AC10 | bad period | no `month`; `2026-13`; `period=week` | `invalid_period` | 422 |
| AC11 | bad `weeks` | `weeks=yes`; `month=2026-13&weeks=yes` | `invalid_request`; `invalid_period` | 422 |
| AC12 | log | request the file | log line without query, names or file name | 200 |

### Frontend tests
| AC | Component | Case | Then |
|---|---|---|---|
| AC13 | `comparisonCsvUrl` | without and with weeks, `calendar` and `mid` | the URLs of AC13, AC14 |
| AC13 | `ComparisonPage` | page shown | link `Vie vertailu (CSV)` with `download`; checkbox unchecked |
| AC14 | `ComparisonPage` | check and uncheck | `href` changes and returns |
| AC15 | `ComparisonPage` | month changed, answer pending | `href` of the shown answer |

### E2E tests
| AC | Journey | Steps | Expected outcome |
|---|---|---|---|
| AC16 | Download the comparison CSV | open Vertailu, check `Viikot mukaan`, click `Vie vertailu (CSV)` | file `vertailu_viikot_<month>.csv` with the header of AC1; axe passes |

### Coverage target
- Backend: 80 % lines; the comparison file builder: every branch.
- Frontend: the new URL function and page code covered by the tests above.

### Test data
- Synthetic fixtures only: the catalog and lines of the examples, built in the tests.
- Mocks: a fake exporter in the service tests; no Tesseract or Ollama.

## Related Documentation (MANDATORY)
- Tier 1: [api-reference.md](../../docs/api-reference.md#export),
  [architecture.md](../../docs/architecture.md#component-map),
  [glossary.md](../../docs/glossary.md), [security.md](../../docs/security.md)
- Tier 2: [export](../../docs/subsystems/export/README.md),
  [budget](../../docs/subsystems/budget/README.md),
  [calculation](../../docs/subsystems/calculation/README.md#budget-comparison),
  [ui](../../docs/subsystems/ui/README.md)
- ADRs: none new

## Plan

### Components and data flow

```
GET /api/export/comparison?month&period&weeks       (routes.py, plain optional strings)
  → ExportService.comparison_file(month, kind, weeks)
      → BudgetService.comparison(month, kind)          InvalidPeriodError first (PC8)
      → parse_weeks(weeks) → bool                        else AppError invalid_request
      → Exporter.comparison_file(comparison, kind, weeks)
          → comparison_rows(comparison, weeks)         (comparison_rows.py)
          → CsvExporter writes cells, names the file
  → _download(file)                                    the existing CSV headers
```

### P1 Remaining of a week (calculation)

`WeekFigures` gets the read-only property `remaining_cents` (`budget_cents −
actual_cents`), the same rule as `ComparisonRow.remaining_cents`. So export still
computes no figure of its own ([export](../../docs/subsystems/export/README.md#overview)).
It is a property, not a field: `WeekFiguresOut` copies the fields by name, so the
`GET /api/budget/comparison` answer does not change.

### P2 Rows of the file (`backend/app/export/comparison_rows.py`, new)

`comparison_rows(comparison, weeks: bool) -> list[ComparisonCsvRow]`, a pure function
beside `rows.py`:

- `ComparisonCsvRow(block, start, end, partial, kind, name, budget_cents, actual_cents,
  remaining_cents)`; `block` is `None` for the whole period, otherwise the week's key.
- The `Koko jakso` block: one row per `comparison.rows` in their order, with the period's
  `start` and `end`, `partial` `False`, and the row's own figures.
- With `weeks`: for each `comparison.weeks[i]` in order, one row per `comparison.rows` with
  the column's dates and `partial`, and `row.weeks[i]`.
- `comparison.total` is not used (no total row, PC4).
- `kind` and `name` are passed on as they are; the CSV exporter turns them into text.

### P3 The CSV file (`backend/app/export/csv_exporter.py`)

`CsvExporter.comparison_file(comparison, kind, weeks) -> ExportFile`:

- Header `COMPARISON_HEADER = ("Jakso", "Alkaa", "Päättyy", "Osittainen", "Tyyppi", "Nimi",
  "Budjetti", "Toteutunut", "Jäljellä")`.
- `Jakso`: `texts.PERIOD_BLOCK` (`Koko jakso`, the PDF's period block text) or the week
  key.
- `Alkaa`, `Päättyy`: the new helper `_finnish_day(day)` → `f"{d:02d}.{m:02d}.{yyyy}"`.
  `finnish.day` is not reused: the PDF writes `1.10.2026` without zeros.
- `Tyyppi`: `{"group": "ryhmä", "category": "kategoria", "none": "kategoria"}`.
- `Nimi`: `_text(name)`, with `texts.NO_CATEGORY` for the `none` row, so the formula guard
  and quoting of PC5 apply.
- Amounts: `_money`. `Osittainen`: `YES` or `NO`.
- Name: `vertailu` + (`_viikot` with weeks) + (`_15-14` for `mid`) + `_<period.first>.csv`.
  `period.first` is the checked month (`2026-10`), as in the PDF's name.

### P4 Exporter interface (`backend/app/export/exporter.py`)

`Exporter` gets `comparison_file(self, comparison: Comparison, kind: str, weeks: bool) ->
ExportFile` (FR-27). The CSV `Exporter` and not the `ReportExporter`, because the file
needs no counts and no creation day. The test exporter `FixedExporter` in
`backend/tests/integration/test_export_api.py` implements `Exporter`, so it gets the same
method, returning a fixed file `vertailu.test` and remembering its arguments as its other
methods do. This is a planned test change for pyright, not a fix of a red test.

### P5 Service and route

- `ExportService.comparison_file(month, kind, weeks)`: reads `BudgetService.comparison`
  (one transaction, reviewed lines only, raises `InvalidPeriodError`), then `parse_weeks`:
  `None` or `"false"` → `False`, `"true"` → `True`, anything else →
  `AppError("invalid_request", texts.INVALID_REQUEST, 422)`. The period is checked first
  because `comparison` parses it before reading (AC11).
- `GET /api/export/comparison` in `routes.py`, `month`, `period`, `weeks` as plain
  optional strings, as the PDF route. The request log is unchanged: it never logs a query
  string or a file name (AC12).

### P6 Frontend

- `frontend/src/api/export.ts`: `comparisonCsvUrl(period: ComparisonPeriod, weeks: boolean)`
  → `/api/export/comparison?month=…&period=…` and `&weeks=true` when `weeks`.
  `URLSearchParams` keeps the order of AC13 and AC14.
- `ComparisonPage.tsx`: state `includeWeeks` (`useState(false)`). In the paragraph of the
  PDF link: the link `Vie vertailu (CSV)` (`download`, class `button`) and the checkbox
  `Viikot mukaan` in a `label`. The link is built from the shown answer (`comparison.month`,
  `comparison.period`), as the PDF link (AC15). The checkbox keeps its state when the
  period changes.
- `fi.ts`: `comparison.exportCsv: "Vie vertailu (CSV)"`, `comparison.includeWeeks:
  "Viikot mukaan"`.
- No new CSS: the checkbox uses the existing form styles; the axe check proves the label.

### P7 E2E

A new `frontend/e2e/comparison-csv.spec.ts`, in the style of `pdf.spec.ts`: open
`/vertailu?month=2026-10`, check `Viikot mukaan`, fetch the link's `href` with
`page.request.get` (status 200, `text/csv; charset=utf-8`, the body starts with the BOM and
the header row of AC1), click the link and check the download's name
`vertailu_viikot_2026-10.csv`, then run the axe check of the page as the other journeys do.
The database outlives a run, so the journey checks the file's header and name, not the
sums; the backend tests check the sums.

### Data model, dependencies, ADR

- No data model change and no migration.
- No new dependency.
- No ADR: the file follows the decisions of the CSV export and budget specs.

### AC check

| AC | Covered by |
|---|---|
| AC1, AC2 | P2, P3, P5 |
| AC3 | P1, P2, P3 |
| AC4 | P1, P2 (the figures of `BudgetService.comparison`) |
| AC5 | P5 (`BudgetService.comparison` reads reviewed lines only) |
| AC6 | P2, P3 (name, dates) |
| AC7, AC8 | P2 (every budget row; no rows without a catalog) |
| AC9 | P3 (`_text`) |
| AC10, AC11 | P5 |
| AC12 | P5 (log unchanged) |
| AC13–AC15 | P6 |
| AC16 | P6, P7 |

### Files to Modify (refined)

Adds to the table above: `backend/app/calculation/budget_comparison.py` (P1),
`backend/app/export/comparison_rows.py` (new, P2), `frontend/e2e/comparison-csv.spec.ts`
(new, P7),
`docs/subsystems/calculation/README.md` (P1: the week's remaining).

## Tasks

Each task runs Red → Green → Refactor; the tests named are written first. Backend tasks end
with `pytest`, `ruff check`, `ruff format --check` and `pyright` green in `backend-test`;
frontend tasks with `npm test`, lint, format check and typecheck green in `frontend-test`.

- [x] **T1 PRD (PC1).** Add FR-52 to PRD section 6.6 (marked *Later release*), add it to
  the Later row of section 9, and make the Later (candidates) change of PC1. Proof: the
  PRD has FR-52 and no comparison CSV candidate; the new date candidate is listed.
- [x] **T2 Week remaining (P1; AC3, AC4).** `WeekFigures.remaining_cents` in
  `app/calculation/budget_comparison.py`. Unit tests: `5161 − 12500 = −7339`;
  `645 − 0 = 645`; the comparison answer's JSON keys of a week are unchanged
  (`budget_cents`, `actual_cents` only).
- [x] **T3 Comparison rows (P2; AC1, AC3, AC6–AC8).** `app/export/comparison_rows.py`. Unit
  tests on a synthetic `Comparison` built with `budget_comparison`: without weeks, three
  rows of the `Koko jakso` block with the period's dates and `partial` false; with weeks,
  the five week blocks of October 2026 in date order with the W40 figures of AC3 and
  `partial` true for W40 and W44; each row's week budgets add up to its budget; the 15–14
  period's first and last week (AC6); no `none` row without such lines (AC7); no rows for
  an empty catalog (AC8); the total is never a row.
- [x] **T4 CSV file (P3, P4; AC1–AC3, AC6–AC9).** `Exporter.comparison_file` in
  `exporter.py`; `CsvExporter.comparison_file` and `_finnish_day` in `csv_exporter.py`;
  the `FixedExporter` method in `tests/integration/test_export_api.py`. Unit tests: the
  exact body of AC1 with BOM and `\r\n`; the W40 block of AC3; `_finnish_day` keeps the
  leading zeros (`01.10.2026`, `09.10.2026`); the four file names of PC6; header only for
  an empty comparison; `'=Ruoka`, `"Juomat; kahvi"` and `-1,99` of AC9.
- [x] **T5 Service and endpoint (P5; AC1–AC12).** `ExportService.comparison_file`, `parse_weeks`
  and `GET /api/export/comparison`. Unit tests of `parse_weeks` (`None`, `"false"`, `"true"`,
  `"yes"`); the order of checks is in the integration tests (AC11). Integration tests: the rows of
  the Integration tests table (AC1–AC12), with real SQLite and the synthetic data of the
  examples.
- [x] **T6 URL helper (P6; AC13, AC14).** `comparisonCsvUrl` in `frontend/src/api/export.ts`.
  Tests: `calendar` and `mid`, with and without weeks, the exact URLs of AC13 and AC14.
- [x] **T7 Vertailu page (P6; AC13–AC15).** The link, the checkbox and the texts in
  `ComparisonPage.tsx` and `fi.ts`. Tests in `ComparisonPage.test.tsx`: the link with
  `download` and the `href` of AC13; the checkbox unchecked; checking and unchecking
  changes the `href` (AC14); a pending answer keeps the shown period's `href` (AC15); the
  PDF link is unchanged.
- [x] **T8 E2E (P7; AC16).** `frontend/e2e/comparison-csv.spec.ts`. Proof:
  `docker compose --profile e2e run --rm e2e` green, the existing journeys included.
- [x] **T9 Docs.** Update the export, budget, calculation and UI READMEs,
  `api-reference.md` (endpoint, query, file names, an example body), `architecture.md`
  (export row), `glossary.md` (comparison CSV file), `content-plan.md` and
  `specs/README.md`. Proof: links resolve; the docs describe the code as built.
- [x] **T10 Full checks and audit.** All check commands of AGENTS.md for the backend and the
  frontend, and the E2E tests; then the `review-audit` skill.

## Audit: Budget comparison CSV export (2026-11-11)

- Acceptance criteria: 16/16 met
- Tests: backend 1460 passed (pytest), frontend 345 passed (Vitest), E2E 41 passed;
  coverage of the new code 100 % (`comparison_rows.py`, `csv_exporter.py`,
  `budget_comparison.py`; target 80 %)
- Security: 0 critical, 0 high, 0 medium
- Docs updated: yes; spec status: Done

| AC | Status | Evidence |
|---|---|---|
| AC1 | ✅ | `test_ac1_file_without_weeks` (unit and integration), `test_ac1_dates_keep_their_leading_zeros` |
| AC2 | ✅ | `test_ac2_weeks_false_is_the_default`, `test_ac2_ac3_weeks_values` |
| AC3 | ✅ | `test_ac3_file_with_weeks` (unit and integration), `test_ac3_each_rows_week_budgets_add_up_to_its_budget`, `test_comparison_csv_ac3_week_remaining_is_budget_minus_actual` |
| AC4 | ✅ | `test_ac4_figures_agree_with_the_page` |
| AC5 | ✅ | `test_ac5_only_reviewed_receipts_count` |
| AC6 | ✅ | `test_ac6_file_names`, `test_ac6_mid_period_dates`, `test_ac6_mid_period` |
| AC7 | ✅ | `test_ac7_zero_rows_without_lines`, `test_ac7_every_budget_row_without_lines` |
| AC8 | ✅ | `test_ac8_header_only_for_an_empty_catalog`, `test_ac8_empty_catalog` |
| AC9 | ✅ | `test_ac9_formula_guard_and_quoting_on_names_only` |
| AC10 | ✅ | `test_ac10_bad_period` |
| AC11 | ✅ | `test_ac11_bad_weeks`, `test_ac11_other_weeks_values_are_invalid_requests` |
| AC12 | ✅ | `test_ac12_request_log_holds_no_query_or_names` |
| AC13 | ✅ | `comparison CSV AC13` (page and URL tests) |
| AC14 | ✅ | `comparison CSV AC14: the box adds and removes the weeks` |
| AC15 | ✅ | `comparison CSV AC15: the link keeps the shown period until the new answer` |
| AC16 | ✅ | `e2e/comparison-csv.spec.ts` |

Checks: `ruff check`, `ruff format --check`, `pyright`, `pip-audit` (no known
vulnerabilities), `npm run lint`, `npm run typecheck`, `npm audit --omit=dev`
(0 vulnerabilities), `npm run format:check`. The format check first failed on almost every
frontend file because of CRLF line endings in the Windows checkout; the user chose
`"endOfLine": "auto"` in `frontend/.prettierrc` as a separate fix
([learnings](../../docs/learnings.md)), and it passes since.

Security and privacy: the file holds group and category names and cents only, no product
or store name; the request log holds method, path, status and duration (AC12); the test
data is synthetic; the test helper `keep_only` uses bound parameters only.

Recorded test edits (G7): one line for this branch,
`backend/tests/integration/test_export_comparison_csv_api.py`. The spec backs it: the file
is this spec's new test file, and the edit rewrote the helper `keep_only` without
string-built SQL after `ruff` (S608) flagged it; no assertion changed. The planned change
to `FixedExporter` in `test_export_api.py` (P4) was made before any red run of that file.

| # | Severity | File | Finding | Recommendation |
|---|---|---|---|---|
| 1 | Low | spec | The Plan named the weeks parser `_weeks` and planned the order-of-checks test as a unit test; the code has `parse_weeks` and the integration test covers the order. | Fixed: the spec now matches the code. |
| 2 | Low | guardrail hook | Parallel tool calls made the hook fail once: two hook runs wrote the session state file at the same time (the file was in use). The call was blocked, not allowed, so nothing slipped through. | The user decides whether the hook should retry or lock the state file (G4: only the user changes it). |
| 3 | Low | guardrail hook | Likely false positives: G1 blocked a read-only `grep` over backend and frontend code folders during the Plan, and G1 and G4 blocked edits of this spec whose text only named a protected word or the hook's file path. | The user checks the G1 and G4 patterns. |

Verdict: PASS. Findings 2 and 3 are outside this feature and left to the user.

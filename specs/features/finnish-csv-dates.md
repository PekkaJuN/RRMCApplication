# Feature: Finnish dates in the lines and totals CSV files

## Overview
- **Status:** Done
- **Created:** 2026-11-11
- **Updated:** 2026-11-11: user answers before Specify: the date columns of the lines and
  totals CSV files become `dd.mm.yyyy`, as in the comparison CSV file; the week and month
  keys (`Viikko`, `Kuukausi`, `Jakso`) and the file names stay as they are. Specify approved
  by the user; Plan added and approved by the user; Tasks added. Spec approved by the user;
  implementation started. Implemented and audited 2026-11-11 (see Audit).
- **Depends on:** [CSV export](csv-export.md), [Free date range for totals](date-range-totals.md),
  [Budget comparison CSV export](comparison-csv-export.md)
- **Implements:** PRD FR-26 (changed: dates as `dd.mm.yyyy`); the Later candidate "dates as
  `dd.mm.yyyy` in the lines and totals CSV files".
- **Affected subsystems:** [export](../../docs/subsystems/export/README.md)

## Problem Statement
The comparison CSV file writes its dates as `01.10.2026`, the Finnish form that Finnish Excel
reads as a date. The lines and totals CSV files still write `2026-10-01`. The user wants the
same Finnish dates in all CSV files, so the files read alike and match what the pages show.

## Current Behavior
- `GET /api/export/lines` writes the column `Päivä` as `YYYY-MM-DD`;
  `GET /api/export/totals` writes `Alkaa` and `Päättyy` as `YYYY-MM-DD`
  ([export](../../docs/subsystems/export/README.md#csv-format),
  [API reference](../../docs/api-reference.md#export)). PRD FR-26 requires this.
- The comparison CSV file writes `Alkaa` and `Päättyy` as `dd.mm.yyyy` with leading zeros
  ([comparison CSV export spec](comparison-csv-export.md)).

## Proposed Change

- **PC1 PRD:** FR-26 says dates are `dd.mm.yyyy` with leading zeros, and that the week and
  month keys and the file names keep their ISO form; the Later candidate is removed.
- **PC2 Lines file:** the column `Päivä` is the purchase date as `dd.mm.yyyy` with leading
  zeros (`06.10.2026`).
- **PC3 Totals file:** the columns `Alkaa` and `Päättyy` are the column's first and last day
  inside the period as `dd.mm.yyyy` with leading zeros (`01.10.2026`), by week and by month.
- **PC4 Unchanged:** `Viikko` (`2026-W41`), `Kuukausi` (`2026-10`) and `Jakso` (`2026-W40`,
  `2026-10`) keep their form; the file names keep their ISO bounds
  (`kuittirivit_2026-10-15_2026-11-14.csv`); every other cell, the headers, the separator,
  the BOM, the amounts and the comparison CSV file are unchanged.
- **PC5 One rule:** all three CSV files write a date with the same function, so they cannot
  drift apart.

### Out of Scope
- The week and month keys, the file names, the PDF files and the pages.
- The comparison CSV file, which already has Finnish dates.
- Dates anywhere else in the API (`start_date`, `purchase_date` stay ISO).

## Acceptance Criteria

The examples use the fixture of the [CSV export spec](csv-export.md): a catalog with the group
`Ruoka` (`Leivät`, `Maitotuotteet`) and the category `Juomat`; an unreviewed receipt of
2.10.2026 with `Maito` 1,25 € (`Maitotuotteet`); a reviewed receipt of 6.10.2026 with
`Ruisleipä` 3,00 € (`Leivät`), `Limu` 2,50 € (`Juomat`), `Tuntematon` 1,99 € and a deposit
refund −0,40 €.

### AC1: Lines file
**Given** the fixture
**When** the user requests `GET /api/export/lines?unit=month&from=2026-10&to=2026-10`
**Then** the body after the header row is exactly:
```text
02.10.2026;2026-W40;2026-10;Testikauppa;Maito;1,25;Ruoka;Maitotuotteet;ei;Tarkistamaton
06.10.2026;2026-W41;2026-10;Testikauppa;Ruisleipä;3,00;Ruoka;Leivät;ei;Vahvistettu
06.10.2026;2026-W41;2026-10;Testikauppa;Limu;2,50;;Juomat;ei;Vahvistettu
06.10.2026;2026-W41;2026-10;Testikauppa;Tuntematon;1,99;;;ei;Vahvistettu
06.10.2026;2026-W41;2026-10;Testikauppa;Panttipalautus;-0,40;;;kyllä;Vahvistettu
```
and the file name is `kuittirivit_2026-10_2026-10.csv`.

### AC2: Weekly totals file
**Given** the fixture
**When** the user requests `GET /api/export/totals?unit=month&from=2026-10&to=2026-10&by=week`
**Then** the body after the header row is exactly:
```text
2026-W40;01.10.2026;04.10.2026;kyllä;Ruoka;Maitotuotteet;1,25
2026-W41;05.10.2026;11.10.2026;ei;Ruoka;Leivät;3,00
2026-W41;05.10.2026;11.10.2026;ei;;Juomat;2,50
2026-W41;05.10.2026;11.10.2026;ei;;Ei kategoriaa;1,99
```

### AC3: Monthly totals file
**Given** the fixture
**When** the user requests the same period with `by=month`
**Then** every row starts with `2026-10;01.10.2026;31.10.2026;ei;`, and the rows are
otherwise those of the CSV export spec (AC16 there).

### AC4: A date range and a year change
**Given** a reviewed line dated 28.12.2026 and one dated 3.1.2027
**When** the user requests the totals by week of the date range 28.12.2026–3.1.2027
(`unit=range&from=2026-12-28&to=2027-01-03&by=week`) and the lines file of the same range
**Then** the totals rows start with `2026-W53;28.12.2026;03.01.2027;ei;`, the lines file's
`Päivä` cells are `28.12.2026` and `03.01.2027`, and the file names are
`summat_viikot_2026-12-28_2027-01-03.csv` and `kuittirivit_2026-12-28_2027-01-03.csv`.

### AC5: Keys and names unchanged
**Given** the fixture
**When** the user requests the three files of AC1–AC3
**Then** `Viikko`, `Kuukausi` and `Jakso` hold `2026-W40`, `2026-W41` and `2026-10` as
before, the headers are unchanged, and the file names are those of the CSV export spec.

### AC6: The comparison file is unchanged
**Given** the example of the [comparison CSV export spec](comparison-csv-export.md)
**When** the user requests `GET /api/export/comparison?month=2026-10&weeks=true`
**Then** the body is the same as before this change (its AC1 and AC3).

### AC7: Download from the page
**Given** the E2E data
**When** the user downloads the weekly and monthly totals files of a month or a date range
on the Yhteenveto page
**Then** their rows hold the `Alkaa` and `Päättyy` dates as `dd.mm.yyyy`, as in AC2 and AC3.

## Files to Modify
| File | Change |
|---|---|
| `specs/PRD.md` | FR-26 and the Later candidates (PC1) |
| `backend/app/export/csv_exporter.py` | `Päivä`, `Alkaa`, `Päättyy` through the Finnish date function; `_day` removed (PC2, PC3, PC5) |
| `backend/tests/unit/export/test_csv_exporter.py` | The expected dates of the lines and totals files become `dd.mm.yyyy` (AC1–AC5): a planned test change backed by this spec |
| `backend/tests/integration/test_export_api.py` | The same (AC1–AC5): a planned test change backed by this spec |
| `frontend/e2e/import.spec.ts` | The expected `Alkaa` and `Päättyy` dates (AC7): a planned test change backed by this spec |
| `docs/subsystems/export/README.md` | The CSV format: one date rule for all CSV files |
| `docs/api-reference.md` | The examples of the lines and totals files |
| `specs/features/csv-export.md` | A note that this spec changed the date form |
| `docs/content-plan.md`, `specs/README.md` | Status |

## Risk
- **What could break:** a user's own Excel sheet or macro that reads the ISO dates of the old
  files. Finnish Excel reads both forms as dates, so a sheet that only shows or sorts the
  dates keeps working.
- **Rollback:** revert the change; no data model change.
- **Dependencies:** none new.

## Testing Strategy (MANDATORY)

The existing tests of the lines and totals files assert ISO dates. Their expected dates are
changed by this spec (Files to Modify); no other expectation in them changes.

### Unit tests
| AC | Function | Case | Given | When | Then | Mocks |
|---|---|---|---|---|---|---|
| AC1 | `CsvExporter.lines_file` | lines | fixture lines | build | rows of AC1 | none |
| AC2 | `CsvExporter.totals_file` | by week | fixture totals | build | rows of AC2 | none |
| AC3 | `CsvExporter.totals_file` | by month | fixture totals | build | rows start `2026-10;01.10.2026;31.10.2026;ei;` | none |
| AC4 | `CsvExporter.totals_file`, `lines_file` | year change | lines of 28.12.2026 and 3.1.2027 | build | `28.12.2026;03.01.2027`; `Päivä` cells; names with ISO bounds | none |
| AC5 | `CsvExporter` | keys and names | fixture | build | `Viikko`, `Kuukausi`, `Jakso`, headers and names unchanged | none |
| AC6 | `CsvExporter.comparison_file` | unchanged | comparison example | build | the existing comparison tests pass unchanged | none |

### Integration tests
Real SQLite (temporary file) and real FastAPI app.
| AC | Scenario | Request / input | Expected output | Status |
|---|---|---|---|---|
| AC1 | lines file | `GET /api/export/lines?unit=month&from=2026-10&to=2026-10` | rows of AC1 | 200 |
| AC2 | weekly totals | `GET /api/export/totals?...&by=week` | rows of AC2 | 200 |
| AC3 | monthly totals | `...&by=month` | rows of AC3 | 200 |
| AC4 | date range over the year | `unit=range&from=2026-12-28&to=2027-01-03` | dates and names of AC4 | 200 |
| AC6 | comparison file | `GET /api/export/comparison?month=2026-10&weeks=true` | the existing comparison tests pass unchanged | 200 |

### E2E tests
| AC | Journey | Steps | Expected outcome |
|---|---|---|---|
| AC7 | Download the totals files | the existing export journeys of `import.spec.ts` | the `Alkaa` and `Päättyy` dates are `dd.mm.yyyy` |

### Coverage target
- Backend: 80 % lines; `csv_exporter.py` stays at 100 %.

### Test data
- Synthetic fixtures only: the CSV export spec's fixture and two lines around the year change.
- Mocks: none.

## Related Documentation (MANDATORY)
- Tier 1: [api-reference.md](../../docs/api-reference.md#export)
- Tier 2: [export](../../docs/subsystems/export/README.md)
- Specs: [CSV export](csv-export.md), [Budget comparison CSV export](comparison-csv-export.md)
- ADRs: none new

## Plan

### P1 One date function (`backend/app/export/csv_exporter.py`)

- `_finnish_day(day)` (added by the comparison CSV export spec) becomes the only date writer
  of the module; its docstring names all three files.
- `lines_file`: `Päivä` is `_finnish_day(line.purchase_date)` instead of
  `day.isoformat()`. `Viikko` and `Kuukausi` stay `isocalendar()` and `YYYY-MM`.
- `totals_file`: `Alkaa` and `Päättyy` are `_finnish_day(row.column.start)` and
  `_finnish_day(row.column.end)`.
- `_day` (ISO) is removed: nothing else uses it.
- `_bounds(period)` is unchanged, so the file names keep `period.first` and `period.last`
  (PC4).

No other module changes: the service, the routes, `rows.py` and the frontend pass dates as
`date` objects or not at all.

### P2 Test changes (planned, backed by this spec)

The expected date cells change from `YYYY-MM-DD` to `dd.mm.yyyy`; nothing else in these tests
changes. They are edited in the Red step of T2, before the production change, so the red
run shows the old ISO output against the new expectation.

| File | Tests |
|---|---|
| `backend/tests/unit/export/test_csv_exporter.py` | `test_ac1_lines_file`, `test_ac2_weekly_totals_file`, `test_ac16_monthly_totals_file`, and the `Päivä` cell of the year-change test (`2027-01-02` → `02.01.2027`) |
| `backend/tests/integration/test_export_api.py` | the lines, weekly and monthly file tests, `test_ac4_week_period_with_partial_months`, `test_ac5_a_category_summing_to_zero`, `test_date_range_ac10_lines_file` and `test_date_range_ac11_totals_files`: their `Alkaa`, `Päättyy` and `Päivä` cells only |
| `frontend/e2e/import.spec.ts` | the `toContain` checks of the weekly and monthly files (`2026-W41;05.10.2026;07.10.2026;kyllä;`, `2026-W41;05.10.2026;11.10.2026;ei;`, `2026-10;01.10.2026;31.10.2026;ei;`) |

New tests: AC4 (year change, unit and integration) and AC5 (keys and names unchanged, unit).
AC6 needs no new test: the comparison CSV tests run unchanged.

### P3 Docs

- `docs/subsystems/export/README.md`: the CSV format says dates are `dd.mm.yyyy` with
  leading zeros in all CSV files; the comparison section drops "Only this file".
- `docs/api-reference.md`: the lines and totals examples get Finnish dates.
- `specs/features/csv-export.md`: a note in its Overview that this spec changed the date
  form of FR-26.
- The glossary has no CSV date term, so it does not change (Files to Modify refined).

### Data model, dependencies, ADR

No data model change, no new dependency, no ADR: the date form follows the comparison CSV
export spec's choice.

### AC check

| AC | Covered by |
|---|---|
| AC1–AC3 | P1, P2 |
| AC4 | P1 (`_finnish_day` keeps zeros; `_bounds` unchanged), new tests |
| AC5 | P1 (keys and `_bounds` unchanged), new unit test |
| AC6 | P1 (comparison file already uses `_finnish_day`), existing tests |
| AC7 | P2 (E2E checks) |

## Tasks

Each task runs Red → Green → Refactor. Backend tasks end with `pytest`, `ruff check`,
`ruff format --check` and `pyright` green in `backend-test`; the E2E task with
`docker compose --profile e2e run --rm e2e` green.

- [x] **T1 PRD (PC1).** FR-26 in PRD section 6.6: dates `dd.mm.yyyy` with leading zeros;
  week and month keys and file names in ISO form. Remove the date candidate from the Later
  (candidates) row of section 9. Proof: the PRD has no `YYYY-MM-DD` rule for CSV dates.
- [x] **T2 Lines and totals files (P1, P2; AC1–AC3).** Red: change the expected date
  cells in `test_csv_exporter.py` and `test_export_api.py` as listed in P2; run them and see
  them fail on the ISO dates only. Green: `_finnish_day` for `Päivä`, `Alkaa`, `Päättyy`;
  remove `_day`. Proof: the full backend suite green, the comparison CSV tests unchanged
  (AC6).
- [x] **T3 Year change and unchanged keys (AC4, AC5).** New unit tests in
  `test_csv_exporter.py` (the range 28.12.2026–3.1.2027: `2026-W53;28.12.2026;03.01.2027;ei;`,
  `Päivä` cells, ISO bounds in both names; `Viikko`, `Kuukausi`, `Jakso`, headers and names
  unchanged) and an integration test in `test_export_api.py` for the range request.
- [x] **T4 E2E (P2; AC7).** Change the three date checks in `frontend/e2e/import.spec.ts`;
  run the E2E suite.
- [x] **T5 Docs (P3).** Export README CSV format and comparison section, the api-reference
  examples, the note in `csv-export.md`, `docs/content-plan.md` and `specs/README.md`.
- [x] **T6 Full checks and audit.** All check commands of AGENTS.md for the backend and the
  frontend, the E2E tests, then the `review-audit` skill.

## Audit: Finnish dates in the lines and totals CSV files (2026-11-11)

- Acceptance criteria: 7/7 met
- Tests: backend 1463 passed (pytest), frontend `npm test` passed, E2E 41 passed;
  `csv_exporter.py` stays at 100 % line coverage
- Security: 0 critical, 0 high, 0 medium
- Docs updated: yes; spec status: Done

| AC | Status | Evidence |
|---|---|---|
| AC1 | ✅ | `test_ac1_lines_file` (unit), `test_ac1_lines_file_of_a_month` (integration) |
| AC2 | ✅ | `test_ac2_weekly_totals_file`, `test_ac2_weekly_totals_file_of_a_month` |
| AC3 | ✅ | `test_ac16_monthly_totals_file`, `test_ac16_monthly_totals_file_of_a_month` |
| AC4 | ✅ | `test_finnish_dates_ac4_a_range_over_the_year_change` (unit and integration) |
| AC5 | ✅ | `test_finnish_dates_ac5_keys_headers_and_names_are_unchanged`, `test_ac6_file_names_and_media_type` |
| AC6 | ✅ | the comparison CSV tests pass unchanged |
| AC7 | ✅ | `export AC1, AC2, AC16, AC13` and `date range AC14, AC20` in `e2e/import.spec.ts` |

Checks: `ruff check`, `ruff format --check`, `pyright`, `pip-audit` (no known
vulnerabilities), `npm test`, `npm run lint`, `npm run format:check`, `npm run typecheck`,
E2E.

Test changes: the expected date cells in `test_csv_exporter.py`, `test_export_api.py` and
`e2e/import.spec.ts`, as listed in P2 (completed before the edits with the date range
tests). They were made in the Red step and failed on the ISO dates only; no other
expectation changed. The guard recorded no test edit for this branch.

The AC4 and AC5 tests passed when written: T2's change already gave that behavior. They
guard the year change, the keys and the file names.

| # | Severity | File | Finding | Recommendation |
|---|---|---|---|---|
| 1 | Medium | `compose.yaml` | The E2E test backend runs without reload and stays up between E2E runs, so a run can test old backend code: the first E2E run of this change passed with the old ISO expectations. The user restarted the service; the E2E then failed as planned and passed after T4. | A separate change: recreate the E2E test backend on every E2E run. |
| 2 | Low | guardrail hook | Likely false positives again: G1 blocked a read-only `grep` of test files, and G2 blocked a restart of the E2E test service. | The user checks the G1 and G2 patterns. |

Verdict: PASS. Findings 1 and 2 are outside this feature and left to the user.

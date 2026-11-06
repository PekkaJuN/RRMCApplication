# Feature: Free date range for totals

## Overview
- **Status:** Done
- **Created:** 2026-11-06
- **Updated:** 2026-11-06: Specify approved by the user; Plan added. After the user's request,
  `Alkaen` and `Päättyen` of `Aikaväli` use the [date field](date-field.md) (PC5, AC13–AC16, AC19,
  P4, P6); these changes approved by the user. Plan approved by the user; Tasks added; spec approved by
  the user; implementation started. After the user's request, `Alkaen` and `Päättyen` of
  `Aikaväli` are chosen from the calendar only (PC5, AC14, AC15, P4). Audited (PASS), see
  [Audit](#audit).
- **Depends on:** [Category totals](totals.md), [CSV export](csv-export.md),
  [Finnish date field](date-field.md)
- **Implements:** PRD FR-49; NFR-1, NFR-3, NFR-6, NFR-15 for the changed view.
- **Affected subsystems:** [calculation](../../docs/subsystems/calculation/README.md) (the
  period), [totals](../../docs/subsystems/totals/README.md),
  [export](../../docs/subsystems/export/README.md),
  [ui](../../docs/subsystems/ui/README.md)

## Problem Statement
The Yhteenveto page and the CSV export cover whole calendar months or whole ISO weeks. The
user cannot see or export a period such as the 15th to the 14th of the next month, a
vacation or any other free range of days (PRD FR-49). The Vertailu page already has a
15–14 period, but its totals cannot be seen by category group or exported.

## Current Behavior
- `GET /api/totals` and both `GET /api/export/*` endpoints take `unit` `month` or `week`,
  with `from` and `to` as `2026-10` or `2026-W40`
  ([API reference](../../docs/api-reference.md#totals)).
- A period is at most 24 months or 104 weeks. Week and month columns are clipped to the
  period's days and marked partial
  ([calculation](../../docs/subsystems/calculation/README.md#period-totals)).
- The Yhteenveto page has the unit choice `Kuukausi` and `Viikko`, the inputs `Alkaen` and
  `Päättyen`, and the period in the address ([ui](../../docs/subsystems/ui/README.md)).
- A partial column's heading shows the end date's year only, because today's partial
  columns lie within one month.
- The export links download the period shown in the tables
  ([export](../../docs/subsystems/export/README.md)).

## Proposed Change

### Concepts

- A **date range** is a period given by its first day and its last day, both included. One
  day is a valid date range.
- The columns, partial marks, category totals, group totals, deposit refund rule, unreviewed
  count and undated count work as in the [totals spec](totals.md#concepts). Only the way the
  period is chosen is new.
- Example: 15.10.2026 (Thu) – 14.11.2026 (Sat) has the week columns 42 (partial,
  15–18 Oct), 43, 44, 45 and 46 (partial, 9–14 Nov), and the month columns October
  (partial, 15–31 Oct) and November (partial, 1–14 Nov).

### Parts

- **PC1 Date range period (FR-49).** The period gets a third unit, `range`, whose `from` and
  `to` are days in the form `YYYY-MM-DD`. The period covers every day from `from` to `to`.
  Whole-month and whole-week periods do not change.
- **PC2 Totals endpoint (FR-49).** `GET /api/totals?unit=range&from=2026-10-15&to=2026-11-14`
  returns the same shape as today, with `unit` `range` and `from` and `to` as given.
- **PC3 Export (FR-49).** `GET /api/export/lines` and `GET /api/export/totals` accept the same
  three parameters. File formats do not change. The file names use the two days:
  `kuittirivit_2026-10-15_2026-11-14.csv`, `summat_viikot_2026-10-15_2026-11-14.csv` and
  `summat_kuukaudet_2026-10-15_2026-11-14.csv`.
- **PC4 Validation.** A `from` or `to` that is not a real day in the form `YYYY-MM-DD`, a year
  outside 1–9998, a `from` after `to`, or a range longer than 731 days gives
  `422 invalid_period`. The limit counts from `from` to `to` inclusive. 731 days is the longest
  possible 24 months, so the limit stays the same as for the month unit.
- **PC5 Period chooser (FR-49).** The unit choice `Jakso` gets the option `Aikaväli` after
  `Viikko`. `Alkaen` and `Päättyen` use the [date field](date-field.md), shown as `dd.mm.yyyy`.
  They are chosen from the calendar only: the text cannot be edited, and a click on the field
  or its button opens the calendar.
  Choosing `Aikaväli` selects the first and last day of the current calendar month by the
  browser's local date, as choosing another unit selects the current month or week. A
  picked day loads the totals.
- **PC6 Address.** The period is kept in the address as
  `/yhteenveto?unit=range&from=2026-10-15&to=2026-11-14`. A reload keeps it, and each change
  adds a history entry. An address with `unit=range` and a bound of another shape opens the
  current month. A bound of the right shape that the backend refuses shows the error.
- **PC7 Partial column heading.** A partial column can now cross a month or a year. When its
  two days are in the same year, the heading is as today: `28.10.–1.11.2026`. When they are in
  different years, both days show their year: `30.12.2026–2.1.2027`.
- **PC8 Privacy (NFR-1, NFR-3).** The query string and the file names hold dates only. Logs
  carry method, path and status only.

### UI texts

| Place | Text |
|---|---|
| New option of the unit choice `Jakso` | `Aikaväli` |

Every other text is in the [totals spec](totals.md#ui-texts). A refused period shows the
existing `Jakso on virheellinen.`.

### Out of Scope

- A ready-made 15–14 choice on the Yhteenveto page. The user picks the two dates.
- Changes to the Vertailu page or the comparison endpoint.
- PDF export (FR-48).
- A column per day. The tables keep week and month columns.
- A saved default period. The default stays the current calendar month (FR-25).
- Client-side validation of date order or length. The backend decides, as for other periods.

## Acceptance Criteria

### AC1: A range is totalled by its days
**Given** lines of category `Leivät` dated 14.10.2026 (100 cents), 15.10.2026 (200),
14.11.2026 (400) and 15.11.2026 (800)
**When** the client sends `GET /api/totals?unit=range&from=2026-10-15&to=2026-11-14`
**Then** the answer is 200 with `unit` `range`, `from` `2026-10-15`, `to` `2026-11-14`, and
`month_totals` `[200, 400]`

### AC2: Columns of a range
**Given** the range 15.10.2026–14.11.2026
**When** the totals are computed
**Then** the week columns are `2026-W42` (15–18 Oct, partial), `2026-W43`, `2026-W44`
(26 Oct – 1 Nov, not partial), `2026-W45` and `2026-W46` (9–14 Nov, partial), and the month
columns are `2026-10` (15–31 Oct, partial) and `2026-11` (1–14 Nov, partial)

### AC3: One-day range
**Given** a line dated 7.10.2026 and a line dated 8.10.2026
**When** the client asks for `unit=range&from=2026-10-07&to=2026-10-07`
**Then** the answer is 200, only the first line counts, and there is one partial week column
`2026-W41` and one partial month column `2026-10`, both covering 7.10.2026 only

### AC4: A range that matches a month gives the month's totals
**Given** lines in October 2026
**When** the client asks for the range 1.10.2026–31.10.2026 and for `unit=month` with
`2026-10`
**Then** `weeks`, `months`, `rows` and their totals are equal in both answers, and the month
column is not partial

### AC5: Range across a year boundary
**Given** lines dated 29.12.2026, 30.12.2026, 2.1.2027 and 3.1.2027
**When** the client asks for the range 30.12.2026–2.1.2027
**Then** only the two middle lines count, the week column is `2026-W53` (partial,
30.12.2026–2.1.2027), and the month columns are `2026-12` (partial) and `2027-01` (partial)

### AC6: Totals rules stay the same
**Given** a range holding a deposit refund line, a line without a category, an unreviewed
receipt, and a receipt without a purchase date
**When** the client asks for the range's totals
**Then** the deposit refund is in no total, the line without a category is in the `none` row,
`unreviewed_receipts` is 1 and `undated_receipts` is 1

### AC7: Longest and too long range
**Given** no special data
**When** the client asks for 1.1.2027–31.12.2028 (731 days) and for 1.1.2027–1.1.2029
(732 days)
**Then** the first answer is 200 and the second is 422 with `error` `invalid_period`

### AC8: Invalid range values
**Given** `unit=range`
**When** the client sends each of: no `from`; no `to`; `2026-02-30`; `2026-2-3`; `20261015`;
`2026-10`; `2026-W40`; `0000-01-01`; `9999-01-01`; a day with non-ASCII digits; `from`
`2026-10-02` with `to` `2026-10-01`
**Then** each answer is 422 with `error` `invalid_period` and the message
`Jakso on virheellinen.`

### AC9: Other units do not take days
**Given** `unit=month` or `unit=week`
**When** `from` and `to` are `2026-10-15`
**Then** the answer is 422 with `error` `invalid_period`

### AC10: Lines file of a range
**Given** the lines of AC1
**When** the client sends `GET /api/export/lines?unit=range&from=2026-10-15&to=2026-11-14`
**Then** the answer is 200, the file is named `kuittirivit_2026-10-15_2026-11-14.csv`, and it
holds the lines dated 15.10.2026 and 14.11.2026 only

### AC11: Totals files of a range
**Given** the lines of AC1
**When** the client asks for `GET /api/export/totals` with the same range and `by=week`, then
`by=month`
**Then** the files are named `summat_viikot_2026-10-15_2026-11-14.csv` and
`summat_kuukaudet_2026-10-15_2026-11-14.csv`; the row of `2026-W46` has Alkaa `2026-11-09`,
Päättyy `2026-11-14`, Osittainen `kyllä` and Summa `4,00`; the row of `2026-11` has Alkaa
`2026-11-01`, Päättyy `2026-11-14`, Osittainen `kyllä` and Summa `4,00`

### AC12: Invalid range in the export
**Given** a range that AC8 refuses
**When** the client asks for either export
**Then** the answer is 422 with `error` `invalid_period`, and `invalid_period` comes before an
invalid `by`, as for other periods

### AC13: Choosing `Aikaväli`
**Given** the browser date 6.11.2026 and the Yhteenveto page with the month period
**When** the user chooses `Aikaväli` in `Jakso`
**Then** the date fields `Alkaen` and `Päättyen` show `01.11.2026` and `30.11.2026`, the page loads
that range, and the address is `/yhteenveto?unit=range&from=2026-11-01&to=2026-11-30`

### AC14: Changing the dates
**Given** the `Aikaväli` unit is chosen
**When** the user picks 15.10.2026 for `Alkaen` and 14.11.2026 for `Päättyen`
**Then** the page loads the range after each picked day, the address holds the last range, and the
tables show its columns with the partial marks of AC2

### AC15: The text cannot be edited
**Given** the `Aikaväli` unit is chosen
**When** the user types in `Alkaen`, or clears the day in the calendar
**Then** the field keeps its date, the page sends no request, and the address and the tables
stay

### AC16: Address opens the range
**Given** the address `/yhteenveto?unit=range&from=2026-10-15&to=2026-11-14`
**When** the page opens or is reloaded
**Then** the unit is `Aikaväli`, the fields show `15.10.2026` and `14.11.2026` and the page loads
that range

### AC17: Back button
**Given** the user has changed the range from A to B
**When** the user presses the back button
**Then** the inputs, the address and the tables show range A

### AC18: Malformed address
**Given** the address `/yhteenveto?unit=range&from=2026-10&to=2026-11-14`, and an address with
`to` missing
**When** the page opens
**Then** the current calendar month is shown and the address shows it

### AC19: Refused range in the UI
**Given** `Alkaen` is after `Päättyen`, or the address holds `from=2026-02-30`, which the date
field cannot show as a real day
**When** the page loads the period
**Then** the page shows `Jakso on virheellinen.` with `role="alert"`, and no tables or export
links

### AC20: Export links follow the shown range
**Given** the tables show the range 15.10.2026–14.11.2026
**When** the user follows the links
**Then** the three links point to `/api/export/...` with `unit=range`, `from=2026-10-15` and
`to=2026-11-14`, and the totals links have `by=week` and `by=month`

### AC21: Partial column heading across months and years
**Given** a partial week column
**When** its days are 28.10.2026–1.11.2026, and when they are 30.12.2026–2.1.2027
**Then** the headings are `vk 44/2026 (osittainen) 28.10.–1.11.2026` and
`vk 53/2026 (osittainen) 30.12.2026–2.1.2027`

### AC22: Existing periods stay the same
**Given** the month and week periods
**When** the existing totals and export tests run
**Then** they pass unchanged, and the default is the current calendar month

## Files to Modify

| File | Change |
|---|---|
| `backend/app/calculation/period.py` | The `PeriodUnit` type, parsing and the 731-day limit |
| `frontend/src/period.ts` | The `range` unit, address, current month as days, heading rule |
| `frontend/src/components/TotalsPage.tsx`, `frontend/src/components/TotalsTable.tsx` | The option, the [date field](date-field.md) |
| `frontend/src/i18n/fi.ts` | `Aikaväli` |
| Test files in [P6](#p6-tests) | New tests |
| `docs/subsystems/calculation/README.md`, `docs/subsystems/totals/README.md`, `docs/subsystems/export/README.md`, `docs/subsystems/ui/README.md` | The date range |
| `docs/api-reference.md` | The `range` unit and its `invalid_period` cases |
| `docs/glossary.md` | Period and new term date range |
| `specs/README.md`, this spec, `docs/content-plan.md` | Status |

## Risk

- **What could break:** month and week periods if parsing or the shared `Period` type changes;
  off-by-one at the range's first and last day; a wrong partial flag or heading now that a
  partial column can cross a month or a year; a month-only assumption in the export or the
  page. The change only reads data.
- **Rollback:** revert the commits. There is no migration and no data change.
- **Dependencies:** none new expected.

## Testing Strategy (MANDATORY)

### Unit tests

| AC | Function | Case | Given | When | Then | Mocks |
|---|---|---|---|---|---|---|
| AC2 | `parse_period` + columns | happy path | 2026-10-15 to 2026-11-14 | columns | The columns of AC2 | none |
| AC3 | `parse_period` + columns | one day | 2026-10-07 twice | columns | One partial week, one partial month | none |
| AC4 | `parse_period` + columns | whole month | 2026-10-01 to 2026-10-31 | compare with `month` | Same columns and flags | none |
| AC5 | `parse_period` + columns | year boundary | 2026-12-30 to 2027-01-02 | columns | `2026-W53`, `2026-12`, `2027-01`, all partial | none |
| AC7 | `parse_period` | limit | 731 and 732 days | parse | Accepted; `PeriodError` | none |
| AC8 | `parse_period` | each bad value | Each value of AC8 | parse | `PeriodError` | none |
| AC9 | `parse_period` | wrong unit | `month` and `week` with days | parse | `PeriodError` | none |
| AC6 | `period_totals` | rules | Deposit refund, no category | totals | Rows and totals as AC6 | none |
| AC18 | `periodFromSearch` | bad shape | `from=2026-10`, no `to` | parse | `null` | none |
| AC16 | `periodFromSearch`, `periodToSearch` | round trip | The range of AC16 | parse, write | The same period and address | none |
| AC13 | `currentMonth` for days | month length | 6.11.2026, February 2028 | call | `2026-11-01`–`2026-11-30`, `2028-02-01`–`2028-02-29` | fake date |
| AC21 | `columnHeading` | across a month, a year | The columns of AC21 | call | The headings of AC21 | none |
| AC20 | `exportUrl` | range | The range of AC20 | call | The URLs of AC20 | none |

### Integration tests

Real SQLite (temporary file) and real FastAPI app; Tesseract and Ollama are not used.

| AC | Scenario | Request / input | Expected output | Status |
|---|---|---|---|---|
| AC1 | Edges of a range | `GET /api/totals?unit=range&from=2026-10-15&to=2026-11-14` | `month_totals` `[200, 400]`; the days before and after are not counted | 200 |
| AC5 | Year boundary | `GET /api/totals` for 30.12.2026–2.1.2027 | Two lines counted, columns of AC5 | 200 |
| AC4 | Same as month | `unit=range` and `unit=month` for October 2026 | Equal `weeks`, `months`, `rows` and totals | 200 |
| AC6 | Rules | `GET /api/totals` for a range | Counts and rows of AC6 | 200 |
| AC7 | Length | 731 and 732 days | 200; `invalid_period` | 200, 422 |
| AC8 | Bad values | Each value of AC8 | `invalid_period`, `Jakso on virheellinen.` | 422 |
| AC9 | Wrong unit | `unit=month&from=2026-10-15&to=2026-10-15` | `invalid_period` | 422 |
| AC10 | Lines file | `GET /api/export/lines` | Name and rows of AC10 | 200 |
| AC11 | Totals files | `GET /api/export/totals` with `by=week`, `by=month` | Names and rows of AC11 | 200 |
| AC12 | Bad export | Bad range, bad `by` | `invalid_period` first | 422 |
| AC22 | Existing periods | The existing totals and export tests | Unchanged and passing | 200, 422 |

### Component tests

MSW for the API; the browser date is faked.

| AC | Scenario | Steps | Expected outcome |
|---|---|---|---|
| AC13 | Choose the unit | Choose `Aikaväli` | Date inputs, request and address of AC13 |
| AC14 | Pick dates | Pick both days | A request per pick, the last range in the address |
| AC15 | Read-only text | Type in `Alkaen`; clear the calendar's day | No request, the field, the address and the tables stay |
| AC16 | Open an address | Render with the address | Unit, inputs and request of AC16 |
| AC17 | Back | Change, then go back | Inputs, address and tables of range A |
| AC18 | Bad address | Render with each address | Current month in the address |
| AC19 | Refused range | The API answers 422 | The alert; no tables or links |
| AC20 | Links | Render the range | The links of AC20 |
| AC22 | Month and week | The existing page tests | Unchanged and passing |

### E2E tests

| AC | Journey | Steps | Expected outcome |
|---|---|---|---|
| AC14, AC20 | Range totals and export | Open Yhteenveto, choose `Aikaväli`, set the two dates of a synthetic receipt's range, reload, download the totals file | The tables show the receipt's sum after the reload; the file has the range in its name |

### Coverage target

- Backend: 90 % lines; period parsing, columns and totals: every branch tested.
- Frontend: 80 % lines for the changed code.

### Test data

- Synthetic fixtures only (no real receipts): test receipts and lines created through the test
  repository with invented names and amounts; the synthetic E2E receipt image.
- Mocks: MSW for the frontend; the browser date is faked in component tests.

## Related Documentation (MANDATORY)

- Tier 1: [API reference](../../docs/api-reference.md#totals),
  [Glossary](../../docs/glossary.md), [PRD FR-25, FR-26, FR-49](../PRD.md#65-totals)
- Tier 2: [calculation](../../docs/subsystems/calculation/README.md),
  [totals](../../docs/subsystems/totals/README.md),
  [export](../../docs/subsystems/export/README.md), [ui](../../docs/subsystems/ui/README.md)
- ADRs: none
- Specs: [Category totals](totals.md), [CSV export](csv-export.md),
  [Monthly budget](budget.md)


## Plan

### P0 Overview

```
GET /api/totals?unit=range&from&to, GET /api/export/lines, GET /api/export/totals
  → existing routes        (plain optional strings: every bad value becomes invalid_period)
  → existing services
      parse_period         calculation/period.py   → Period, or PeriodError → 422
      existing reads       storage, by period.start and period.end
      period_totals        calculation/period_totals.py, unchanged
  → existing schemas and CsvExporter

Yhteenveto → period.ts (shape, address, heading) → existing API clients → the routes above
```

No migration, no new dependency, no new endpoint and no ADR. Every backend reader already uses
`period.start`, `period.end` and the clipped columns, so one new branch in `parse_period` gives
the totals and the export the new unit.

### P1 Units (`calculation/period.py`)

- `Unit` stays `Literal["month", "week"]`: it is the kind of a column, and the export's `by`,
  `TOTALS_NAMES` and `long_rows` use it. A file cannot be `by=range`.
- A new `PeriodUnit = Unit | Literal["range"]` types `Period.unit`.
- A new constant `MAX_RANGE_DAYS = 731`.
- The module docstring names the date range.

### P2 Parsing (`calculation/period.py`, PC1, PC4)

```python
_DAY = re.compile(r"([0-9]{4})-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])")
```

- `_day(value: str) -> date`: `fullmatch` with explicit digits, as for months and weeks; the year
  must be 1–`MAX_YEAR`; `date(...)` raising `ValueError` becomes `PeriodError` (`2026-02-30`).
  `date.fromisoformat` is not used, because it also accepts other forms such as `20261015`.
- `parse_period` gets a `range` branch after `week`: both days through `_day`, then
  `length = (end - start).days + 1`, and `1 <= length <= MAX_RANGE_DAYS` or `PeriodError`.
- It returns `Period("range", first, last, start, end)`. `first` and `last` are the checked
  strings, so the answer's `from` and `to` and `_bounds` in the file names need no change.
- `unit=month` and `unit=week` already refuse a day through `_month` and `_monday` (AC9); this
  needs tests only.
- The columns need no change: `_clip` already sets `partial`. Year 1 starts on a Monday, so
  `week_columns` cannot run below `date.min`, and `MAX_YEAR` keeps the last week inside
  `date.max`.

### P3 Period module (`frontend/src/period.ts`)

- `PeriodUnit` gets `"range"`. A new `ColumnUnit = Exclude<PeriodUnit, "range">` types
  `columnHeading` and `TotalsTable`, because a table is always weeks or months.
- `DAY = /^[0-9]{4}-[0-9]{2}-[0-9]{2}$/`. It checks the shape only; the backend decides whether
  the day exists (AC19).
- `isUnitValue` selects from a `Record<PeriodUnit, RegExp>`, and `periodFromSearch` accepts
  `range`.
- `currentMonthRange(today: Date): Period` returns the local month's first and last day. The
  last day is `new Date(year, month + 1, 0).getDate()`.
- `columnHeading` compares the years of `start_date` and `end_date`. The same year gives
  `formatDayMonth(start)`, different years `formatDate(start)`, then `–` and `formatDate(end)`.
  The comment that a partial column lies within one month is removed.

### P4 Page (`frontend/src/components/`)

- `TotalsPage`: a map `Record<PeriodUnit, (today: Date) => Period>` replaces the ternary in
  `changeUnit`. With `range` the page renders `EditableField` with `type="date"` and
  `pickerOnly` for both bounds ([date field P6](date-field.md#p6-yhteenveto)), and `choose` gets
  the picked day; with
  `month` and `week` the native inputs stay.
- A third `<option value="range">` follows `Viikko`.
- `choose`, the address, `popstate`, `shownPeriod` and the alert need no change: they work on
  `Period` and `isUnitValue`. That gives AC14–AC19.
- An address day that is not real, such as `from=2026-02-30`, reaches the backend unchanged, and
  the field shows `30.02.2026`.
- `TotalsTable.Props.unit` becomes `ColumnUnit`.
- `fi.totals.range = "Aikaväli"`.
- `api/totals.ts` and `api/export.ts` need no change: they pass the unit on as it is (AC20).

### P5 Refinement of the spec

`Files to Modify` is now exact. No code change is needed in `calculation/period_totals.py`,
`export/`, `totals/` or `api/`; those parts get tests only.

### P6 Tests

| Test file | ACs |
|---|---|
| `backend/tests/unit/calculation/test_period.py` | AC2, AC3, AC4, AC5, AC7, AC8, AC9 |
| `backend/tests/unit/calculation/test_period_totals.py` | AC6 |
| `backend/tests/integration/test_totals_api.py` | AC1, AC4, AC5, AC6, AC7, AC8, AC9 |
| `backend/tests/integration/test_export_api.py` | AC10, AC11, AC12 |
| `frontend/src/period.test.ts` | AC13, AC16, AC18, AC21 |
| `frontend/src/api/export.test.ts` | AC20 |
| `frontend/src/components/TotalsPage.test.tsx` | AC13–AC20 |
| `frontend/e2e/import.spec.ts` | AC14, AC20: a new journey for a range around the synthetic receipt's date 5.10.2026, in a real browser, with the days set through the calendar's input |

AC22 is the existing tests, which must pass without edits. `TotalsTable` needs a type change
only, so its tests do not change.

### P7 Plan checked against the ACs

| ACs | Covered by |
|---|---|
| AC1–AC5 | P2, with the existing columns and reads |
| AC6 | Existing `period_totals`, service counts |
| AC7, AC8 | P2 |
| AC9 | Existing `_month` and `_monday` |
| AC10–AC12 | P2, with the existing export; P1 keeps `by` as it is |
| AC13 | P3 `currentMonthRange`, P4 |
| AC14–AC19 | P3 shape and address, with the existing page logic |
| AC20 | Existing `exportUrl` |
| AC21 | P3 `columnHeading` |
| AC22 | P1 and P2 add a branch only; P3 keeps the month and week results |

### P8 Documentation

- `docs/subsystems/calculation/README.md`: the date range, its limit and its parsing.
- `docs/subsystems/totals/README.md`, `docs/subsystems/export/README.md`: the third unit; the
  export's file names with days.
- `docs/subsystems/ui/README.md`: `Aikaväli` and the address.
- `docs/api-reference.md`: the `range` unit in totals and export, and `invalid_period`.
- `docs/glossary.md`: `Period` is updated and `Date range` (`aikaväli`) added.
- `specs/README.md`: the status of this spec.

## Tasks

Do these after [date field](date-field.md) T1–T9.

- [x] **T1 Period type and parsing (P1, P2).** AC2, AC3, AC4, AC5, AC7, AC8, AC9. `PeriodUnit`,
  `MAX_RANGE_DAYS`, `_day` and the `range` branch. Test:
  `backend/tests/unit/calculation/test_period.py`.
- [x] **T2 Totals rules for a range.** AC6. Tests only. Test:
  `backend/tests/unit/calculation/test_period_totals.py`.
- [x] **T3 Totals endpoint.** AC1, AC4, AC5, AC6, AC7, AC8, AC9. Tests only. Test:
  `backend/tests/integration/test_totals_api.py`.
- [x] **T4 CSV export.** AC10, AC11, AC12. Tests only. Test:
  `backend/tests/integration/test_export_api.py`.
- [x] **T5 Period module (P3).** AC13, AC16, AC18, AC20, AC21. Tests:
  `frontend/src/period.test.ts`, `frontend/src/api/export.test.ts`.
- [x] **T6 Yhteenveto page (P4, date field P6).** AC13–AC20, date field PC6. The option, the
  `EditableField` date fields, `fi.totals.range` and `ColumnUnit` in `TotalsTable`. Test:
  `frontend/src/components/TotalsPage.test.tsx`.
- [x] **T7 E2E (P6).** AC14, AC20, date field AC15 for Yhteenveto. Tests:
  `frontend/e2e/import.spec.ts`, `frontend/e2e/style.spec.ts`.
- [x] **T8 Documentation (P8).** The documents of P8.
- [x] **T9 Full check.** AC22. Every backend and frontend command in `AGENTS.md`, the E2E tests
  and the container tests pass, and no existing test of the month and week periods was changed.

## Audit

Audited 2026-11-06 against this spec, with two independent reviews and a documentation
scan: **PASS**. The user tried the final build with the mouse.

- Acceptance criteria 22/22 and PC1–PC8 met. Coverage: `calculation/period.py` 100 %,
  `period.ts` 100 %, frontend 98.8 % lines (target 80 %).
- Tests: backend 1320 passed, frontend 328 passed, E2E 36 passed (two runs, also the real
  calendar by keyboard); ruff, pyright, ESLint and tsc clean; container tests and `pip-audit`
  passed. The repository-wide `format:check` reports the known CRLF working-tree warning; the
  changed files pass Prettier with `--end-of-line auto`.
- The second review found that every step inside the open calendar counted as a pick, which
  saved a receipt's date or loaded totals. Fixed test first with the native `change` event
  (date field PC3, AC17; [learnings](../../docs/learnings.md)). The fix had no code review of its
  own; the tests and the user's mouse check cover it.
- The scan found one gap of this change and older count and order errors in the content plan;
  all are fixed. It did not check every identifier or the Tier 1 docs line by line.
- Security: no findings. No receipt data in tests or logs; the query string and the file names
  hold dates only. `npm audit`: 7 moderate findings; this change adds no dependency.
- Manual check: after the fix, the user confirmed with the mouse in `Aikaväli` that browsing
  the calendar changes nothing and that picking a day loads the totals.
- Existing tests of the month and week periods were not changed (AC22).
- Fixed during the audit: the review found that typed text could outlive the back button, and
  that an invalid `Alkaen` could stay beside a loaded range. The user's decision to choose the
  range from the calendar only removes both (PC5, AC15).

# Feature: Category totals

## Overview
- **Status:** Done
- **Created:** 2026-11-02
- **Updated:** 2026-11-02: user answers: lines without a category form a `Ei kategoriaa`
  row; unreviewed receipts count, and the page shows how many are in the period; the page
  shows how many receipts have no date; the period is at most 24 months or 104 weeks; the
  period is kept in the address; a month is shown as `10/2026`. Specify approved by the
  user; Plan added. Plan approved by the user; Tasks added; spec approved by the user;
  implementation started. During T5 the AC fixture names were corrected to the real default
  catalog (`Leivät`, not `Leipä`; `Juomat` as the category without a group, because
  `Polttoaineet` is in the group `Auto`) and AC1 names the category list order; the
  behavior is unchanged. After an independent review: AC14 names the address with the
  period (as PC5 already required), the expand button's text is its accessible name, the
  Yhteenveto link keeps the period while the page is open (PC5), and years are 1–9998 (P1);
  these changes approved by the user. Audited (PASS), see [Audit](#audit).
- **Depends on:** [Receipt review](receipt-review.md), [Line editing](line-editing.md),
  [Line categorization](categorization.md)
- **Implements:** PRD FR-22, FR-23, FR-24, FR-25, FR-44 (totals); NFR-1, NFR-3, NFR-6,
  NFR-15 for the totals view.
- **Affected subsystems:** [calculation](../../docs/subsystems/calculation/README.md) (the
  period totals), [storage](../../docs/subsystems/storage/README.md) (the query),
  [ui](../../docs/subsystems/ui/README.md) (a new page); the endpoint's package is decided
  in the Plan.

## Problem Statement
Receipts are read, categorized, reviewed and corrected, but the app does not yet answer
the question it exists for: how much was spent per category each week and each month
(PRD G2, section 5 step 7). This spec adds the totals: per category and group, per ISO week
and per calendar month, by purchase date, for a period the user chooses. CSV export
(FR-26) comes next and reuses the period and the totals of this spec.

## Current Behavior
- Receipts have a purchase date (`NULL` when it is not a real date) and lines with an
  amount in cents, a category or none, and a deposit refund flag
  ([datamodel](../../docs/datamodel.md#receipts)).
- Calculation computes one receipt's line sum, check and category subtotals
  ([calculation](../../docs/subsystems/calculation/README.md)). There are no totals across
  receipts.
- The UI has the pages Tuotteet, Tuonti, Kuitit and the receipt page
  ([ui](../../docs/subsystems/ui/README.md)). There is no totals page.

## Proposed Change

### Concepts

- A **period** is a continuous range of whole calendar months or whole ISO weeks, given by
  its unit (`month` or `week`), its first unit and its last unit. One month or one week is a
  period whose first and last unit are the same. The period covers every day from the first
  day of its first unit to the last day of its last unit.
- A **column** is one ISO week or one calendar month that has at least one day inside the
  period. A column is **partial** when some of its days are outside the period. Only the
  days inside the period count (FR-25). Example: October 2026 (Thu 1 Oct – Sat 31 Oct) has
  the week columns 40 (partial, 1–4 Oct), 41, 42, 43 and 44 (partial, 26–31 Oct), and the
  month column October.
- A week column is named by its ISO year and week number, which can differ from the
  calendar year: Mon 29 Dec 2025 – Sun 4 Jan 2026 is week 1 of 2026; Mon 28 Dec 2026 –
  Sun 3 Jan 2027 is week 53 of 2026.
- A **category total** of a column is the sum of the amounts of the lines in that category
  whose receipt's purchase date is a day of the column inside the period (FR-22, FR-23).
- A **group total** is the sum of its categories' totals (FR-22).
- Deposit refund lines are in no total (FR-44). Lines that are not deposit refunds and have
  no category are summed into one **no category** row, so the column total is the full
  spending.
- The **column total** is the sum of all rows of the column, the no-category row included.
- Every receipt counts, reviewed or not. The **unreviewed count** is the number of
  unreviewed receipts whose purchase date is in the period, so the user knows which totals
  may still change.
- A receipt without a purchase date is in no period. The **undated count** is the number
  of all receipts without a purchase date, whatever the period, so the user knows they are
  missing from the totals.

### Parts

- **PC1 Totals calculation (FR-22, FR-23, FR-25, FR-44).** Calculation gets the period and
  the lines (purchase date, amount, category, deposit refund flag) and returns the week
  columns and the month columns in date order, each with its category totals, its column
  total and its partial flag. Integer cents only (NFR-6). It changes no data and does no
  I/O.
- **PC2 Totals endpoint (FR-22–FR-25).** `GET /api/totals?unit=month&from=2026-10&to=2026-10`
  or `GET /api/totals?unit=week&from=2026-W40&to=2026-W44` returns the period's first and
  last day, the week columns, the month columns and the rows: groups with their
  categories, standalone categories, and the no-category row last. Rows follow the
  category list order (`GET /api/categories`) and include only categories that have at
  least one line in the period; a group is included when one of its categories is. The
  totals are computed from the database on every request, so they always reflect the
  latest edits (FR-24).
- **PC3 Period validation.** A missing or malformed `unit`, `from` or `to`, a `from` after
  `to`, a week that does not exist (e.g. `2027-W53`), or a period longer than the limit
  gives `422 invalid_period`. The limit is 24 months for `month` and 104 weeks for `week`,
  counted from `from` to `to` inclusive.
- **PC4 Yhteenveto page (FR-22, FR-25).** A new navigation link **Yhteenveto**
  (`/yhteenveto`) after Kuitit. The page has the period chooser and two tables: **weekly
  totals** (one column per week column) and **monthly totals** (one column per month
  column). Rows are the groups, the standalone categories and the no-category row, then a
  total row `Yhteensä`. A group row shows its group total and a button to expand or
  collapse its categories; groups start collapsed. A partial column's heading has the mark
  `(osittainen)` and the days it covers.
- **PC5 Period chooser (FR-25).** The user chooses the unit (`Kuukausi` or `Viikko`), the
  first unit and the last unit. A month is chosen with a month input, a week with a week
  input. Changing a value loads the totals for the new period. On opening, the period is
  the current calendar month by the browser's local date. The chosen period is kept in the
  address as `/yhteenveto?unit=week&from=2026-W40&to=2026-W41`, so a reload keeps it, and
  each change adds a history entry, so the back button returns to the previous period. An
  address without a complete, well-formed period opens the current month. The navigation
  link `Yhteenveto` does nothing while the page is open, so it does not drop the period.
- **PC6 Empty and error states.** A period without lines shows `Ei ostoksia valitulla
  jaksolla.` instead of the tables. A refused period or a failed load shows the error
  message with `role="alert"`.
- **PC7 Money and dates in the UI.** As in the receipt review spec PC10: `123456` →
  `1234,56 €`, `-40` → `-0,40 €`; dates `5.10.2026`. A week is shown as `vk 40/2026`, a
  month as `10/2026` (no leading zero: `1/2027`).
- **PC8 Privacy (NFR-1, NFR-3).** The totals hold category and group names and sums only,
  no product names. Logs carry method, path and status only; the query string holds dates,
  never receipt content.

### UI texts

| Place | Text |
|---|---|
| Navigation link and page heading | `Yhteenveto` |
| Unit choice label and options | `Jakso`: `Kuukausi`, `Viikko` |
| First and last unit labels | `Alkaen`, `Päättyen` |
| Weekly table heading and `aria-label` | `Viikot` |
| Monthly table heading and `aria-label` | `Kuukaudet` |
| First column heading | `Kategoria` |
| Week column heading | `vk 40/2026` |
| Month column heading | `10/2026` |
| Partial column mark | `(osittainen)` and the days, e.g. `1.10.–4.10.2026` |
| No-category row | `Ei kategoriaa` |
| Total row | `Yhteensä` |
| Expand / collapse button: its name (`aria-label`, `aria-expanded`); it shows `+` / `−` before the group name | `Näytä kategoriat: <group>` / `Piilota kategoriat: <group>` |
| No lines in the period | `Ei ostoksia valitulla jaksolla.` |
| Unreviewed count, shown when it is not 0 (`role="status"`) | `Tarkistamattomia kuitteja jaksolla: <n>` |
| Undated count, shown when it is not 0 (`role="status"`) | `Kuitteja ilman päivää (ei mukana): <n>` |

### API shape

`GET /api/totals?unit=month&from=2026-10&to=2026-10`:

```json
{
  "unit": "month",
  "from": "2026-10",
  "to": "2026-10",
  "start_date": "2026-10-01",
  "end_date": "2026-10-31",
  "weeks": [
    {"key": "2026-W40", "start_date": "2026-10-01", "end_date": "2026-10-04", "partial": true},
    {"key": "2026-W41", "start_date": "2026-10-05", "end_date": "2026-10-11", "partial": false}
  ],
  "months": [
    {"key": "2026-10", "start_date": "2026-10-01", "end_date": "2026-10-31", "partial": false}
  ],
  "rows": [
    {"kind": "group", "id": 1, "name": "Ruoka", "weeks": [125, 0], "months": [125],
     "categories": [
       {"kind": "category", "id": 12, "name": "Maitotuotteet", "weeks": [125, 0], "months": [125]}
     ]},
    {"kind": "category", "id": 30, "name": "Juomat", "weeks": [0, 5000], "months": [5000]},
    {"kind": "none", "id": null, "name": null, "weeks": [0, 199], "months": [199]}
  ],
  "week_totals": [125, 5199],
  "month_totals": [5324],
  "unreviewed_receipts": 1,
  "undated_receipts": 0
}
```

`start_date` and `end_date` of a column are the days inside the period. `weeks` and
`months` in a row are cents, in the order of the `weeks` and `months` columns.
`unreviewed_receipts` is the unreviewed count and `undated_receipts` the undated count.

### Error codes

| Status | `error` | `message` | When |
|---|---|---|---|
| 422 | `invalid_period` | `Jakso on virheellinen.` | PC3 |

### Out of Scope
- CSV export (FR-26, FR-27): the next spec. It reuses PC1 and the period of PC3.
- A free date range (from any day to any day): the PRD allows months and ISO weeks only.
- Charts, comparisons with an earlier period, averages and budgets.
- Totals by store, or by product.
- Archived data (FR-40–FR-42): a later release.
- Quantity and unit price: not read or stored (PRD FR-8 note).

## Acceptance Criteria

Fixture for AC1–AC11 unless the AC says otherwise: the default catalog (PRD section
6.9), in which the group `Ruoka` holds `Maitotuotteet` and `Leivät`, and `Juomat` is a
category without a group. Amounts are in cents.

### AC1: Month totals per category and group
**Given** receipt A dated 2026-10-05 with lines Maitotuotteet 125 and Leivät 300, and
receipt B dated 2026-10-20 with Maitotuotteet 200
**When** the client calls `GET /api/totals?unit=month&from=2026-10&to=2026-10`
**Then** the answer is 200, `months` has one column `2026-10` with `partial` false, the row
`Ruoka` has `months` `[625]`, its categories are `Leivät` `[300]` and `Maitotuotteet`
`[325]` in category list order, and `month_totals` is `[625]`

### AC2: Week columns of a month, partial at both ends
**Given** the fixture of AC1, plus receipt C dated 2026-10-02 with Leivät 100 and receipt D
dated 2026-11-01 with Leivät 999
**When** the client calls `GET /api/totals?unit=month&from=2026-10&to=2026-10`
**Then** `weeks` are `2026-W40` (2026-10-01–2026-10-04, partial), `2026-W41`, `2026-W42`,
`2026-W43` (not partial) and `2026-W44` (2026-10-26–2026-10-31, partial); `Leivät` has
`weeks` `[100, 300, 0, 0, 0]`; receipt D is in no column (`month_totals` `[725]`)

### AC3: Week period, month columns partial
**Given** receipts dated 2026-09-30 (Leivät 100) and 2026-10-01 (Leivät 200)
**When** the client calls `GET /api/totals?unit=week&from=2026-W40&to=2026-W40`
**Then** `start_date` is `2026-09-28`, `end_date` `2026-10-04`, `weeks` has one column
`2026-W40` (not partial) with `Leivät` `[300]`, and `months` are `2026-09`
(2026-09-28–2026-09-30, partial) with `[100]` and `2026-10` (2026-10-01–2026-10-04,
partial) with `[200]`

### AC4: ISO week across the year boundary
**Given** receipts dated 2025-12-30 (Leivät 100) and 2026-01-02 (Leivät 200)
**When** the client calls `GET /api/totals?unit=month&from=2026-01&to=2026-01`
**Then** the first week column is `2026-W01` with days 2026-01-01–2026-01-04, partial, and
`Leivät` `[200, ...]`; the receipt of 2025-12-30 is not counted

### AC5: Week 53
**Given** a receipt dated 2027-01-02 with Leivät 100
**When** the client calls `GET /api/totals?unit=week&from=2026-W53&to=2026-W53`
**Then** `start_date` is `2026-12-28`, `end_date` `2027-01-03`, `weeks` is `[2026-W53]`
with `[100]`, and `months` are `2026-12` (partial, `[0]`) and `2027-01` (partial, `[100]`)

### AC6: Deposit refunds are not counted
**Given** a receipt dated 2026-10-05 with Maitotuotteet 229 and a deposit refund of -40
**When** the client gets the totals for October 2026
**Then** `Maitotuotteet` has `months` `[229]`, `month_totals` is `[229]`, and no row holds
the -40

### AC7: Lines without a category
**Given** a receipt dated 2026-10-05 with Leivät 300 and a line without a category of 199
**When** the client gets the totals for October 2026
**Then** the last row has `kind` `none` with `months` `[199]`, and `month_totals` is `[499]`

### AC8: Purchase date, not import date
**Given** a receipt imported on 2026-11-02 with purchase date 2026-10-05 and Leivät 300
**When** the client gets the totals for October 2026 and for November 2026
**Then** October has `Leivät` `[300]`, and November has no rows

### AC9: Receipts without a date
**Given** a receipt without a purchase date with Leivät 300
**When** the client gets the totals for any period
**Then** it is in no total, and `undated_receipts` is 1 for every period

### AC10: Rows and their order
**Given** lines in October 2026 in Juomat and Leivät only, and the default catalog
order
**When** the client gets the totals for October 2026
**Then** the rows are `Ruoka` (with only `Leivät` under it) and `Juomat`, in category
list order; categories without lines in the period are not listed

### AC11: Totals follow edits (FR-24)
**Given** the totals for October 2026 show `Leivät` `[300]`
**When** the line is changed to 350 and moved to Maitotuotteet (line editing endpoints),
and the totals are requested again
**Then** `Leivät` is not listed and `Maitotuotteet` has `[350]`

### AC12: Invalid period
**Given** any data
**When** the client calls `/api/totals` with `unit=day`; with `from=2026-13`; with
`from=2026-11&to=2026-10`; with `unit=week&from=2027-W53&to=2027-W53`; with `from` missing;
with `unit=month&from=2024-10&to=2026-10` (25 months); or with
`unit=week&from=2025-W01&to=2026-W53` (105 weeks)
**Then** each answer is 422 with `error` `invalid_period` and `message`
`Jakso on virheellinen.` **And** `unit=month&from=2024-11&to=2026-10` (24 months) and
`unit=week&from=2025-W01&to=2026-W52` (104 weeks) answer 200

### AC13: Empty period
**Given** no receipts in March 2026
**When** the client gets the totals for March 2026
**Then** the answer is 200 with the week and month columns, `rows` `[]`, and all column
totals 0

### AC14: Yhteenveto page opens on the current month
**Given** the browser's date is 2026-11-02 and the backend has totals for November 2026
**When** the user opens `Yhteenveto` from the navigation
**Then** the address is `/yhteenveto?unit=month&from=2026-11&to=2026-11` (PC5), the chooser shows `Kuukausi`, `Alkaen` 11/2026,
`Päättyen` 11/2026, and the tables `Viikot` and `Kuukaudet` show the answer's columns and
rows, with amounts as `1234,56 €`

### AC15: Groups expand and collapse
**Given** the page shows the group `Ruoka`
**When** the user presses `Näytä kategoriat: Ruoka`
**Then** the rows `Maitotuotteet` and `Leivät` appear under `Ruoka` in both tables, and the
button becomes `Piilota kategoriat: Ruoka` with `aria-expanded="true"`; pressing it again
hides them

### AC16: Choosing a period
**Given** the page is open
**When** the user chooses `Viikko`, `Alkaen` week 40 of 2026 and `Päättyen` week 41 of 2026
**Then** the page requests `unit=week&from=2026-W40&to=2026-W41` and shows its answer

### AC17: Partial column heading
**Given** an answer with the week column `2026-W40` partial from 2026-10-01 to 2026-10-04
**When** the page shows it
**Then** its heading is `vk 40/2026 (osittainen) 1.10.–4.10.2026`

### AC18: Empty and error states on the page
**Given** an answer with `rows` `[]`
**When** the page shows it
**Then** it shows `Ei ostoksia valitulla jaksolla.` and no tables. **And** when the request
is refused with `invalid_period` or cannot reach the backend, the page shows the error
message with `role="alert"`

### AC19: Privacy
**Given** a receipt with a product name
**When** the totals are requested
**Then** the answer holds no product name and the backend log holds only method, path,
query of dates and status

### AC20: Unreviewed count
**Given** in October 2026 one confirmed and two unreviewed receipts, and one unreviewed
receipt in November 2026
**When** the client gets the totals for October 2026
**Then** `unreviewed_receipts` is 2, all three October receipts are in the totals, and the
page shows `Tarkistamattomia kuitteja jaksolla: 2`; with 0 the text is not shown

### AC21: Undated count on the page
**Given** an answer with `undated_receipts` 1
**When** the page shows it
**Then** it shows `Kuitteja ilman päivää (ei mukana): 1`; with 0 the text is not shown

### AC22: Period in the address
**Given** the user chose `Viikko` 40/2026 – 41/2026
**When** the user reloads the page, and then presses the browser's back button
**Then** after the reload the address is `/yhteenveto?unit=week&from=2026-W40&to=2026-W41`
and the same period is shown; back returns to the previous period. **And** opening
`/yhteenveto?unit=week&from=bad` shows the current month

### AC23: Month and week labels
**Given** an answer with the month columns `2026-12` and `2027-01` and the week column
`2027-W01`
**When** the page shows it
**Then** the headings are `12/2026`, `1/2027` and `vk 1/2027`

## Files to Modify

Refined by the Plan.

| File | Change |
|---|---|
| `backend/app/calculation/period.py` | New: `Period`, `Column`, `parse_period`, `PeriodError` (P1) |
| `backend/app/calculation/period_totals.py` | New: `TotalLine`, `period_totals`, rows with group totals (P2) |
| `backend/app/storage/receipt_repository.py` | `dated_lines`, `count_unreviewed`, `count_undated` (P3) |
| `backend/app/totals/` (`__init__.py`, `service.py`, `routes.py`, `schemas.py`, `errors.py`) | New package: `TotalsService`, `GET /api/totals`, `InvalidPeriodError` (P4) |
| `backend/app/texts.py` | `INVALID_PERIOD` |
| `backend/app/main.py` | Include the totals router |
| `backend/tests/unit/calculation/test_period.py`, `test_period_totals.py` | Unit tests |
| `backend/tests/unit/storage/` (receipt repository tests) | The three queries |
| `backend/tests/integration/test_totals_api.py` | Integration tests |
| `frontend/src/period.ts` (+ `period.test.ts`) | New: period from and to the address, current month, labels (P5) |
| `frontend/src/api/totals.ts` | `getTotals()` and the `Totals` types |
| `frontend/src/components/TotalsPage.tsx` (+ test) | New page (P6) |
| `frontend/src/components/TotalsTable.tsx` (+ test) | One table, used for weeks and months (P6) |
| `frontend/src/navigation.ts` (+ test), `frontend/src/App.tsx` (+ test) | Page `totals` at `/yhteenveto`, the link after Kuitit |
| `frontend/src/format.ts` (+ test) | `formatDayMonth()` for partial column days |
| `frontend/src/i18n/fi.ts` | Texts of the UI texts table |
| `frontend/src/test/totals.ts` | MSW fixtures |
| `frontend/e2e/import.spec.ts` | The E2E journey (it already imports the synthetic receipt) |
| `docs/subsystems/calculation/README.md` | Period and period totals |
| `docs/subsystems/totals/README.md` | New Tier 2 doc for the totals package |
| `docs/subsystems/storage/README.md` | The three queries |
| `docs/subsystems/ui/README.md` | The Yhteenveto page |
| `docs/api-reference.md` | `GET /api/totals`, `invalid_period` |
| `docs/architecture.md` | `totals` in the component map and the folder structure |
| `docs/glossary.md` | Period, column, partial column, group total, unreviewed and undated count |
| `docs/content-plan.md`, `specs/README.md` | Status, new Tier 2 row |

## Risk
- **What could break:** wrong ISO week or year at year boundaries (week 1 starting in
  December, week 53); off-by-one at partial column edges; totals that drift from receipt
  subtotals if the two rule sets differ (deposit refunds, no category). The change only
  reads data and adds one page.
- **Rollback:** revert the commit; no migration, no data change.
- **Dependencies:** none new expected; Python `datetime.date.fromisocalendar` and
  `isocalendar` for ISO weeks.

## Testing Strategy (MANDATORY)

### Unit tests
| AC | Function | Case | Given | When | Then | Mocks |
|---|---|---|---|---|---|---|
| AC1 | period totals | happy path | lines of AC1 | October 2026 | category, group and column totals of AC1 | none |
| AC2 | period columns | month with partial weeks | October 2026 | columns | W40 and W44 partial with the days of AC2 | none |
| AC2 | period totals | outside the period | line dated 2026-11-01 | October 2026 | not counted | none |
| AC3 | period columns | week period, partial months | W40 2026 | columns | 2026-09 and 2026-10 partial | none |
| AC4 | period columns | year boundary | January 2026 | columns | `2026-W01` 1.–4.1., partial | none |
| AC5 | period parsing | week 53 exists | `2026-W53` | parse | 2026-12-28–2027-01-03 | none |
| AC6 | period totals | deposit refund | line -40 refund | totals | not in any row or total | none |
| AC7 | period totals | no category | line without category | totals | `none` row, in column total | none |
| AC12 | period parsing | invalid | each value of AC12 | parse | `invalid_period` | none |
| AC12 | period parsing | at the limit | 24 months, 104 weeks | parse | accepted | none |
| AC13 | period totals | no lines | March 2026 | totals | columns, no rows, zero totals | none |

### Integration tests
Real SQLite (temporary file) and real FastAPI app.
| AC | Scenario | Request / input | Expected output | Status |
|---|---|---|---|---|
| AC1 | month totals | `GET /api/totals?unit=month&from=2026-10&to=2026-10` | AC1 body | 200 |
| AC2 | partial weeks | same, fixture of AC2 | AC2 values | 200 |
| AC3 | week period | `unit=week&from=2026-W40&to=2026-W40` | AC3 values | 200 |
| AC4 | year boundary | January 2026 | AC4 values | 200 |
| AC5 | week 53 | `2026-W53` | AC5 values | 200 |
| AC6 | deposit refund | October 2026 | AC6 values | 200 |
| AC7 | no category | October 2026 | AC7 values | 200 |
| AC8 | purchase date | October and November | AC8 values | 200 |
| AC9 | undated receipt | any period | `undated_receipts` 1 | 200 |
| AC10 | rows and order | October 2026 | AC10 rows | 200 |
| AC11 | after edits | `PATCH` line, then `GET` | AC11 values | 200 |
| AC12 | invalid period | each query of AC12 | `invalid_period` | 422 |
| AC12 | limits accepted | 24 months, 104 weeks | totals | 200 |
| AC20 | unreviewed count | October 2026 | `unreviewed_receipts` 2, all counted | 200 |
| AC13 | empty period | March 2026 | AC13 body | 200 |
| AC19 | privacy | October 2026, captured log | no product name in body or log | 200 |

### Frontend component tests (MSW)
| AC | Case | Expected |
|---|---|---|
| AC14 | open on 2026-11-02 (fake date) | request for `2026-11`, tables shown, amounts formatted |
| AC15 | expand and collapse | category rows appear and disappear, `aria-expanded` |
| AC16 | change unit and weeks | request with `unit=week&from=2026-W40&to=2026-W41` |
| AC17 | partial heading | `vk 40/2026 (osittainen) 1.10.–4.10.2026` |
| AC18 | empty, refused, network error | empty text; alert with the message |
| AC20, AC21 | counts 2 and 1, then 0 | status texts shown, then hidden |
| AC22 | address | period from the address; a change pushes history; back restores; a bad address opens the current month |
| AC23 | labels | `12/2026`, `1/2027`, `vk 1/2027` |

### E2E tests
| AC | Journey | Steps | Expected outcome |
|---|---|---|---|
| AC14, AC11 | import, edit, see totals | import the synthetic receipt, change a line's category on its page, open Yhteenveto for the receipt's month | the new category's total shows the line amount |

### Coverage target
- Backend: 90 % lines; the period parsing, columns and totals: every branch tested.
- Frontend: 80 % lines for the new page.

### Test data
- Synthetic fixtures only (no real receipts): test receipts and lines created through the
  test repository with invented names and amounts; the synthetic E2E receipt image.
- Mocks: MSW for the frontend; the browser date is faked in component tests.

## Related Documentation (MANDATORY)
- Tier 1: [PRD](../PRD.md) FR-22–FR-26, FR-44;
  [architecture](../../docs/architecture.md#component-map);
  [datamodel](../../docs/datamodel.md); [API reference](../../docs/api-reference.md);
  [glossary](../../docs/glossary.md)
- Tier 2: [calculation](../../docs/subsystems/calculation/README.md),
  [storage](../../docs/subsystems/storage/README.md),
  [ui](../../docs/subsystems/ui/README.md), [review](../../docs/subsystems/review/README.md)
- ADRs: [0001 tech stack](../../docs/adr/0001-tech-stack.md)

## Plan

### P0 Overview

```
GET /api/totals?unit&from&to
  → totals/routes.py      (query strings without FastAPI validation: every bad value is invalid_period)
  → TotalsService.totals  (one connection, one read transaction)
      parse_period                 calculation/period.py  → Period, or PeriodError → 422 invalid_period
      dated_lines(start, end), count_unreviewed(start, end), count_undated()   storage
      CategoryService catalog order (each group followed by its categories, then standalone)
      period_totals(period, lines, catalog)               calculation/period_totals.py
  → TotalsOut (schemas.py)
```

No migration and no new dependency. Calculation stays pure (no I/O); storage holds the SQL;
the new `totals` package wires them, as `review` does for one receipt. The CSV export spec
will call `TotalsService` too, so the totals are computed in one place.

### P1 Period (`calculation/period.py`)

- `parse_period(unit: str | None, first: str | None, last: str | None) -> Period` raises
  `PeriodError(ValueError)` for every PC3 case.
  - `month`: `^\d{4}-(0[1-9]|1[0-2])$`. `week`: `^\d{4}-W(0[1-9]|[1-4][0-9]|5[0-3])$`, then
    `date.fromisocalendar(year, week, 1)`, which raises for a week that does not exist
    (`2027-W53`). Years 1–9998: the columns of a period in 9999 would run past `date.max`.
  - Length: months `(y2*12 + m2) - (y1*12 + m1) + 1`; weeks
    `(monday(last) - monday(first)).days // 7 + 1`. `from` after `to`, or a length over 24
    months or 104 weeks, is an error.
- `Period(unit, first, last, start: date, end: date)`: `start` is the 1st of the first
  month or the Monday of the first week; `end` is the last day of the last month or the
  Sunday of the last week.
- `Period.week_columns()` and `Period.month_columns()` return `list[Column(key, start, end,
  partial)]`: they walk the ISO weeks (Monday steps from the Monday on or before `start`)
  and the months (from the month of `start`) up to `end`, and clip each to `[start, end]`.
  `partial` is true when a column was clipped. Keys are `2026-W40` (four-digit ISO year,
  two-digit week) and `2026-10`.

### P2 Period totals (`calculation/period_totals.py`)

- Input: `TotalLine(purchase_date: date, amount_cents, category_id | None,
  is_deposit_refund)` and the catalog as `RowCategory(id, name, kind, parent_id)` in
  catalog order.
- Deposit refunds and lines outside `[period.start, period.end]` are skipped. The
  repository already filters by date; the check keeps the function correct on its own.
- A line goes to its week column by `purchase_date.isocalendar()` and to its month column
  by `(year, month)`; sums are kept per category id and column in integer cents.
- Rows: walk the catalog in order. A group row is built when at least one of its
  categories has a line in the period; its amounts are the column-wise sums of those
  categories, which are its `categories`. A standalone category gets a row when it has a
  line. The `none` row comes last when a line without a category exists. A category whose
  lines sum to 0 is still listed.
- `week_totals` and `month_totals` sum the top-level rows (groups, standalone categories,
  `none`), so no group is counted twice.
- Output: `PeriodTotals(period, weeks, months, rows, week_totals, month_totals)` with
  `TotalsRow(kind, id, name, weeks: list[int], months: list[int], categories:
  list[TotalsRow])`.
- A category id missing from the catalog cannot happen (`ON DELETE RESTRICT`). As in
  `category_subtotals`, it does not raise: its amounts go to no row. A unit test pins that
  it does not crash.

### P3 Storage (`ReceiptRepository`)

- `dated_lines(start: str, end: str) -> list[DatedLineRow]`:
  `SELECT r.purchase_date, l.amount_cents, l.category_id, l.is_deposit_refund FROM
  receipt_lines l JOIN receipts r ON r.id = l.receipt_id WHERE r.purchase_date BETWEEN ?
  AND ?`. `YYYY-MM-DD` text sorts like dates, and the column `CHECK` guarantees the shape.
  No product names are selected (PC8).
- `count_unreviewed(start, end) -> int`: receipts with `reviewed = 0` and the date in the
  range.
- `count_undated() -> int`: receipts with `purchase_date IS NULL`.
- No index on `purchase_date`: one user's receipts are a few thousand rows a year, and a
  full scan stays fast. Add one by migration if that changes.

### P4 Totals package (`app/totals/`)

- `TotalsService(catalog: CatalogRepository, receipts: ReceiptRepository)` with
  `totals(unit, first, last) -> PeriodTotals` plus the two counts. It turns `PeriodError`
  into `InvalidPeriodError` (`AppError("invalid_period", texts.INVALID_PERIOD, 422)`).
- It reads the lines, the counts and the catalog in one read transaction, so they agree.
- `routes.py`: `create_totals_router(settings)`; `GET /api/totals` takes `unit: str | None`,
  `from` (`Query(None, alias="from")`) and `to: str | None`, so a missing value reaches
  `parse_period` and gives `invalid_period`, not the generic `invalid_request`.
- `schemas.py`: `TotalsOut`, `ColumnOut` and `TotalsRowOut` as in the API shape; dates as
  `YYYY-MM-DD` strings.
- The request log already leaves out the query string (@backend/app/logging_setup.py), so
  AC19 needs no change there; the integration test pins it.

### P5 Frontend period (`frontend/src/period.ts`)

- `type Period = {unit: "month" | "week"; from: string; to: string}`.
- `periodFromSearch(search)`: the same patterns as P1 (shape only); `null` for anything
  incomplete or malformed. The backend still decides validity (week 53, order, length).
- `periodToSearch(period)` → `?unit=week&from=2026-W40&to=2026-W41`.
- `currentMonth(today: Date)` → `{unit: "month", from: "2026-11", to: "2026-11"}` from the
  local date; `currentWeek(today)` likewise for the ISO week.
- `weekLabel("2026-W40")` → `vk 40/2026`; `monthLabel("2027-01")` → `1/2027`.
- `formatDayMonth("2026-10-01")` in `format.ts` → `1.10.`; a partial heading adds
  `(osittainen)` and `formatDayMonth(start) + "–" + formatDate(end)`. A partial column
  always lies within one month, so one year is enough.
- When the unit changes, `from` and `to` become the unit that contains today (current
  month or current ISO week), so the inputs never hold a value of the other unit.

### P6 Frontend page

- `navigation.ts`: `Page` gets `totals` and `PAGE_PATHS.totals = "/yhteenveto"`; `usePage`
  still tracks only the path. `App` adds the link `Yhteenveto` after Kuitit.
- `TotalsPage` owns the period. The first value is `periodFromSearch(location.search) ??
  currentMonth(new Date())`, written to the address with `history.replaceState`, so the
  address always shows the period. A change calls `history.pushState` with
  `/yhteenveto?...`; a `popstate` listener reads the period again (AC22).
- Inputs: a `select` `Jakso` (`Kuukausi`, `Viikko`) and two native inputs `Alkaen` and
  `Päättyen` of `type="month"` or `type="week"`, whose values are exactly the API format
  (`2026-10`, `2026-W40`). Chrome and Edge show pickers; Firefox shows a text field that
  accepts the same text. The E2E browser is Chromium. An emptied input sends no request.
- One request per period. An answer for an older period is ignored (a request counter in a
  ref), so fast changes cannot show stale totals.
- `TotalsTable({label, columns, rows, totals, expanded, onToggle})` is rendered twice
  (`Viikot`, `Kuukaudet`). The expanded groups are one `Set<number>` in the page, so a group
  opens in both tables at once (AC15). Category rows are indented under their group.
  Amounts use `formatCents`.
- The two counts are `role="status"` paragraphs above the tables, each only when not 0.
- Errors: `role="alert"` with the API client's message, as on the other pages.

### P7 AC check

| AC | Covered by |
|---|---|
| AC1, AC6, AC7, AC10, AC13 | P2 (unit), P4 (integration) |
| AC2–AC5 | P1 columns, P2 (unit), P4 (integration) |
| AC8, AC9, AC20 | P3 queries, P4 |
| AC11 | P4 computes on every request; integration test with the line editing endpoints |
| AC12 | P1 `parse_period`; P4 routes without FastAPI validation |
| AC14, AC16, AC22 | P5, P6 |
| AC15, AC17, AC18, AC21, AC23 | P6 `TotalsTable` and page states, P5 labels |
| AC19 | P3 selects no names; logging unchanged |

### P8 Decisions (no ADR needed)

- A new `totals` package instead of growing `review`: review is about one receipt; totals
  span receipts and will be shared with export.
- Native month and week inputs instead of custom selects: no new dependency and no year
  range to invent. The cost is a plain text field in Firefox.

## Tasks

Each task is one Red → Green → Refactor cycle (or a few small ones) and ends with the
tests, lint, format check and type check of the part it changed.

### Backend

- [x] **T1 Period parsing** (AC5, AC12). `parse_period` and `PeriodError` in
  `calculation/period.py`. Tests `tests/unit/calculation/test_period.py`: one month, a
  month range, one week, `2026-W53` → 2026-12-28–2027-01-03; every invalid value of AC12
  (unit, malformed month and week, `2027-W53`, missing value, `from` after `to`, 25 months,
  105 weeks); the limits 24 months and 104 weeks accepted.
- [x] **T2 Columns** (AC2, AC3, AC4, AC5). `Period.week_columns()` and `month_columns()`.
  Tests in `test_period.py`: October 2026 (W40 and W44 partial with their days), week 40
  of 2026 (2026-09 and 2026-10 partial), January 2026 (`2026-W01` partial 1.–4.1.), week 53
  of 2026 (2026-12 and 2027-01 partial), a whole-month and whole-week period with no
  partial column.
- [x] **T3 Period totals** (AC1, AC2, AC6, AC7, AC10, AC13). `period_totals` in
  `calculation/period_totals.py`. Tests `test_period_totals.py`: category, group and column
  totals of AC1; week amounts of AC2; a line outside the period skipped; deposit refund
  skipped; the `none` row last and in the column total; rows in catalog order, only
  categories with lines, a group listed with only its used categories; a category with lines
  summing to 0 listed; no lines → no rows and zero totals; an unknown category id does not
  crash.
- [x] **T4 Storage queries** (AC8, AC9, AC20). `dated_lines`, `count_unreviewed`,
  `count_undated` in `ReceiptRepository`. Tests in `tests/unit/storage/`: dates at both
  range edges included, outside excluded, undated receipts excluded; unreviewed count only
  inside the range; undated count over all receipts.
- [x] **T5 Totals service and endpoint** (AC1–AC13, AC20). `app/totals/` package,
  `texts.INVALID_PERIOD`, router in `main.py`. Tests
  `tests/integration/test_totals_api.py`: one test per integration row of the Testing
  Strategy, including AC11 through the line editing endpoints and every AC12 query.
- [x] **T6 Privacy** (AC19). Integration test: a receipt with a product name; the
  `/api/totals` body and the captured log contain no product name, and the log line has
  no query string.

### Frontend

- [x] **T7 Period helpers** (AC14, AC22, AC23, AC17). `period.ts` and `formatDayMonth`.
  Tests `period.test.ts`, `format.test.ts`: `periodFromSearch` (valid month and week,
  incomplete, malformed → null), `periodToSearch`, `currentMonth` and `currentWeek` (with
  dates at a year boundary), `weekLabel` (`vk 1/2027`), `monthLabel` (`12/2026`,
  `1/2027`), `formatDayMonth` (`1.10.`).
- [x] **T8 API client and fixtures**. `api/totals.ts`, `test/totals.ts`. Covered by the page
  tests of T10–T12; typecheck proves the types.
- [x] **T9 Navigation** (AC14). `totals` page at `/yhteenveto`, the link after Kuitit.
  Tests `navigation.test.ts` (`/yhteenveto` and `/yhteenveto?...` → totals) and
  `App.test.tsx` (the link opens the page, `aria-current`).
- [x] **T10 Totals table** (AC15, AC17, AC23). `TotalsTable.tsx`. Tests: headings with
  labels and the partial mark `vk 40/2026 (osittainen) 1.10.–4.10.2026`; group rows with
  totals, the `Yhteensä` row; expand and collapse with `aria-expanded`.
- [x] **T11 Totals page: load and show** (AC14, AC15, AC18, AC20, AC21). `TotalsPage.tsx`.
  Tests: on a faked date 2026-11-02 it requests November 2026 and shows both tables;
  expanding a group shows its categories in both tables; empty answer text; `invalid_period`
  and network error as alert; counts shown when not 0 and hidden at 0.
- [x] **T12 Totals page: period chooser and address** (AC16, AC22). Tests: choosing
  `Viikko` sets the current week; choosing weeks 40–41 requests
  `unit=week&from=2026-W40&to=2026-W41` and pushes the address; `popstate` restores the
  previous period; the address period is used on open; a bad address opens the current
  month; an older answer arriving last is ignored; an emptied input sends no request.
- [x] **T13 E2E** (AC14, AC11). In `e2e/import.spec.ts`: import the synthetic receipt,
  change a line's category on its page, open Yhteenveto with the receipt's month in the
  address, expand the group, see the line's amount under the new category.

### Docs and closing

- [x] **T14 Docs.** Create `docs/subsystems/totals/README.md`; update the calculation,
  storage and UI READMEs, `api-reference.md` (`GET /api/totals`, `invalid_period`),
  `architecture.md` (component map, folder structure), `glossary.md`, `content-plan.md`
  and `specs/README.md`.
- [x] **T15 Full check.** Every command in the AGENTS.md command table, including the E2E
  and container tests; coverage meets the targets. Then hand over to `review-audit`.

## Audit

Audited 2026-11-02 against this spec, with an independent review: **PASS**.

- Acceptance criteria 23/23 and PC1–PC8 met; every Testing Strategy row has a test.
- Tests: backend 973 passed, frontend 176 passed, E2E 9 passed (three runs, also on a kept
  database), container tests passed; ruff, pyright, ESLint and tsc clean. Coverage: the new
  backend code 100 % lines and branches (target 90 %); the new frontend files 100 % lines
  (target 80 %).
- Security: no findings. Parameterized SQL; no product names in the answer or the log, and
  no query string in the log (AC19). `pip-audit`: no known vulnerabilities. `npm audit`: one
  moderate finding in `minimatch` under the ESLint tooling (development only, not changed
  by this spec).
- Fixed during the audit (test first): the `Yhteenveto` link dropped the period from the
  address while the page was open; a period in year 9999 gave 500 instead of
  `invalid_period`; column keys now have four-digit years.
- Format check: files not touched by this spec fail `npm run format:check` because their
  working copies have CRLF line endings (`core.autocrlf=true`); the content in Git is fine.
- Later:
  - The E2E test adds a new line and gives it a category instead of changing an existing
    line's category: the E2E database is kept between runs, and changing a known product's
    category would also move earlier runs' lines (FR-36). The integration test covers AC11
    directly.
  - The CSV export spec reuses `TotalsService` and the period (FR-26).

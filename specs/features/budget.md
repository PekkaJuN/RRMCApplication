# Feature: Monthly budget

## Overview
- **Status:** Done
- **Created:** 2026-11-05
- **Depends on:** [Category totals](totals.md), [Product management](product-management.md),
  [Receipt review](receipt-review.md)
- **Updated:** 2026-11-06: user request and answers: the comparison can also use a fixed
  period from the 15th to the 14th of the next month, chosen on the Vertailu page and named
  after its starting month. Specify changes, the Plan and the Tasks approved by the user.
  User decisions after the audit: budget saves run one at a time; a well-formed month the
  backend refuses shows the error and is not replaced by the current period. Audited
  2026-11-06 in two cycles; the last fixes (the AC28 polling test and two docs) were
  checked by hand.
  2026-11-05: user answers: budgeting removed from the PRD non-goals and FR-50
  added; a week's budget follows its days in the month, so the weeks add up to the monthly
  budget (this replaces the first rule of a quarter of the month); a category moved into a
  group takes its budget to the group; the week table is shown only on request. Specify
  approved by the user.
- **Implements:** PRD FR-50 (Next release).
- **Affected subsystems:** [calculation](../../docs/subsystems/calculation/README.md),
  [storage](../../docs/subsystems/storage/README.md),
  [categorization](../../docs/subsystems/categorization/README.md),
  [ui](../../docs/subsystems/ui/README.md); the endpoints are in the new
  [budget](../../docs/subsystems/budget/README.md) package.

## Problem Statement
The app shows how much was spent, but not whether that was within what the user planned to
spend. This spec lets the user set one monthly budget for each group and standalone
category, and compare the budget with the spending of a month and its weeks. The month can
be a calendar month or a period from the 15th to the 14th of the next month.

## Current Behavior
- Categories have at most two levels: a group holds categories, and a category either
  belongs to a group or stands alone ([datamodel](../../docs/datamodel.md)).
- The Yhteenveto page shows spending per ISO week and month and counts every receipt,
  reviewed or not ([totals](../../docs/subsystems/totals/README.md)).
- There are no budgets.

## Proposed Change

### Concepts

- A **budget row** is a group or a standalone category. A category inside a group is not a
  budget row: its spending counts toward its group.
- A **monthly budget** is the amount of one budget row in integer cents. The user can type
  an amount from 0 to the receipt total limit (`AMOUNT_LIMIT`). A row without a saved amount
  has 0.
- The **total budget** is the sum of the monthly budgets of all budget rows. It is computed,
  never entered.
- The budget is **the same for every month**. It has no history: a change also changes the
  comparison of earlier months.
- A **comparison period** is one of two kinds, both named by a month `YYYY-MM`.
  A **calendar month** is that month. A **15–14 period** starts on the 15th of that month
  and ends on the 14th of the next, so `2026-10` is 15.10.2026–14.11.2026. The start day is
  fixed.
- The monthly budget applies in full to either kind, whatever the number of days.
- The **weekly budget** of a row is the monthly budget divided by the days of the period,
  times the week's days in that period. Example: 310,00 € in October 2026 gives 70,00 € for
  a full week, 40,00 € for week 40 (4 days) and 60,00 € for week 44 (6 days).
- Rounding keeps the sum exact. With monthly budget `M`, `D` days in the period, and a week
  covering the days `s`–`e` of the period, counted from its first day as 1, the weekly
  budget is `round(M × e / D) − round(M × (s − 1) / D)`, rounded to the nearest cent, half
  up. So a row's weekly budgets always add up to its monthly budget.
- The total of a week's budget is the sum of the rows' weekly budgets, so the column adds
  up.
- **Actual spending** follows the totals rules (purchase date, deposit refunds not counted,
  FR-23, FR-44) with one difference: **only reviewed receipts count**.
- **Remaining** is the budget minus the actual spending. It is negative when the row is
  over budget.

### Parts

- **PC1 Budget storage and rows.** Monthly budgets are stored per budget row. Rows follow
  the category list order. A new group or standalone category appears with 0.
- **PC2 Budget endpoints.** `GET /api/budget` returns the rows and the total budget.
  `PUT /api/budget/{id}` saves the amount of one budget row.
- **PC3 Budget page.** A new navigation link **Budjetti** (`/budjetti`). One amount field
  per budget row, in category list order, and the row `Yhteensä` with the total budget.
  A valid amount is saved when the field loses focus or Enter is pressed, and the total
  updates. Saves run one at a time, in the order the user made them, because each answer
  holds every row and an older answer must not replace a newer one.
- **PC4 Comparison calculation.** Pure calculation of the rows, the month figures and the
  week figures from the budget and the reviewed lines. Integer cents only (NFR-6).
- **PC5 Comparison endpoint.** `GET /api/budget/comparison?month=2026-10&period=mid`.
  `period` is `calendar` or `mid` (the 15–14 period); a missing `period` means `calendar`.
  A missing or malformed month or an unknown `period` gives `422 invalid_period`. Figures
  are computed on every request.
- **PC6 Vertailu page.** A new navigation link **Vertailu** (`/vertailu`), after Budjetti.
  A period select `Jakso` with `Kalenterikuukausi` and `15.–14.`, a month input, and the
  line `Jakso: 15.10.2026–14.11.2026` with the dates the figures cover. On opening, the
  period is the current calendar month. Choosing a kind selects the period of that kind
  that holds today: on 2026-11-06, `15.–14.` selects `2026-10`. The month input then
  chooses another period of the same kind. The choice is kept in the address as
  `/vertailu?month=2026-10` or `/vertailu?month=2026-10&period=mid`. An address with an
  unknown `period` opens the current calendar month; an address with `period=mid` and a
  month of a bad shape opens the current 15–14 period. A month of the right shape that the
  backend refuses, such as `9999-01`, stays in the address, and the page shows the error;
  the controls still work. The page shows the month table. The week table
  stays hidden until the user presses `Näytä viikot`, and `Piilota viikot` hides it again.
  Changing the month or the kind keeps it open or hidden as it was; after a reload it is
  hidden.
  - **Kuukausi:** columns `Kategoria`, `Budjetti`, `Toteutunut`, `Jäljellä`.
  - **Viikot:** the column `Kategoria`, then for each ISO week with at least one day in the
    period a heading over two columns, `Budjetti` and `Toteutunut`, for that week's days
    inside the period.

  Both have the row `Yhteensä`. A negative `Jäljellä` is shown with the text `Ylitetty` as
  well as the sign, so the meaning does not depend on color. In the week table, a
  `Toteutunut` value over the week's budget has the same text.
- **PC7 Lines without a category.** Lines of reviewed receipts without a category form the
  last row `Ei kategoriaa`, budget 0, so `Yhteensä` shows the full reviewed spending. The
  row is shown only when such lines exist.
- **PC8 Catalog changes.** A budget belongs to the group or standalone category by its id.
  - Deleting a group or category (allowed only when unused, FR-37) deletes its budget.
  - A renamed row keeps its budget.
  - A standalone category moved into a group stops being a budget row. Its monthly budget
    is added to the group's, in the same transaction, so the total budget does not change.
    The category's own budget is removed. The sum may exceed `AMOUNT_LIMIT`, which applies
    only to amounts the user types.
  - A category taken out of a group becomes a budget row with 0. The group's budget does
    not change.
- **PC9 Counts.** The Vertailu page shows the number of unreviewed receipts of the period
  that are left out, and the undated count, each only when it is not 0.
- **PC10 Partial weeks.** A partial week's budget and spending cover only its days in the
  period, and its heading has the mark `(osittainen)` and the days, as on Yhteenveto.
- **PC11 Money and dates in the UI.** As in the totals spec PC7. Amounts are typed as in
  the line editor (`parseCents`).
- **PC12 Privacy (NFR-1, NFR-3).** Answers hold category and group names and sums only, no
  product names. Logs carry method, path and status only.

### UI texts

| Place | Text |
|---|---|
| Navigation link and page heading | `Budjetti`, `Vertailu` |
| Budget page row label | the group or category name |
| Total row | `Yhteensä` |
| Period select label and options | `Jakso`: `Kalenterikuukausi`, `15.–14.` |
| Month input label | `Kuukausi` |
| Covered dates | `Jakso: 15.10.2026–14.11.2026` |
| Week table button (`aria-expanded`) | `Näytä viikot` / `Piilota viikot` |
| Table headings and `aria-label` | `Kuukausi`, `Viikot` |
| Month table columns | `Kategoria`, `Budjetti`, `Toteutunut`, `Jäljellä` |
| Week table columns | `Kategoria`; per week the heading `vk 40/2026` over `Budjetti`, `Toteutunut` |
| Over budget mark | `Ylitetty` |
| No-category row | `Ei kategoriaa` |
| Unreviewed count (`role="status"`) | `Tarkistamattomia kuitteja, ei mukana: <n>` |
| Undated count (`role="status"`) | `Kuitteja ilman päivää (ei mukana): <n>` |

### API shape

`GET /api/budget`:

```json
{
  "rows": [
    {"kind": "group", "id": 1, "name": "Ruoka", "amount_cents": 40000},
    {"kind": "category", "id": 30, "name": "Juomat", "amount_cents": 5000}
  ],
  "total_cents": 45000
}
```

`PUT /api/budget/1` with `{"amount_cents": 40000}` returns the same shape as `GET`.

`GET /api/budget/comparison?month=2026-10` (with `period=mid`, `period` is `mid`, the dates
are `2026-10-15` and `2026-11-14`, and `weeks` follow them):

```json
{
  "month": "2026-10",
  "period": "calendar",
  "start_date": "2026-10-01",
  "end_date": "2026-10-31",
  "weeks": [
    {"key": "2026-W40", "start_date": "2026-10-01", "end_date": "2026-10-04", "partial": true}
  ],
  "rows": [
    {"kind": "group", "id": 1, "name": "Ruoka", "budget_cents": 40000,
     "actual_cents": 12500, "remaining_cents": 27500,
     "weeks": [{"budget_cents": 5161, "actual_cents": 12500}]},
    {"kind": "none", "id": null, "name": null, "budget_cents": 0,
     "actual_cents": 199, "remaining_cents": -199,
     "weeks": [{"budget_cents": 0, "actual_cents": 199}]}
  ],
  "total": {"budget_cents": 40000, "actual_cents": 12699, "remaining_cents": 27301,
            "weeks": [{"budget_cents": 5161, "actual_cents": 12699}]},
  "unreviewed_receipts": 1,
  "undated_receipts": 0
}
```

### Error codes

| Status | `error` | `message` | When |
|---|---|---|---|
| 404 | `not_found` | `Pyydettyä kohdetta ei löydy.` | `PUT` with an unknown id |
| 422 | `not_a_budget_row` | `Budjetin voi asettaa vain ryhmälle tai ryhmättömälle kategorialle.` | `PUT` for a category inside a group |
| 422 | `invalid_amount` | `Summa ei kelpaa.` | `PUT` with a negative or too large amount |
| 422 | `invalid_period` | `Jakso on virheellinen.` | PC5 |

### Out of Scope
- A different budget per month, budget history, or carrying over unused budget.
- Budgets for categories inside a group.
- Expanding a group into its categories on the Vertailu page.
- Forecasting, charts and alerts.
- Budget figures in the CSV export or on the Yhteenveto page.
- Comparison over several months. The page shows one period.
- Another start day than the 15th, or a saved default period.
- The 15–14 period on the Yhteenveto page or in the CSV export. PRD FR-49 (free date range
  for totals) brings it there later.

## Acceptance Criteria

Fixture unless the AC says otherwise: the default catalog (PRD section 6.9), budgets
`Ruoka` 40000 and `Juomat` 5000, other rows 0. Amounts are in cents.

### AC1: Budget rows
**Given** the default catalog and no saved budgets
**When** the client calls `GET /api/budget`
**Then** the rows are the 2 groups and 8 standalone categories in category list order, each
with `amount_cents` 0, no category inside a group is listed, and `total_cents` is 0

### AC2: Saving a budget updates the total
**Given** the fixture
**When** the client calls `PUT /api/budget/<Auto>` with `{"amount_cents": 15000}`
**Then** the answer is 200, `Auto` has 15000, `total_cents` is 60000, and `GET /api/budget`
returns the same

### AC3: A category inside a group has no budget
**Given** the default catalog
**When** the client calls `PUT /api/budget/<Maitotuotteet>`
**Then** the answer is 422 with `error` `not_a_budget_row` and nothing is saved

### AC4: Invalid amounts and unknown ids
**Given** any data
**When** the client sends `amount_cents` -1, `AMOUNT_LIMIT` + 1, a float or a string, or an
unknown id
**Then** the amounts answer 422 and the unknown id 404, and nothing is saved. **And** 0 and
`AMOUNT_LIMIT` answer 200

### AC5: Weekly budgets follow the days and add up to the month
**Given** a monthly budget of 10000
**When** the weekly budgets of October 2026 (31 days, weeks of 4, 7, 7, 7 and 6 days) are
computed
**Then** they are `[1290, 2258, 2258, 2259, 1935]`, which add up to 10000. **And** a monthly
budget of 31000 gives `[4000, 7000, 7000, 7000, 6000]`

### AC6: A month of four whole weeks, and the weekly total
**Given** two rows with monthly budgets 10002 and 10002 in February 2027 (28 days, four
whole weeks)
**When** the comparison is computed
**Then** each row's weekly budgets are `[2501, 2500, 2501, 2500]`, the total's are
`[5002, 5000, 5002, 5000]`, and no week is partial

### AC7: Only reviewed receipts count
**Given** in October 2026 a reviewed receipt with Maitotuotteet 125 and an unreviewed
receipt with Maitotuotteet 300
**When** the client calls `GET /api/budget/comparison?month=2026-10`
**Then** `Ruoka` has `actual_cents` 125, `remaining_cents` 39875, and `unreviewed_receipts`
is 1

### AC8: Over budget
**Given** a reviewed receipt in October 2026 with Juomat 5100
**When** the client gets the comparison for October 2026
**Then** `Juomat` has `remaining_cents` -100, and the page shows `-1,00 €` with `Ylitetty`.
**And** when that receipt is dated 2026-10-02, the week `2026-W40` has budget 645 and actual
5100, and its `Toteutunut` value has `Ylitetty`; a value equal to the budget does not

### AC9: Same budget every month
**Given** the fixture
**When** the client gets the comparison for October 2026 and for March 2027
**Then** `Ruoka` has `budget_cents` 40000 in both. **And** after `Ruoka` is changed to
30000, both show 30000

### AC10: Weeks of a month
**Given** a reviewed receipt dated 2026-10-02 with Juomat 100 and one dated 2026-11-01 with
Juomat 999
**When** the client gets the comparison for October 2026
**Then** `weeks` are `2026-W40` (2026-10-01–2026-10-04, partial), `2026-W41`, `2026-W42`,
`2026-W43` and `2026-W44` (2026-10-26–2026-10-31, partial), and `Juomat` has the weekly
budgets `[645, 1129, 1129, 1129, 968]` and the actual amounts `[100, 0, 0, 0, 0]`

### AC11: ISO week across a year boundary
**Given** a reviewed receipt dated 2027-01-02 with Juomat 100
**When** the client gets the comparison for January 2027
**Then** the first week column is `2026-W53` with days 2027-01-01–2027-01-03, partial, with
actual 100 for `Juomat` and a budget for 3 of January's 31 days (484)

### AC12: Deposit refunds, undated receipts and purchase date
**Given** a reviewed receipt dated 2026-10-05, imported in November, with Maitotuotteet 229
and a deposit refund of -40, and a reviewed receipt without a purchase date with
Maitotuotteet 300
**When** the client gets the comparison for October 2026
**Then** `Ruoka` has `actual_cents` 229, and `undated_receipts` is 1

### AC13: Lines without a category
**Given** a reviewed receipt in October 2026 with Juomat 300 and a line without a category
of 199
**When** the client gets the comparison for October 2026
**Then** the last row has `kind` `none`, `budget_cents` 0, `actual_cents` 199 and
`remaining_cents` -199, and the total's `actual_cents` is 499. **And** without such lines
no `none` row exists

### AC14: Empty month
**Given** no reviewed receipts in March 2026
**When** the client gets the comparison for March 2026
**Then** the answer is 200, every budget row is listed with `actual_cents` 0, and the
total's `remaining_cents` is 45000

### AC15: Invalid month
**Given** any data
**When** the client calls the comparison with `month` missing, `2026-13` or `2026-W40`
**Then** each answer is 422 with `error` `invalid_period`

### AC16: Catalog changes
**Given** a standalone category `Testi` with a budget of 1000 and no products or lines
**When** it is deleted
**Then** it is not in `GET /api/budget`, `total_cents` drops by 1000, and a new category
named `Testi` has 0. **And** a renamed row keeps its budget

### AC23: A budgeted category moves into a group
**Given** the fixture
**When** `Juomat` (5000) is moved into the group `Ruoka` (40000)
**Then** `GET /api/budget` lists `Ruoka` with 45000 and no `Juomat` row, `total_cents` is
still 45000, and spending in `Juomat` counts toward the `Ruoka` row of the comparison

### AC24: A category leaves a group
**Given** the fixture
**When** `Maitotuotteet` is taken out of the group `Ruoka`
**Then** `GET /api/budget` lists `Maitotuotteet` with 0, `Ruoka` still has 40000, and
spending in `Maitotuotteet` counts toward its own row

### AC26: A 15–14 period holds its first and last day
**Given** reviewed receipts with Juomat dated 2026-10-14 (999), 2026-10-15 (100), 2026-11-14
(200) and 2026-11-15 (999)
**When** the client calls `GET /api/budget/comparison?month=2026-10&period=mid`
**Then** `period` is `mid`, `start_date` is `2026-10-15`, `end_date` is `2026-11-14`, and
`Juomat` has `budget_cents` 5000, `actual_cents` 300 and `remaining_cents` 4700

### AC27: Weeks of a 15–14 period
**Given** the receipts of AC26
**When** the client gets the same comparison
**Then** `weeks` are `2026-W42` (2026-10-15–2026-10-18, partial), `2026-W43`, `2026-W44`
(2026-10-26–2026-11-01, not partial), `2026-W45` and `2026-W46` (2026-11-09–2026-11-14,
partial), and `Juomat` has the weekly budgets `[645, 1129, 1129, 1129, 968]`, which add up
to 5000, and the actual amounts `[100, 0, 0, 0, 200]`

### AC28: 15–14 periods across a year and over February
**Given** a monthly budget of 10000 for one row and 10002 for another
**When** the comparison is computed for `2026-12` and for `2027-02` with `period=mid`
**Then** `2026-12` covers 2026-12-15–2027-01-14, with the weeks `2026-W51`, `2026-W52`,
`2026-W53`, `2027-W01` and `2027-W02`, and weekly budgets
`[1935, 2259, 2258, 2258, 1290]` for 10000. **And** `2027-02` covers 2027-02-15–2027-03-14
(28 days), with the four whole weeks `2027-W07`–`2027-W10`, none partial, and weekly budgets
`[2501, 2500, 2501, 2500]` for 10002

### AC29: Counts follow the period
**Given** an unreviewed receipt dated 2026-11-03
**When** the client gets the comparison for `2026-10` with `period=mid`, and without `period`
**Then** `unreviewed_receipts` is 1 with `period=mid` and 0 without it

### AC30: The period parameter
**Given** any data
**When** the client calls the comparison with `month=2026-10` and `period=bad`, or with
`period=mid` and no `month`
**Then** each answer is 422 with `error` `invalid_period`. **And** `month=2026-10` with
`period=calendar` and with no `period` both answer 200 with `period` `calendar`,
`start_date` `2026-10-01` and `end_date` `2026-10-31`

### AC31: Choosing the 15–14 period
**Given** the browser's date is 2026-11-06 and the Vertailu page is open
**When** the user chooses `15.–14.` in `Jakso`
**Then** the address is `/vertailu?month=2026-10&period=mid`, the page requests that period
and shows `Jakso: 15.10.2026–14.11.2026`. **And** on 2026-11-20 the same choice gives
`2026-11`, and on 2027-01-10 it gives `2026-12`. **And** changing the month keeps `15.–14.`,
a reload keeps both, choosing `Kalenterikuukausi` gives `/vertailu?month=2026-11`, and the
week table stays open or hidden as it was. **And** `/vertailu?month=bad&period=mid` opens
the current 15–14 period, and `/vertailu?month=2026-10&period=bad` opens the current
calendar month

### AC32: Budget saves run in order
**Given** the budget page, and a save of `Auto` whose answer has not arrived
**When** the user saves `Juomat`
**Then** the page sends the second request only after the first answer, and `Yhteensä`
shows both new amounts

### AC33: A month the backend refuses
**Given** the address `/vertailu?month=9999-01&period=mid`, which the backend answers with
`invalid_period`
**When** the page opens
**Then** the address stays as it is and the page shows `Jakso on virheellinen.` with
`role="alert"`. **And** choosing `Kalenterikuukausi` opens the current month and removes
the error

### AC17: Budget page
**Given** the fixture
**When** the user opens `Budjetti`, types `150` in the field of `Auto` and leaves the field
**Then** the page sends `amount_cents` 15000 and `Yhteensä` shows `600,00 €`

### AC18: Invalid input on the budget page
**Given** the budget page
**When** the user types `abc` or `-5`, or the save fails
**Then** the page shows an error with `role="alert"`, and the total does not change

### AC19: Vertailu page opens on the current month
**Given** the browser's date is 2026-11-05
**When** the user opens `Vertailu`
**Then** the address is `/vertailu?month=2026-11`, the table `Kuukausi` shows the answer, and
the table `Viikot` is not shown. **And** a reload keeps a chosen month, and
`/vertailu?month=bad` opens the current month

### AC25: Weeks on request
**Given** the Vertailu page shows the month table
**When** the user presses `Näytä viikot`
**Then** the table `Viikot` appears and the button becomes `Piilota viikot` with
`aria-expanded="true"`, and the page sends no new request. **And** changing the month keeps
the table open if it was open and hidden if it was hidden, pressing the button again hides
it, and after a reload it is hidden

### AC20: Counts on the page
**Given** an answer with `unreviewed_receipts` 2 and `undated_receipts` 1
**When** the page shows it
**Then** it shows `Tarkistamattomia kuitteja, ei mukana: 2` and
`Kuitteja ilman päivää (ei mukana): 1`; with 0 neither is shown

### AC21: Privacy
**Given** a reviewed receipt with a product name
**When** the comparison is requested
**Then** the answer and the backend log hold no product name

### AC22: Yhteenveto is unchanged
**Given** an unreviewed receipt in October 2026
**When** the client calls `GET /api/totals` for October 2026
**Then** the receipt is still counted, as in the totals spec

## Files to Modify

Refined by the Plan.

| File | Change |
|---|---|
| `specs/PRD.md` | Done in this spec's review: budgeting out of the non-goals, FR-50 in the Next release, the 15–14 period |
| `backend/app/categorization/service.py` | Moving a category moves its budget (PC8) |
| `docs/projectdescription.md` | Add the feature (the scope change is done) |
| `backend/app/storage/migrations/0007_budgets.sql` | New: the budgets table |
| `backend/app/storage/catalog_repository.py`, `receipt_repository.py` | Budget queries; `reviewed_only` for dated lines |
| `backend/app/calculation/period.py` | `comparison_period`, the 15–14 period |
| `backend/app/calculation/budget_comparison.py` | New: rows, weekly budget, comparison |
| `backend/app/calculation/money.py`, `backend/app/review/fields.py` | `AMOUNT_LIMIT` moves to calculation (P5) |
| `backend/app/budget/` | New package: service, routes, schemas, errors |
| `backend/app/texts.py`, `backend/app/main.py` | Error text; include the router |
| `backend/tests/` | Unit and integration tests |
| `frontend/src/api/client.ts`, `frontend/src/api/budget.ts` | `apiPut`; new API client and types |
| `frontend/src/comparison.ts` (+ tests) | New: the address and the current period |
| `frontend/src/components/BudgetPage.tsx`, `ComparisonPage.tsx`, `ComparisonTable.tsx` (+ tests) | New pages |
| `frontend/src/period.ts`, `frontend/src/components/TotalsTable.tsx` | `columnHeading` shared by both tables |
| `frontend/src/navigation.ts`, `frontend/src/App.tsx`, `frontend/src/i18n/fi.ts` | Pages, links and texts |
| `frontend/src/test/budget.ts` | MSW fixtures |
| `frontend/e2e/` | The E2E journey |
| `specs/features/receipt-management.md`, `backend/tests/unit/storage/test_receipts_schema.py` | AC15 no longer fixes the newest version, so migration 0007 does not break it (user decision 2026-11-06) |
| `docs/subsystems/budget/README.md` | New Tier 2 doc |
| `docs/subsystems/calculation/README.md`, `storage/README.md`, `categorization/README.md`, `totals/README.md`, `ui/README.md` | The new parts |
| `AGENTS.md`, `docs/README.md` | The new subsystem in their lists |
| `frontend/src/components/ImportPage.test.tsx`, `docs/learnings.md` | The new test files exposed a timing race in the AC28 polling test (user decision 2026-11-06) |
| `docs/api-reference.md`, `docs/datamodel.md`, `docs/architecture.md`, `docs/glossary.md` | Endpoints, table, component map, terms |
| `docs/content-plan.md`, `specs/README.md` | Status, new Tier 2 row |

## Risk
- **What could break:** the user may read Vertailu and Yhteenveto as disagreeing, because
  only Vertailu leaves out unreviewed receipts; the page's count explains the gap. The same
  month name means different dates in the two kinds of period, so the page shows the
  covered dates.
  Changing a budget changes earlier months. Moving a category changes the group's budget,
  so the move and the budget change must share one transaction. Rounding and ISO week
  edges are the likely bugs.
- **Rollback:** revert the commit. Migration 0007 only adds a table. The migration runner
  applies only files newer than the database (@backend/app/storage/migrate.py), so a
  reverted app starts on a database that is ahead and ignores the table.
- **Dependencies:** none new expected.

## Testing Strategy (MANDATORY)

### Unit tests
| AC | Function | Case | Given | When | Then | Mocks |
|---|---|---|---|---|---|---|
| AC5 | weekly budget | partial weeks, rounding | 10000 and 31000, October 2026 | compute | AC5 lists, each adds up to the month | none |
| AC6 | comparison | whole weeks, weekly total | two rows of 10002, February 2027 | compute | AC6 lists | none |
| AC8 | comparison | over budget | actual over budget | compute | remaining negative | none |
| AC10 | comparison | weeks | lines inside and outside the month | compute | AC10 week values | none |
| AC11 | comparison | year boundary | January 2027 | compute | first week `2026-W53` | none |
| AC12 | comparison | deposit refund | line -40 refund | compute | not counted | none |
| AC13 | comparison | no category | line without category | compute | `none` row last, in the total | none |
| AC14 | comparison | no lines | March 2026 | compute | all rows, actual 0 | none |
| AC7 | storage | reviewed only | reviewed and unreviewed lines | query | only reviewed lines | none |
| AC26 | period | 15–14 bounds | `2026-10`, `mid` | parse | 2026-10-15–2026-11-14 | none |
| AC27 | comparison | weeks of a 15–14 period | lines on the bounds, 5000 | compute | AC27 values | none |
| AC28 | period, comparison | year change, February | `2026-12` and `2027-02`, `mid` | compute | AC28 values | none |
| AC30 | period | bad kind | `bad`, no month | parse | `PeriodError` | none |

### Integration tests
Real SQLite (temporary file) and real FastAPI app.
| AC | Scenario | Request / input | Expected output | Status |
|---|---|---|---|---|
| AC1 | rows | `GET /api/budget` | 10 rows, total 0 | 200 |
| AC2 | save | `PUT /api/budget/<Auto>` | total 60000, persisted | 200 |
| AC3 | category in a group | `PUT /api/budget/<Maitotuotteet>` | `not_a_budget_row` | 422 |
| AC4 | invalid amounts | each value of AC4 | refused, nothing saved | 422 |
| AC4 | unknown id | `PUT /api/budget/99999` | `not_found` | 404 |
| AC4 | limits | 0, `AMOUNT_LIMIT` | saved | 200 |
| AC7 | reviewed only | comparison for October | AC7 values | 200 |
| AC9 | same every month | two months, then a change | AC9 values | 200 |
| AC10 | weeks | comparison for October | AC10 values | 200 |
| AC12 | rules | comparison for October | AC12 values | 200 |
| AC13 | no category | comparison for October | AC13 values | 200 |
| AC14 | empty month | comparison for March 2026 | AC14 values | 200 |
| AC15 | invalid month | each value of AC15 | `invalid_period` | 422 |
| AC26 | 15–14 bounds | comparison with `period=mid` | AC26 values | 200 |
| AC27 | 15–14 weeks | comparison with `period=mid` | AC27 values | 200 |
| AC29 | counts | with and without `period=mid` | AC29 values | 200 |
| AC30 | period parameter | each value of AC30 | `invalid_period`, or `calendar` | 422, 200 |
| AC16 | catalog changes | delete and rename | AC16 values | 200 |
| AC23 | move into a group | `PATCH /api/categories/<Juomat>` | budget added to `Ruoka`, total unchanged | 200 |
| AC24 | leave a group | `PATCH /api/categories/<Maitotuotteet>` | own row with 0, group unchanged | 200 |
| AC21 | privacy | comparison, captured log | no product name | 200 |
| AC22 | Yhteenveto unchanged | `GET /api/totals` | unreviewed receipt counted | 200 |

### Frontend component tests (MSW)
| AC | Case | Expected |
|---|---|---|
| AC17 | type and leave the field | request with cents, total updates |
| AC18 | `abc`, `-5`, failed save | alert, total unchanged |
| AC19 | fake date 2026-11-05; reload; bad address | month in the address, month table shown, week table not |
| AC25 | show and hide weeks; change the month while open and while hidden; reload | table and button follow, the state survives the month change, hidden after a reload, `aria-expanded`, no new request on opening |
| AC8 | negative remaining; week over and equal to its budget | `-1,00 €` and `Ylitetty`; the week text only when over |
| AC20 | counts 2 and 1, then 0 | texts shown, then hidden |
| AC32 | first answer held back, second field saved | one request until the answer, then both; the total shows both amounts |
| AC33 | backend refuses `9999-01` | alert, address unchanged; `Kalenterikuukausi` recovers |
| AC31 | fake dates 2026-11-06, 2026-11-20, 2027-01-10; change month and kind; reload; bad addresses | AC31 addresses, requests and dates; week table state kept |

### E2E tests
| AC | Journey | Steps | Expected outcome |
|---|---|---|---|
| AC17, AC19, AC7 | set a budget and compare | set a budget on Budjetti, type in a synthetic receipt dated 2026-03-10, open Vertailu for its month, confirm the receipt, open Vertailu again | the row shows the budget; the spending grows by the receipt only after it is confirmed |
| AC26, AC31 | compare a 15–14 period | choose `15.–14.` and `2026-02`, the period that holds a synthetic receipt dated 2026-03-10, then type in and confirm one | the spending grows by the receipt and the page shows the dates 15.2.2026–14.3.2026 |

### Coverage target
- Backend: 90 % lines; the weekly budget and the comparison: every branch tested.
- Frontend: 80 % lines for the new pages.

### Test data
- Synthetic fixtures only (no real receipts): invented names and amounts. The E2E receipts
  are typed in, because the import journeys empty the import folder, and they are dated in
  March, away from the receipts of the other specs.
- Mocks: MSW for the frontend; the browser date is faked in component tests.

## Related Documentation (MANDATORY)
- Tier 1: [PRD](../PRD.md) FR-11, FR-22–FR-25, FR-37, FR-44;
  [architecture](../../docs/architecture.md#component-map);
  [datamodel](../../docs/datamodel.md); [API reference](../../docs/api-reference.md);
  [glossary](../../docs/glossary.md)
- Tier 2: [budget](../../docs/subsystems/budget/README.md),
  [totals](../../docs/subsystems/totals/README.md),
  [calculation](../../docs/subsystems/calculation/README.md),
  [categorization](../../docs/subsystems/categorization/README.md),
  [storage](../../docs/subsystems/storage/README.md), [ui](../../docs/subsystems/ui/README.md)
- ADRs: [0001 tech stack](../../docs/adr/0001-tech-stack.md)

## Plan

### P0 Overview

```
PUT /api/budget/{id}, GET /api/budget
  → budget/routes.py → BudgetService → CategoryService.list(), CatalogRepository budget SQL

GET /api/budget/comparison?month&period
  → budget/routes.py       (plain optional strings: every bad value becomes invalid_period)
  → BudgetService.comparison (one connection, one transaction)
      comparison_period            calculation/period.py  → Period, or PeriodError → 422
      dated_lines(start, end, reviewed_only=True), count_unreviewed, count_undated  storage
      CategoryService catalog order, budgets                                        storage
      budget_comparison(period, lines, catalog, budgets)   calculation/budget_comparison.py
  → ComparisonOut (schemas.py)
```

One migration, no new dependency. The endpoints get their own `budget` package, because the
budget is not a catalog rule and the figures are not the totals. Calculation stays pure.

### P1 Data model (`storage/migrations/0007_budgets.sql`)

```sql
CREATE TABLE budgets (
  category_id  INTEGER PRIMARY KEY REFERENCES categories (id) ON DELETE CASCADE,
  amount_cents INTEGER NOT NULL CHECK (amount_cents >= 0)
);
```

- A row exists only for an amount the user saved or a moved budget; a missing row means 0.
- `ON DELETE CASCADE` gives PC8's delete rule (AC16). A new row with the same name has a new
  id, so it starts at 0.
- No upper `CHECK`: a moved budget may exceed `AMOUNT_LIMIT` (PC8).
- A group and a standalone category share `categories`, so one table and one id space serve
  both, and a rename changes nothing here.

### P2 Storage

- `CatalogRepository` holds the budget SQL, so `CategoryService` moves a budget in its own
  transaction: `budgets() -> dict[int, int]`, `set_budget(category_id, cents)` (upsert) and
  `move_budget(from_id, to_id)`. The move adds the old amount to the target by upsert and
  deletes the old row; with no old row it does nothing.
- `ReceiptRepository.dated_lines(start, end, *, reviewed_only=False)`: adds
  `AND receipts.reviewed = 1`. The default keeps the totals and the export unchanged (AC22).
- `count_unreviewed` and `count_undated` are reused as they are.

### P3 Comparison period (`calculation/period.py`)

- `comparison_period(month: str | None, kind: str | None) -> Period` raises `PeriodError`
  when `kind` is not `None`, `calendar` or `mid`, and for any month `parse_period` refuses.
- `calendar` and `None` return `parse_period("month", month, month)`.
- `mid` takes that period and returns `Period("month", month, month, start, end)`, with
  `start` the 15th of the month and `end` the 14th of the next month (a year change included).
- `Period.week_columns()` already clips to any `start` and `end`, so it needs no change.
  The docstring of the module is updated: a period may start mid-month.

### P4 Comparison (`calculation/budget_comparison.py`)

- `budget_rows(catalog, budgets) -> list[BudgetRow]`: groups and categories without a
  group, in catalog order, with their amount or 0. It serves both `GET /api/budget` and the
  comparison, so the two cannot disagree.
- `weekly_budget(amount_cents, period, weeks) -> list[int]`: for each column, the day
  numbers `s = (column.start - period.start).days + 1` and
  `e = (column.end - period.start).days + 1`, with `D` the period's days. The share is
  `share(k) = (2 * amount_cents * k + D) // (2 * D)`, half up in integers (amounts are
  never negative), and the week's budget is `share(e) - share(s - 1)`. Each row's figures
  therefore add up to its monthly budget (AC5, AC6, AC27, AC28).
- `budget_comparison(period, lines, catalog, budgets) -> Comparison` calls `period_totals`
  and reads each row's week sums from it, so deposit refunds, group membership and the
  no-category row follow one rule (FR-44, AC12, AC13, AC23, AC24). A budget row without
  lines gets zeros (AC14). The `none` row comes last, only when `period_totals` has it, with
  zero budgets. `total` sums the rows column by column (AC6).
- `Comparison(period, weeks, rows, total)`; a row is `ComparisonRow(kind, id, name,
  budget_cents, actual_cents, remaining_cents, weeks)`; a week is `(budget_cents,
  actual_cents)`.

### P5 Amount limit

Architecture forbids a dependency on `review`, so `budget` cannot import `AMOUNT_LIMIT` from
`review/fields.py`. The constant moves to `calculation/money.py`, and `review/fields.py`
imports it, so its behavior does not change. `budget/errors.py` defines its own
`InvalidBudgetAmountError` and `NotABudgetRowError` with texts from `texts.py`.

### P6 Catalog changes (`categorization/service.py`)

`CategoryService.update`, inside its transaction, after `_check_parent`:

```python
if item.parent_id is None and new_parent is not None:
    self._repository.move_budget(item.id, new_parent)
```

This covers a standalone category moved into a group (AC23) and a group that becomes a
category in a group. A move between two groups, or out of a group, finds no budget, and an
item leaving a group shows 0 (AC24). A rename touches nothing (AC16).

### P7 Budget package (`backend/app/budget/`)

- `service.py`: `BudgetService(catalog, receipts)` with `rows()`, `save(item_id, cents)` and
  `comparison(month, kind)`. `save` checks in order: unknown id `NotFoundError`, a category
  inside a group `NotABudgetRowError`, then the amount `InvalidBudgetAmountError`.
- `routes.py`: `create_budget_router(settings)`. `month` and `period` are plain optional
  strings, as in `totals/routes.py`. A `StrictInt` body refuses a float or a string with
  the generic 422 `invalid_request` (AC4).
- `schemas.py`: the API shape; `ColumnOut` comes from `totals/schemas.py`.
- `errors.py`: as in P5. `InvalidPeriodError` comes from `totals/errors.py` and
  `NotFoundError` from `categorization/errors.py`.
- `main.py` includes the router. New dependency rule: `budget` → `calculation`,
  `categorization`, `totals` (the two types above), `storage`.

### P8 Frontend

- `api/client.ts` gets `apiPut`; `api/budget.ts` holds the types, `getBudget`, `saveBudget`
  and `getComparison(month, kind)`.
- `comparison.ts` (new): `comparisonFromSearch`, `comparisonToSearch` and
  `currentComparison(today, kind)`. For `mid`, the month is the local month from the 15th on
  and the previous month before it, so 2026-11-06 gives `2026-10` and 2027-01-10 gives
  `2026-12`. `calendar` is left out of the address.
- `BudgetPage.tsx`: an `EditableField` per row with the class `amount`. Saves chain on one
  promise, so the next starts after the previous answer. Keeping only the latest answer would
  not be enough: the backend could handle the two requests the other way round, and the
  latest answer would then lack the other save. `parseCents` null
  shows the existing `Anna summa muodossa 1,25.`; `-5` goes to the backend, which refuses
  it. The answer of a save replaces the rows, so the total updates.
- `ComparisonPage.tsx`: follows `TotalsPage.tsx`, with the address, popstate, a draft for an
  emptied month input and only the latest request shown. Changing `Jakso` selects
  `currentComparison` of the new kind. `showWeeks` is plain state, so it survives the month
  and period changes and resets on a reload, and pressing the button sends no request.
- `ComparisonTable.tsx`: the month and week tables inside `.table-box`. The week table has
  two heading rows, with `colSpan={2}` and `scope="colgroup"` over `Budjetti` and
  `Toteutunut`.
- The heading of a partial column moves from `TotalsTable.tsx` to `columnHeading` in
  `period.ts`, so both tables use it. Its comment still holds: a partial column lies within
  one month.
- `navigation.ts`: pages `budget` (`/budjetti`) and `comparison` (`/vertailu`). `App.tsx`:
  the links after Yhteenveto, and Vertailu's own link keeps the address, as Yhteenveto's does.

### P9 Check against the ACs

| ACs | Covered by |
|---|---|
| AC1–AC4 | P1, P2, P4 `budget_rows`, P7 |
| AC5, AC6, AC10, AC11 | P4 `weekly_budget`, existing `week_columns` |
| AC7–AC9, AC12–AC15 | P2 `reviewed_only`, P4, P7 |
| AC16, AC23, AC24 | P1 cascade, P6 |
| AC17–AC20, AC25 | P8 |
| AC21 | No product name is selected; the request log has no query string |
| AC22 | P2 default `reviewed_only=False` |
| AC26–AC28, AC30 | P3, P4 |
| AC29 | `count_unreviewed` with the period's bounds |
| AC31–AC33 | P8 |

## Tasks

Each task is one Red → Green → Refactor cycle. Test names and commits carry the AC IDs.
Paths are under `backend/` or `frontend/` as the group says.

### Backend: storage and calculation

- [x] **T1 Budgets table** (AC16). `app/storage/migrations/0007_budgets.sql` (P1).
  Test: `tests/unit/storage/test_budgets_schema.py`: schema version 7, a negative amount is
  refused, deleting a category deletes its budget row.
- [x] **T2 Budget queries** (AC2, AC23). `budgets`, `set_budget` and `move_budget` in
  `CatalogRepository` (P2). Test: `tests/unit/storage/test_budget_queries.py`: upsert, a move
  adds to the target and removes the source, a move with no source row changes nothing, a
  sum above `AMOUNT_LIMIT` is stored.
- [x] **T3 Reviewed lines only** (AC7, AC22). `dated_lines(..., reviewed_only=False)` (P2).
  Test: the storage test of the Testing Strategy; the default still returns unreviewed lines.
- [x] **T4 Comparison period** (AC26, AC28, AC30). `comparison_period` in
  `calculation/period.py` (P3). Test: `tests/unit/calculation/test_period.py`: the bounds of
  `2026-10` and `2026-12` with `mid`, the calendar month with `None` and `calendar`,
  `PeriodError` for `bad`, an empty kind and a missing month, and `week_columns` of the
  three periods of AC27 and AC28.
- [x] **T5 Budget rows and weekly budget** (AC1, AC5, AC6, AC27, AC28). `budget_rows` and
  `weekly_budget` in `calculation/budget_comparison.py` (P4). Test:
  `tests/unit/calculation/test_budget_comparison.py`: rows in catalog order without
  categories inside a group, the AC lists of weekly budgets, and each list's sum equals the
  monthly budget.
- [x] **T6 Comparison** (AC6, AC8, AC10–AC14, AC23, AC24, AC27). `budget_comparison` (P4).
  Test: the same file: each unit row of the Testing Strategy, every branch covered.

### Backend: rules and endpoints

- [x] **T7 Amount limit moves** (no AC; P5). `calculation/money.py`; `review/fields.py`
  imports it. Refactor only: no new test, the existing review tests stay green unchanged.
- [x] **T8 A category's budget moves with it** (AC23, AC24). `CategoryService.update` (P6).
  Test: `tests/unit/categorization/`: a standalone category into a group, a group turned
  into a category in a group, a move between groups, leaving a group, and a refused update
  moves nothing. Integration: `tests/integration/test_budget_api.py` rows AC23 and AC24.
- [x] **T9 Budget endpoints** (AC1–AC4, AC16). `app/budget/` with `GET /api/budget` and
  `PUT /api/budget/{id}`, `errors.py`, `schemas.py`, the text in `texts.py` and the router in
  `main.py` (P7). Test: `tests/integration/test_budget_api.py`: the integration rows of
  those ACs, including a delete and a rename.
- [x] **T10 Comparison endpoint** (AC7, AC9, AC10, AC12–AC15, AC21, AC22, AC26, AC27,
  AC29, AC30). `BudgetService.comparison` and the route (P7). Test: the same file: the
  integration rows of those ACs, with the captured log for AC21.

### Frontend

- [x] **T11 API client** (AC2, AC30). `apiPut` in `api/client.ts`, `api/budget.ts` and the
  MSW fixtures in `src/test/budget.ts` (P8). Test: `client.test.ts` and `api/budget.test.ts`:
  the method and body of a save, and the query with and without `period=mid`.
- [x] **T12 Pages and links** (AC17, AC19). `navigation.ts`, `App.tsx` and the texts in
  `i18n/fi.ts`. Test: `navigation.test.ts` and `App.test.tsx`: the paths and links in order,
  and Vertailu's own link keeps the address.
- [x] **T13 Budget page** (AC17, AC18). `components/BudgetPage.tsx` (P8). Test:
  `BudgetPage.test.tsx`: the rows of the Testing Strategy.
- [x] **T14 Period in the address** (AC19, AC31). `src/comparison.ts` (P8). Test:
  `comparison.test.ts`: both address forms, bad months and kinds, and the current period on
  2026-11-06, 2026-11-14, 2026-11-15, 2026-11-20 and 2027-01-10.
- [x] **T15 Shared column heading** (no AC; P8). `columnHeading` in `period.ts`, used by
  `TotalsTable.tsx`. Refactor only: `TotalsTable.test.tsx` stays green unchanged.
- [x] **T16 Comparison tables** (AC8, AC13, PC10). `components/ComparisonTable.tsx` (P8).
  Test: `ComparisonTable.test.tsx`: `-1,00 €` with `Ylitetty`, a week over and equal to its
  budget, the `Ei kategoriaa` row, a partial week's heading, and the two heading rows.
- [x] **T17 Vertailu page** (AC19, AC20, AC25, AC31). `components/ComparisonPage.tsx` (P8).
  Test: `ComparisonPage.test.tsx`: the rows of the Testing Strategy with a fake date.
- [x] **T18 E2E journeys** (AC7, AC17, AC19, AC26, AC31). `e2e/budget.spec.ts`: both rows of
  the Testing Strategy. The receipts of other journeys share this database, so the test
  compares the page with what it set itself and does not assume an empty month.

### After the audit

- [x] **T21 Budget saves in order** (AC32). The save chain in `components/BudgetPage.tsx`
  (P8). Test: `BudgetPage.test.tsx`.
- [x] **T22 A month the backend refuses** (AC33). No code change; the behavior is fixed by
  the spec. Test: `ComparisonPage.test.tsx`.

### Docs and closing

- [x] **T19 Documentation.** New `docs/subsystems/budget/README.md`; update the calculation,
  storage, categorization and UI READMEs, `docs/api-reference.md`, `docs/datamodel.md`
  (table, schema version 7), `docs/architecture.md` (component map, dependency rule),
  `docs/glossary.md`, `docs/projectdescription.md`, `docs/content-plan.md` and
  `specs/README.md`.
- [x] **T20 Full check.** Backend: tests, ruff, pyright and pip-audit. Frontend: tests, lint,
  format check and type check. E2E and container tests. Confirm the coverage target, then
  hand over to `review-audit`.

# Feature: Monthly budget

## Overview
- **Status:** Review
- **Created:** 2026-11-05
- **Depends on:** [Category totals](totals.md), [Product management](product-management.md),
  [Receipt review](receipt-review.md)
- **Updated:** 2026-11-05: user answers: budgeting removed from the PRD non-goals and FR-50
  added; a week's budget follows its days in the month, so the weeks add up to the monthly
  budget (this replaces the first rule of a quarter of the month); a category moved into a
  group takes its budget to the group; the week table is shown only on request. Specify
  approved by the user; the Plan waits until the user asks for it.
- **Implements:** PRD FR-50 (Next release).
- **Affected subsystems:** [calculation](../../docs/subsystems/calculation/README.md),
  [storage](../../docs/subsystems/storage/README.md),
  [categorization](../../docs/subsystems/categorization/README.md),
  [ui](../../docs/subsystems/ui/README.md); the endpoints' package is decided in the Plan.

## Problem Statement
The app shows how much was spent, but not whether that was within what the user planned to
spend. This spec lets the user set one monthly budget for each group and standalone
category, and compare the budget with the spending of a month and its weeks.

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
- The **weekly budget** of a row is the monthly budget divided by the days of the month,
  times the week's days in that month. Example: 310,00 € in October 2026 gives 70,00 € for
  a full week, 40,00 € for week 40 (4 days) and 60,00 € for week 44 (6 days).
- Rounding keeps the sum exact. With monthly budget `M`, `D` days in the month, and a week
  covering the days `s`–`e` of the month, the weekly budget is
  `round(M × e / D) − round(M × (s − 1) / D)`, rounded to the nearest cent, half up. So a
  row's weekly budgets always add up to its monthly budget.
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
  updates.
- **PC4 Comparison calculation.** Pure calculation of the rows, the month figures and the
  week figures from the budget and the reviewed lines. Integer cents only (NFR-6).
- **PC5 Comparison endpoint.** `GET /api/budget/comparison?month=2026-10`. A missing or
  malformed month gives `422 invalid_period`. Figures are computed on every request.
- **PC6 Vertailu page.** A new navigation link **Vertailu** (`/vertailu`), after Budjetti.
  A month input. On opening, the month is the current calendar month; the chosen month is
  kept in the address as `/vertailu?month=2026-10`. The page shows the month table. The
  week table stays hidden until the user presses `Näytä viikot`, and `Piilota viikot` hides
  it again. Changing the month keeps it open or hidden as it was; after a reload it is
  hidden.
  - **Kuukausi:** columns `Kategoria`, `Budjetti`, `Toteutunut`, `Jäljellä`.
  - **Viikot:** the column `Kategoria`, then for each ISO week with at least one day in the
    month a heading over two columns, `Budjetti` and `Toteutunut`, for that week's days
    inside the month.

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
- **PC9 Counts.** The Vertailu page shows the number of unreviewed receipts of the month
  that are left out, and the undated count, each only when it is not 0.
- **PC10 Partial weeks.** A partial week's budget and spending cover only its days in the
  month, and its heading has the mark `(osittainen)` and the days, as on Yhteenveto.
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
| Month input label | `Kuukausi` |
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

`GET /api/budget/comparison?month=2026-10`:

```json
{
  "month": "2026-10",
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
- Comparison over several months. The page shows one month.

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
| `specs/PRD.md` | Done in this spec's review: budgeting out of the non-goals, FR-50 in the Next release |
| `backend/app/categorization/service.py` | Moving a category moves its budget (PC8) |
| `docs/projectdescription.md` | Add the feature (the scope change is done) |
| `backend/app/storage/migrations/0007_budgets.sql` | New: the budgets table |
| `backend/app/storage/` | Budget queries; reviewed-only dated lines |
| `backend/app/calculation/` | New: comparison and weekly budget |
| `backend/app/budget/` | New package: service, routes, schemas, errors |
| `backend/app/texts.py`, `backend/app/main.py` | Error text; include the router |
| `backend/tests/` | Unit and integration tests |
| `frontend/src/api/budget.ts` | New: API client and types |
| `frontend/src/components/BudgetPage.tsx`, `ComparisonPage.tsx` (+ tests) | New pages |
| `frontend/src/navigation.ts`, `frontend/src/App.tsx`, `frontend/src/i18n/fi.ts` | Pages, links and texts |
| `frontend/src/test/budget.ts` | MSW fixtures |
| `frontend/e2e/` | The E2E journey |
| `docs/subsystems/budget/README.md` | New Tier 2 doc |
| `docs/subsystems/calculation/README.md`, `storage/README.md`, `ui/README.md` | The new parts |
| `docs/api-reference.md`, `docs/datamodel.md`, `docs/architecture.md`, `docs/glossary.md` | Endpoints, table, component map, terms |
| `docs/content-plan.md`, `specs/README.md` | Status, new Tier 2 row |

## Risk
- **What could break:** the user may read Vertailu and Yhteenveto as disagreeing, because
  only Vertailu leaves out unreviewed receipts; the page's count explains the gap.
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

### E2E tests
| AC | Journey | Steps | Expected outcome |
|---|---|---|---|
| AC17, AC19, AC7 | set a budget and compare | set a budget on Budjetti, import and confirm the synthetic receipt, open Vertailu for its month | the row shows the budget, the actual spending and the remaining amount |

### Coverage target
- Backend: 90 % lines; the weekly budget and the comparison: every branch tested.
- Frontend: 80 % lines for the new pages.

### Test data
- Synthetic fixtures only (no real receipts): invented names and amounts; the synthetic E2E
  receipt image.
- Mocks: MSW for the frontend; the browser date is faked in component tests.

## Related Documentation (MANDATORY)
- Tier 1: [PRD](../PRD.md) FR-11, FR-22–FR-25, FR-37, FR-44;
  [architecture](../../docs/architecture.md#component-map);
  [datamodel](../../docs/datamodel.md); [API reference](../../docs/api-reference.md);
  [glossary](../../docs/glossary.md)
- Tier 2: [totals](../../docs/subsystems/totals/README.md),
  [calculation](../../docs/subsystems/calculation/README.md),
  [categorization](../../docs/subsystems/categorization/README.md),
  [storage](../../docs/subsystems/storage/README.md), [ui](../../docs/subsystems/ui/README.md)
- ADRs: [0001 tech stack](../../docs/adr/0001-tech-stack.md)

<!-- The Plan phase appends "## Plan" and the Tasks phase appends "## Tasks" below. -->

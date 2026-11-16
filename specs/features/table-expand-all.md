# Feature: Expand and collapse a whole level of the year table

## Overview
- **Status:** Done (Specify, Plan and Tasks approved 2026-11-16; the user approved
  correcting the AC3 total from `1 500,00 €` to `15,00 €`, the example data's 1500 cents).
  Implementation notes (2026-11-16), for the audit: `levelKeys` counts every category as
  having products, since rows without lines are left out of the totals (archiving PC11);
  a check for an empty category could never be false and was removed, which gives 100 %
  branch coverage of `ArchiveTotalsTable`. No CSS change was needed (P3). The archive README
  does not describe the toggles and is unchanged. The AC1 page tests were seen failing with
  the buttons removed; the AC9 tests check absence and cannot fail that way. The E2E line
  goes to `Leivät` of the seeded group `Ruoka`, so the table has a group. G7 record: no
  existing test changed; tests were only added to `YearPage.test.tsx`,
  `ArchiveYearPage.test.tsx` and `year.spec.ts`. Audited 2026-11-16: AC1–AC10 covered,
  all checks green. After the merge (2026-11-16, approved by the user): the E2E receipt
  moved from 16.03. to 16.06., because a confirmed receipt in March races the budget
  journey's March total (see the unreviewed receipts note spec's G7 record); no
  expectation changed; all 47 E2E tests pass.
- **Created:** 2026-11-16
- **Updated:** 2026-11-16: user decisions: two level buttons (one for categories, one for
  products), the table opens as now (groups open, categories closed), and both pages that
  show the year table get the buttons (`Vuosi tuotteineen` and the archived year page).
  Decided by the agent for review: see [Agent decisions for review](#agent-decisions-for-review).
- **Affected subsystems:** [ui](../../docs/subsystems/ui/README.md),
  [archive](../../docs/subsystems/archive/README.md)

## Problem Statement
The year table of the `Vuosi tuotteineen` page and of the archived year page opens with
the groups open. To see every product, the user opens each category one by one; to see
only the top level, the user closes each group one by one. With many categories this takes
many clicks.

## Current Behavior
- The year table shows groups, categories and products by month. Each group and each
  category with rows below it has its own toggle button. On opening, groups show their
  categories and categories hide their products
  ([year with products PC6](year-products.md#proposed-change),
  [archiving PC15](archiving.md#proposed-change),
  [ui](../../docs/subsystems/ui/README.md)).
- There is no way to open or close all rows of one level at once.

## Proposed Change
- **PC1 Level buttons.** Above the year table there are two buttons:
  - the **categories button** `Näytä kategoriat` / `Piilota kategoriat`;
  - the **products button** `Näytä tuotteet` / `Piilota tuotteet`.

  Each is a button with `aria-expanded` and `aria-controls` pointing at the table. Its
  visible text tells what a click does.
- **PC2 Categories button.**
  - It reads `Piilota kategoriat` (`aria-expanded="true"`) when every group is open, else
    `Näytä kategoriat` (`aria-expanded="false"`).
  - `Näytä kategoriat` opens every group. Category toggles are not changed.
  - `Piilota kategoriat` closes every group and every category, so only the top-level rows
    show: the groups, the categories without a group, `Ei kategoriaa` and `Yhteensä`.
- **PC3 Products button.**
  - It reads `Piilota tuotteet` (`aria-expanded="true"`) when every group and every
    category with products is open, else `Näytä tuotteet` (`aria-expanded="false"`).
  - `Näytä tuotteet` opens every group and every category, so every row shows.
  - `Piilota tuotteet` closes every category. Group toggles are not changed.
- **PC4 Together with the row toggles.** The row toggles work as before. The level buttons
  follow the state of the rows: after the user opens or closes rows one by one, the
  buttons show the state of PC2 and PC3.
- **PC5 Only when there is something to open.** The categories button is shown only when
  the table has at least one group; the products button only when at least one category
  has products. With no table (an empty year, a failed request) neither is shown.
- **PC6 Both pages.** The buttons are part of the year table, so they appear on
  `Vuosi tuotteineen` (`/vuosi`) and on the archived year page (`/arkisto/<year>`).

### Agent decisions for review
1. `Piilota kategoriat` also closes the categories (PC2), so one click gives the shortest
   view and `Näytä kategoriat` then returns to the opening view. Closing only the groups
   would leave products of the top-level categories (`Kahvi`, `Ei kategoriaa`) showing.
2. The button texts are `Näytä kategoriat`, `Piilota kategoriat`, `Näytä tuotteet` and
   `Piilota tuotteet`: the words of the row toggles without a name.
3. The buttons stand in one row above the table box, not inside the table, so they do not
   scroll sideways with the table.
4. The open state is not remembered: reloading the page opens the table as before.

### Out of Scope
- Changing the opening state of the table.
- Remembering the open rows across page loads.
- The Yhteenveto table and its `Näytä kategoriat: <ryhmä>` toggles.
- The CSV files and the totals (no backend change).

## Acceptance Criteria

The examples use the year totals of [year with products AC1](year-products.md#ac1-current-year-totals)
(rows `Kahvi` → `Kahvi 500g`; group `Maitotuotteet` → `Juusto` → `Edam` and `Maito` →
`Maito 1l`; `Ei kategoriaa` → `TUNTEMATON`). The archived year page uses the same rows for
2025 ([archiving AC26](archiving.md#ac26-archived-year-totals)). "Rows shown" lists the name cells of `tbody` in order.

### AC1: Buttons on opening
**Given** the table of the example data just opened, on `/vuosi` and on `/arkisto/2025`
**When** the user looks above the table
**Then** two buttons are shown in this order: `Piilota kategoriat` with
`aria-expanded="true"` and `Näytä tuotteet` with `aria-expanded="false"`; both have
`aria-controls` equal to the table's `id`. Rows shown: `Kahvi`, `Maitotuotteet`, `Juusto`,
`Maito`, `Ei kategoriaa`

### AC2: Show all products
**Given** the table of AC1
**When** the user clicks `Näytä tuotteet`
**Then** rows shown: `Kahvi`, `Kahvi 500g`, `Maitotuotteet`, `Juusto`, `Edam`, `Maito`,
`Maito 1l`, `Ei kategoriaa`, `TUNTEMATON`; the buttons read `Piilota kategoriat` and
`Piilota tuotteet`, both `aria-expanded="true"`; every row toggle has `aria-expanded="true"`

### AC3: Hide all categories
**Given** the table of AC2
**When** the user clicks `Piilota kategoriat`
**Then** rows shown: `Kahvi`, `Maitotuotteet`, `Ei kategoriaa`; `Yhteensä` still shows
15,00 € in `Vuosi`; the buttons read `Näytä kategoriat` and `Näytä tuotteet`, both
`aria-expanded="false"`

### AC4: Show the categories again
**Given** the table of AC3
**When** the user clicks `Näytä kategoriat`
**Then** rows shown: `Kahvi`, `Maitotuotteet`, `Juusto`, `Maito`, `Ei kategoriaa` (the
opening view of AC1); the buttons read `Piilota kategoriat` and `Näytä tuotteet`

### AC5: Hide all products
**Given** the table of AC2
**When** the user clicks `Piilota tuotteet`
**Then** rows shown are those of AC4; the buttons read `Piilota kategoriat` and
`Näytä tuotteet`

### AC6: Buttons follow the row toggles
**Given** the table of AC1
**When** the user opens `Kahvi`, `Juusto`, `Maito` and `Ei kategoriaa` with their row
toggles, then closes `Maitotuotteet` with its row toggle
**Then** after the fourth click the products button reads `Piilota tuotteet`; after closing
`Maitotuotteet` the buttons read `Näytä kategoriat` and `Näytä tuotteet`, and rows shown are
`Kahvi`, `Kahvi 500g`, `Maitotuotteet`, `Ei kategoriaa`, `TUNTEMATON`

### AC7: Show categories keeps open categories
**Given** the table of AC2, after the user closes `Maitotuotteet` with its row toggle
**When** the user clicks `Näytä kategoriat`
**Then** rows shown are those of AC2 (the categories of `Maitotuotteet` were still open)

### AC8: No groups
**Given** year totals with only the rows `Kahvi` → `Kahvi 500g` and `Ei kategoriaa` →
`TUNTEMATON`
**When** the table opens
**Then** only the products button is shown, reading `Näytä tuotteet`; clicking it shows
`Kahvi 500g` and `TUNTEMATON`

### AC9: No table, no buttons
**Given** an empty current year ([year with products AC14](year-products.md#ac14-empty-year-on-the-page)),
or a failed request (AC16 there)
**When** the user opens `/vuosi`
**Then** no `Näytä kategoriat`, `Piilota kategoriat`, `Näytä tuotteet` or `Piilota tuotteet`
button is shown

### AC10: Accessibility
**Given** `/vuosi` with one typed-in reviewed receipt of this year
**When** axe runs on the page as opened, after `Näytä tuotteet` and after
`Piilota kategoriat`, and the user moves to the buttons with Tab
**Then** axe finds no WCAG 2.1 AA violation, and both buttons are reached with Tab before
the first row toggle

## Files to Modify
| File | Change |
|---|---|
| `frontend/src/components/ArchiveTotalsTable.tsx` | the level buttons and their state (PC1–PC5) |
| `frontend/src/components/ArchiveTotalsTable.test.tsx` | new: AC1–AC8 |
| `frontend/src/components/YearPage.test.tsx` | AC1 on `/vuosi`, AC9 |
| `frontend/src/components/ArchiveYearPage.test.tsx` | AC1 on the archived year page |
| `frontend/src/i18n/fi.ts` | the four button texts |
| `frontend/e2e/year.spec.ts` | AC2, AC3, AC10 |
| `docs/subsystems/ui/README.md` | the level buttons of the year table |
| `docs/subsystems/archive/README.md` | not changed: it does not describe the table's toggles; the ui README does |
| `specs/README.md` | row 23 |

## Risk
- **What could break:** the row toggles of the year table (the same state is changed by
  more buttons); tests that look for buttons by a name prefix, since `Näytä tuotteet` is the
  start of `Näytä tuotteet: <kategoria>` (Playwright matches names by substring unless
  `exact` is set).
- **Rollback:** revert the commit; frontend only, no data or API change.
- **Dependencies:** none.

## Testing Strategy (MANDATORY)

### Unit tests
| AC | Function | Case | Given | When | Then | Mocks |
|---|---|---|---|---|---|---|
| AC1 | `ArchiveTotalsTable` | opening | example totals | render | two buttons, texts, `aria-expanded`, `aria-controls`; rows of AC1 | none |
| AC2 | `ArchiveTotalsTable` | show products | AC1 | click `Näytä tuotteet` | rows and buttons of AC2 | none |
| AC3 | `ArchiveTotalsTable` | hide categories | AC2 | click `Piilota kategoriat` | rows, total and buttons of AC3 | none |
| AC4 | `ArchiveTotalsTable` | show categories | AC3 | click `Näytä kategoriat` | rows and buttons of AC4 | none |
| AC5 | `ArchiveTotalsTable` | hide products | AC2 | click `Piilota tuotteet` | rows and buttons of AC5 | none |
| AC6 | `ArchiveTotalsTable` | row toggles | AC1 | row clicks | buttons and rows of AC6 | none |
| AC7 | `ArchiveTotalsTable` | keep open categories | AC2, group closed | click `Näytä kategoriat` | rows of AC2 | none |
| AC8 | `ArchiveTotalsTable` | no groups | totals without a group | render, click | only the products button; products shown | none |
| AC1 | `YearPage` | on `/vuosi` | example totals | render | both buttons above the table | API |
| AC9 | `YearPage` | empty, error | empty year / API error | render | no level button | API |
| AC1 | `ArchiveYearPage` | on the archived year page | archive totals | render | both buttons above the table | API |

### Integration tests
None apply: no backend change. The table's data comes from the endpoints already tested by
the year with products and archiving specs.

### E2E tests
| AC | Journey | Steps | Expected outcome |
|---|---|---|---|
| AC2, AC3 | open and close all | on `/vuosi` click `Näytä tuotteet`, then `Piilota kategoriat` | the typed-in product shows, then hides |
| AC10 | accessibility | axe on `/vuosi` as opened, after each click; Tab to the buttons | no WCAG 2.1 AA violation; buttons before the row toggles |

### Coverage target
- Frontend: every branch of the level-button state in `ArchiveTotalsTable`.
- Backend: not changed.

### Test data
- Synthetic fixtures only: the year totals of `frontend/src/test/year.ts` and
  `frontend/src/test/archive.ts`; in E2E one typed-in receipt as in `year.spec.ts`.
- Mocks: the API through MSW in unit tests.

## Related Documentation (MANDATORY)
- Tier 1: [docs/architecture.md](../../docs/architecture.md)
- Tier 2: [ui](../../docs/subsystems/ui/README.md),
  [archive](../../docs/subsystems/archive/README.md)
- Specs: [year with products](year-products.md), [archiving](archiving.md)
- ADRs: none

## Plan

### P1 Components
Only `ArchiveTotalsTable` changes; `YearPage` and `ArchiveYearPage` get the buttons through
it (PC6) and do not change.

- The open rows stay one set of row keys (`expanded`), as now. The row toggles keep their
  code.
- A helper `levelKeys(rows)` walks the tree once and returns two key lists:
  - `groups`: the keys of the group rows (top level, kind `group`);
  - `categories`: the keys of every row with products, at the top level (kind `category`
    and `none`) or inside a group.
- Derived each render, not stored (PC4):
  - `categoriesOpen` = every key of `groups` is in `expanded`;
  - `productsOpen` = every key of `groups` and of `categories` is in `expanded`.
- Clicks (PC2, PC3):
  - `Näytä kategoriat`: add `groups`;
  - `Piilota kategoriat`: empty set (every group and category closed);
  - `Näytä tuotteet`: add `groups` and `categories`;
  - `Piilota tuotteet`: remove `categories`.
- Markup: the component returns a `<p>` with the buttons, then the table box as now. Each
  button is `<button type="button" className="button" aria-expanded aria-controls>`; the
  table gets `id` from `useId()`. The categories button is rendered only when `groups` is
  not empty, the products button only when `categories` is not empty (PC5). The buttons
  come before the table in the DOM, so Tab reaches them first (AC10).

### P2 Data flow
No change: the pages load the totals and hand them to the table as before. No API, backend
or storage change.

### P3 Texts and styles
- `fi.archive` gets `showAllCategories: "Näytä kategoriat"`,
  `hideAllCategories: "Piilota kategoriat"`, `showAllProducts: "Näytä tuotteet"` and
  `hideAllProducts: "Piilota tuotteet"`.
- No CSS change: `button` and `.button` already share one style, and the existing rule
  `.button + .button` spaces the two buttons. `styles.css` leaves Files to Modify.

### P4 Data model and dependencies
None.

### P5 Existing tests
- `YearPage.test.tsx` AC12 and `ArchiveYearPage.test.tsx` check that every button on the
  page has `aria-expanded`; the new buttons have it, so these pass unchanged.
- Row-toggle tests look buttons up by their full names (`Näytä tuotteet: Maito`); Testing
  Library matches names exactly, so they are not affected.
- E2E `archive.spec.ts` `openAll` looks for closed buttons inside the table only; the level
  buttons are outside it. `year.spec.ts` uses full row-toggle names, which the level button
  names do not contain. New E2E steps use `exact: true` (Risk).
- New tests are added to the existing `YearPage.test.tsx`, `ArchiveYearPage.test.tsx` and
  `year.spec.ts` files; no existing expectation changes.

### P6 Documentation
- `docs/subsystems/ui/README.md`: the `ArchiveTotalsTable` line and the archived year page
  paragraph get the level buttons and their texts.
- `docs/subsystems/archive/README.md`: only if it describes the table's toggles; it links
  to the ui README for the page, so likely no change.
- `specs/README.md`: row 23 status.

### P7 Check against the ACs
| AC | Covered by |
|---|---|
| AC1 | P1 markup, `aria-controls`, derived state on opening |
| AC2–AC5 | P1 clicks |
| AC6, AC7 | P1 derived state; `Näytä kategoriat` adds groups only |
| AC8, AC9 | P1 rendering only with keys; no table means no component |
| AC10 | P1 DOM order; native buttons; axe in E2E |

## Tasks

- [x] **T1 Level buttons in the table (AC1–AC8).** Red: new
  `frontend/src/components/ArchiveTotalsTable.test.tsx` with one test per AC1–AC8 (the
  example totals of `src/test/year.ts`; AC8 with a tree without groups). Green: the four
  texts in `fi.archive`, `levelKeys`, the derived state, the clicks and the markup of P1 in
  `ArchiveTotalsTable.tsx`. Refactor with all frontend tests green.
- [x] **T2 The buttons on both pages (AC1, AC9).** Tests in `YearPage.test.tsx` (both
  buttons above the table on `/vuosi`; none for an empty year and for a failed request) and
  in `ArchiveYearPage.test.tsx` (both buttons above the archived year's table). These pass
  on T1's code; check that each fails when the buttons are removed.
- [x] **T3 E2E (AC2, AC3, AC10).** A test in `frontend/e2e/year.spec.ts`: on `/vuosi` the
  typed-in product shows after `Näytä tuotteet` and hides after `Piilota kategoriat`
  (`exact: true`); Tab reaches both buttons before the first row toggle; axe as opened and
  after each click. Run the whole E2E suite.
- [x] **T4 Documentation.** `docs/subsystems/ui/README.md` (the `ArchiveTotalsTable` line
  and the archived year page paragraph); `docs/subsystems/archive/README.md` only if it
  describes the toggles; `specs/README.md` row 23.
- [x] **T5 Checks and audit.** Frontend tests, lint, format check, type check and E2E;
  `review-audit` against AC1–AC10; status `Done`.

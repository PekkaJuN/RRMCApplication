# Feature: Note on old and undated unreviewed receipts

## Overview
- **Status:** Done (Specify, Plan and Tasks approved 2026-11-16). Implementation notes
  (2026-11-16), for the audit: the E2E receipts are dated two years back, not last year
  (T4 said "previous year"): the archiving journey archives last year, and an unreviewed
  receipt there would block it; two years back is that journey's blocked year. AC9 is
  met, since the note names that earlier year. The fixtures also hold
  `FUTURE_UNREVIEWED` and `attentionReceipts` for AC4 and the subsets. G7 record, edits
  after a red run, none changing an expectation: `e2e/receipts.spec.ts` (this spec's own
  new test; its RegExp lost its backslashes in a template literal, now `String.raw`);
  `src/components/ReceiptsPage.test.tsx` (the type check refused `cells[1]` as possibly
  `undefined`, now `cells[1] ?? ""`); `e2e/year.spec.ts` of the year with products spec,
  approved by the user: its receipt moved from 15.03. to 15.06., because a confirmed
  receipt in March raced the budget journey's March total (+125 cents) whenever the two
  files ran at once. Audited 2026-11-16: AC1–AC9 covered, all checks green; the changed
  code is fully covered (the only uncovered line of `ReceiptsPage.tsx` is the existing
  cancel branch).
- **Created:** 2026-11-16
- **Updated:** 2026-11-16: user decisions: the note on the Kuitit page names the two kinds
  separately, with the years of the old receipts; a filter button shows only these
  receipts in the list. Decided by the agent for review: see
  [Agent decisions for review](#agent-decisions-for-review).
- **Affected subsystems:** [ui](../../docs/subsystems/ui/README.md)

## Problem Statement
An unreviewed receipt is left out of the year totals (FR-54) and blocks archiving its year
(archiving AC7). A receipt without a purchase date belongs to no week, month or year, so it
is in no totals at all. Such receipts are easy to forget: the Kuitit page lists them among
all the others, and nothing says that they need attention.

## Current Behavior
- The Kuitit page lists every receipt with its date (or `–`), store, total, warning and
  state `Tarkistamaton` or `Vahvistettu` (FR-21,
  [ui](../../docs/subsystems/ui/README.md)). The list comes from `GET /api/receipts`,
  undated receipts first, then by date, newest first.
- The Vuosi tuotteineen page counts only the unreviewed receipts of the current year
  ([year with products PC4](year-products.md#proposed-change)); the Arkisto page shows the
  unreviewed count of each year that can be archived ([archiving](archiving.md)).
- Nothing points out unreviewed receipts without a date or from earlier years.

## Proposed Change
New requirement **FR-55** in the PRD: *The Kuitit page tells how many unreviewed receipts
have no purchase date, and how many are dated in earlier years and in which years, and
lets the user show only these receipts in the list.*

- **PC1 Which receipts.** A receipt *needs attention* when it is unreviewed and either has
  no purchase date or is dated before 1 January of the current year. The current year is
  the year of today in Finnish time (`Europe/Helsinki`), as on the Vuosi tuotteineen page.
  Reviewed receipts, and unreviewed receipts dated in the current year or later, do not
  need attention.
- **PC2 The note.** When at least one receipt needs attention, the Kuitit page shows a
  note above the list, with `role="status"` (the existing notice style). It has a sentence
  for each kind that is not 0:
  - `Tarkistamattomia kuitteja ilman päivämäärää: 2.`
  - `Tarkistamattomia kuitteja edellisiltä vuosilta: 3 (2024, 2025).` The years are those
    of the receipts, each once, in ascending order.

  With no receipt that needs attention there is no note.
- **PC3 Filter button.** The note has a button `Näytä vain nämä kuitit` with
  `aria-pressed`. Pressing it shows only the receipts that need attention, in the list's
  own order; pressing it again shows every receipt. The button is a toggle: its text stays,
  `aria-pressed` tells the state.
- **PC4 No backend change.** The page computes the note and the filter from the list it
  already loads (`purchase_date` and `reviewed`). The state is not remembered: opening the
  page shows every receipt.

### Agent decisions for review
1. The note uses `role="status"`, so it gets the notice style that the app already uses
   for notes that need attention. It is not an error, so not `role="alert"`.
2. The filter button stands in the note, after the sentences, so it is clear which
   receipts it shows.
3. The button text stays `Näytä vain nämä kuitit`; `aria-pressed="true"` or `"false"` tells
   whether the filter is on. A screen reader reads it as a toggle button.
4. Dates later than the current year are not counted (they are not "earlier years");
   finding wrong future dates is out of scope.
5. The note is computed in the browser with the year in `Europe/Helsinki`, so on New
   Year's night it agrees with the Vuosi tuotteineen page whatever the computer's time zone.

### Out of Scope
- Other filters (by store, state or date) and sorting changes.
- Notes on other pages; the Arkisto and Vuosi tuotteineen notes stay as they are.
- Remembering the filter across page loads or in the address.
- Receipts dated in the future.
- Any backend or API change.

## Acceptance Criteria

The examples use a clock at 2026-06-15 12:00 Finnish time unless an AC says otherwise.
The **example list** is, in the order `GET /api/receipts` gives it:

| id | purchase_date | reviewed |
|---|---|---|
| 1 | none | false |
| 2 | none | true |
| 3 | 2026-03-01 | false |
| 4 | 2025-12-31 | false |
| 5 | 2025-05-01 | false |
| 6 | 2024-02-10 | false |
| 7 | 2024-01-05 | true |

### AC1: Note with both kinds
**Given** the example list
**When** the user opens the Kuitit page
**Then** a note with `role="status"` above the list reads
`Tarkistamattomia kuitteja ilman päivämäärää: 1. Tarkistamattomia kuitteja edellisiltä
vuosilta: 3 (2024, 2025).` and has the button `Näytä vain nämä kuitit` with
`aria-pressed="false"`; the list shows all seven receipts

### AC2: Only undated receipts
**Given** the receipts 1, 2 and 3 of the example list
**When** the user opens the Kuitit page
**Then** the note reads `Tarkistamattomia kuitteja ilman päivämäärää: 1.` only

### AC3: Only receipts of earlier years
**Given** the receipts 3, 4, 5 and 6 of the example list
**When** the user opens the Kuitit page
**Then** the note reads `Tarkistamattomia kuitteja edellisiltä vuosilta: 3 (2024, 2025).`
only

### AC4: No note
**Given** the receipts 2, 3 and 7 of the example list, and a receipt dated 2027-01-10,
unreviewed
**When** the user opens the Kuitit page
**Then** there is no note and no `Näytä vain nämä kuitit` button

### AC5: Filter on
**Given** the page of AC1
**When** the user presses `Näytä vain nämä kuitit`
**Then** the list shows the receipts 1, 4, 5 and 6, in this order; the button has
`aria-pressed="true"`; the note still reads as in AC1

### AC6: Filter off
**Given** the page of AC5
**When** the user presses `Näytä vain nämä kuitit` again
**Then** the list shows all seven receipts in the order of the example list, and the
button has `aria-pressed="false"`

### AC7: Finnish New Year
**Given** a clock at 2025-12-31 22:30 UTC (2026-01-01 00:30 in Finland) and the receipts 3
and 4 of the example list
**When** the user opens the Kuitit page
**Then** the note reads `Tarkistamattomia kuitteja edellisiltä vuosilta: 1 (2025).`

### AC8: Failed list
**Given** `GET /api/receipts` answers with an error
**When** the user opens the Kuitit page
**Then** the page shows the backend's message with `role="alert"` as before, and no note

### AC9: Accessibility
**Given** the Kuitit page with an unreviewed receipt dated in an earlier year
**When** axe runs on the page, before and after the filter button is pressed
**Then** axe finds no WCAG 2.1 AA violation, and the button can be pressed with the
keyboard (Enter and Space)

## Files to Modify
| File | Change |
|---|---|
| `frontend/src/components/ReceiptsPage.tsx` | the note and the filter (PC1–PC4) |
| `frontend/src/receiptsAttention.ts` | new: which receipts need attention, and the current year in Finnish time (PC1) |
| `frontend/src/receiptsAttention.test.ts` | new: AC1–AC4, AC7 at the function level |
| `frontend/src/components/ReceiptsPage.test.tsx` | AC1–AC6, AC8 |
| `frontend/src/test/receipts.ts` | the example list `ATTENTION_LIST` |
| `frontend/src/i18n/fi.ts` | the note sentences and the button text |
| `frontend/src/styles.css` | the notice style for the note `div` |
| `frontend/e2e/receipts.spec.ts` | AC5, AC6, AC9 |
| `docs/subsystems/ui/README.md` | the note and the filter of the Kuitit page |
| `docs/content-plan.md` | the spec's line in the gap list |
| `frontend/e2e/year.spec.ts` | the receipt date moved to June (G7 record above) |
| `specs/PRD.md` | FR-55 |
| `specs/README.md` | row 24 |

## Risk
- **What could break:** the receipt list (it now renders a filtered copy); a wrong year at
  New Year if the browser's time zone were used (AC7 guards it); existing E2E and unit
  tests that read the Kuitit page's first paragraph or count its buttons.
- **Rollback:** revert the commit; frontend only, no data or API change.
- **Dependencies:** `Intl.DateTimeFormat` with the `Europe/Helsinki` time zone (in every
  supported browser and in Node).

## Testing Strategy (MANDATORY)

### Unit tests
| AC | Function | Case | Given | When | Then | Mocks |
|---|---|---|---|---|---|---|
| AC1 | attention function | both kinds | example list, year 2026 | compute | undated 1; earlier 3; years 2024, 2025 | none |
| AC2 | attention function | undated only | receipts 1–3 | compute | undated 1; earlier 0 | none |
| AC3 | attention function | earlier only | receipts 3–6 | compute | undated 0; earlier 3; years 2024, 2025 | none |
| AC4 | attention function | none | receipts 2, 3, 7 and a 2027 receipt | compute | 0 and 0 | none |
| AC7 | current year | Finnish New Year | 2025-12-31T22:30Z | year | 2026 | none |
| AC1 | `ReceiptsPage` | note | example list | render | note text, `role="status"`, button `aria-pressed="false"`, seven rows | API, clock |
| AC2–AC4 | `ReceiptsPage` | one kind / none | lists of AC2–AC4 | render | note text / no note and no button | API, clock |
| AC5, AC6 | `ReceiptsPage` | filter | example list | press, press again | rows 1, 4, 5, 6; then all seven; `aria-pressed` | API, clock |
| AC7 | `ReceiptsPage` | New Year | list of AC7, clock of AC7 | render | note of AC7 | API, clock |
| AC8 | `ReceiptsPage` | error | API error | render | alert, no note | API |

### Integration tests
None apply: no backend change. `GET /api/receipts` and its fields are tested by the
existing receipt review tests.

### E2E tests
| AC | Journey | Steps | Expected outcome |
|---|---|---|---|
| AC5, AC6, AC9 | filter old receipts | type in an unreviewed receipt dated in the previous year; open Kuitit; press the button with the keyboard; press again | the note names the previous year; only receipts that need attention show, among them the typed-in one, and a reviewed receipt does not; then all show; axe finds no violation |

### Coverage target
- Frontend: every branch of the attention function and of the note and filter in
  `ReceiptsPage`.
- Backend: not changed.

### Test data
- Synthetic fixtures only: the example list above; in E2E one typed-in receipt with a
  store name unique to the run.
- Mocks: the API through MSW; the clock with Vitest fake timers (`Date` only).

## Related Documentation (MANDATORY)
- Tier 1: [docs/architecture.md](../../docs/architecture.md),
  [docs/glossary.md](../../docs/glossary.md)
- Tier 2: [ui](../../docs/subsystems/ui/README.md)
- Specs: [year with products](year-products.md), [archiving](archiving.md),
  [receipt review](receipt-review.md)
- PRD: [FR-21](../PRD.md), FR-55 (new)
- ADRs: none

## Plan

### P1 Components
- **New module `frontend/src/receiptsAttention.ts`**, pure functions:
  - `finnishYear(now: Date): number`: the year of `now` in `Europe/Helsinki`, read with
    `Intl.DateTimeFormat("fi-FI", { timeZone: "Europe/Helsinki", year: "numeric" })`
    (PC1, AC7).
  - `needsAttention(receipt, year): boolean`: unreviewed, and `purchase_date` is `null` or
    its year (the first four characters of the ISO date) is below `year` (PC1).
  - `attention(receipts, year): { undated: number; earlier: number; years: number[] }`:
    the counts and the sorted distinct years of the earlier receipts (PC2).
- **`ReceiptsPage`**:
  - new state `onlyAttention` (boolean, starts `false`, PC4);
  - after the list loads, `attention(receipts, finnishYear(new Date()))`;
  - when `undated + earlier > 0`, a `<div role="status">` above the new receipt button
    holds a `<p>` with the sentences (PC2) and a `<button type="button" aria-pressed>`
    (PC3). The note is a `div` because it holds a paragraph and a button; the existing
    notice style is on `main p[role="status"]`, so P3 adds the same rule for the `div`;
  - the table renders `receipts.filter(needsAttention)` when `onlyAttention` is on,
    else `receipts`; the order is the list's own (AC5).
- No change to `api/receipts.ts`, the backend or routing.

### P2 Data flow
`GET /api/receipts` (unchanged) → `ReceiptsPage` state → `attention` for the note and
`needsAttention` for the filter. Today is read on render with `new Date()`; tests fix it
with Vitest fake timers (`toFake: ["Date"]`), as `TotalsPage.test.tsx` does.

### P3 Texts and styles
- `fi.receipts` gets:
  - `undatedUnreviewed: (count) => "Tarkistamattomia kuitteja ilman päivämäärää: N."`;
  - `earlierUnreviewed: (count, years) => "Tarkistamattomia kuitteja edellisiltä vuosilta:
    N (2024, 2025)."`;
  - `onlyAttention: "Näytä vain nämä kuitit"`.
- `styles.css`: the notice rule `main p[role="status"]` also covers
  `main div[role="status"]`, and the paragraph inside it gets no box of its own.

### P4 Data model and dependencies
None. `Intl.DateTimeFormat` with a time zone is built into browsers and Node.

### P5 Existing tests
- `ReceiptsPage.test.tsx`: the existing tests use `SUMMARY_A` and `SUMMARY_B`, dated
  2026-10-05 and 2026-10-06; one is unreviewed. Without a fixed clock they show no note
  only while the year is 2026, but they do not look for a note, so they pass either way.
  The new tests fix the clock.
- E2E: other specs leave receipts in the E2E database, some unreviewed and from earlier
  years, so the note can show on the Kuitit page in any E2E test. No existing E2E test
  reads the Kuitit page's paragraphs by position; `style.spec.ts` runs axe on every page,
  which then also checks the note.
- The new E2E test finds its own receipt by a store name unique to the run, and checks
  only that the previous year is named, not the counts.
- Test helpers: the example list goes into `frontend/src/test/receipts.ts` as
  `ATTENTION_LIST`.

### P6 Documentation
- `docs/subsystems/ui/README.md`: the Kuitit paragraph gets the note and the filter; the
  module list gets `receiptsAttention.ts`.
- `docs/glossary.md`: no new term; "needs attention" stays a spec word, the UI says
  `Tarkistamaton`.
- `specs/PRD.md`: FR-55 after FR-54, and the Later release row.
- `specs/README.md`: row 24 status.

### P7 Check against the ACs
| AC | Covered by |
|---|---|
| AC1–AC4 | `attention`, the note in `ReceiptsPage` |
| AC5, AC6 | `onlyAttention` and `needsAttention` |
| AC7 | `finnishYear` with `Europe/Helsinki` |
| AC8 | the note is computed only from a loaded list |
| AC9 | native button with `aria-pressed`; notice style contrast; axe in E2E |

## Tasks

- [x] **T1 Which receipts need attention (AC1–AC4, AC7).** Red: new
  `frontend/src/receiptsAttention.test.ts` with the unit rows of `attention` and
  `finnishYear`, and `ATTENTION_LIST` in `frontend/src/test/receipts.ts`. Green:
  `frontend/src/receiptsAttention.ts`. Refactor with all frontend tests green.
- [x] **T2 The note (AC1–AC4, AC7, AC8).** Red: tests in `ReceiptsPage.test.tsx` with a
  fixed clock: the note texts, `role="status"`, no note for AC4 and AC8. Green: the texts
  in `fi.receipts`, the note in `ReceiptsPage.tsx`, the notice style for
  `main div[role="status"]` in `styles.css`.
- [x] **T3 The filter (AC5, AC6).** Red: tests in `ReceiptsPage.test.tsx`: press, press
  again; rows and `aria-pressed`. Green: `onlyAttention` and the filtered rows.
- [x] **T4 E2E (AC5, AC6, AC9).** A test in `frontend/e2e/receipts.spec.ts`: type in an
  unreviewed receipt dated in the previous year; the note names that year; press the
  button with the keyboard; the receipt shows and a reviewed one does not; press again;
  axe before and after. Run the whole E2E suite.
- [x] **T5 Documentation.** `docs/subsystems/ui/README.md`, `specs/PRD.md` (FR-55 and the
  Later release row), `specs/README.md` row 24, and `docs/content-plan.md` if its gap list
  or review date needs it.
- [x] **T6 Checks and audit.** Frontend tests, lint, format check, type check, E2E and
  `npm audit`; `review-audit` against AC1–AC9; status `Done`.

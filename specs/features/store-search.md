# Feature: Store search

## Overview
- **Status:** Done (Specify and Plan approved 2026-11-22, Tasks approved and audited 2026-11-23)
- **Created:** 2026-11-22
- **Affected subsystems:** [review](../../docs/subsystems/review/README.md),
  [ui](../../docs/subsystems/ui/README.md), [storage](../../docs/subsystems/storage/README.md)
- **Implements:** FR-58 (new)
- **Changes:** [receipt search](receipt-search.md) PC1 (the field's label), AC9 and AC14
  (the field is found by its new label)

## Problem Statement

The Kuitit page can search receipts by product name, but not by store. To find the receipts
of one store, the user scrolls the whole list.

## Current Behavior

- `GET /api/receipts` takes `name` (product name search) and `uncategorized`
  ([API reference](../../docs/api-reference.md#receipts),
  [review](../../docs/subsystems/review/README.md#receipt-search)).
- The Kuitit page has the field `Hae tuotteella`, the `Hae` button and the checkbox
  `Vain kuitit, joilla on rivejä ilman kategoriaa`; a search runs on `Hae` or Enter
  ([ui](../../docs/subsystems/ui/README.md), [receipt search spec](receipt-search.md)).
- A receipt's store is stored as read and trimmed; it is `''` when the model found none,
  and `NULL` for a receipt imported before reading existed
  ([data model](../../docs/datamodel.md#receipts)).

## Proposed Change

- **PC1 One field, two targets.** The search field is labelled `Hakusana`. Next to it, a
  radio group `Hakukohde` has `Tuote` (checked when the page opens) and `Kauppa`. With
  `Tuote` the field searches by product name exactly as in the receipt search spec; with
  `Kauppa` it searches by store. The `Hae` button, Enter and the checkbox stay as they are.
- **PC2 Store match.** A receipt matches when the search text is part of its store name.
  The match ignores case (including `ä`, `ö`, `å`), leading and trailing spaces, and repeated
  inner spaces, the same way as the [normalized name](../../docs/glossary.md). A receipt
  with no store (`''` or `NULL`) never matches a store search.
- **PC3 Changing the target.** Choosing the other radio button searches again at once with
  the last searched text (as the checkbox does). Text typed but not yet searched is not
  used. Without a searched text, changing the target sends no request.
- **PC4 With the checkbox.** With `Kauppa` and the checkbox, a receipt is shown when its
  store matches and it has at least one line without a category that is not a deposit
  refund. The store is a receipt field, so the same-line rule of the product search does not
  apply. `Näytä vain nämä kuitit`, the note, the no results text, the error and the list
  order work as in the receipt search spec.
- **PC5 API.** `GET /api/receipts` takes an optional query parameter `store` (0–100
  characters after trimming). A blank `store` is no condition. With `name` and `store`
  both, a receipt must meet both. The page sends only one of them.
- **PC6 Not remembered.** The chosen target is not remembered across page loads.

### Out of Scope

- Searching archived receipts.
- A list or suggestions of store names.
- One search that matches the product or the store.
- Fuzzy matching of OCR noise in store names.

## Acceptance Criteria

Test data for AC1–AC8 (synthetic):

| Receipt | Date | Store | Lines |
|---|---|---|---|
| S1 | 2026-10-05 | `K-Market Keskusta` | `Maito` with a category |
| S2 | 2026-10-04 | `Prisma Itäkeskus` | `PORKKANA` without a category |
| S3 | 2026-10-03 | `K-Citymarket` | `MAITOSUKLAA` without a category |
| S4 | 2026-10-02 | `''` (none found) | `Leipä` with a category |
| S5 | no date | `NULL` (before reading) | none |
| S6 | 2026-10-01 | `ÄRRÄ Asema` | `Kahvi` with a category |

The unfiltered list is S5, S1, S2, S3, S4, S6.

### AC1: Search by a part of the store name
**Given** the test data
**When** the client sends `GET /api/receipts?store=k-market`, and then `?store=market`
**Then** the first answer is S1 only, and the second is S1, S3 in that order

### AC2: Case, spaces and Finnish letters
**Given** the test data
**When** the client sends `?store=%20%20ärrä%20%20`, `?store=ITÄ` and
`?store=prisma%20%20%20itäkeskus` (three inner spaces)
**Then** the answers are S6 only, S2 only and S2 only

### AC3: Empty store text
**Given** the test data
**When** the client sends `?store=` and `?store=%20%20`
**Then** each answer is the unfiltered list S5, S1, S2, S3, S4, S6

### AC4: A receipt without a store never matches
**Given** the test data
**When** the client sends `?store=a`
**Then** the answer is S1, S2, S3, S6; S4 (`''`) and S5 (`NULL`) are not in it

### AC5: Store and lines without a category
**Given** the test data
**When** the client sends `?store=k&uncategorized=true`
**Then** the answer is S2, S3 (`k` is in `K-Market Keskusta`, `Prisma Itäkeskus` and
`K-Citymarket`; S1 has no line without a category)

### AC6: Store and product name together
**Given** the test data
**When** the client sends `?name=maito&store=k`, and then `?name=maito&store=prisma`
**Then** the first answer is S1, S3, and the second is `[]`

### AC7: No match
**Given** the test data
**When** the client sends `?store=lidl`
**Then** the answer is 200 with `[]`

### AC8: Store text too long
**Given** any data
**When** the client sends `?store=` with 101 characters after trimming
**Then** the answer is 422 `invalid_request`; 100 characters with spaces around give 200

### AC9: The field and the target on the Kuitit page
**Given** the Kuitit page with receipts
**When** the page opens
**Then** the search form has the field `Hakusana` (`maxLength` 100), the radio group
`Hakukohde` with `Tuote` checked and `Kauppa` not checked, the `Hae` button and the
checkbox. A product search works as before: `Tuote` and `maito` with Enter sends
`?name=maito`

### AC10: Store search on the Kuitit page
**Given** the page shows S1–S6
**When** the user chooses `Kauppa`, types `market` and presses Enter (or clicks `Hae`)
**Then** the page sends `?store=market` and shows S1 and S3 only, in that order

### AC11: Changing the target searches again
**Given** the user has searched `market` with `Kauppa` (S1, S3 shown)
**When** the user types more text without searching, and then chooses `Tuote`
**Then** the page sends `?name=market` (the searched text, not the typed one) and shows
its answer; with an empty answer the page shows `Hakuehdoilla ei löytynyt kuitteja.`

**And** on a freshly opened page, choosing `Kauppa` without a searched text sends no request
and the full list stays

### AC12: Store search with the checkbox
**Given** the page shows S1–S6
**When** the user searches `k` with `Kauppa` and checks the checkbox
**Then** the page sends `?store=k&uncategorized=true` and shows S2 and S3 only

### AC13: No match and a failed store search
**Given** the page shows S1–S6 and `Kauppa` is chosen
**When** the user searches `lidl`, and then a search the backend answers with an error
**Then** the first shows `Hakuehdoilla ei löytynyt kuitteja.` without a table; the second
shows the message with `role="alert"` in place of the table; the field keeps its text and
`Kauppa` stays chosen

## Files to Modify

| File | Change |
|---|---|
| `backend/app/review/routes.py` | Query parameter `store` |
| `backend/app/review/service.py` | Normalize and check the store text |
| `backend/app/storage/receipt_repository.py` | Store condition in the summary query |
| `backend/tests/` | Unit and integration tests for AC1–AC8 |
| `frontend/src/api/receipts.ts` | `store` in `ReceiptFilter` |
| `frontend/src/components/ReceiptsPage.tsx` | Field label, radio group, target in the search |
| `frontend/src/i18n/fi.ts` | The new texts; `Hae tuotteella` becomes `Hakusana` |
| `frontend/src/**/*.test.ts(x)` | Tests for AC9–AC13; receipt search tests find the field by its new label |
| `frontend/e2e/receipts.spec.ts` | E2E journey for AC10; the receipt search journeys use the new label |
| `docs/api-reference.md` | The `store` parameter |
| `docs/subsystems/review/README.md` | The store condition |
| `docs/subsystems/storage/README.md` | The store condition in `summaries` |
| `docs/subsystems/ui/README.md` | The field, the target and its change |
| `docs/content-plan.md` | Status note |
| `specs/features/receipt-search.md` | A note that this spec changes its field label |
| `specs/PRD.md` | FR-58; release row |
| `specs/README.md` | Spec 27 row |

The Plan phase refines this list.

## Risk

- **What could break:** the product search (its field gets a new label, and its tests find
  the field by it); the unfiltered list; the stale answer protection, because the target is
  a new part of the search.
- **Rollback:** revert the change. No migration and no data change.
- **Dependencies:** none. Tesseract and Ollama are not used.

## Testing Strategy (MANDATORY)

### Unit tests
| AC | Function | Case | Given | When | Then | Mocks |
|---|---|---|---|---|---|---|
| AC1 | repository summary query | part of the store | test data | `store_key="k-market"`, `"market"` | S1; S1, S3 | none (temp SQLite) |
| AC2 | repository summary query | Finnish letters | test data | `"ärrä"`, `"itä"` | S6; S2 | none |
| AC4 | repository summary query | no store | test data | `"a"` | S1, S2, S3, S6 | none |
| AC5 | repository summary query | with uncategorized | test data | `"k"`, uncategorized | S2, S3 | none |
| AC6 | repository summary query | with name | test data | `name_key="maito"`, `store_key="k"` / `"prisma"` | S1, S3; `[]` | none |
| AC7 | repository summary query | no match | test data | `"lidl"` | `[]` | none |
| AC2 | service | normalization | test data | `"  ÄRRÄ  "`, `"prisma   itäkeskus"` | S6; S2 | none |
| AC3 | service | blank | test data | `""`, `"  "` | all six | none |
| AC8 | service | length | | 101 / 100 characters after trimming | `invalid_request`; passes | none |
| AC9 | `ReceiptsPage` | form | mocked API | render | `Hakusana`, `Hakukohde` with `Tuote` checked | `fetch` |
| AC9 | `ReceiptsPage` | product search | mocked API | `maito` Enter | `?name=maito` | `fetch` |
| AC10 | `ReceiptsPage` | store search | mocked API | `Kauppa`, `market`, Enter / `Hae` | `?store=market`; S1, S3 | `fetch` |
| AC11 | `ReceiptsPage` | change target | after a store search | type, choose `Tuote` | `?name=market`; no results text | `fetch` |
| AC11 | `ReceiptsPage` | no searched text | fresh page | choose `Kauppa` | no request; full list | `fetch` |
| AC12 | `ReceiptsPage` | with checkbox | mocked API | `Kauppa`, `k`, checkbox | `?store=k&uncategorized=true`; S2, S3 | `fetch` |
| AC13 | `ReceiptsPage` | no match, error | mocked API | `lidl`; then a 500 answer | no results text; alert; values kept | `fetch` |
| — | `listReceipts` | query string | `{store: "ä & b"}`, blank store | call | encoded `store`; blank left out | `fetch` |

### Integration tests
| AC | Scenario | Request / input | Expected output | Status |
|---|---|---|---|---|
| AC1 | part of the store | `?store=k-market`, `?store=market` | S1; S1, S3 | 200 |
| AC2 | case, spaces, ä | `?store=%20%20ärrä%20%20`, `?store=ITÄ`, `?store=prisma%20%20%20itäkeskus` | S6; S2; S2 | 200 |
| AC3 | blank | `?store=`, `?store=%20%20` | all six | 200 |
| AC4 | no store | `?store=a` | S1, S2, S3, S6 | 200 |
| AC5 | with uncategorized | `?store=k&uncategorized=true` | S2, S3 | 200 |
| AC6 | with name | `?name=maito&store=k`, `?name=maito&store=prisma` | S1, S3; `[]` | 200 |
| AC7 | no match | `?store=lidl` | `[]` | 200 |
| AC8 | too long | `?store=` 101 × `a`; 100 × `a` with spaces | `invalid_request`; 200 | 422; 200 |

### E2E tests
| AC | Journey | Steps | Expected outcome |
|---|---|---|---|
| AC10 | search by store | two synthetic receipts with unique stores; open Kuitit; choose `Kauppa`; type a part of one store; Enter | only that receipt; choosing `Tuote` searches again |

### Coverage target
- Backend: 80 % lines; every branch of the store condition and its check.
- Frontend: every new branch of `ReceiptsPage` and `listReceipts`.

### Test data
- Synthetic fixtures only (no real receipts): the S1–S6 table above.
- Mocks: `fetch` in the frontend unit tests. No OCR or model.

## Related Documentation (MANDATORY)
- Tier 1: [API reference](../../docs/api-reference.md#receipts),
  [data model](../../docs/datamodel.md#receipts), [glossary](../../docs/glossary.md)
- Tier 2: [review](../../docs/subsystems/review/README.md#receipt-search),
  [ui](../../docs/subsystems/ui/README.md), [storage](../../docs/subsystems/storage/README.md)
- Specs: [receipt search](receipt-search.md)
- ADRs: none

<!-- The Plan phase appends "## Plan" and the Tasks phase appends "## Tasks" below. -->

## Plan

The change extends the receipt search ([receipt search plan](receipt-search.md#plan)). No
new module, table, migration or dependency.

### P1 Route (`backend/app/review/routes.py`)

`list_receipts` gets `store: str = ""` and passes it to `service.summaries(name, store=store,
uncategorized=...)`. Like `name`, the text stays in the query string and out of the request
log.

### P2 Service (`backend/app/review/service.py`)

`summaries(name="", uncategorized=False, store="")`. The existing normalization moves to a
private helper `_search_key(text) -> str | None`: `normalize_display`, the 100 character
check (`AppError` `invalid_request`), `casefold()`, and `None` for a blank text. Both `name`
and `store` go through it, so AC8 and receipt search AC8 share one rule. The repository gets
`name_key`, `store_key`, `uncategorized` and `key=normalize_key`.

### P3 Repository (`backend/app/storage/receipt_repository.py`)

`summaries(*, name_key=None, store_key=None, uncategorized=False, key=None)`.

- The `WHERE` becomes a list of receipt conditions joined with `AND`, each with its
  parameters in the same order:
  - `store_key`: `instr(name_key(COALESCE(receipts.store, '')), ?) > 0`. `COALESCE` keeps
    `NULL` away from the Python function. SQLite does not promise to skip the call after a
    failed `IS NOT NULL`. An empty store never contains a non-empty key, so `''` and `NULL`
    never match (AC4).
  - The line conditions (`name_key`, `uncategorized`) stay in the one `EXISTS` subquery
    (`_MATCHING_LINE`), so they still hold for the same line. The store condition sits
    outside it, so with the checkbox the store and the line are separate conditions (PC4,
    AC5).
- The `name_key` SQL function is registered when `name_key` or `store_key` is set. A
  condition without `key` raises `ValueError` as now.
- Every condition is built from fixed fragments with bound parameters (ruff S608).

### P4 Frontend API (`frontend/src/api/receipts.ts`)

`ReceiptFilter` gets `store?: string`. A blank `store` is left out, as a blank `name` is.
The order of the parameters is `name`, `store`, `uncategorized`.

### P5 Kuitit page (`frontend/src/components/ReceiptsPage.tsx`)

- New state `target: "product" | "store"`, `"product"` at start.
- The form gets a `<fieldset>` with `<legend>Hakukohde</legend>` and two radio inputs
  (`name="search-target"`) labelled `Tuote` and `Kauppa`. The field's label becomes
  `Hakusana`.
- From the searched text: `productText = target === "product" ? name : ""` and
  `storeText = target === "store" ? name : ""`. The search key becomes
  `${uncategorized}:${productText}:${storeText}`, and the effect depends on these values.
  - Changing the target with a searched text changes the key, so the effect searches
    again with the last searched text (PC3, AC11).
  - Without a searched text both values stay `""`, so the key does not change and no
    request is sent (AC11), even with the checkbox on.
  - The existing key check and cleanup still drop stale answers.
- The request is `listReceipts({ name: productText, store: storeText, uncategorized })`.
  The rest of the page (note, toggle, no results text, error) is unchanged.

Texts in `fi.receipts`: `search` becomes `"Hakusana"`; new `searchTarget: "Hakukohde"`,
`targetProduct: "Tuote"`, `targetStore: "Kauppa"`.

### P6 Existing receipt search tests (G7)

The receipt search tests find the field as `searchbox` named `Hae tuotteella`. AC9 of this
spec renames it, so these lookups change to `Hakusana`. The lookups are in
`frontend/src/components/ReceiptsPage.test.tsx` (`searchField`) and
`frontend/e2e/receipts.spec.ts` (two journeys). Nothing else in them changes. The receipt
search spec gets a note that its field label changed.

The radio `Kauppa` (AC9) shares its label with the store field of the new receipt form, so
`getByLabelText("Kauppa")` finds two elements on the Kuitit page. Two receipt-management
tests find that field this way: AC29 in `frontend/src/App.test.tsx` and AC34 in
`frontend/src/components/ReceiptsPage.test.tsx`. Their lookups change to
`getByRole("textbox", { name: "Kauppa" })`, the same field; nothing else in them changes
(user decision 2026-11-23). The E2E tests find the field inside the form and need no change.

### P7 Plan against the ACs

| AC | Covered by |
|---|---|
| AC1, AC2, AC4, AC7 | P3 store condition, P2 key |
| AC3, AC8 | P2 `_search_key` |
| AC5 | P3 store outside the `EXISTS` |
| AC6 | P3 conditions joined with `AND` |
| AC9 | P5 form, P6 |
| AC10, AC12, AC13 | P4, P5 |
| AC11 | P5 search key from `productText` and `storeText` |

### P8 Files to Modify (refined)

| File | Change |
|---|---|
| `backend/app/review/routes.py` | P1 |
| `backend/app/review/service.py` | P2 |
| `backend/app/storage/receipt_repository.py` | P3 |
| `backend/tests/store_search_data.py` | New: the S1–S6 fixture |
| `backend/tests/unit/storage/test_receipt_repository.py` | P3 rows |
| `backend/tests/unit/review/test_review_service.py` | P2 rows |
| `backend/tests/integration/test_receipts_api.py` | Integration rows |
| `frontend/src/api/receipts.ts`, `receipts.test.ts` | P4 |
| `frontend/src/components/ReceiptsPage.tsx`, `ReceiptsPage.test.tsx` | P5, P6 |
| `frontend/src/App.test.tsx` | P6: the store field lookup of receipt-management AC29 |
| `frontend/src/i18n/fi.ts` | P5 texts |
| `frontend/e2e/receipts.spec.ts` | E2E row, P6 |
| `docs/api-reference.md` | The `store` parameter and its 422 |
| `docs/subsystems/review/README.md` | The store condition in [receipt search](../../docs/subsystems/review/README.md#receipt-search) |
| `docs/subsystems/storage/README.md` | `store_key` and `COALESCE` |
| `docs/subsystems/ui/README.md` | `Hakusana`, `Hakukohde` and the target change |
| `docs/content-plan.md` | Status note |
| `specs/features/receipt-search.md` | Note on the changed label |
| `specs/PRD.md` | FR-58; release row |
| `specs/README.md` | Status |

## Tasks

Each task is Red → Green → Refactor. Backend checks after T3, frontend checks after T6,
all checks and E2E after T7.

- [x] **T1 Repository store condition (AC1, AC2, AC4, AC5, AC6, AC7).** Add the S1–S6
  fixture in `backend/tests/store_search_data.py`. In `test_receipt_repository.py`:
  `store_key` `k-market` gives S1 and `market` S1, S3; `ärrä` S6 and `itä` S2; `a` gives
  S1, S2, S3, S6 (no `''` or `NULL` store, and no error from `NULL`); `k` with
  `uncategorized` gives S2, S3; `name_key="maito"` with `store_key` `k` gives S1, S3 and
  with `prisma` `[]`; `lidl` gives `[]`; a store condition without `key` raises
  `ValueError`. Then implement P3.
- [x] **T2 Service store text (AC2, AC3, AC8).** In `test_review_service.py`:
  `"  ÄRRÄ  "` and `"prisma   itäkeskus"` give S6 and S2; `""` and `"  "` give all six;
  101 characters after trimming raise `AppError` `invalid_request`, and 100 with spaces pass.
  The receipt search service tests still pass. Then implement P2.
- [x] **T3 Route parameter (AC1–AC8).** In `test_receipts_api.py`, add every integration
  row. Then implement P1. Run the backend tests, lint, format check and type check.
- [x] **T4 API client (P4).** In `receipts.test.ts`: `{store: "ä & b"}` requests
  `?store=%C3%A4+%26+b`; a blank store is left out; `{name, store, uncategorized}` keeps the
  order `name`, `store`, `uncategorized`. Then implement P4.
- [x] **T5 Field label and existing tests (AC9, P6).** Change the `searchField` lookup in
  `ReceiptsPage.test.tsx` to `Hakusana` and add the AC9 form test (`Hakukohde`, `Tuote`
  checked, `Kauppa` not, `maxLength` 100, `?name=maito` from `Tuote`). Then rename the label
  and add the radio group.
- [x] **T6 Store search on the page (AC10–AC13).** In `ReceiptsPage.test.tsx`: `Kauppa` and
  `market` with Enter and with `Hae` send `?store=market` and show S1, S3; after it, typing
  and choosing `Tuote` sends `?name=market` and shows the no results text; a fresh page
  choosing `Kauppa` sends nothing, also with the checkbox on after its request;
  `Kauppa`, `k` and the checkbox send `?store=k&uncategorized=true` and show S2, S3;
  `lidl` shows the no results text; an error answer shows the alert and keeps the text and
  `Kauppa`. Then implement P5. Run the frontend tests, lint, format check and type check.
- [x] **T7 E2E (AC10, P6).** In `frontend/e2e/receipts.spec.ts`, change the field lookups
  of the receipt search journeys to `Hakusana`. Add the store journey: two synthetic
  receipts with unique stores, `Kauppa`, part of one store, Enter, only that receipt, then
  `Tuote` searches again. Run the E2E tests.
- [x] **T8 Docs (all).** Update `docs/api-reference.md`, `docs/subsystems/review/README.md`,
  `docs/subsystems/storage/README.md`, `docs/subsystems/ui/README.md`,
  `docs/content-plan.md`, the note in `specs/features/receipt-search.md`, `specs/PRD.md`
  (FR-58, release row) and `specs/README.md`.
- [x] **T9 Audit.** Run the `review-audit` skill against this spec. Set the status to Done
  when it passes.

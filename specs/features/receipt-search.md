# Feature: Receipt search

## Overview
- **Status:** Done (approved and audited 2026-11-22)
- **Created:** 2026-11-22
- **Affected subsystems:** [review](../../docs/subsystems/review/README.md),
  [ui](../../docs/subsystems/ui/README.md), [storage](../../docs/subsystems/storage/README.md)
- **Implements:** FR-56 (new), FR-57 (new)

## Problem Statement

The Kuitit page lists every receipt, but not their lines. To find the receipts with a given
product, the user must open receipts one by one. The same holds for lines without a category:
they show up as `Ei kategoriaa` on the Vuosi tuotteineen page, but the user cannot see which
receipts they are on, so they cannot fix them.

## Current Behavior

- `GET /api/receipts` returns every receipt summary, with no filter
  ([API reference](../../docs/api-reference.md#receipts)).
- The Kuitit page shows the whole list, with the unreviewed receipts note and its
  `Näytä vain nämä kuitit` toggle ([ui](../../docs/subsystems/ui/README.md),
  [unreviewed receipts note spec](unreviewed-receipts-note.md)).
- A line has no category when the model gave no suggestion at import, when it was added or
  renamed without a product match, or when it was stored before categorization
  ([categorization](../../docs/subsystems/categorization/README.md#line-categorization)).
  A reviewed receipt may have such lines.

## Proposed Change

- **PC1 Product name search.** The Kuitit page has a search field `Hae tuotteella` and a
  button `Hae`. A search shows only the receipts that have at least one line whose name
  contains the search text. A line's name here is its own name or its linked product's
  name; either one matching is enough. The match ignores case (including `ä`, `ö`, `å`),
  leading and trailing spaces, and repeated inner spaces, the same way as the
  [normalized name](../../docs/glossary.md). A search runs on `Hae` or Enter.
  An empty or blank search text means no name condition.
- **PC2 Lines without a category.** A checkbox `Vain kuitit, joilla on rivejä ilman
  kategoriaa` shows only the receipts that have at least one line without a category that
  is not a deposit refund. Deposit refunds never have a category (FR-44), so they do not
  count. The list updates when the box changes.
- **PC3 Together.** With both a search text and the checkbox, a receipt is shown when one
  and the same line matches both. The `Näytä vain nämä kuitit` toggle applies on top of
  them. The list keeps its order (no date first, newest date first, newest import first).
- **PC4 The note counts every receipt.** The unreviewed receipts note counts all receipts,
  whatever the search or checkbox shows.
- **PC5 No results.** When the conditions match no receipt, the page shows
  `Hakuehdoilla ei löytynyt kuitteja.` instead of the table.
- **PC6 API.** `GET /api/receipts` takes two optional query parameters: `name` (the search
  text, 0–100 characters after trimming) and `uncategorized` (`true` or `false`, default
  `false`). Without them the answer is the same as today.

### Out of Scope

- Searching archived receipts.
- Highlighting the matching lines, or showing them in the list.
- Searching by store, date or amount.
- Remembering the search or checkbox across page loads or in the URL.
- Fuzzy matching of OCR noise (`MAIT0` does not match `maito`).
- Lines without a linked product that do have a category (the model's suggestions).

## Acceptance Criteria

Test data for AC1–AC7 (synthetic):

| Receipt | Date | Lines |
|---|---|---|
| R1 | 2026-10-05 | `Kevytmaito 1L` category `Maito`, linked to product `Kevytmaito 1L`; `Leipä` category `Leipä` |
| R2 | 2026-10-04 | `KAURAJUOMA` linked to product `Kaurajuoma` (renamed later), category `Maito`; `PORKKANA` no category |
| R3 | 2026-10-03 | `Panttipalautus` deposit refund −40 |
| R4 | 2026-10-02 | `MAITOSUKLAA` no category |
| R5 | no date | `Äyriäiset` category `Kala` |

### AC1: Search by a part of the line name
**Given** the test data
**When** the client sends `GET /api/receipts?name=maito`
**Then** the answer is R1, R4 in that order (R1's `Kevytmaito 1L` and R4's `MAITOSUKLAA`),
newest date first as in the unfiltered list; R2 is not in it (corrected 2026-11-22: the
order was written as R4, R1, against the stated rule)

### AC2: Search matches the linked product's name
**Given** the test data, R2's line name is `KAURAJUOMA` and its product is `Kaurajuoma`
**When** the client sends `GET /api/receipts?name=kaurajuoma` and then `?name=AJUOM`
**Then** both answers are R2 only

### AC3: Case, spaces and Finnish letters
**Given** the test data
**When** the client sends `GET /api/receipts?name=%20%20ÄYRIÄ%20%20` (with leading and
trailing spaces)
**Then** the answer is R5 only (the undated receipt is searched too)

**And** `?name=kevytmaito%20%20%201l` (three inner spaces) gives R1 only

### AC4: Empty search text
**Given** the test data
**When** the client sends `GET /api/receipts?name=` and `?name=%20%20`
**Then** each answer is all five receipts, the same as `GET /api/receipts`

### AC5: Lines without a category
**Given** the test data
**When** the client sends `GET /api/receipts?uncategorized=true`
**Then** the answer is R2, R4 in that order; R3 (only a deposit refund) is not in it

**And** `?uncategorized=false` gives all five receipts

### AC6: Both conditions on the same line
**Given** the test data
**When** the client sends `GET /api/receipts?name=maito&uncategorized=true`
**Then** the answer is R4 only. R1 has a `maito` line, but it has a category.

**And** `?name=kaurajuoma&uncategorized=true` gives `[]`: R2's line without a category is
`PORKKANA`, not the one named `KAURAJUOMA`

### AC7: No match
**Given** the test data
**When** the client sends `GET /api/receipts?name=banaani`
**Then** the answer is 200 with `[]`

### AC8: Invalid parameters
**Given** any data
**When** the client sends `?name=` with 101 characters after trimming, or
`?uncategorized=yes`
**Then** the answer is 422 `invalid_request`

### AC9: Search on the Kuitit page
**Given** the page shows R1–R5
**When** the user types `maito` in `Hae tuotteella` and presses Enter (or clicks `Hae`)
**Then** the table shows R1 and R4 only, in that order. Clearing the field and pressing `Hae` shows all
five again.

### AC10: The checkbox on the Kuitit page
**Given** the page shows R1–R5
**When** the user checks `Vain kuitit, joilla on rivejä ilman kategoriaa`
**Then** the table shows R2 and R4 only, without pressing `Hae`. Unchecking it shows all
five again. With `maito` searched and the box checked, it shows R4 only.

### AC11: The note counts every receipt
**Given** R1–R4 are reviewed, R5 is unreviewed and undated, and the user has searched `maito`
**When** the page shows the search result (R1, R4), and then the user presses
`Näytä vain nämä kuitit`
**Then** the note still says `Tarkistamattomia kuitteja ilman päivämäärää: 1.` both times,
and after the press no receipt matches both, so the page shows
`Hakuehdoilla ei löytynyt kuitteja.`

### AC12: No results text
**Given** the page shows R1–R5
**When** the user searches `banaani`
**Then** the page shows `Hakuehdoilla ei löytynyt kuitteja.` and no table; the search field
keeps `banaani`

### AC13: A failed search
**Given** the backend answers the search with an error, or cannot be reached
**When** the user searches
**Then** the page shows the error message with `role="alert"`, and the search field and the
checkbox keep their values

### AC14: Field length
**Given** the Kuitit page
**When** the user types into `Hae tuotteella`
**Then** the field accepts at most 100 characters (`maxLength` 100)

## Files to Modify

| File | Change |
|---|---|
| `backend/app/review/routes.py` | Query parameters `name` and `uncategorized` on `GET /api/receipts` |
| `backend/app/review/service.py` | Pass the conditions to the repository; normalize the search text |
| `backend/app/storage/receipt_repository.py` | Filtered summary query |
| `backend/tests/` | Unit and integration tests for AC1–AC8 |
| `frontend/src/api/receipts.ts` | `listReceipts` with optional conditions |
| `frontend/src/components/ReceiptsPage.tsx` | Search field, button, checkbox, no results text |
| `frontend/src/i18n/fi.ts` | The new texts |
| `frontend/src/**/*.test.ts(x)` | Tests for AC9–AC14 |
| `frontend/e2e/receipts.spec.ts` | E2E journeys for AC9, AC10 |
| `docs/api-reference.md` | The query parameters |
| `docs/subsystems/review/README.md` | The search rule |
| `docs/subsystems/ui/README.md` | The Kuitit page search |
| `specs/PRD.md` | FR-56, FR-57 |
| `specs/README.md` | Spec 26 row |

The Plan phase refines this list.

## Risk

- **What could break:** the unfiltered receipt list (it must stay exactly the same); the
  unreviewed receipts note, if it counted the filtered list; case folding of Finnish letters,
  because SQLite's `LIKE` folds ASCII letters only.
- **Rollback:** revert the change. No migration and no data change.
- **Dependencies:** none. Tesseract and Ollama are not used.

## Testing Strategy (MANDATORY)

### Unit tests
| AC | Function | Case | Given | When | Then | Mocks |
|---|---|---|---|---|---|---|
| AC1 | repository summary query | part of the name | test data | `name="maito"` | R1, R4 | none (temp SQLite) |
| AC2 | repository summary query | product name | test data | `kaurajuoma`, `ajuom` | R2 | none |
| AC3 | search text normalization | case, spaces, ä | `"  ÄYRIÄ  "` | normalize | `"äyriä"` | none |
| AC4 | service | blank text | `"  "` | list | no name condition | none |
| AC5 | repository summary query | uncategorized | test data | `uncategorized=True` | R2, R4 | none |
| AC6 | repository summary query | same line | test data | both conditions | R4; `kaurajuoma` gives `[]` | none |
| AC7 | repository summary query | no match | test data | `banaani` | `[]` | none |
| AC9 | `ReceiptsPage` | Enter and `Hae` | mocked API | search `maito` | request with `name=maito`; R1, R4 shown | `fetch` |
| AC9 | `ReceiptsPage` | clear | after a search | empty text, `Hae` | all receipts | `fetch` |
| AC10 | `ReceiptsPage` | checkbox | mocked API | check, uncheck | `uncategorized=true` request; then all | `fetch` |
| AC11 | `ReceiptsPage` | note | mocked API | search | note from the full list; toggle and search combined | `fetch` |
| AC12 | `ReceiptsPage` | no results | API answers `[]` | search | the no results text, no table | `fetch` |
| AC13 | `ReceiptsPage` | error | API answers 500 / network error | search | `role="alert"`, values kept | `fetch` |
| AC14 | `ReceiptsPage` | length | page | render | `maxLength` 100 | none |
| — | `listReceipts` | query string | conditions | call | URL encodes `name`, omits empty values | `fetch` |

### Integration tests
| AC | Scenario | Request / input | Expected output | Status |
|---|---|---|---|---|
| AC1 | part of the name | `GET /api/receipts?name=maito` | R1, R4 | 200 |
| AC2 | product name | `?name=kaurajuoma`, `?name=AJUOM` | R2 | 200 |
| AC3 | case, spaces, ä | `?name=%20%20ÄYRIÄ%20%20`, `?name=kevytmaito%20%20%201l` | R5; R1 | 200 |
| AC4 | empty | `?name=`, `?name=%20%20` | all five | 200 |
| AC5 | uncategorized | `?uncategorized=true`, `=false` | R2, R4; all five | 200 |
| AC6 | both | `?name=maito&uncategorized=true`, `?name=kaurajuoma&uncategorized=true` | R4; `[]` | 200 |
| AC7 | no match | `?name=banaani` | `[]` | 200 |
| AC8 | too long | `?name=` 101 × `a` | `invalid_request` | 422 |
| AC8 | bad boolean | `?uncategorized=yes` | `invalid_request` | 422 |
| — | unchanged list | `GET /api/receipts` | same as before the change | 200 |

### E2E tests
| AC | Journey | Steps | Expected outcome |
|---|---|---|---|
| AC9 | search by product | synthetic receipts; open Kuitit; type a product name; Enter | only the receipts with that product; clearing shows all |
| AC10 | lines without a category | synthetic receipt with a line without a category; check the box | only that receipt |

### Coverage target
- Backend: 80 % lines; every branch of the filtered query and the parameter checks.
- Frontend: every new branch of `ReceiptsPage` and `listReceipts`.

### Test data
- Synthetic fixtures only (no real receipts): the R1–R5 table above.
- Mocks: `fetch` in the frontend unit tests. No OCR or model.

## Related Documentation (MANDATORY)
- Tier 1: [API reference](../../docs/api-reference.md#receipts),
  [data model](../../docs/datamodel.md#receipt_lines), [glossary](../../docs/glossary.md)
- Tier 2: [review](../../docs/subsystems/review/README.md),
  [ui](../../docs/subsystems/ui/README.md),
  [categorization](../../docs/subsystems/categorization/README.md#line-categorization),
  [storage](../../docs/subsystems/storage/README.md)
- Specs: [unreviewed receipts note](unreviewed-receipts-note.md),
  [year with products](year-products.md)
- ADRs: none

## Plan

### P1 Components and data flow

```
ReceiptsPage ──listReceipts({name, uncategorized})──▶ GET /api/receipts?name=&uncategorized=
                                                      routes.list_receipts
                                                      ReviewService.summaries(name, uncategorized)
                                                      ReceiptRepository.summaries(name_key, uncategorized, key)
```

No new module, table, migration or dependency.

### P2 Route (`backend/app/review/routes.py`)

`list_receipts` gets two query parameters:

- `name: str = ""`
- `uncategorized: Literal["true", "false"] = "false"`. A plain `bool` is not used, because
  FastAPI also accepts `yes`, `on` and `1`, and AC8 requires 422 for `yes`. A value outside
  the literal is a `RequestValidationError`, which the existing handler turns into 422
  `invalid_request`.

The route passes `name` and `uncategorized == "true"` to the service. The search text stays
in the query string. The request log does not contain it, as with the failed images.

### P3 Service (`backend/app/review/service.py`)

`ReviewService.summaries(name: str = "", uncategorized: bool = False)`:

1. `display = normalize_display(name)` (from `app.categorization.names`). If it has more
   than 100 characters, raise `AppError("invalid_request", texts.INVALID_REQUEST, 422)`
   (AC8, 101 characters after trimming).
2. `name_key = display.casefold()`, which is the same as `normalize_key(name)`. An empty
   key means no name condition (AC4).
3. Call `self._receipts.summaries(name_key=name_key or None, uncategorized=uncategorized,
   key=normalize_key)`, then build the summaries with the warning as today.

The warning still uses the sum of **all** lines of the receipt, not only the matching ones.

### P4 Repository (`backend/app/storage/receipt_repository.py`)

`summaries(*, name_key: str | None = None, uncategorized: bool = False,
key: Callable[[str], str] | None = None)`.

- Line names are stored as display names, not as keys. The comparison must fold `Ä` and
  `ä`, which SQLite's `LIKE` and `lower()` do not. So the repository registers the
  caller's `key` function on its connection as the SQL function `name_key`
  (`create_function(..., 1, key, deterministic=True)`). The function is passed in, so
  storage does not import categorization. With no condition the function is not needed.
- With a condition, the query adds one `EXISTS` subquery on the lines, so the line sum stays
  the sum of all lines:

```sql
SELECT receipts.id, ..., COALESCE(SUM(receipt_lines.amount_cents), 0) AS line_sum_cents
FROM receipts LEFT JOIN receipt_lines ON receipt_lines.receipt_id = receipts.id
WHERE EXISTS (
  SELECT 1 FROM receipt_lines AS m LEFT JOIN products AS p ON p.id = m.product_id
  WHERE m.receipt_id = receipts.id
    AND (instr(name_key(m.name), :key) > 0 OR instr(p.name_key, :key) > 0)   -- with name
    AND m.category_id IS NULL AND m.is_deposit_refund = 0                    -- uncategorized
)
GROUP BY receipts.id
ORDER BY purchase_date IS NOT NULL, purchase_date DESC, receipts.id DESC
```

  Both conditions sit in one subquery, so they must hold for the same line (PC3, AC6).
  `instr` matches literally, so `%` and `_` need no escaping, as in `list_products`. The
  conditions are bound parameters. Without a condition the query is exactly the one used
  today (the `WHERE` is left out).
- Performance: every line name is folded in Python for each search. For one user's
  receipts (thousands of lines) this takes milliseconds, so no key column or index is added.
  A stored key column would need a migration and FR-43 upkeep. Revisit it if the search gets
  slow.

### P5 Frontend API (`frontend/src/api/receipts.ts`)

```ts
export interface ReceiptFilter { name?: string; uncategorized?: boolean }
export function listReceipts(filter: ReceiptFilter = {}): Promise<ApiResult<ReceiptSummary[]>>
```

The function builds the query with `URLSearchParams`. A blank `name` and a `false`
`uncategorized` are left out, so no filter gives `/api/receipts` as today.

### P6 Kuitit page (`frontend/src/components/ReceiptsPage.tsx`)

State:

| State | Meaning |
|---|---|
| `all` | The unfiltered list, loaded when the page opens; the note counts it (PC4, AC11) |
| `shown` | The list from the last search; `all` while no condition is active |
| `text` | The typed search text |
| `submitted` | The search text of the last `Hae` or Enter |
| `uncategorized` | The checkbox |
| `searchError` | The message of a failed search |

- The search controls are a `<form role="search">` above the table. The form holds the
  labelled input `Hae tuotteella` (`maxLength={100}`, AC14), the `Hae` submit button and
  the checkbox. Submitting sets `submitted` to `text`. Changing the checkbox uses the
  current `submitted`, not unsubmitted typing (AC10).
- When `submitted.trim()` or `uncategorized` changes, the page calls `listReceipts` with
  the conditions. With no condition, `shown` is `all` and no request is sent (AC9 clear).
  Answers are matched to their request by a counter in a `useRef`, so a slow earlier answer
  cannot overwrite a later one.
- `Näytä vain nämä kuitit` filters `shown` with `needsAttention`, as now (PC3).
- After the filters, an empty list while `all` is not empty shows
  `Hakuehdoilla ei löytynyt kuitteja.` and no table (PC5, AC11, AC12). An empty `all`
  shows the existing empty text.
- A failed search shows `searchError` with `role="alert"` in place of the table. The input
  and the checkbox keep their values (AC13). The next successful search clears the error.
  A failed load of `all` keeps today's error.

Texts in `frontend/src/i18n/fi.ts` (`fi.receipts`): `search: "Hae tuotteella"`,
`searchButton: "Hae"`, `uncategorized: "Vain kuitit, joilla on rivejä ilman kategoriaa"`,
`noMatches: "Hakuehdoilla ei löytynyt kuitteja."`.

### P7 Plan against the ACs

| AC | Covered by |
|---|---|
| AC1, AC2, AC3, AC6, AC7 | P4 query (`name_key` on the line, `p.name_key`, one `EXISTS`), P3 key |
| AC4 | P3 empty key gives no condition; P4 query unchanged |
| AC5 | P4 `category_id IS NULL AND is_deposit_refund = 0` |
| AC8 | P2 `Literal`, P3 length check |
| AC9, AC10, AC12, AC13, AC14 | P5, P6 |
| AC11 | P6 `all` for the note, `needsAttention` on `shown` |

### P8 Files to Modify (refined)

| File | Change |
|---|---|
| `backend/app/review/routes.py` | P2 |
| `backend/app/review/service.py` | P3 |
| `backend/app/storage/receipt_repository.py` | P4 |
| `backend/tests/unit/review/test_review_service.py` | P3 rows (AC4, AC8 length) |
| `backend/tests/unit/storage/` (receipt repository tests) | P4 rows (AC1–AC3, AC5–AC7) |
| `backend/tests/integration/` (receipt routes tests) | integration rows |
| `frontend/src/api/receipts.ts`, `receipts.test.ts` | P5 |
| `frontend/src/components/ReceiptsPage.tsx`, `ReceiptsPage.test.tsx` | P6 |
| `frontend/src/i18n/fi.ts` | P6 texts |
| `frontend/e2e/receipts.spec.ts` | E2E rows |
| `docs/api-reference.md` | Query parameters of `GET /api/receipts` |
| `docs/subsystems/review/README.md` | The search rule |
| `docs/subsystems/storage/README.md` | `summaries` conditions and the `name_key` SQL function |
| `docs/subsystems/ui/README.md` | Kuitit page search |
| `specs/PRD.md` | FR-56 (product name search), FR-57 (lines without a category); release row |
| `specs/README.md` | Status |
| `backend/tests/receipt_search_data.py` | The shared R1–R5 fixture (added in T1) |
| `docs/content-plan.md` | Review row and status note (added in T8) |

The test files are `backend/tests/unit/storage/test_receipt_repository.py`,
`backend/tests/unit/review/test_review_service.py` and
`backend/tests/integration/test_receipts_api.py`.

## Tasks

Each task is Red → Green → Refactor. Backend checks after T1–T3, frontend checks after
T4–T6, all checks and E2E after T7.

- [x] **T1 Repository filter (AC1, AC2, AC3, AC5, AC6, AC7).** Add the R1–R5 fixture to
  `test_receipt_repository.py`. Add tests: `name_key="maito"` gives R1, R4; `kaurajuoma`
  and `ajuom` give R2; `äyriä` gives R5; `uncategorized=True` gives R2, R4;
  both conditions give R4, and `kaurajuoma` plus `uncategorized` gives `[]`; `banaani`
  gives `[]`; the line sum of a matched receipt is the sum of all of its lines; no condition
  gives the same list as before. Then implement P4.
- [x] **T2 Service conditions (AC3, AC4, AC8).** In `test_review_service.py`:
  `"  ÄYRIÄ  "` and `"kevytmaito   1l"` reach the repository as `"äyriä"` and
  `"kevytmaito 1l"`; `""` and `"  "` give no name condition; 101 characters after trimming
  raise `AppError` `invalid_request`, and 100 characters with surrounding spaces pass. Then
  implement P3.
- [x] **T3 Route parameters (AC1–AC8).** In `test_receipts_api.py`, add every integration
  row of the Testing Strategy, including `?uncategorized=yes` → 422 and the unchanged
  unfiltered list. Then implement P2. Run the backend tests, lint, format check and type
  check.
- [x] **T4 API client (P5).** In `receipts.test.ts`: no filter requests `/api/receipts`;
  `{name: "maito", uncategorized: true}` requests `/api/receipts?name=maito&uncategorized=true`;
  a blank name and `false` are left out; `ä` and `&` are encoded. Then implement P5.
- [x] **T5 Search and checkbox on the page (AC9, AC10, AC12, AC14).** In
  `ReceiptsPage.test.tsx`: Enter and `Hae` send `name=maito` and show R1, R4; clearing and
  `Hae` show all with no request; the checkbox sends `uncategorized=true` at once with the
  submitted text, not the unsubmitted typing; unchecking shows all; no match shows
  `Hakuehdoilla ei löytynyt kuitteja.` without a table and keeps the text; `maxLength` is
  100; a slow earlier answer does not overwrite a later one. Then implement P6 and the
  texts.
- [x] **T6 Note and errors (AC11, AC13).** In `ReceiptsPage.test.tsx`: after a search the
  note still counts the full list; `Näytä vain nämä kuitit` with the search shows the
  no-matches text; a 500 answer and a network error show `role="alert"` in place of the
  table, and the input and checkbox keep their values; the next successful search clears
  the alert. Then complete P6. Run the frontend tests, lint, format check and type check.
- [x] **T7 E2E (AC9, AC10).** In `frontend/e2e/receipts.spec.ts`, use synthetic receipts.
  Search a product name: only its receipts show, and clearing shows all. Check the box:
  only the receipt with a line without a category shows. Run the E2E tests.
- [x] **T8 Docs (all).** Update `docs/api-reference.md`, `docs/subsystems/review/README.md`,
  `docs/subsystems/storage/README.md`, `docs/subsystems/ui/README.md`, `specs/PRD.md`
  (FR-56, FR-57, release row) and `specs/README.md`. Check the content plan entries.
- [x] **T9 Audit.** Run the `review-audit` skill against this spec. Set the status to Done
  when it passes.

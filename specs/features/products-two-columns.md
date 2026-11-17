# Feature: Tuotteet page in two columns

## Overview
- **Status:** Done (Specify, Plan and Tasks approved 2026-11-17; implemented and audited
  2026-11-17; PC11 and AC24 added, approved, implemented and re-audited 2026-11-17; PC11
  and AC24 changed for a wider category column, approved, implemented and re-audited
  2026-11-17, see [Audit](#audit)).
  Implementation notes, for the audit: the new product form's heading became `h4`, under
  the product column's `h3`; the new group and new category forms lost their own `h3`, as
  the button above names them. Removing the filter variant left `CategorySelect`'s
  `"" → null` branch reachable only through its disabled first option.
  **G7 record** (no expectation changed; only how a control is reached, unless noted):
  - `CategoryPanel.test.tsx`: the row-control tests (product management AC6, AC9, AC11,
    AC12, AC13, AC14, AC15, AC28) moved to the new `CategoryTools.test.tsx`; AC1 checks the
    tree instead of list items with controls; the add-form tests (AC5, AC8) open the form
    with its button first.
  - `ProductsPage.test.tsx`: `productCount` reads the count beside the tree item; the two
    AC24 tests select in the tree instead of `Näytä`, and the deleted-group test deletes
    with the tools and expects `Kaikki tuotteet` pressed instead of `Kaikki` in `Näytä`
    (PC4, PC6). The new AC2 test's expected URL was corrected before it passed (the client
    leaves out an empty `q`; AC2 asks only for `category_id`).
  - `CategorySelect.test.tsx`: the filter-variant test was removed with the variant (T6).
  - `App.test.tsx`: the allowed texts swap `<ryhmä> (koko ryhmä)` for the toggle names and
    their `−`/`+` signs; the navigation test finds `Juomat` as a tree button.
  - `e2e/products.spec.ts`: helpers moved to the tree and the tools (scoped to the tools,
    since the product column also holds rows and the add form's error); the heading check
    for `Tuotteet` got `exact: true`, because `Kaikki tuotteet` contains the word.
  - `e2e/products.spec.ts` AC24: the expected widths changed with the approved change of
    AC24 (product column 768 px instead of category column 352 px; the 16 px gaps; 352 px
    at 1000 px). The spec changed first, then the test.
  Most test edits were made with scripts, so `.agents/guardrails/state/test-edits.log` has
  no line for this branch; this list is the record.
- **Created:** 2026-11-17
- **Updated:** 2026-11-17: user decisions: two columns (category tree on the left, products
  on the right); all current functions and their ease of use stay; the page opens with all
  products; the tools of a group or category show only for the selected one; groups in the
  tree open and close and start open; the new group and new category forms open from a
  button. Decided by the agent for review: see
  [Agent decisions for review](#agent-decisions-for-review). After the first audit the
  user asked why the left side of a wide screen is empty (the 1200 px limit of `main`) and
  approved PC11: the page uses the window's width, with a category column of fixed width.
  Then the user found the category column too narrow and the product column too wide (its
  width before PC11 was right) and approved the change of PC11 and AC24: the product column
  is at most 48 rem, the category column takes the rest, the counts stay at the column's
  right edge with 16 px between them and the column's scroll bar.
- **Implements:** FR-11, FR-33, FR-34, FR-39 (layout of the existing functions; no new
  requirement)
- **Affected subsystems:** [ui](../../docs/subsystems/ui/README.md),
  [categorization](../../docs/subsystems/categorization/README.md)

## Problem Statement
The Tuotteet page lists every group and category with four or five controls each, then the
new group and new category forms, and only then the search, the new product form and the
table of all products. With many groups, categories and products the page is very long, and
the products are far down.

## Current Behavior
- The page stacks, from the top: the category panel (groups with their categories, then the
  categories without a group; each row has `Nimeä`, a group dropdown for a category,
  `Muuta ryhmäksi` or `Muuta kategoriaksi`, and `Poista`), the `Uusi ryhmä` and
  `Uusi kategoria` forms, the search box `Hae` and the filter dropdown `Näytä`, the
  `Uusi tuote` form, and the product table `Tuotelista`
  ([product management PC9](product-management.md#parts),
  [ui](../../docs/subsystems/ui/README.md)).
- The filter dropdown offers `Kaikki`, each group as `<ryhmä> (koko ryhmä)` and each
  category ([product management AC24](product-management.md#ac24-filter-products-by-category-or-group)).
- The product list has no pagination
  ([product management, Out of Scope](product-management.md#out-of-scope)).

## Proposed Change
- **PC1 Two columns.** On a window at least 900 px wide, the page has two columns: the
  **category column** on the left (at least 22 rem, PC11) and the **product column** on the
  right (at most 48 rem, PC11).
  On a narrower window the category column comes above the product column. The page heading
  `Tuotteet` stays above both.
- **PC2 Category tree.** The category column has the heading `Kategoriat` and a tree:
  - first the item `Kaikki tuotteet`;
  - then each group with its categories below it, then the categories without a group, in
    the backend's order as now;
  - each group shows its category count, each category its product count, with the texts of
    today (`3 kategoriaa`, `1 tuote`).

  Each group, category and `Kaikki tuotteet` is a button that selects it. The selected item
  is marked (`aria-pressed="true"`, the others `"false"`). The tree has no rename, move,
  convert or delete controls.
- **PC3 Group toggles.** Each group has a toggle button before its name:
  `Piilota kategoriat: <ryhmä>` (`aria-expanded="true"`) or `Näytä kategoriat: <ryhmä>`
  (`aria-expanded="false"`), with `aria-controls` pointing at the group's list of
  categories. Groups start open. Closing a group hides its categories and does not change
  the selection. A group without categories has no toggle.
- **PC4 Selection filters the products.** The selection replaces the filter dropdown `Näytä`,
  which is removed. `Kaikki tuotteet` shows all products, a category shows its products, a
  group shows the products of all its categories (as the filter does now). The search
  combines with the selection as now. The page opens with `Kaikki tuotteet` selected.
- **PC5 Product column.** From the top: a heading with the selected item's name
  (`Kaikki tuotteet`, a group's or a category's name); the tools of the selected item
  (PC6); the search box `Hae`; the `Uusi tuote` form; the product table `Tuotelista`; the
  empty-state messages as now. Product rows keep their controls: category dropdown,
  `Nimeä`, `Poista`.
- **PC6 Tools of the selected item.** Below the product column heading, for a selected
  category: `Nimeä`, the group dropdown `Ryhmä: <kategoria>`, `Muuta ryhmäksi` and
  `Poista`; for a selected group: `Nimeä`, `Muuta kategoriaksi` and `Poista`. They act as
  the controls of the category panel do now, and an error is shown beside them. With
  `Kaikki tuotteet` selected there are no tools. After a rename, move or conversion the item
  stays selected; after a delete `Kaikki tuotteet` is selected.
- **PC7 New group and new category.** Below the tree are two buttons, `Uusi ryhmä` and
  `Uusi kategoria`, each with `aria-expanded` and `aria-controls`. A click opens the form of
  today below the buttons and moves the focus to its name field; a second click, or
  `Peruuta` in the form, closes it. Only one form is open at a time. After a successful add
  the name field is emptied and the form stays open. The `Uusi kategoria` form's group
  dropdown starts at the selected group, or at the group of the selected category; else at
  `Ei ryhmää`.
- **PC8 New product suggests the selected category.** When a category is selected, the
  `Uusi tuote` form's category dropdown starts at it, and changes to it when the selection
  changes. With a group or `Kaikki tuotteet` selected, it starts at `Valitse kategoria` as
  now.
- **PC9 The category column stays in sight.** On a wide window the category column stays
  in view while the product column scrolls; if the tree is taller than the window, the
  column scrolls on its own.
- **PC10 Everything else stays.** The rules of the [product management](product-management.md)
  spec still hold for the page: errors beside the action that caused them (AC27), delete
  confirmation in place (AC28), group headings in the category dropdowns (AC29), Finnish
  texts (AC30), empty states (AC34), and a selection whose item was deleted meanwhile falls
  back to `Kaikki tuotteet`. No backend or API change.

- **PC11 The window's width.** On a window at least 900 px wide, the Tuotteet page (its
  heading, the load errors and both columns) spans the window less 24 px on each side, not
  only the 1200 px of `main`, as the Vertailu week table does
  ([styling PC2](styling.md#proposed-change)). The product column is at most 48 rem
  (768 px) wide, about its width inside `main`; the category column takes the rest, and is
  at least 22 rem (352 px) wide. The product table is as wide as the product column. The
  counts in the tree stay at the category column's right edge, with 16 px between them and
  the column's scroll bar (or its right edge, when it does not scroll). On a narrower
  window the page stays inside `main` as before.

### Agent decisions for review
1. The tree replaces the filter dropdown `Näytä` (PC4): two filters for the same thing would
   disagree. Every filter of today (`Kaikki`, a group, a category) is a tree item.
2. On a narrow window the category column stays first (PC1), as in the left-to-right order;
   the groups can be closed to make it short.
3. The tools of a group or category sit in the product column (PC6), under the heading that
   names the selected item, so the tree stays one line per item.
4. A new group or category form stays open after an add (PC7), so several can be added in a
   row, as today.
5. The selection, the open groups and the open form are not remembered across page loads.
6. The tree items are buttons with `aria-pressed`, not an ARIA `tree` widget: native buttons
   work with Tab and Enter without extra keyboard code.

### Out of Scope
- Pagination or virtual scrolling of the product list.
- Remembering the selection or the open groups across page loads.
- Drag and drop of categories or products.
- A product count for groups or for `Kaikki tuotteet` (the API does not give one).
- Any backend, API or data change.

## Acceptance Criteria

The examples use the default list (PRD 6.9: groups `Auto` with 3 categories and `Ruoka`
with 10, then 8 categories without a group) and the products `Kevytmaito 1L` in
`Maitotuotteet`, `Ruisleipä` in `Leivät` and `Moottoriöljy` in `Autotarvikkeet`.
"Products shown" lists the name cells of `Tuotelista` in order. "Tree items" lists the
selectable buttons of the tree in order.

### AC1: Page on opening
**Given** the example data
**When** the Tuotteet page opens
**Then** the category column has the heading `Kategoriat`; tree items: `Kaikki tuotteet`,
`Auto`, its 3 categories, `Ruoka`, its 10 categories, the 8 categories without a group;
`Kaikki tuotteet` has `aria-pressed="true"` and every other item `"false"`; `Auto` shows
`3 kategoriaa` and `Maitotuotteet` shows `1 tuote`; the product column heading is
`Kaikki tuotteet`; products shown: `Kevytmaito 1L`, `Moottoriöljy`, `Ruisleipä`; there is
no combobox named `Näytä`, and no `Nimeä`, `Muuta ryhmäksi`, `Muuta kategoriaksi` or
`Poista` button outside the product rows

### AC2: Select a category
**Given** the page of AC1
**When** the user clicks `Leivät` in the tree
**Then** the products are requested with `category_id` of `Leivät`; products shown:
`Ruisleipä`; the product column heading is `Leivät`; `Leivät` has `aria-pressed="true"`
and `Kaikki tuotteet` `"false"`

### AC3: Select a group
**Given** the page of AC1
**When** the user clicks `Ruoka` in the tree
**Then** products shown: `Kevytmaito 1L`, `Ruisleipä`; the product column heading is
`Ruoka`

### AC4: Search with a selection
**Given** `Ruoka` selected
**When** the user types `öljy` in `Hae`, then clicks `Kaikki tuotteet`
**Then** first no products and the text `Ehdoilla ei löytynyt tuotteita.`; then products
shown: `Moottoriöljy`, with `öljy` still in `Hae`

### AC5: Close and open a group
**Given** the page of AC1
**When** the user clicks `Piilota kategoriat: Ruoka`, then `Näytä kategoriat: Ruoka`
**Then** after the first click the 10 categories of `Ruoka` are not shown, the toggle reads
`Näytä kategoriat: Ruoka` with `aria-expanded="false"`, and the categories of `Auto` and
those without a group are still shown; after the second click the tree is that of AC1 and
the toggle reads `Piilota kategoriat: Ruoka` with `aria-expanded="true"`; each toggle's
`aria-controls` is the `id` of its group's category list

### AC6: Closing a group keeps the selection
**Given** `Leivät` selected
**When** the user clicks `Piilota kategoriat: Ruoka`
**Then** products shown: `Ruisleipä`; the product column heading is `Leivät`

### AC7: Group without categories has no toggle
**Given** a group `Koti` with no categories
**When** the page opens
**Then** `Koti` is a tree item showing `0 kategoriaa`, and there is no
`Näytä kategoriat: Koti` or `Piilota kategoriat: Koti` button

### AC8: Tools of a selected category
**Given** the page of AC1
**When** the user clicks `Maitotuotteet`
**Then** below the heading `Maitotuotteet` there are the button `Nimeä`, the combobox
`Ryhmä: Maitotuotteet` with `Ruoka` selected, the button `Muuta ryhmäksi` and the button
`Poista`, each once outside the product rows

### AC9: Tools of a selected group
**Given** the page of AC1
**When** the user clicks `Ruoka`
**Then** below the heading `Ruoka` there are the buttons `Nimeä`, `Muuta kategoriaksi` and
`Poista`, and no combobox named `Ryhmä: Ruoka`

### AC10: Rename the selected item
**Given** `Leivät` selected
**When** the user clicks `Nimeä` in the tools, types `Leipä` and clicks `Tallenna`
**Then** the tree item and the product column heading read `Leipä`; `Leipä` is still
selected; products shown: `Ruisleipä`

### AC11: Move the selected category
**Given** `Maitotuotteet` selected
**When** the user chooses `Ei ryhmää` in `Ryhmä: Maitotuotteet`
**Then** `Maitotuotteet` is a tree item among the categories without a group, no longer
below `Ruoka`; `Ruoka` shows `9 kategoriaa`; `Maitotuotteet` is still selected and
products shown: `Kevytmaito 1L`

### AC12: Convert the selected item
**Given** `Lemmikit` (no group, no products) selected
**When** the user clicks `Muuta ryhmäksi`, then `Muuta kategoriaksi`
**Then** after the first click `Lemmikit` is a group showing `0 kategoriaa`, still
selected, with the tools of AC9; after the second it is a category again, still selected,
with the tools of AC8 except that `Ryhmä: Lemmikit` shows `Ei ryhmää`

### AC13: A refused action shows its message beside the tools
**Given** `Juomat` selected, and a product in `Juomat`
**When** the user clicks `Muuta ryhmäksi`; then `Poista` and confirms
**Then** first the alert `Kategoriaa, jossa on tuotteita tai kuittirivejä, ei voi muuttaa
ryhmäksi.` is shown beside the tools; then an alert starting with `Kategoriaa käyttää 1
tuote` is shown beside the tools; `Juomat` is still a tree item and still selected

### AC14: Delete the selected item
**Given** `Lemmikit` (no products) selected
**When** the user clicks `Poista` in the tools and confirms
**Then** `Lemmikit` is not a tree item; `Kaikki tuotteet` has `aria-pressed="true"`; the
product column heading is `Kaikki tuotteet`; products shown are those of AC1. Clicking
`Poista` and then cancelling sends no request

### AC15: New group and new category forms open from buttons
**Given** the page of AC1
**When** the user clicks `Uusi ryhmä`, types `Koti`, clicks `Lisää`; then clicks
`Uusi kategoria`; then clicks `Uusi kategoria` again
**Then** on opening neither form `Uusi ryhmä` nor `Uusi kategoria` is shown and both
buttons have `aria-expanded="false"` and `aria-controls`; after the first click the form
`Uusi ryhmä` is shown, the button has `aria-expanded="true"` and the focus is in
`Ryhmän nimi`; after `Lisää` the tree has `Koti`, `Ryhmän nimi` is empty and the form is
still shown; after the `Uusi kategoria` click its form is shown and the `Uusi ryhmä` form
is not; after the last click neither form is shown

### AC16: Cancel closes a form
**Given** the form `Uusi kategoria` open with `Kahvi` typed in its name field
**When** the user clicks `Peruuta` in the form
**Then** the form is not shown, `Uusi kategoria` has `aria-expanded="false"`, and no
request was sent

### AC17: New category suggests the selected group
**Given** the page of AC1
**When** the user opens `Uusi kategoria` with `Leivät` selected; with `Ruoka` selected;
with `Juomat` selected; with `Kaikki tuotteet` selected
**Then** its `Ryhmä` dropdown shows `Ruoka`, `Ruoka`, `Ei ryhmää` and `Ei ryhmää`; adding
`Kahvi` with `Leivät` selected creates it in `Ruoka` (`parent_id` of `Ruoka`)

### AC18: New product suggests the selected category
**Given** the page of AC1
**When** the user selects `Leivät`, types `Näkkileipä` in `Tuotteen nimi` of `Uusi tuote`
and clicks `Lisää`; then selects `Ruoka`
**Then** with `Leivät` selected the form's `Kategoria` shows `Leivät`; after `Lisää`
products shown are `Näkkileipä`, `Ruisleipä` and `Leivät` shows `2 tuotetta`; with `Ruoka`
selected the form's `Kategoria` shows `Valitse kategoria`

### AC19: Recategorizing a product in a filtered list
**Given** `Leivät` selected
**When** the user chooses `Juomat` in the `Kategoria` dropdown of the `Ruisleipä` row
**Then** no products are shown and the text `Ehdoilla ei löytynyt tuotteita.`; `Leivät`
shows `0 tuotetta` and `Juomat` shows `1 tuote`

### AC20: Load errors
**Given** the categories request fails with "Taustapalveluun ei saada yhteyttä."
**When** the page opens
**Then** the alert `Taustapalveluun ei saada yhteyttä.` is shown at the top of the page;
the tree has only `Kaikki tuotteet`, selected; the products of AC1 are shown; the
`Uusi tuote` form does not say `Lisää ensin kategoria.`

### AC21: Two columns on a wide window
**Given** the example data in a window 1280 px wide
**When** the page opens, and then the window is scrolled down by 400 px with 60 products
listed
**Then** the category column's right edge is left of the product column's left edge and
their tops differ by at most 1 px; after the scroll the `Kaikki tuotteet` button is still
inside the window

### AC22: One column on a narrow window
**Given** the example data in a window 800 px wide
**When** the page opens
**Then** the category column's bottom edge is above the product column's top edge, and no
part of the page is wider than the window

### AC24: The page uses the window's width
**Given** the example data in a window 1920 px wide
**When** the page opens
**Then** the category column's left edge is 24 px (±1 px) from the window's left edge; the
product column is 768 px (±1 px) wide and its right edge is at most 24 px from the window's
right edge, not counting a vertical scroll bar; the category column ends 16 px (±1 px)
before the product column; the table `Tuotelista` is as wide as the product column
(±1 px); the heading `Tuotteet` starts at the category column's left edge (±1 px); the
count `10 kategoriaa` of `Ruoka` ends 16 px (±1 px) before the inner right edge of the
category column (its scroll bar excluded); and the page does not scroll sideways. In a
window 1000 px wide the category column is 352 px (±1 px) wide

### AC23: Accessibility
**Given** the example data
**When** axe runs on the page as opened, with `Maitotuotteet` selected, with `Ruoka` closed
and with the `Uusi ryhmä` form open; and the user presses Tab from the last navigation link
**Then** axe finds no WCAG 2.1 AA violation; Tab reaches, in this order, `Kaikki tuotteet`,
`Piilota kategoriat: Auto`, `Auto`, `Autohuolto`, and reaches `Uusi ryhmä` and
`Uusi kategoria` before the search box `Hae`

## Files to Modify
| File | Change |
|---|---|
| `frontend/src/components/ProductsPage.tsx` | two columns, selection instead of the filter dropdown, product column heading, tools of the selected item, the new product form's suggestion (PC1, PC4, PC5, PC8, PC10) |
| `frontend/src/components/CategoryPanel.tsx` | the tree with selection and group toggles; the add forms behind buttons (PC2, PC3, PC7) |
| `frontend/src/components/CategoryTools.tsx` | new: the tools of the selected group or category (PC6), moved from the panel's rows |
| `frontend/src/components/CategoryTools.test.tsx` | new: the row-control tests moved from `CategoryPanel.test.tsx` (G7 record) |
| `frontend/src/components/CategorySelect.tsx` | remove the filter variant (`isFilter`), no longer used |
| `frontend/src/components/ProductsPage.test.tsx` | AC1–AC4, AC8–AC14, AC18–AC20; existing tests that use the filter dropdown move to the tree (G7 record) |
| `frontend/src/components/CategoryPanel.test.tsx` | AC1, AC5–AC7, AC15–AC17; existing tests that use row controls move to the tools (G7 record) |
| `frontend/src/App.test.tsx` | the allowed Finnish texts get the group toggle names and their `−`/`+` signs instead of the filter's `<ryhmä> (koko ryhmä)`; the navigation test finds `Juomat` as a tree button (G7 record) |
| `frontend/src/components/CategorySelect.test.tsx` | tests of the filter variant removed with it (G7 record) |
| `frontend/src/i18n/fi.ts` | `Kaikki tuotteet`; remove `filter`, `all`, `wholeGroup` |
| `frontend/src/styles.css` | the two columns and the sticky category column (PC1, PC9); the page across the window and the fixed category column (PC11) |
| `specs/features/styling.md` | Overview note: the Tuotteet page is a second exception to the 1200 px limit of PC2 |
| `frontend/e2e/products.spec.ts` | journeys move to the tree and tools; AC21–AC23 |
| `specs/features/product-management.md` | note in Overview: the page layout of PC9 and the filter dropdown of AC24 are superseded by this spec |
| `docs/subsystems/ui/README.md` | the Tuotteet page lines and the error paragraph; the `main` width rule and the class table (PC11) |
| `docs/subsystems/categorization/README.md` | only if it describes the page layout |
| `specs/README.md` | row 25 |

## Risk
- **What could break:** the existing product and category tests, which find the row
  controls, the filter dropdown and the always-shown forms; E2E helpers (`entry`,
  `deleteEntry`) that look for controls inside the tree's list items. Each test that moves
  is recorded for the audit (G7); its expectation stays, only the way to reach the control
  changes. A wrong selection could hide products the user expects to see; the heading names
  the selection to make that visible.
- **Rollback:** revert the commit; frontend only, no data or API change.
- **Dependencies:** none.

## Testing Strategy (MANDATORY)

### Unit tests
Component tests with Vitest and React Testing Library; the API through MSW
(`fakeCatalog` of `src/test/catalog.ts`).

| AC | Function | Case | Given | When | Then | Mocks |
|---|---|---|---|---|---|---|
| AC1 | `ProductsPage` | opening | example data | render | tree items, `aria-pressed`, counts, heading, products; no `Näytä`, no tools | API |
| AC2 | `ProductsPage` | category | AC1 | click `Leivät` | request `category_id`; products; heading; pressed | API |
| AC3 | `ProductsPage` | group | AC1 | click `Ruoka` | products; heading | API |
| AC4 | `ProductsPage` | search + selection | `Ruoka` | type `öljy`, click `Kaikki tuotteet` | empty message, then `Moottoriöljy` | API |
| AC5 | `CategoryPanel` | toggle | default list | close, open `Ruoka` | categories hidden and shown; texts; `aria-expanded`; `aria-controls` | none |
| AC6 | `ProductsPage` | toggle keeps selection | `Leivät` | close `Ruoka` | products and heading unchanged | API |
| AC7 | `CategoryPanel` | empty group | group `Koti` | render | no toggle; `0 kategoriaa` | none |
| AC8 | `ProductsPage` | category tools | AC1 | click `Maitotuotteet` | four tools; `Ruoka` in the dropdown | API |
| AC9 | `ProductsPage` | group tools | AC1 | click `Ruoka` | three tools; no group dropdown | API |
| AC10 | `ProductsPage` | rename | `Leivät` | rename to `Leipä` | tree and heading; still selected | API |
| AC11 | `ProductsPage` | move | `Maitotuotteet` | `Ei ryhmää` | position in tree; `9 kategoriaa`; still selected | API |
| AC12 | `ProductsPage` | convert | `Lemmikit` | convert twice | group, then category; still selected; tools | API |
| AC13 | `ProductsPage` | refused | `Juomat` with a product | convert; delete | alerts beside the tools; still selected | API (409/422 answers) |
| AC14 | `ProductsPage` | delete | `Lemmikit` | delete, confirm; delete, cancel | back to `Kaikki tuotteet`; no request on cancel | API |
| AC15 | `CategoryPanel` | add forms | default list | open, add, switch, close | forms, `aria-expanded`, focus, cleared name | API |
| AC16 | `CategoryPanel` | cancel | open form with text | `Peruuta` | closed; no request | API |
| AC17 | `CategoryPanel` | suggested group | each selection | open `Uusi kategoria` | dropdown value; `parent_id` sent | API |
| AC18 | `ProductsPage` | suggested category | `Leivät`, then `Ruoka` | add product | dropdown value; products; count | API |
| AC19 | `ProductsPage` | recategorize | `Leivät` | `Juomat` in the row | empty message; counts | API |
| AC20 | `ProductsPage` | load error | categories fail | render | alert; only `Kaikki tuotteet`; products; no hint | API (network error) |

### Integration tests
None apply: no backend change. The page uses the catalog endpoints already tested by the
[product management](product-management.md) spec.

### E2E tests
| AC | Journey | Steps | Expected outcome |
|---|---|---|---|
| AC2, AC8, AC10, AC14, AC15, AC18 | manage through the tree | open `Uusi ryhmä`, add a group; `Uusi kategoria` in it; select the category, add a product; rename the category in the tools; delete the product, the category and the group | each step shows in the tree and the product column; ends on `Kaikki tuotteet` |
| AC13 | refused deletes | select a used category and a group with categories, delete each | the messages beside the tools; both stay |
| AC4 | search | add two products, search one | only the match is shown |
| AC21, AC22 | layout | 1280 px with 60 products, scroll; 800 px | positions as in the ACs |
| AC24 | the window's width | 1920 px | edges and widths as in AC24 |
| AC23 | accessibility | axe in the four states; Tab from the last navigation link | no violation; tab order |

### Coverage target
- Frontend: every branch of the selection, the tools and the form state in
  `ProductsPage`, `CategoryPanel` and `CategoryTools`.
- Backend: not changed.

### Test data
- Synthetic fixtures only: the default list of `src/test/catalog.ts` and the example
  products above; in E2E names made up for each journey, as now.
- Mocks: the API through MSW in unit tests.

## Related Documentation (MANDATORY)
- Tier 1: [docs/architecture.md](../../docs/architecture.md)
- Tier 2: [ui](../../docs/subsystems/ui/README.md),
  [categorization](../../docs/subsystems/categorization/README.md)
- Specs: [product management](product-management.md),
  [visual style and accessibility](styling.md)
- ADRs: none

## Plan

### P1 Components
The page splits into three components, all in `frontend/src/components/`.

- **`ProductsPage`** owns the data and the selection:
  - state as now (`items`, `products`, `query`, errors, `version`), with `filterId` renamed
    `selectedId` (`null` = `Kaikki tuotteet`). The existing fallback
    (`activeSelectedId` is `null` when the item is no longer in `items`) covers a deleted
    selection (PC6, PC10), so a delete needs no extra code;
  - markup: the heading `Tuotteet`, the load errors, then
    `<div className="products-columns">` with two children:
    `<CategoryPanel>` (the category column) and `<section className="product-column">`
    (the product column, heading `h3` with the selected item's name or `Kaikki tuotteet`);
  - the product column holds `<CategoryTools>` (only when an item is selected), the search
    box, `AddProductForm`, the table and the empty states as now. The `Näytä` dropdown is
    removed (PC4).
- **`CategoryPanel`** becomes the category column. Props: `items`, `selectedId`,
  `onSelect(id | null)`, `onChanged`.
  - The tree: `<ul className="category-tree">` with `Kaikki tuotteet` first, then each
    group, then the ungrouped categories. Each item is
    `<button type="button" className="tree-item" aria-pressed>` with the name in
    `<span data-name>` and the count after it (PC2).
  - Group toggles: state `closedGroups: Set<number>`, empty at start, so every group and a
    group added later start open (PC3). The toggle is the year table's pattern: a button
    with `aria-expanded`, `aria-label` `Piilota kategoriat: <ryhmä>` or
    `Näytä kategoriat: <ryhmä>`, visible text `−` or `+`, and `aria-controls` = the `id` of
    the group's `<ul>` (from `useId()` plus the group id). It is rendered only when the
    group has categories (AC7). A closed group's `<ul>` is not rendered; `aria-controls`
    then points at no element, which ARIA allows for a collapsed region.
  - Add forms: state `openForm: "group" | "category" | null`. The buttons `Uusi ryhmä` and
    `Uusi kategoria` (`aria-expanded`, `aria-controls` = the form's `id`) set or clear it;
    only the open form is rendered (PC7). `AddForm` gets a `Peruuta` button (`onCancel`) and
    an `initialParentId`; it focuses its name field on mount with a ref and `useEffect`
    (the jsx-a11y rule forbids `autoFocus`). Because the form mounts when it opens, its
    group dropdown starts at the value of that moment (AC17).
  - The row controls (`Entry`'s rename, move, convert, delete) move out to `CategoryTools`.
- **`CategoryTools`** (new): the tools of one selected group or category, the body of
  today's `Entry` without the name and count: `Nimeä` with its inline form, the
  `Ryhmä: <kategoria>` dropdown for a category, `Muuta ryhmäksi` or `Muuta kategoriaksi`,
  `ConfirmDelete`, and the error with `role="alert"` (PC6, AC13). Props: `item`, `groups`,
  `onChanged`. It keeps its own error state as the panel does now. `ProductsPage` gives it
  `key={item.id}`, so an open rename form or error does not carry over to another item.

### P2 Suggested category of a new product (PC8)
`AddProductForm` gets `suggestedId` (the selected item's id when it is a category, else
`null`). Its choice is stored with the suggestion it was made under:
`chosen: {suggestedId, id}`. The shown value is `chosen.id` while `chosen.suggestedId`
equals the current `suggestedId`, else `suggestedId`. So a new selection resets the
dropdown to the new suggestion, and a choice made by the user holds until the selection
changes. No effect sets state, which the React lint rules forbid.

### P3 Data flow
No change: the page loads `GET /api/categories` and `GET /api/products?q=&category_id=`
and reloads both after every successful write, as now. The selection is sent as
`category_id` exactly as the filter is now (AC2, AC3). No API, backend or storage change.

### P4 Texts and styles
- `fi.products`: add `allProducts: "Kaikki tuotteet"`; remove `filter`, `all` and
  `wholeGroup` with the filter variant of `CategorySelect`. `fi.categories`: add
  `showCategories(name)` and `hideCategories(name)` with the year table's texts. The year
  table keeps its own copies in `fi.archive`, so neither page changes the other.
- `styles.css`:
  - `.products-columns`: one column; at `min-width: 900px` a grid
    `minmax(0, 1fr) minmax(0, 2fr)` with `gap: var(--space-3)` and `align-items: start`,
    the receipt page's pattern (PC1);
  - `.category-column` at that width: `position: sticky; top: var(--space-3);
    max-height: calc(100vh - 2 * var(--space-3)); overflow-y: auto` (PC9);
  - `.category-tree`: no bullets, a nested list indented under its group;
  - `.tree-item`: full width, left-aligned, no border; `[aria-pressed="true"]` in bold
    with the accent border on the left, so the selection does not rely on colour alone;
  - the group toggle keeps the fixed width of the year table's toggle, so the names line
    up.

### P5 Data model and dependencies
None.

### P6 Existing tests (G7 record)
The expectations stay; only the way to reach a control changes. Each moved test is listed
in the spec's Overview at the end.
- `CategoryPanel.test.tsx`: the tests of row controls (AC6, AC9, AC11, AC12, AC13, AC14,
  AC15, AC28 of product management) move to a new `CategoryTools.test.tsx` that renders the
  tools of one item; the add-form tests (AC5, AC8) first click `Uusi ryhmä` or
  `Uusi kategoria`. AC1 there checks the tree instead of list items with controls.
- `ProductsPage.test.tsx`: the filter tests (AC24, the deleted-group fallback) click tree
  items instead of choosing in `Näytä`.
- `CategorySelect.test.tsx`: the filter-variant tests are removed with the variant.
- `e2e/products.spec.ts`: `entry()` finds a tree item; `deleteEntry()` and the rename and
  move steps select the item first and use the tools; the add forms are opened first.

### P7 Documentation
- `docs/subsystems/ui/README.md`: the lines of `ProductsPage`, `CategoryPanel`,
  `CategorySelect` and the new `CategoryTools`; the Tuotteet paragraph on errors and the
  fallback.
- `specs/features/product-management.md`: Overview note that this spec supersedes the
  layout of PC9 and the filter dropdown of AC24.
- `docs/subsystems/categorization/README.md`: no change; it does not describe the page.
- `specs/README.md`: row 25.

### P9 The window's width (PC11)
- `ProductsPage`'s outer `section` gets the class `products-page`.
- `styles.css`, at `min-width: 900px`: `.products-page` takes the width and offset of
  `.table-box-wide` (`width: calc(100vw - 2 * var(--space-4))`,
  `margin-left: calc(50% - 50vw + var(--space-4))`), so its heading and both columns span
  the window; `.products-columns` becomes
  `grid-template-columns: minmax(22rem, 1fr) minmax(0, 48rem)`; `.category-column` gets
  `padding-right: var(--space-3)`, which sits inside its scroll bar, so the counts keep
  16 px from it; `.product-column table` gets `width: 100%`. `100vw` includes the vertical scroll bar,
  which is why AC24 does not count it.
- No change to `main` or to any other page.

### P8 Check against the ACs
| AC | Covered by |
|---|---|
| AC1 | P1 tree, no `Näytä`, tools only for a selection |
| AC2–AC4 | P1 selection as `category_id`; P3 |
| AC5–AC7 | P1 `closedGroups`, toggle only with categories |
| AC8–AC14 | P1 `CategoryTools`; fallback on delete; `key` per item |
| AC15–AC17 | P1 `openForm`, focus on mount, `initialParentId` |
| AC18 | P2 |
| AC19 | P3 reload after the write |
| AC20 | P1 the tree from `items`, empty after a failed load |
| AC21, AC22 | P4 grid and sticky column |
| AC23 | P1 native buttons in DOM order; P4 selection not by colour alone |
| AC24 | P9 |

## Tasks

- [x] **T1 Category tools (AC8, AC9, AC12, AC13, AC14).** Red: new
  `frontend/src/components/CategoryTools.test.tsx`; move the row-control tests of
  `CategoryPanel.test.tsx` (rename, move, convert, refused convert, delete in use, delete a
  group with categories, cancel, delete) there, changed only to render the tools of one item
  (G7 record), and add AC8 and AC9 (which tools for a category, which for a group). Green:
  `CategoryTools.tsx` from the body of `Entry`. Refactor with all frontend tests green.
- [x] **T2 Category tree and group toggles (AC1, AC5, AC7).** Red: in
  `CategoryPanel.test.tsx`, AC1 of product management checks the tree items and their
  counts (G7 record); new tests for `aria-pressed`, `onSelect`, AC5 and AC7. Green: the
  tree, `selectedId`, `onSelect`, `closedGroups` and the toggles in `CategoryPanel.tsx`;
  `fi.categories.showCategories` / `hideCategories`.
- [x] **T3 Add forms behind buttons (AC15, AC16, AC17).** Red: the add-form tests of
  `CategoryPanel.test.tsx` first click `Uusi ryhmä` or `Uusi kategoria` (G7 record); new
  tests for AC15–AC17. Green: `openForm`, the buttons, `Peruuta`, focus on mount and
  `initialParentId` in `AddForm`.
- [x] **T4 Products page with selection and tools (AC1–AC4, AC6, AC8–AC14, AC19, AC20).**
  Red: in `ProductsPage.test.tsx` the filter tests click tree items instead of `Näytä`
  (G7 record); new tests for AC1–AC4, AC6, AC10, AC11, AC12 (still selected), AC14 (back to
  `Kaikki tuotteet`), AC19 and AC20. Green: `selectedId`, the two columns' markup, the
  product column heading and `CategoryTools` with `key`; remove the `Näytä` dropdown;
  `fi.products.allProducts`.
- [x] **T5 Suggested product category (AC18).** Red: AC18 in `ProductsPage.test.tsx`.
  Green: `suggestedId` and `chosen` in `AddProductForm` (P2).
- [x] **T6 Remove the filter variant.** Remove `isFilter` from `CategorySelect.tsx`, its
  tests from `CategorySelect.test.tsx` (G7 record) and `fi.products.filter`, `all` and
  `wholeGroup`. All frontend tests, lint and type check green.
- [x] **T7 Styles (AC21, AC22).** `.products-columns`, `.category-column`, `.category-tree`
  and `.tree-item` in `styles.css` (P4).
- [x] **T8 E2E (AC2, AC4, AC8, AC10, AC13–AC15, AC18, AC21–AC23).** Update the helpers and
  journeys of `frontend/e2e/products.spec.ts` to the tree, the tools and the add buttons
  (G7 record); add the layout test (1280 px with 60 products and a scroll; 800 px) and the
  accessibility test (axe in four states, Tab order). Use names no other journey uses. Run
  the whole E2E suite.
- [x] **T9 Documentation.** `docs/subsystems/ui/README.md` (P7); the Overview note in
  `specs/features/product-management.md`; `specs/README.md` row 25; the G7 record in this
  spec's Overview.
- [x] **T11 The window's width (AC24).** Red: an AC24 test in `frontend/e2e/products.spec.ts`
  (1920 px). Green: P9 in `ProductsPage.tsx` and `styles.css`. Docs: the ui README's width
  rule and class table; the styling spec's Overview note. Run the whole E2E suite, then
  re-audit.
- [x] **T12 Wider category column (AC24 changed).** Red: the AC24 test in
  `frontend/e2e/products.spec.ts` for the changed widths, the 16 px before the count and
  the 352 px at 1000 px. Green: P9's grid and padding in `styles.css`. Docs: the ui README's
  class table. Run the whole E2E suite, then re-audit.
- [x] **T10 Checks and audit.** Frontend tests, lint, format check, type check and E2E;
  `review-audit` against AC1–AC23; status `Done`.

## Audit

Audited 2026-11-17.

- Acceptance criteria: 24/24 met. Unit tests: AC1–AC4, AC6, AC8–AC14, AC18–AC20 in
  `ProductsPage.test.tsx`; AC1, AC2, AC5–AC7, AC15–AC17 in `CategoryPanel.test.tsx`; AC8–AC11
  and the moved product management ACs in `CategoryTools.test.tsx`. E2E in
  `e2e/products.spec.ts`: AC2, AC4, AC8, AC10, AC13–AC15, AC18, AC21–AC24.
- Re-audit for PC11 and AC24: the AC24 test was seen failing (category column at 376 px)
  before `products-page` and the 22 rem column were added; the styling spec's AC4 test
  (1200 px on Kuitit) still passes, so only the Tuotteet page changed width.
- Re-audit for the changed PC11 and AC24: the changed AC24 test was seen failing (product
  column 1504 px) before the grid `minmax(22rem, 1fr) minmax(0, 48rem)` and the column's
  16 px right padding; a screenshot at 1920 px showed the counts at the column's right
  edge and the product column at its earlier width.
- Tests: frontend 446 passed; E2E 50 passed; lint, format check and type check green.
- Coverage: `CategoryPanel.tsx` and `CategoryTools.tsx` 100 % lines, `ProductsPage.tsx`
  98.8 % lines (the untouched product row's rename `Peruuta`). The branches left are
  `?? 0` count fallbacks and the `draft !== null` guard, which the UI cannot reach.
- Security and privacy: frontend only; no receipt data, no new dependency, no
  `dangerouslySetInnerHTML`; the E2E products are synthetic names.
- Files to Modify: all changed as listed; `docs/subsystems/categorization/README.md` did not
  need a change (it does not describe the page).
- Docs: `docs/subsystems/ui/README.md` and the product management spec's Overview updated.

Verdict: PASS.

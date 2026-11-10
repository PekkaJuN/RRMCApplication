# Feature: Visual style and accessibility

## Overview
- **Status:** Done
- **Created:** 2026-11-02
- **Updated:** 2026-11-02: user answers before Specify: one plain CSS file with CSS custom
  properties, no CSS framework or UI library; automated accessibility checks with axe in
  the E2E tests; no dark mode. Specify approved by the user; Plan added. Plan approved
  by the user; Tasks added. Spec approved by the user. Implemented and audited (PASS).
- **Implements:** PRD NFR-16 (new); NFR-1 for the UI's resources.
- **Affected subsystems:** [ui](../../docs/subsystems/ui/README.md)

## Problem Statement
The UI has no stylesheet. Every page uses the browser's default look: tables without
borders or alignment, amounts aligned left, buttons and the download links that look
different, errors that look like plain text, and a few inline styles in the components
(the receipt page's two columns, the totals tables' indent, the download links). The pages
are hard to read, and nothing checks that they stay usable with a keyboard or a screen
reader, or that text has enough contrast.

This spec gives the app one consistent look from one stylesheet and adds an automated
accessibility check (WCAG 2.1 level AA) of every page to the E2E tests.

## Current Behavior
- The app shell (`App.tsx`) has a header with the title, the navigation and the status
  line, and a `main` with the page ([ui](../../docs/subsystems/ui/README.md)).
- The pages are Tuotteet, Tuonti, Kuitit, a receipt and Yhteenveto. Tables: `Tuotteet`,
  `Kuittilista`, `Kuittirivit`, `Viikot` and `Kuukaudet`.
- Errors are `role="alert"` and notices `role="status"`, both unstyled.
- Inline styles: @frontend/src/components/ReceiptPage.tsx (columns),
  @frontend/src/components/TotalsTable.tsx (category indent),
  @frontend/src/components/TotalsPage.tsx (download links).
- No CSS file and no accessibility check exist.

## Proposed Change

- **PC1 One stylesheet (NFR-16).** `frontend/src/styles.css` is the only source of style.
  Colors, spacing, font sizes and the border radius are CSS custom properties on `:root`,
  so the look changes in one place. Components use class names and semantic elements; no
  element has an inline `style` attribute. The font is the system font
  (`system-ui, "Segoe UI", Roboto, sans-serif`); no font, image or stylesheet is loaded
  from another host (NFR-1).
- **PC2 Layout.** The header holds the title, the navigation and the status line; on a
  window at least 900 px wide they are on one row. The content of `main` is at most
  1200 px wide and centred; the Vertailu week table is the one exception
  ([budget](budget.md) PC6). The page never scrolls sideways at a window width of 600 px or
  more: a table wider than the window scrolls inside its own box.
- **PC3 Navigation.** The current page's link (`aria-current="page"`) is bold and
  underlined with a 3 px accent-colored line; the other links are not bold and have no
  line.
- **PC4 Tables.** Header cells are bold with a line below them; body rows are separated by
  a thin line. Money amounts (cells and amount inputs) are aligned right with tabular
  figures, so the decimal commas line up. In the totals tables, group rows and the
  `Yhteensä` row are bold, and a category row's name is indented under its group.
- **PC5 Buttons.** Buttons and the download links on the Yhteenveto page share one button
  style (border, radius, padding, background) and the `pointer` cursor. A disabled button
  looks disabled (lighter, and the `not-allowed` cursor).
- **PC6 Forms.** Text inputs, number-like inputs and selects share one style (border,
  radius, padding) and the same height as buttons.
- **PC7 Messages.** An error paragraph (`p` with `role="alert"`) has a red-tinted
  background, dark red text and a 4 px red left border. A notice paragraph in `main`
  (`p` with `role="status"`) has a yellow-tinted background, dark brown text and a 4 px
  amber left border. An inline error (`span` with `role="alert"`, next to a field) is only
  dark red text. The header's status line keeps its own look.
- **PC8 Keyboard focus.** An element focused with the keyboard shows a solid outline at
  least 2 px wide in the accent color (`:focus-visible`), on every link, button, input and
  select.
- **PC9 Receipt page columns.** On a window at least 900 px wide the image is on the left
  and the lines on the right, their tops aligned; on a narrower window the image is above
  the lines.
- **PC10 Accessibility check (NFR-16).** The E2E tests run axe (`@axe-core/playwright`)
  with the rules tagged `wcag2a`, `wcag2aa`, `wcag21a` and `wcag21aa` on every page. Every
  violation found is fixed in this spec, in the stylesheet or the markup. A fix that would
  change a visible text, a label or a behavior is a spec change first.

### Out of Scope
- A CSS framework, a UI component library, CSS Modules or CSS-in-JS.
- New texts, new controls, changed page structure or behavior; every existing component
  and E2E test passes unchanged.
- Logo, icons, images, animations and print styles.
- Web fonts (they would be loaded from another host, or added as files; the system font
  is used).
- Windows narrower than 600 px (the app runs on the user's computer).
- A dark color scheme (the user's choice, 2026-11-02).
- Manual accessibility testing with a screen reader; axe finds only part of the possible
  problems.

## Acceptance Criteria

The E2E checks run in Chromium (Playwright) with a window of 1280 × 800 px unless the AC
says otherwise. "The pages" means: Tuotteet, Tuonti, Kuitit, a receipt imported in the
test, and Yhteenveto with the month of that receipt and the group `Ruoka` expanded.

### AC1: No inline styles
**Given** each of the pages
**When** it has loaded
**Then** `document.querySelectorAll("[style]").length` is 0. **And** in the component
tests, `TotalsPage`, `TotalsTable` and `ReceiptPage` render no element with a `style`
attribute

### AC2: Stylesheet and font
**Given** the Tuotteet page
**When** it has loaded
**Then** the computed `font-family` of `body` starts with `system-ui`, and the custom
property `--color-accent` on `:root` is not empty

### AC3: Nothing from other hosts
**Given** the pages
**When** they load
**Then** every request the browser makes goes to `127.0.0.1:5173` (the app's origin)

### AC4: Content width
**Given** a window of 1600 × 900 px and the Kuitit page
**When** it has loaded
**Then** the content of `main` is 1200 px wide (±1 px), and its left and right distances to
the window's edges differ by at most 1 px

### AC5: No sideways scrolling at 600 px
**Given** a window of 600 × 800 px and each of the pages, Yhteenveto with
`unit=week&from=2026-W40&to=2026-W48`
**When** it has loaded
**Then** `document.documentElement.scrollWidth` is at most 600; on Yhteenveto the table
`Viikot` is scrollable inside its box (its box's `scrollWidth` is greater than its
`clientWidth`)

### AC6: Current page in the navigation
**Given** the Kuitit page
**When** it has loaded
**Then** the link `Kuitit` has a computed `font-weight` of 700 and a 3 px solid bottom
border in the color of `--color-accent`; the links `Tuotteet`, `Tuonti` and `Yhteenveto`
have `font-weight` 400 and no bottom border

### AC7: Amounts aligned right
**Given** the pages
**When** they have loaded
**Then** every table cell whose text matches `^-?[0-9]+,[0-9]{2} €$`, and every input whose
label starts with `Summa`, has a computed `text-align` of `right` and a
`font-variant-numeric` that contains `tabular-nums`

### AC8: Totals table rows
**Given** Yhteenveto with `Ruoka` expanded
**When** the user looks at the table `Kuukaudet`
**Then** the row headers `Ruoka` and `Yhteensä` have `font-weight` 700, and the left edge
of the text `Leivät` is at least 16 px to the right of the left edge of the text `Ruoka`

### AC9: One button style
**Given** the Tuonti page and the Yhteenveto page
**When** they have loaded
**Then** the button `Tuo kuitit` and the link `Vie rivit (CSV)` have equal computed
`border-top-width`, `border-top-left-radius`, `padding-left`, `padding-top` and
`background-color`, and the background is not transparent

### AC10: Disabled button
**Given** the Tuonti page, with the button `Tuo kuitit` made disabled by the test (the app
disables it only while an import runs, which is too short to catch reliably)
**When** the user looks at it
**Then** its computed `cursor` is `not-allowed` and its `opacity` is below 1; with the
button enabled again, `cursor` is `pointer` and `opacity` is 1

### AC11: Error message style
**Given** Yhteenveto with the address `/yhteenveto?unit=month&from=2026-11&to=2026-10`
(refused by the backend)
**When** the message `Jakso on virheellinen.` shows
**Then** the paragraph has a `background-color` that differs from `body`'s, and a solid
left border of 4 px

### AC12: Notice style
**Given** Yhteenveto for the month of an unreviewed receipt
**When** the notice `Tarkistamattomia kuitteja jaksolla: …` shows
**Then** the paragraph has a solid 4 px left border and a `background-color` that differs
from `body`'s and from the error paragraph's of AC11

### AC13: Keyboard focus
**Given** the Tuotteet page
**When** the user presses Tab until the link `Tuonti` has focus, and on the Tuonti page
until the button `Tuo kuitit` has focus
**Then** each has a computed `outline-style` of `solid`, an `outline-width` of at least
2 px and an `outline-color` equal to `--color-accent`

### AC14: Receipt page side by side on a wide window
**Given** a window of 1280 × 800 px and the receipt page
**When** it has loaded
**Then** the right edge of the receipt image is left of the left edge of the table
`Kuittirivit`, and their top edges differ by at most 1 px

### AC15: Receipt page stacked on a narrow window
**Given** a window of 800 × 800 px and the receipt page
**When** it has loaded
**Then** the bottom edge of the receipt image is above the top edge of the table
`Kuittirivit`

### AC16: Accessibility check of every page
**Given** each of the pages, and Yhteenveto also in the error state of AC11
**When** axe runs with the tags `wcag2a`, `wcag2aa`, `wcag21a` and `wcag21aa`
**Then** it reports no violations (`violations` is `[]`)

## Files to Modify

Refined by the Plan.

| File | Change |
|---|---|
| `frontend/src/styles.css` | New: custom properties and every rule (P1–P4) |
| `frontend/src/main.tsx` | Import the stylesheet once |
| `frontend/src/App.tsx` | Classes of the header and navigation (P3) |
| `frontend/src/components/ReceiptPage.tsx` (+ test) | Column classes instead of inline styles; table box; `amount` on the amount input (P3) |
| `frontend/src/components/TotalsTable.tsx` (+ test) | `amount` cells, row classes instead of the inline indent; table box (P3) |
| `frontend/src/components/TotalsPage.tsx` (+ test) | Download links with the `button` class instead of the inline style (P3) |
| `frontend/src/components/ReceiptsPage.tsx`, `ProductsPage.tsx` | Table box; `amount` cells (P3) |
| `frontend/src/components/EditableField.tsx`, `AddLineForm.tsx` | Optional `className` on the input, for `amount` (P3) |
| other `frontend/src/components/*.tsx` | Only fixes that axe finds (P5) |
| `frontend/package.json`, `frontend/package-lock.json` | `@axe-core/playwright` as a development dependency (P5) |
| `frontend/playwright.config.ts` | A `style` project that runs after the other E2E tests (P6) |
| `frontend/e2e/style.spec.ts` | New: AC1–AC16 (P6) |
| `frontend/e2e/synthetic.ts` | New: a valid synthetic PNG with unique bytes per run (P6) |
| `specs/PRD.md` | NFR-16; Resolved entry |
| `docs/subsystems/ui/README.md` | Styling section: the stylesheet, its custom properties, the class names; the accessibility check |
| `docs/development.md` | Style rules in the code standards; the axe check and the `style` project in the E2E section |
| `docs/architecture.md` | Tech stack: plain CSS |
| `docs/content-plan.md`, `specs/README.md` | Status, spec row |

## Risk
- **What could break:** a style can hide or overlap elements, so an existing E2E test that
  clicks them fails; a fix found by axe can change markup that tests query. The existing
  tests stay unchanged and must pass.
- **Rollback:** remove the stylesheet import from `main.tsx`; the app falls back to the
  browser's look. The markup fixes from axe stay valid without the stylesheet.
- **Dependencies:** `@axe-core/playwright` (development only, runs in the `e2e` container,
  makes no network calls). No backend change.

## Testing Strategy (MANDATORY)

Vitest does not apply the stylesheet in jsdom, so computed styles are checked in the E2E
tests in Chromium. Component tests check the markup.

### Unit tests
| AC | Function | Case | Given | When | Then | Mocks |
|---|---|---|---|---|---|---|
| AC1 | `TotalsPage`, `TotalsTable` | no inline style | totals of October with `Ruoka` expanded | render | no element with `style` | MSW totals |
| AC1 | `ReceiptPage` | no inline style | a receipt with lines | render | no element with `style` | MSW receipt |

### Integration tests
None: the backend does not change.

### E2E tests
In `frontend/e2e/style.spec.ts`, on a receipt it imports itself (a synthetic 1 × 1 PNG,
P6) and the E2E backend with the fakes; the `style` project runs after the other E2E tests.
| AC | Journey | Steps | Expected outcome |
|---|---|---|---|
| AC1, AC3, AC16 | every page | open each page; collect requests; check `[style]`; run axe | no inline style, only same-origin requests, no violations |
| AC2 | font | Tuotteet | AC2 values |
| AC4 | wide window | 1600 px, Kuitit | `main` content 1200 px, centred |
| AC5 | narrow window | 600 px, each page, 9-week Yhteenveto | no page scroll; `Viikot` scrolls in its box |
| AC6 | navigation | Kuitit | AC6 values |
| AC7 | amounts | each page with amounts | right aligned, tabular figures |
| AC8 | totals rows | Yhteenveto, expand `Ruoka` | bold rows, indent ≥ 16 px |
| AC9, AC10 | buttons | Tuonti and Yhteenveto; disable `Tuo kuitit` in the page | equal button styles; disabled and enabled look |
| AC11, AC12 | messages | refused period; unreviewed receipt's month | AC11, AC12 values |
| AC13 | keyboard | Tab on Tuotteet and Tuonti | AC13 outline |
| AC14, AC15 | receipt columns | 1280 px and 800 px | side by side; stacked |
| AC16 | error state | refused period, axe | no violations |

### Coverage target
- Backend: unchanged.
- Frontend: every changed component keeps its coverage; every AC has an E2E check.

### Test data
- Synthetic fixtures only: a generated 1 × 1 grey PNG (P6) and the fake OCR and model; MSW answers in the component tests.

## Related Documentation (MANDATORY)
- Tier 1: [architecture.md](../../docs/architecture.md),
  [development.md](../../docs/development.md#code-standards), [PRD](../PRD.md) (NFR-16)
- Tier 2: [ui](../../docs/subsystems/ui/README.md)
- Specs: [Category totals](totals.md) (tables), [CSV export](csv-export.md) (download
  links), [Receipt review](receipt-review.md) (receipt page columns)
- External: [WCAG 2.1](https://www.w3.org/TR/WCAG21/),
  [axe-core rule tags](https://github.com/dequelabs/axe-core/blob/develop/doc/API.md#axe-core-tags),
  [@axe-core/playwright](https://playwright.dev/docs/accessibility-testing)

## Plan

### P0 Overview

```
main.tsx  → import "./styles.css"        (Vite bundles it; no request to another host)
styles.css
  :root custom properties (P1)
  element rules: body, header, nav, main, table, th, td, button, input, select, p[role=…]
  class rules:   .amount .table-box .button .receipt-columns .receipt-image .row-group
                 .row-category .row-total
components → class names only; no style attribute
e2e/style.spec.ts (Playwright project "style", after the others) → computed styles + axe
```

Frontend only; no backend change, no migration. The only new dependency is
`@axe-core/playwright` (development). No ADR: NFR-16 records the choice of plain CSS, and
the rest follows the existing frontend conventions.

### P1 Custom properties and palette

Element rules first, classes only where an element rule cannot tell the cases apart. All
colors pass WCAG AA against the background they are used on (contrast computed with the
WCAG formula; axe checks the text colors in AC16).

| Property | Value | Use | Contrast |
|---|---|---|---|
| `--color-text` | `#1f2937` | body text | 14.7:1 on white |
| `--color-muted` | `#4b5563` | partial column headings, secondary text | 7.6:1 |
| `--color-bg` | `#ffffff` | page | — |
| `--color-surface` | `#f3f4f6` | header, button background | text 13.3:1; accent 6.1:1 |
| `--color-border` | `#6b7280` | inputs, buttons, header line of tables | 4.8:1 on white, 4.4:1 on the surface (non-text 3:1 met) |
| `--color-line` | `#e5e7eb` | row separators | decorative |
| `--color-accent` | `#1d4ed8` | links, current page line, focus outline | 6.7:1 |
| `--color-error-text`, `-bg`, `-border` | `#991b1b`, `#fef2f2`, `#dc2626` | error paragraph | 7.6:1 on its background |
| `--color-notice-text`, `-bg`, `-border` | `#78350f`, `#fffbeb`, `#d97706` | notice paragraph | 8.8:1 |
| `--space-1`, `-2`, `-3`, `-4` | `4px`, `8px`, `16px`, `24px` | gaps and padding | — |
| `--radius` | `4px` | buttons, inputs, messages | — |
| `--content-width` | `1200px` | `main` | — |
| `--font` | `system-ui, "Segoe UI", Roboto, sans-serif` | `body` | — |

### P2 Element rules

- `body`: margin 0, `font-family: var(--font)`, `line-height: 1.5`, colors from P1.
- `header`: `--color-surface` background, a bottom line, padding; `display: flex`,
  `flex-wrap: wrap`, `align-items: center`, `gap`; on `min-width: 900px` the title, the
  navigation and the status line fit one row (the status line pushed right with
  `margin-left: auto`).
- `nav a`: accent color, `font-weight: 400`, no bottom border, padding;
  `nav a[aria-current="page"]`: `font-weight: 700`,
  `border-bottom: 3px solid var(--color-accent)` (AC6).
- `main`: `max-width: var(--content-width)`, `margin: 0 auto`, padding,
  `box-sizing: border-box`; AC4 measures the `main` element's box.
- `table`: `border-collapse: collapse`; `th`, `td`: padding, `text-align: left`,
  `vertical-align: middle`; `thead th`: bold, `border-bottom: 2px solid var(--color-border)`;
  `tbody tr`: `border-bottom: 1px solid var(--color-line)`.
- `button` and `.button`: one rule (AC9): `--color-surface` background, `1px solid
  var(--color-border)`, `--radius`, padding `--space-1` `--space-3`, `font: inherit`,
  `color: var(--color-text)`, `cursor: pointer`, `text-decoration: none`,
  `display: inline-block`; `:hover` a darker surface; `button:disabled`: `opacity: 0.5`,
  `cursor: not-allowed` (AC10).
- `input:not([type="checkbox"])`, `select`: the same border, radius, padding and font as a
  button, so they line up (PC6).
- `:focus-visible`: `outline: 2px solid var(--color-accent)`, `outline-offset: 2px` (AC13).
- `main p[role="alert"]`: error colors, `border-left: 4px solid`, padding, `--radius`
  (AC11). `main p[role="status"]`: notice colors, the same shape (AC12).
  `span[role="alert"]`: error text color only. The header's status line is a `div`, so
  these rules do not reach it.
- `img`: `display: block`, `max-width: 100%`, `height: auto` (block, so the image's top
  lines up with the lines table, AC14).

### P3 Class names in the components

- `.amount`: `text-align: right`, `font-variant-numeric: tabular-nums` (AC7). On the
  amount `td` and `th` of `TotalsTable` (every column after the first) and of
  `ReceiptsPage` (`Loppusumma` column), and on the amount inputs: `EditableField` and the
  `Summa` input of `AddLineForm` get an optional `className` prop. The `Summa` heading of
  the lines table gets it too, so heading and values line up.
- `.table-box`: `overflow-x: auto`, `max-width: 100%`; a `div` around each of the five
  tables, so a wide table scrolls inside it (AC5). It adds no role; the tables keep their
  names, so the tests that find them by role do not change. If axe asks for keyboard
  access to a scrolling box (`scrollable-region-focusable`), the box gets `tabIndex={0}`
  and the table's name as `aria-label` (P5 rule).
- `TotalsTable`: `.row-group` and `.row-total` (bold) on those rows, `.row-category` on a
  category row. The group's toggle has a fixed width (`2.5em`), and a category's `th` is
  indented by the cell padding, the toggle, its margin and `--space-4`, so its name starts
  at least 16 px right of the group's name (AC8). The toggle stays a button with the
  button style.
- `ReceiptPage`: `.receipt-columns` holds `.receipt-image` and `.receipt-lines`. By
  default they stack (`display: block`, the image column with a bottom margin); on
  `min-width: 900px` the holder is a grid `minmax(0, 1fr) minmax(0, 2fr)` (was `2fr 3fr`, changed 2026-11-02, see `docs/learnings.md`) with
  `align-items: start` (AC14, AC15). The image's inline `maxWidth` moves to the `img`
  rule.
- `TotalsPage`: the three download links get the `button` class; the inline style object
  is removed.
- `App`: no class needed; the element rules of P2 cover the header and navigation.

### P4 Rules for later changes

`docs/development.md` code standards get: style lives in `styles.css`; no `style`
attribute; colors and spacing only through the custom properties; prefer element and
ARIA-state selectors (`[aria-current]`, `[role="alert"]`, `:disabled`) over new classes;
a new class is named after what it is (`amount`), not how it looks.

### P5 Accessibility check (axe)

- `@axe-core/playwright` is added to `devDependencies` with an exact version (the current
  release at install time), as the other development dependencies are pinned. It runs in
  the `e2e` container only and makes no network calls.
- `new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
  .analyze()`; the test expects `violations` to equal `[]`, and on failure prints each
  violation's rule id and target selector.
- The first run of AC16 lists the violations of today's markup. Each is fixed in the
  stylesheet or with markup that changes no visible text, label or behavior (for example
  an `aria-label` on a table box, a `scope` on a header cell). A fix that would change a
  text or behavior stops the work: the spec is changed first and the user asked.

### P6 E2E tests

- `frontend/e2e/synthetic.ts`: `syntheticPng(tag)` returns a valid 1 × 1 grey PNG with a
  `tEXt` chunk holding `tag`, so each run has a new image hash; built from a constant
  base64 PNG, no image library. The fake reader returns `FAKE_RECEIPT` for any image, and
  the browser can show this one (AC14, AC15 measure the `img`).
- `playwright.config.ts`: two projects, `chromium` (every spec except `style.spec.ts`)
  and `style` (only `style.spec.ts`, `dependencies: ["chromium"]`). So the style tests
  start after the import journeys: they do not run an import at the same time, and
  `import.spec.ts`'s cleanup of the import folder cannot remove their file. The command
  stays `docker compose --profile e2e run --rm e2e`.
- `style.spec.ts` `beforeAll`: writes `kuitti-<run>_tyyli.png`, runs `Tuo kuitit`, waits
  for `Tuotu: 1`, and opens the newest receipt dated 5.10.2026 to learn its address. The
  receipt stays unreviewed (AC12 uses October 2026).
- Helpers: `css(locator, property)` reads `getComputedStyle`; `accent(page)` reads
  `--color-accent` from `:root` and converts it to the `rgb(...)` form the browser
  returns; `pages` lists the five pages of the ACs with how to open each (Yhteenveto
  opens `unit=month&from=2026-10&to=2026-10` and expands `Ruoka`).
- Requests (AC3) are collected with `page.on("request")` from the first navigation on;
  each URL's origin must be `http://127.0.0.1:5173` (the Vite dev server, which also
  serves `/api` through its proxy).
- Component tests (AC1) render `TotalsPage`, `TotalsTable` and `ReceiptPage` with MSW
  answers and expect `container.querySelectorAll("[style]")` to be empty.

### P7 AC check

| AC | Covered by |
|---|---|
| AC1 | P3 (no style attribute), P6 component and E2E tests |
| AC2 | P1 `--font`, `--color-accent` |
| AC3 | P0 (bundled CSS, system font), P6 request check |
| AC4 | P2 `main` |
| AC5 | P3 `.table-box`, P2 `header` wrap |
| AC6 | P2 `nav a` rules |
| AC7 | P3 `.amount` |
| AC8 | P3 `TotalsTable` row classes |
| AC9, AC10 | P2 `button`, `.button`, `:disabled` |
| AC11, AC12 | P2 message rules |
| AC13 | P2 `:focus-visible` |
| AC14, AC15 | P3 `.receipt-columns` |
| AC16 | P5 |

### P8 Decisions (no ADR needed)

- Element and ARIA-state selectors before classes: the markup already says what an element
  is, so the stylesheet follows the semantics, and a component gains few classes.
- A Playwright project dependency instead of a shared lock: the style tests need an import
  of their own, and the import journeys clean the import folder; running after them is the
  simplest order that cannot race.
- A neutral palette with one blue accent: calm for a data-heavy page, and every text color
  above 4.5:1.

## Tasks

Each task is one Red → Green → Refactor cycle (or a few small ones) and ends with the
frontend tests, lint, format check (of the changed files) and type check. The existing
component and E2E tests stay unchanged and green throughout.

### Setup

- [x] **T1 axe and the style project** (AC16 setup). Add `@axe-core/playwright` (exact
  version) to `devDependencies`; `playwright.config.ts` projects `chromium` and `style`
  (P6); `e2e/synthetic.ts` `syntheticPng(tag)`; `e2e/style.spec.ts` with the `beforeAll`
  import and the helpers. Check: the E2E run still passes, and a first style test that
  only opens the imported receipt passes.

### Markup (component tests)

- [x] **T2 No inline styles** (AC1). Red: component tests for `TotalsPage`, `TotalsTable`
  and `ReceiptPage` expecting no `[style]`. Green: the classes of P3 (`button` on the
  download links, row classes in `TotalsTable`, `.receipt-columns` in `ReceiptPage`)
  replacing the inline styles.
- [x] **T3 Amount and table classes** (AC5, AC7, AC8 markup). `.amount` cells and
  headings, the `className` prop of `EditableField` and `AddLineForm`, `.table-box`
  around the five tables. Component tests stay green; no new component test (the classes
  are style, checked in E2E).

### Stylesheet (E2E)

- [x] **T4 Stylesheet, font, origin, no inline style** (AC1, AC2, AC3). Red: E2E checks of
  the pages. Green: `styles.css` with the P1 custom properties and the `body` rule,
  imported in `main.tsx`.
- [x] **T5 Layout** (AC4, AC5). Red: the 1600 px and 600 px checks. Green: `main`,
  `header` and `.table-box` rules.
- [x] **T6 Navigation** (AC6). Red, then the `nav a` rules.
- [x] **T7 Tables and amounts** (AC7, AC8). Red, then the table, `.amount` and row rules.
- [x] **T8 Buttons and inputs** (AC9, AC10). Red, then the `button`, `.button`,
  `:disabled` and input rules.
- [x] **T9 Messages** (AC11, AC12). Red, then the message rules.
- [x] **T10 Keyboard focus** (AC13). Red, then `:focus-visible`.
- [x] **T11 Receipt columns** (AC14, AC15). Red, then the `.receipt-columns` rules.

### Accessibility

- [x] **T12 axe on every page** (AC16). Red: axe on the five pages and the error state;
  list the violations. Green: fix each (P5 rule; stop and ask if a fix would change a
  text, label or behavior). Record the fixed rule ids in the UI README.

### Docs and closing

- [x] **T13 Docs.** UI README Styling section; `development.md` code standards and E2E
  section (the `style` project, axe); `architecture.md` tech stack; `content-plan.md`;
  `specs/README.md`.
- [x] **T14 Full check.** Every command in the AGENTS.md command table, including the E2E
  tests twice (the second on the kept database) and the container tests; `npm audit` for
  the new dependency. Then hand over to `review-audit`.

## Audit

Audited 2026-11-02 against this spec: **PASS**.

- Acceptance criteria 16/16 and PC1–PC10 met; every Testing Strategy row has a test
  (component tests for AC1, `frontend/e2e/style.spec.ts` for AC1–AC16).
- Tests: frontend 186 passed (coverage 98.7 % lines), E2E 23 passed on a fresh and on a
  kept database, container tests passed; ESLint and tsc clean; the changed files pass
  Prettier. The backend did not change.
- The axe test was checked to fail: with `--color-text` set to `#bbbbbb` it reported
  `color-contrast` on every page. The first axe run of the existing markup found no
  violation, so no markup changed for PC10.
- Security: no findings. The UI loads nothing from another host (AC3). `npm audit
  --omit=dev`: 0 vulnerabilities; the full `npm audit` lists the known moderate
  `minimatch` finding under the ESLint tooling (13 packages that depend on it), not
  `@axe-core/playwright`.
- Plan updated during implementation: the category indent counts the group toggle's fixed
  width (P3), and `img` is a block (P2), so AC8 and AC14 hold.
- Format check: files not touched by this spec fail `npm run format:check` because their
  working copies have CRLF line endings (`core.autocrlf=true`); the content in Git is fine.

# UI

Navigation: ↑ [Architecture](../../architecture.md) | → [API reference](../../api-reference.md) | → [Categorization](../categorization/README.md) | → [Import](../import/README.md) | → [Review](../review/README.md) | → [Totals](../totals/README.md) | → [Budget](../budget/README.md) | → [Storage](../storage/README.md) | → [Receipt reading](../receipt-reading/README.md)

## Overview

The UI is a React + Vite + TypeScript app in Finnish (NFR-15), opened at
<http://127.0.0.1:5173>. It shows what the API returns and holds no business rules.

It has the app shell (the heading `Kuittisovellus`, the navigation and a status line that
reports the backend's health) and seven pages: **Tuotteet** for groups, categories and
products, **Tuonti** for importing receipt images, **Kuitit** for the receipt list, the
**receipt page** for one receipt, **Yhteenveto** for the category totals, **Budjetti** for
the monthly budgets and **Vertailu** for the budget against spending. The app opens on
Tuotteet.

A few pages do not justify a router library. @frontend/src/navigation.ts maps the address to
a page and switches pages with the History API: `/tuonti` → Tuonti, `/kuitit` → Kuitit,
`/kuitit/<id>` (a positive number without leading zeros) → the receipt, any other
`/kuitit/...` → Kuitit, `/yhteenveto` → Yhteenveto, `/budjetti` → Budjetti, `/vertailu` →
Vertailu, any other path → Tuotteet. `usePage()` returns the page, `go(page,
receiptId?)` and the open receipt's id. The navigation links are real links (`/`, `/tuonti`,
`/kuitit`, `/yhteenveto`, `/budjetti`, `/vertailu`), and so are the date links of the list and the back link of a receipt; a plain
left click (`isPlainLeftClick`) is handled in the page without reloading, the current link
has `aria-current="page"` (Kuitit also on a receipt), the back button works, and a reload
keeps the page because Vite answers every path with `index.html`.

## Key Files and Entry Points

- @frontend/src/main.tsx — mounts `App` and imports the stylesheet
- @frontend/src/styles.css — the app's only stylesheet (see [Styling](#styling))
- @frontend/src/App.tsx — app shell: heading, navigation, status line, `<main>` with the
  current page
- @frontend/src/navigation.ts — `usePage()`, `pageFromPath()`, `PAGE_PATHS`
- @frontend/src/components/ImportPage.tsx — the Tuonti page: the "Tuo kuitit" button,
  progress, and the report of the latest run
- @frontend/src/components/ReceiptsPage.tsx — the Kuitit page: the `Uusi kuitti` button and
  form, and the receipt list
- @frontend/src/components/DateInput.tsx — a date as `dd.mm.yyyy` text with a calendar button;
  holds no state. A native date input shows the browser's format, so it stays only as the
  hidden calendar; only its native `change` event is a pick. With `pickerOnly` the text cannot be edited, and a click opens the calendar
- @frontend/src/components/NewReceiptForm.tsx — the `Uusi kuitti` form: store, date, total
  and a failed image with its preview
- @frontend/src/components/ReceiptPage.tsx — one receipt: editable store, date and total,
  review state, the `Poista kuitti` button of an unreviewed receipt, warning, image (or
  `Ei kuvaa.`) beside the editable line table (name, amount, deposit refund, category,
  delete), the add form, line sum and subtotals; one save queue
- @frontend/src/components/EditableField.tsx — an input that saves when it is left or on
  Enter, only when changed; Esc puts back the saved value; a refused save keeps the typed
  text and shows its message. With `type="date"` it uses `DateInput`, takes and saves
  `YYYY-MM-DD`, and sends no text that is not a real day
- @frontend/src/components/AddLineForm.tsx — the `Uusi rivi` form
- @frontend/src/components/TotalsPage.tsx — the Yhteenveto page: the period chooser, the
  three download links, the two counts and the two tables; owns the period and keeps it
  in the address
- @frontend/src/components/TotalsTable.tsx — one totals table (weeks or months): group rows
  that expand, categories, `Ei kategoriaa`, `Yhteensä`; partial column headings
- @frontend/src/components/BudgetPage.tsx — the Budjetti page: an amount field per budget
  row and the total
- @frontend/src/components/ComparisonPage.tsx — the Vertailu page: the period, the covered
  dates, the counts and the tables; owns the period and keeps it in the address
- @frontend/src/components/ComparisonTable.tsx — `ComparisonMonthTable` and
  `ComparisonWeekTable`, with the text `Ylitetty`
- @frontend/src/comparison.ts — the Vertailu period's address form and `currentComparison`
- @frontend/src/period.ts — the period's address form (`periodFromSearch`,
  `periodToSearch`), `currentMonth`, `currentWeek` (ISO), `weekLabel`, `monthLabel`,
  `columnHeading`, `currentMonthRange`
- @frontend/src/api/budget.ts — `getBudget()`, `saveBudget()`, `getComparison()` and their
  types
- @frontend/src/api/totals.ts — `getTotals()` and the `Totals` types
- @frontend/src/api/export.ts — `exportUrl(kind, period)`: the download URLs of the
  [export](../export/README.md)
- @frontend/src/components/StatusLine.tsx — reads the health on mount and every 30 seconds
- @frontend/src/components/ProductsPage.tsx — the Tuotteet page: search, filter, add form,
  product table; loads the lists and reloads them after every successful change
- @frontend/src/components/CategoryPanel.tsx — groups with their categories, then the
  ungrouped ones; add, rename, move, convert and delete
- @frontend/src/components/CategorySelect.tsx — category dropdown with groups as `optgroup`
  headings that cannot be chosen; the filter variant adds `Kaikki` and whole groups
- @frontend/src/components/ConfirmDelete.tsx — delete button that asks `Poistetaanko?` in
  place; no browser dialog; an optional `label` names the first button (`Poista kuitti`)
  and `disabled` turns it off
- @frontend/src/api/client.ts — shared API client (`apiGet`, `apiPost`, `apiPatch`,
  `apiPut`, `apiDelete`)
- @frontend/src/api/health.ts — `getHealth()` and the `Health` type
- @frontend/src/api/catalog.ts — typed catalog client and the `CatalogItem` and `Product`
  types
- @frontend/src/api/imports.ts — `getImport()`, `startImport()` and the `ImportState` type
- @frontend/src/api/receipts.ts — `listReceipts()`, `getReceipt()`, `editLine()`,
  `addLine()`, `deleteLine()`, `editReceipt()`, `setLineCategory()`, `setReviewed()`,
  `receiptImageUrl()`, `createReceipt()`, `deleteReceipt()`, `failedImages()`,
  `failedImageUrl()` and the receipt types
- @frontend/src/format.ts — `formatCents()` (`-40` → `-0,40 €`, no thousands separator),
  `formatCentsInput()` (`-40` → `-0,40`, an amount field's value), `dateToText()`
  (`2026-10-05` → `05.10.2026`), `parseDateText()` (`5.10.2026` → `2026-10-05`, or null),
  `formatDayMonth()`
  (`2026-10-01` → `1.10.`), `parseCents()` (`1,25` or
  `1.25` → `125`, `null` for anything else) and `formatDate()` (`2026-10-05` → `5.10.2026`),
  with integer arithmetic and string splitting only
- @frontend/src/i18n/fi.ts — every Finnish UI text
- @frontend/index.html — `lang="fi"`, title `Kuittisovellus`

## Interfaces

`apiGet<T>(path)`, `apiPost<T>(path, body)`, `apiPatch<T>(path, body)`,
`apiPut<T>(path, body)` and `apiDelete(path)` return `{ok: true, data}` or `{ok: false, error: {code, message}}`
(`data` is `undefined` for a 204). An
error response in the [API error format](../../api-reference.md#error-format) keeps its code
and Finnish message. A failed request, or an answer that is not in that format (the Vite
proxy answers that way when the backend is down), gives code `network_error` with
`Taustapalveluun ei saada yhteyttä.`

On the Tuotteet page, each action keeps its own error and shows the backend's `message`
beside the item or form that caused it (`role="alert"`); the lists stay as they were. A list
that cannot be loaded shows its error at the top of the page; "Lisää ensin kategoria." is
shown only after the categories loaded and there were none. A filter whose item was deleted,
or an add-form choice whose item was deleted or turned into a group, falls back to no choice.

The status line shows one text per failing check, in this order: model, OCR, folders,
database; `Kaikki palvelut toiminnassa` when all are `ok`; and the error message when the
health cannot be read. It is empty until the first answer arrives. The texts are in the
foundation spec, PC10.

On the Tuonti page, the state of the latest run is loaded when the page opens. While it is
`running`, the page asks for it again 1 second after each answer, so requests never overlap,
and stops when the page closes. A start that is refused (409, 503) or cannot reach the
backend shows the message next to the button with `role="alert"`; the shown report stays.
That includes a start refused because OCR or the model is unavailable. A failed poll shows
the same alert and polling goes on. A run that stopped because the model was lost shows the
backend's `stopped.message` in the report with `role="status"`. Failure items show the
backend's message, so new reasons need no UI change. The texts are in the
[receipt import spec](../../../specs/features/receipt-import.md#ui-texts-tuonti-page) and the
[receipt-reading spec](../../../specs/features/receipt-reading.md#ui-texts-tuonti-page-added).

On the Kuitit page the list is loaded when the page opens; missing date, store and total
show `–`. A list that cannot be loaded shows the error with `role="alert"`.

The `Uusi kuitti` button above the list opens the new receipt form (receipt-management
PC11). The form loads the failed images when it opens, and a failed load shows its error beside
the select; the `Kuva` select offers `Ei kuvaa`
and then each failed image, and a chosen image shows its preview (`Valittu kuva`) from
`/api/failed-images/image?name=...`, or `Kuvaa ei voitu näyttää.` when it does not load. An
empty date or an unreadable total is refused without a request. A failed create keeps every
value and shows the backend's message. `Luo kuitti` is disabled while the request runs,
because a receipt without an image has no duplicate check. `Peruuta` unmounts the form, so it opens empty again.
After a create the new receipt's page opens.

The receipt page loads the receipt and the categories in parallel. The backend computes the
line sum, warning and subtotals; the page only shows them. The store, date (a [date field](../../glossary.md))
and total, and each line's name and amount, are `EditableField`s; a missing value is an empty
input. Each line also has a deposit refund checkbox, its category and a delete button that
asks first (`ConfirmDelete`); the `Uusi rivi` form under the table adds a line. Every change
sends one request, and the page shows the receipt from the answer, so subtotals, marks,
warning and other lines of the same product update without a reload (FR-19).

An unreviewed receipt has a `Poista kuitti` button next to the review button; it asks
first (`ConfirmDelete`), runs in the save queue after any waiting change, and on success
calls `onBack`, which opens the list. The button is disabled until the answer arrives. A
failed delete keeps the page and shows the message
by the button. A receipt without an image (`file_name` `null`) shows `Ei kuvaa.` and the
page never requests its image.

Changes go through one queue (a promise chain in a `useRef`): each request starts after the
previous answer, so answers cannot arrive out of order, and no edit control is disabled, so
the user keeps the focus while a save waits; only `Poista kuitti` is, while the delete runs. An amount field accepts `1,25`, `1.25`, `-0,40` or
`3`; anything else shows `Anna summa muodossa 1,25.` without a request. A refused change
shows its message next to its field, checkbox, dropdown, delete button, the add button or
the confirmation button (`role="alert"`); a text field keeps the typed text until Esc, the
checkbox and dropdown show the saved value again, and the add form keeps its values. While
the categories load, or after they failed, a line shows its category as text
(`Ryhmä > Kategoria`, or `–`) instead of a dropdown. A model
suggestion shows the mark `ehdotus`; a deposit refund shows `Pantinpalautus` and no
dropdown. An image that cannot be loaded (the `img` gets an error, for example the 404
`image_missing`) is replaced by `Kuvaa ei löydy valmiiden kansiosta.`; the image and the
table sit side by side on a window at least 900 px wide and stack on a narrower one
(`.receipt-columns`). The texts are in the
[receipt review spec](../../../specs/features/receipt-review.md#ui-texts) and the
[line editing spec](../../../specs/features/line-editing.md#ui-texts).

The Budjetti page saves an amount with `EditableField` when the field is left or on Enter.
Text that is no amount shows `Anna summa muodossa 1,25.` and sends nothing; the backend
decides the limits. The answer of a save replaces the rows, so the total follows it. Saves
run one at a time, because every answer holds all rows and an older one must not arrive last.

The Vertailu page takes its period from the address (`/vertailu?month=2026-10`, or
`/vertailu?month=2026-10&period=mid` for the period from the 15th to the 14th), and writes
it back with `replaceState`. Without a valid month it opens the current period of the
address's kind: the calendar month, or with `period=mid` the current 15–14 period. An
unknown `period` opens the current calendar month. The page checks only the month's shape,
so a month the backend refuses, such as `9999-01`, shows the backend's error, and the
controls still work. The `Jakso` select chooses the kind and moves to the period of that kind that
holds today by the browser's local date, so `15.–14.` on 2026-11-06 selects `2026-10`. The
month input then chooses another period of the same kind. Each change pushes a history
entry, and the `Vertailu` link does nothing while the page is open. The week table is plain
state: it survives changes of period and sends no request, and a reload hides it.

The Yhteenveto page takes its period from the address (`/yhteenveto?unit=week&from=2026-W40&to=2026-W41`
or `/yhteenveto?unit=range&from=2026-10-15&to=2026-11-14`),
or the current month by the browser's local date when the address has no complete,
well-formed period, and writes it back with `replaceState`, so the address always shows the
period. Each change pushes a history entry, and `popstate` reads the period again, so the
back button returns to the previous period. The `Yhteenveto` link does nothing while the
page is open, so it cannot drop the period from the address. The chooser is a `Jakso` select (`Kuukausi`,
`Viikko`, `Aikaväli`) and two inputs, `Alkaen` and `Päättyen`. For a month or a week they
are native inputs whose values are the API's format; for `Aikaväli` they are calendar-only
date fields (`EditableField` with `type="date"` and `pickerOnly`), and a picked day loads
the totals. Changing the
unit sets both to the month or ISO week of today, or to the first and last day of this
month. An emptied input sends nothing. Only the answer to the latest request is shown. The backend
decides validity, so a refused period shows `Jakso on virheellinen.` (`role="alert"`). The
two tables share one set of expanded groups, so a group opens in both. The counts of
unreviewed and undated receipts show as `role="status"` when not 0. For a month or a week, Chrome and Edge show
pickers; Firefox shows text fields that accept the same text. The texts are
in the [totals spec](../../../specs/features/totals.md#ui-texts).

Under the chooser, three plain links with the `download` attribute, `Vie viikkosummat
(CSV)`, `Vie kuukausisummat (CSV)` and `Vie rivit (CSV)`, point at the export URLs of the
period whose totals are shown, not the draft; while a new period loads, they keep the
previous one, so the links and the tables always agree. The browser downloads the file itself, through the Vite proxy,
and takes its name from `Content-Disposition`. They are shown while the totals of the
period are loaded (also when it has no lines) and hidden while the period is refused or
the totals cannot be loaded. They have the `button` class. The texts are
in the [CSV export spec](../../../specs/features/csv-export.md#ui-texts).

### Styling

One plain CSS file, @frontend/src/styles.css, imported once in `main.tsx`, styles the whole
app (NFR-16, [styling spec](../../../specs/features/styling.md)). There is no CSS framework
and no `style` attribute in the components. Vite bundles the file, and the font is the
system font, so the UI loads nothing from another host.

- **Custom properties** on `:root` hold every color, space, the radius, the content width
  and the font: `--color-text`, `--color-muted`, `--color-bg`, `--color-surface`,
  `--color-surface-hover`,
  `--color-border`, `--color-line`, `--color-accent`, the error and notice colors,
  `--space-1` to `--space-4`, `--radius`, `--content-width`, `--font`. Every text color
  meets WCAG AA (4.5:1) on its background; the ratios are in the spec's Plan P1.
- **Element and state selectors first:** the header, `nav a[aria-current="page"]`, tables,
  `button`, inputs, `:focus-visible`, `button:disabled`, `main p[role="alert"]` (error),
  `main p[role="status"]` (notice), `span[role="alert"]` (inline error).
- **Classes**, only where the markup cannot tell the cases apart:

  | Class | Where | Does |
  |---|---|---|
  | `amount` | money cells and headings, amount inputs (`EditableField`'s `className`) | Right aligned, tabular figures |
  | `table-box` | a `div` around each table | A wide table scrolls inside it, not the page |
  | `button` | the download links | The button look |
  | `row-group`, `row-category`, `row-total` | totals table rows | Bold group and total rows; categories indented under the group name (the toggle has a fixed width) |
  | `receipt-columns`, `receipt-image`, `receipt-lines` | receipt page | Side by side from 900 px, stacked below |
  | `confirm-delete` | a line's delete confirmation | Keeps the question and its buttons on one row |
  | `new-receipt-preview` | new receipt form | Keeps the preview small, so the form's buttons stay in sight |

- `main` is at most 1200 px wide and centred; the header wraps on a narrow window.
- The input rule's `font` shorthand resets `font-variant-numeric`, so `input.amount` comes
  after it.

The E2E tests in @frontend/e2e/style.spec.ts check the computed styles in Chromium and run
axe on every page; jsdom in the component tests does not apply the stylesheet. The first
axe run of the existing markup found no WCAG 2.1 AA violation, so no markup changed for it.

## Data Flow

The browser loads the UI from Vite and calls `/api/...` on the same origin. Vite forwards
these calls to the backend container (`VITE_API_TARGET`, default `http://backend:8000`), so
the UI never needs the backend's port.

## Dependencies

- Uses: the backend through the [API](../../api-reference.md) only.
- Used by: the user.

## Modules

None yet.

## Known Issues and Gotchas

- Receipt fixtures (@frontend/src/test/receipts.ts) use the ids of `defaultItems()`, so a
  receipt page test answers `GET /api/categories` with `ITEMS` from the same file.

- Component tests mock the API with MSW at the network level (@frontend/src/test/); a request
  without a handler fails the test. MSW 3 calls this option `onUnhandledFrame`.
- `fakeCatalog(server)` in @frontend/src/test/catalog.ts is an in-memory catalog behind MSW,
  for components that write and then reload. It has none of the backend's rules. Add error
  answers with `server.use` **after** it, because MSW prefers the handlers added last.
- Category names appear both in the panel and in dropdown options; tests find the panel
  entry with the selector `[data-name]`.
- Tests that need the 30 second refresh fake only `setInterval` and `clearInterval`, so fetch
  and MSW keep their real timers.
- The Tuonti page tests use `vi.useFakeTimers({ shouldAdvanceTime: true })` and step the
  poll with `vi.advanceTimersByTimeAsync(1000)`; `userEvent` gets
  `advanceTimers: vi.advanceTimersByTime`.
- Tests that switch pages reset the address with `history.replaceState(null, "", "/")` in
  `beforeEach`, because jsdom keeps it between tests.
- The `node_modules` folder lives in a Docker volume; after a dependency change run
  `docker compose run --rm frontend npm ci` ([development.md](../../development.md#dependencies-and-lock-files)).

## Related Documents

- [Foundation spec](../../../specs/features/foundation.md) PC10
- [Product management spec](../../../specs/features/product-management.md) PC9
- [Receipt import spec](../../../specs/features/receipt-import.md) PC11
- [Receipt-reading spec](../../../specs/features/receipt-reading.md) PC9
- [Receipt review spec](../../../specs/features/receipt-review.md) PC7–PC10
- [Line editing spec](../../../specs/features/line-editing.md)
- [Receipt deletion and manual receipts spec](../../../specs/features/receipt-management.md) PC11
- [Category totals spec](../../../specs/features/totals.md) PC4–PC7
- [CSV export spec](../../../specs/features/csv-export.md) PC6
- [Visual style and accessibility spec](../../../specs/features/styling.md)
- [development.md](../../development.md#code-standards): TypeScript and React rules

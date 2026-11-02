# UI

Navigation: ↑ [Architecture](../../architecture.md) | → [API reference](../../api-reference.md) | → [Categorization](../categorization/README.md) | → [Import](../import/README.md) | → [Review](../review/README.md) | → [Totals](../totals/README.md) | → [Storage](../storage/README.md) | → [Receipt reading](../receipt-reading/README.md)

## Overview

The UI is a React + Vite + TypeScript app in Finnish (NFR-15), opened at
<http://127.0.0.1:5173>. It shows what the API returns and holds no business rules.

It has the app shell (the heading `Kuittisovellus`, the navigation and a status line that
reports the backend's health) and five pages: **Tuotteet** for groups, categories and
products, **Tuonti** for importing receipt images, **Kuitit** for the receipt list, the
**receipt page** for one receipt, and **Yhteenveto** for the category totals. The app opens
on Tuotteet.

A few pages do not justify a router library. @frontend/src/navigation.ts maps the address to
a page and switches pages with the History API: `/tuonti` → Tuonti, `/kuitit` → Kuitit,
`/kuitit/<id>` (a positive number without leading zeros) → the receipt, any other
`/kuitit/...` → Kuitit, `/yhteenveto` → Yhteenveto, any other path → Tuotteet. `usePage()` returns the page, `go(page,
receiptId?)` and the open receipt's id. The navigation links are real links (`/`, `/tuonti`,
`/kuitit`), and so are the date links of the list and the back link of a receipt; a plain
left click (`isPlainLeftClick`) is handled in the page without reloading, the current link
has `aria-current="page"` (Kuitit also on a receipt), the back button works, and a reload
keeps the page because Vite answers every path with `index.html`.

## Key Files and Entry Points

- @frontend/src/main.tsx — mounts `App`
- @frontend/src/App.tsx — app shell: heading, navigation, status line, `<main>` with the
  current page
- @frontend/src/navigation.ts — `usePage()`, `pageFromPath()`, `PAGE_PATHS`
- @frontend/src/components/ImportPage.tsx — the Tuonti page: the "Tuo kuitit" button,
  progress, and the report of the latest run
- @frontend/src/components/ReceiptsPage.tsx — the Kuitit page: the receipt list
- @frontend/src/components/ReceiptPage.tsx — one receipt: editable store, date and total,
  review state, warning, image beside the editable line table (name, amount, deposit refund,
  category, delete), the add form, line sum and subtotals; one save queue
- @frontend/src/components/EditableField.tsx — an input that saves when it is left or on
  Enter, only when changed; Esc puts back the saved value; a refused save keeps the typed
  text and shows its message
- @frontend/src/components/AddLineForm.tsx — the `Uusi rivi` form
- @frontend/src/components/TotalsPage.tsx — the Yhteenveto page: the period chooser, the
  three download links, the two counts and the two tables; owns the period and keeps it
  in the address
- @frontend/src/components/TotalsTable.tsx — one totals table (weeks or months): group rows
  that expand, categories, `Ei kategoriaa`, `Yhteensä`; partial column headings
- @frontend/src/period.ts — the period's address form (`periodFromSearch`,
  `periodToSearch`), `currentMonth`, `currentWeek` (ISO), `weekLabel`, `monthLabel`
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
  place; no browser dialog
- @frontend/src/api/client.ts — shared API client (`apiGet`, `apiPost`, `apiPatch`,
  `apiDelete`)
- @frontend/src/api/health.ts — `getHealth()` and the `Health` type
- @frontend/src/api/catalog.ts — typed catalog client and the `CatalogItem` and `Product`
  types
- @frontend/src/api/imports.ts — `getImport()`, `startImport()` and the `ImportState` type
- @frontend/src/api/receipts.ts — `listReceipts()`, `getReceipt()`, `editLine()`,
  `addLine()`, `deleteLine()`, `editReceipt()`, `setLineCategory()`, `setReviewed()`,
  `receiptImageUrl()` and the receipt types
- @frontend/src/format.ts — `formatCents()` (`-40` → `-0,40 €`, no thousands separator),
  `formatCentsInput()` (`-40` → `-0,40`, an amount field's value), `formatDayMonth()`
  (`2026-10-01` → `1.10.`), `parseCents()` (`1,25` or
  `1.25` → `125`, `null` for anything else) and `formatDate()` (`2026-10-05` → `5.10.2026`),
  with integer arithmetic and string splitting only
- @frontend/src/i18n/fi.ts — every Finnish UI text
- @frontend/index.html — `lang="fi"`, title `Kuittisovellus`

## Interfaces

`apiGet<T>(path)`, `apiPost<T>(path, body)`, `apiPatch<T>(path, body)` and
`apiDelete(path)` return `{ok: true, data}` or `{ok: false, error: {code, message}}`
(`data` is `undefined` for a 204). An
error response in the [API error format](../../api-reference.md#error-format) keeps its code
and Finnish message. A failed request, or an answer that is not in that format (the Vite
proxy answers that way when the backend is down), gives code `network_error` with
`Taustapalveluun ei saada yhteyttä.`

On the Tuotteet page, each action keeps its own error and shows the backend's `message`
beside the item or form that caused it (`role="alert"`); the lists stay as they were. A list
that cannot be loaded shows its error at the top of the page; "Lisää ensin kategoria." is
shown only after the categories loaded and there were none. A filter or an add-form choice
whose item was deleted, or turned into a group, falls back to no choice.

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

The receipt page loads the receipt and the categories in parallel. The backend computes the
line sum, warning and subtotals; the page only shows them. The store, date (a date input)
and total, and each line's name and amount, are `EditableField`s; a missing value is an empty
input. Each line also has a deposit refund checkbox, its category and a delete button that
asks first (`ConfirmDelete`); the `Uusi rivi` form under the table adds a line. Every change
sends one request, and the page shows the receipt from the answer, so subtotals, marks,
warning and other lines of the same product update without a reload (FR-19).

Changes go through one queue (a promise chain in a `useRef`): each request starts after the
previous answer, so answers cannot arrive out of order, and no control is disabled, so the
user keeps the focus while a save waits. An amount field accepts `1,25`, `1.25`, `-0,40` or
`3`; anything else shows `Anna summa muodossa 1,25.` without a request. A refused change
shows its message next to its field, checkbox, dropdown, delete button, the add button or
the confirmation button (`role="alert"`); a text field keeps the typed text until Esc, the
checkbox and dropdown show the saved value again, and the add form keeps its values. While
the categories load, or after they failed, a line shows its category as text
(`Ryhmä > Kategoria`, or `–`) instead of a dropdown. A model
suggestion shows the mark `ehdotus`; a deposit refund shows `Pantinpalautus` and no
dropdown. An image that cannot be loaded (the `img` gets an error, for example the 404
`image_missing`) is replaced by `Kuvaa ei löydy valmiiden kansiosta.`; the image and the
table sit side by side through inline flex styles that wrap on a narrow window, since the
app has no stylesheet. The texts are in the
[receipt review spec](../../../specs/features/receipt-review.md#ui-texts) and the
[line editing spec](../../../specs/features/line-editing.md#ui-texts).

The Yhteenveto page takes its period from the address (`/yhteenveto?unit=week&from=2026-W40&to=2026-W41`),
or the current month by the browser's local date when the address has no complete,
well-formed period, and writes it back with `replaceState`, so the address always shows the
period. Each change pushes a history entry, and `popstate` reads the period again, so the
back button returns to the previous period. The `Yhteenveto` link does nothing while the
page is open, so it cannot drop the period from the address. The chooser is a `Jakso` select (`Kuukausi`,
`Viikko`) and two native `month` or `week` inputs, `Alkaen` and `Päättyen`, whose values
are the API's format; changing the unit sets both to the month or ISO week of today. An
emptied input sends nothing. Only the answer to the latest request is shown. The backend
decides validity, so a refused period shows `Jakso on virheellinen.` (`role="alert"`). The
two tables share one set of expanded groups, so a group opens in both. The counts of
unreviewed and undated receipts show as `role="status"` when not 0. Chrome and Edge show
pickers for the inputs; Firefox shows text fields that accept the same text. The texts are
in the [totals spec](../../../specs/features/totals.md#ui-texts).

Under the chooser, three plain links with the `download` attribute, `Vie viikkosummat
(CSV)`, `Vie kuukausisummat (CSV)` and `Vie rivit (CSV)`, point at the export URLs of the
period whose totals are shown, not the draft; while a new period loads, they keep the
previous one, so the links and the tables always agree. The browser downloads the file itself, through the Vite proxy,
and takes its name from `Content-Disposition`. They are shown while the totals of the
period are loaded (also when it has no lines) and hidden while the period is refused or
the totals cannot be loaded. They look like buttons through an inline style. The texts are
in the [CSV export spec](../../../specs/features/csv-export.md#ui-texts).

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
- [Category totals spec](../../../specs/features/totals.md) PC4–PC7
- [CSV export spec](../../../specs/features/csv-export.md) PC6
- [development.md](../../development.md#code-standards): TypeScript and React rules

# UI

Navigation: ↑ [Architecture](../../architecture.md) | → [API reference](../../api-reference.md) | → [Categorization](../categorization/README.md) | → [Import](../import/README.md) | → [Storage](../storage/README.md) | → [Receipt reading](../receipt-reading/README.md)

## Overview

The UI is a React + Vite + TypeScript app in Finnish (NFR-15), opened at
<http://127.0.0.1:5173>. It shows what the API returns and holds no business rules.

It has the app shell (the heading `Kuittisovellus`, the navigation and a status line that
reports the backend's health) and two pages: **Tuotteet** for groups, categories and
products, and **Tuonti** for importing receipt images. The app opens on Tuotteet.

Two pages do not justify a router library. @frontend/src/navigation.ts maps the address to a
page (`/tuonti` → Tuonti, any other path → Tuotteet) and switches pages with the History API.
The navigation links are real links (`/` and `/tuonti`); a plain left click is handled in the
page without reloading, the current link has `aria-current="page"`, the back button works,
and a reload keeps the page because Vite answers every path with `index.html`.

## Key Files and Entry Points

- @frontend/src/main.tsx — mounts `App`
- @frontend/src/App.tsx — app shell: heading, navigation, status line, `<main>` with the
  current page
- @frontend/src/navigation.ts — `usePage()`, `pageFromPath()`, `PAGE_PATHS`
- @frontend/src/components/ImportPage.tsx — the Tuonti page: the "Tuo kuitit" button,
  progress, and the report of the latest run
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
- [development.md](../../development.md#code-standards): TypeScript and React rules

# UI

Navigation: ↑ [Architecture](../../architecture.md) | → [API reference](../../api-reference.md) | → [Categorization](../categorization/README.md) | → [Storage](../storage/README.md) | → [Receipt reading](../receipt-reading/README.md)

## Overview

The UI is a React + Vite + TypeScript app in Finnish (NFR-15), opened at
<http://127.0.0.1:5173>. It shows what the API returns and holds no business rules.

It has the app shell (the heading `Kuittisovellus`, the navigation and a status line that
reports the backend's health) and one page, **Tuotteet**, for groups, categories and
products. With one page there is no router: the navigation has one link, marked as the
current page, and the page is always shown. The first spec with a second page adds a
router.

## Key Files and Entry Points

- @frontend/src/main.tsx — mounts `App`
- @frontend/src/App.tsx — app shell: heading, navigation, status line, `<main>`
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
- The `node_modules` folder lives in a Docker volume; after a dependency change run
  `docker compose run --rm frontend npm ci` ([development.md](../../development.md#dependencies-and-lock-files)).

## Related Documents

- [Foundation spec](../../../specs/features/foundation.md) PC10
- [Product management spec](../../../specs/features/product-management.md) PC9
- [development.md](../../development.md#code-standards): TypeScript and React rules

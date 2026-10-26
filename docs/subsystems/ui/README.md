# UI

Navigation: ↑ [Architecture](../../architecture.md) | → [API reference](../../api-reference.md) | → [Storage](../storage/README.md) | → [Receipt reading](../receipt-reading/README.md)

## Overview

The UI is a React + Vite + TypeScript app in Finnish (NFR-15), opened at
<http://127.0.0.1:5173>. It shows what the API returns and holds no business rules.

Today it has the app shell: the heading `Kuittisovellus`, an empty navigation area that
feature specs fill (first: `Tuotteet`), and a status line that reports the backend's health.

## Key Files and Entry Points

- @frontend/src/main.tsx — mounts `App`
- @frontend/src/App.tsx — app shell: heading, navigation, status line, `<main>`
- @frontend/src/components/StatusLine.tsx — reads the health on mount and every 30 seconds
- @frontend/src/api/client.ts — shared API client (`apiGet`)
- @frontend/src/api/health.ts — `getHealth()` and the `Health` type
- @frontend/src/i18n/fi.ts — every Finnish UI text
- @frontend/index.html — `lang="fi"`, title `Kuittisovellus`

## Interfaces

`apiGet<T>(path)` returns `{ok: true, data}` or `{ok: false, error: {code, message}}`. An
error response in the [API error format](../../api-reference.md#error-format) keeps its code
and Finnish message. A failed request, or an answer that is not in that format (the Vite
proxy answers that way when the backend is down), gives code `network_error` with
`Taustapalveluun ei saada yhteyttä.`

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
- Tests that need the 30 second refresh fake only `setInterval` and `clearInterval`, so fetch
  and MSW keep their real timers.
- The `node_modules` folder lives in a Docker volume; after a dependency change run
  `docker compose run --rm frontend npm ci` ([development.md](../../development.md#dependencies-and-lock-files)).

## Related Documents

- [Foundation spec](../../../specs/features/foundation.md) PC10
- [development.md](../../development.md#code-standards): TypeScript and React rules

# API Reference

- **Status:** In Progress (health endpoint and error format; feature endpoints are added by
  their specs)
- **Updated:** 2026-10-26

## Overview

The backend serves a JSON REST API under `/api`. It listens only on `127.0.0.1` (default
port `8000`). There is no login: the app is local and single-user.

The UI calls the API on its own origin (`http://127.0.0.1:5173/api/...`); the Vite dev
server forwards these requests to the backend. CORS allows only
`http://127.0.0.1:<RRMC_UI_PORT>`.

Each request is logged as one line with method, path, status and duration. Query strings and
bodies are never logged.

## Error format

Every error response has this body:

```json
{"error": "<code>", "message": "<Finnish text for the user>"}
```

`error` is a stable `snake_case` code for programs; `message` is shown to the user as is.
Messages come from @backend/app/texts.py and never contain receipt content.

| Status | `error` | `message` | When |
|---|---|---|---|
| 404 | `not_found` | `Pyydettyä kohdetta ei löydy.` | Unknown `/api/...` path, or an id that does not exist |
| 422 | `invalid_request` | `Pyyntö on virheellinen.` | Body or parameters not valid, including a body that is not JSON |
| 500 | `internal_error` | `Odottamaton virhe. Katso lisätiedot palvelimen lokista.` | Unexpected error; the stack trace is in the backend log |

Feature specs add their own codes in the same format, raised as `AppError`
(@backend/app/errors.py).

## Endpoints

### GET /api/health

Reports whether the backend's dependencies are available. The checks run on every request,
so a service started later (for example Ollama) is noticed without a restart. The answer
comes within 3 seconds even when Ollama does not answer. The status is always 200; problems
are reported in the body.

Response `200`:

```json
{
  "status": "ok",
  "model_name": "qwen2.5:7b",
  "checks": {"database": "ok", "folders": "ok", "ocr": "ok", "model": "ok"}
}
```

| Field | Values | Meaning |
|---|---|---|
| `status` | `ok`, `degraded` | `ok` when every check is `ok` |
| `model_name` | text | The `RRMC_MODEL` setting |
| `checks.database` | `ok`, `unavailable` | The database file exists and can be read |
| `checks.folders` | `ok`, `unavailable` | The import, done and failed folders exist and can be written to |
| `checks.ocr` | `ok`, `unavailable` | Tesseract runs and has the `fin` and `eng` language data |
| `checks.model` | `ok`, `unavailable`, `missing_model` | `unavailable`: Ollama does not answer; `missing_model`: Ollama answers but has not pulled `RRMC_MODEL` |

A model listed by Ollama as `name:latest` matches `RRMC_MODEL=name`. When a health check
finds the model available and it has not been loaded yet, the backend asks Ollama to load it
and keep it loaded (FR-30). With `RRMC_ENGINES=fake`, `ocr` and `model` are always `ok` and
neither Tesseract nor Ollama is called.

Implemented in @backend/app/health/.

## Subsystems

- [ui](subsystems/ui/README.md) — the only client of the API

## Related Documents

- [architecture.md](architecture.md): dependency rules and cross-cutting rules
- [Foundation spec](../specs/features/foundation.md) PC5 and PC8
- [development.md](development.md#troubleshooting): what the health results mean for the user

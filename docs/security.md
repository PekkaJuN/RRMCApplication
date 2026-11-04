# Security

- **Status:** Done
- **Updated:** 2026-11-04

## Overview

Receipts are personal financial data. This document describes what data the app holds, how
it is protected, and what it does not protect against. The requirements are PRD
[NFR-1 to NFR-5](../specs/PRD.md#71-privacy-and-security). The working rules for developers
and agents are in [AGENTS.md](../AGENTS.md#privacy-and-security).

The app runs on one person's own computer. It protects receipt data from leaving that
computer. It does not protect data from someone who can already use the computer.

## Data the app holds

| Data | Where | Default location |
|---|---|---|
| Receipt images | Import, done and failed folders on this computer | `source/import`, `source/import_done`, `source/import_failed` |
| Receipts, lines, products, raw OCR text | SQLite database | Docker volume `rrmc_rrmc-data` |
| Evaluation images and results | Evaluation folder (development tool) | `source/eval` |
| CSV exports | Wherever the browser saves them | The user's download folder |
| Logs | Standard output of the containers | Docker's log of each container |
| Settings | `.env` file | Project root |

The app does not encrypt any of this. Protection at rest comes from the computer: its user
account and disk encryption.

## Network

- **Ports:** Compose publishes the backend and the UI on `127.0.0.1` only (`compose.yaml`), so
  other computers cannot reach them. Inside their containers they listen on `0.0.0.0`,
  because Docker's port mapping needs that.
- **Outgoing:** the backend's only external call is to Ollama at `RRMC_OLLAMA_URL`, on this
  computer. The call carries OCR text and product names over plain HTTP between the container
  and Windows.
- **Cloud models:** Ollama runs with `OLLAMA_NO_CLOUD=1`
  ([setup](development.md#setup)). The backend also refuses a model name that Ollama would
  run in its cloud service (`is_cloud_model` in @backend/app/engines/model.py), both when
  loading it and when an import starts.
- **Browser:** the UI loads nothing from another host. CORS allows only
  `http://127.0.0.1:<RRMC_UI_PORT>` (@backend/app/main.py).
- **Login:** there is none, by design ([PRD non-goals](../specs/PRD.md#3-non-goals)).

## Input handling

| Input | Protection |
|---|---|
| Request bodies | Strict: unknown fields, `null` and wrong types give `invalid_request` ([API reference](api-reference.md)) |
| Ids | An id outside SQLite's integer range counts as not existing |
| SQL | Values are bound as parameters; all SQL is in the storage package |
| File names of failed images | Only a plain name directly in the failed folder is accepted: no paths, no links out of the folder (@backend/app/review/failed_images.py) |
| Image files | The file's signature must match a JPEG or PNG; the images are served with `Cache-Control: no-store` |
| Model output | Validated against a schema; invalid output is a failure, not stored data (FR-8) |
| CSV cells | User text that Excel could run as a formula gets a leading `'` (@backend/app/export/csv_exporter.py) |

## Logs and errors

- A request logs its method, path, status and duration. The query string and the bodies are
  never logged (@backend/app/logging_setup.py). Uvicorn's own access log is off.
- Import errors log the error type and traceback frames, not the message, because a message
  can hold a file path (`log_without_message` in @backend/app/receipt_import/run.py).
- API errors return a fixed Finnish text and never the details of the exception.

See [known limits](#known-limits) for the one exception.

## Version control

`.gitignore` keeps `.env`, `source/`, SQLite files and `service_account*.json` out of the
repository. Tests use synthetic receipts only (NFR-12). The app has no secrets today. The
Google Sheets export will need a service-account key, stored outside the repository and
outside cloud-synced folders (NFR-5).

## Dependencies

Check the backend and frontend dependencies for known vulnerabilities:

```powershell
docker compose run --rm backend pip-audit
docker compose run --rm frontend npm audit --omit=dev
```

Both reported no known vulnerabilities on 2026-11-04.

## Known limits

Each limit was checked against the running code on 2026-11-04.

- **Anything on this computer can call the API.** There is no login, so any program running
  on the computer can read and change the data.
- **CORS does not stop every request.** It stops another site from reading answers, and it
  refuses the preflight of JSON, `PATCH` and `DELETE` requests. A request without a preflight
  still reaches the backend: a page on any site can start an import with `POST /api/import`.
  It cannot read the result, and it can only start what the button in the UI starts.
- **The backend does not check the `Host` header.** A malicious site could use DNS rebinding
  to appear as the same origin as the backend and read its answers. It needs the user to
  open that site while the app is running.
- **An unexpected error logs its message.** `_handle_unexpected_error` in
  @backend/app/errors.py logs the full exception, unlike the import errors above. The API
  answer stays clean, but a message that holds receipt content or a file name would reach
  the log, which goes against NFR-3.

## Related Documents

- [PRD](../specs/PRD.md): NFR-1 to NFR-5
- [Architecture](architecture.md): runtime and deployment, cross-cutting rules
- [API reference](api-reference.md): error format and request rules
- [Development guide](development.md): setup and commands
- [AGENTS.md](../AGENTS.md): guardrails, privacy and security rules
- [Content plan](content-plan.md): documentation index

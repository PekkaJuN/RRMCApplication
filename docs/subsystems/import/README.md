# Import

Navigation: ↑ [Architecture](../../architecture.md) | → [Data model](../../datamodel.md#receipts) | → [Storage](../storage/README.md) | → [UI](../ui/README.md) | → [Receipt reading](../receipt-reading/README.md)

## Overview

Import takes the receipt images that the user copied into the import folder and records each
new one as a receipt (PRD FR-1–FR-5, FR-45). The user starts a run with the "Tuo kuitit"
button; the folder is not watched. A run moves every file out of the import folder except
duplicates: new images go to the done folder after their receipt is committed, and files that
fail go to the failed folder.

Every new image is read by [receipt reading](../receipt-reading/README.md) between the
duplicate check and the commit, and the receipt is stored with its read data and lines. A run
starts only when OCR and the model are available, and stops if the model is lost during the
run (FR-31). Import does not choose categories.

The behavior is specified in the [receipt import spec](../../../specs/features/receipt-import.md)
and the [receipt-reading spec](../../../specs/features/receipt-reading.md).

## Key Files and Entry Points

- @backend/app/receipt_import/files.py — the file rules (`image_identifier`, `check_format`,
  `is_ignored`, `free_target_name`) and `FileStore` with its disk implementation
  `LocalFileStore`
- @backend/app/receipt_import/run.py — `process_file`: the steps of one file and their
  failure reasons; `FileResult`, `ImportFolders`
- @backend/app/receipt_import/service.py — `ImportService`: start checks, the background
  run, the state in memory, the log lines; `RunHooks`
- @backend/app/receipt_import/routes.py — `GET` and `POST /api/import`
- @backend/app/receipt_import/schemas.py, @backend/app/receipt_import/errors.py — the run
  state and the error codes

The package is called `receipt_import` because `import` is a Python keyword.

## Interfaces

| Function or class | Purpose |
|---|---|
| `ImportService.start()` | Checks the folders, lists the import folder, starts the run in a background thread and returns its first state. Raises `ImportRunningError` (409) or `FoldersUnavailableError` (503) |
| `ImportService.state()` | A copy of the current or latest run state (`idle`, `running`, `finished`) |
| `process_file(path, store=, repository=, folders=, now=)` | Imports one file and returns `imported`, `duplicate`, or `failed` with a reason |
| `FileStore` | `list_files`, `read_bytes`, `names_in`, `move`; tests replace it to simulate failing disks |

The endpoints, the state fields and the error codes are in
[api-reference.md](../../api-reference.md#import).

### Files

- A run takes the regular files directly in the import folder. Subfolders, symbolic links,
  names starting with `.`, `desktop.ini` and `Thumbs.db` (any case) are ignored: not counted
  and not moved.
- Files are processed in name order, compared case-insensitively. Files added after the run
  listed the folder wait for the next run.
- A supported file has the extension `.jpg`, `.jpeg` or `.png` (any case) **and** starts
  with the matching signature (JPEG `FF D8 FF`, PNG `89 50 4E 47 0D 0A 1A 0A`). The image is
  not decoded.
- The image identifier is the SHA-256 of the file's bytes, as 64 lowercase hex characters.
- A moved file keeps its name unless the target folder has it already (compared
  case-insensitively); then it gets the first free suffix: `kuitti (2).jpg`,
  `kuitti (3).jpg`, … No file is overwritten.

## Data Flow

Steps of one file (`process_file`):

| Step | On error | Reason | File ends in |
|---|---|---|---|
| 1. Read the bytes | `OSError` | `read_failed` | failed folder |
| 2. Check the format | not supported | `unsupported_format` | failed folder |
| 3. Hash; a receipt with that hash exists | (not an error) | duplicate | import folder |
| 4. Read the image (`ReceiptReader.read`) | `ReadFailedError` | its reason: `unreadable_image`, `ocr_failed`, `no_text`, `parse_failed` | failed folder |
| | `ModelUnavailableError` | none: the run stops | import folder |
| 5. Choose the free name in the done folder | `OSError` | `move_failed` | import folder |
| 6. Commit the receipt row and its lines in one transaction | `sqlite3.Error` | `save_failed` | failed folder |
| 7. Move to the done folder | `OSError` | `move_failed`; the row is deleted again, its lines with it | import folder |
| any step | other exception | `internal_error` | failed folder |

- Duplicates are found before reading, so they cost no OCR or model time.
- The row stores the file's final name, so the name is chosen before the commit (step 5).
- The file moves only after the commit (NFR-7). If the move fails, the row is deleted, so a
  later run imports the file instead of calling it a duplicate.
- A failed file stores nothing, so the user can move it back from the failed folder and
  retry. If moving it to the failed folder fails too, it stays in the import folder with its
  original reason.
- One file's failure never stops the run. If the run itself fails (for example the database
  cannot be opened), the files not yet handled are reported as `internal_error` and are not
  moved.

`ImportService` keeps one state behind a lock. `start()` checks the folders under the lock,
then OCR and the model outside it (so `GET /api/import` never waits for Ollama), then checks
again that no run started meanwhile and lists the files under the lock, so two starts cannot
both run. A cloud model (`RRMC_MODEL` ending in `-cloud` or `:cloud`) is refused like an
unavailable one (NFR-1).

When `process_file` raises `ModelUnavailableError`, `_run` stops: the current file and the
ones after it are not counted and stay in the import folder, and the state gets
`stopped` (`model_unavailable`). No file moves to the failed folder for that reason.

`_run` opens its own database connection in a daemon thread and
updates the state after each file. The UI polls `GET /api/import` while the state is
`running`. The state lives in memory: after a backend restart it is `idle`.

## Dependencies

- Uses: [receipt reading](../receipt-reading/README.md) (`ReceiptReader`, the engines'
  `check()`), [storage](../storage/README.md) (`ReceiptRepository`, `connect`),
  `check_folders` from @backend/app/health/service.py, and the folder settings
  (@backend/app/settings.py).
- Used by: the API ([api-reference.md](../../api-reference.md#import)) and the Tuonti page
  ([ui](../ui/README.md)).

## Modules

None yet.

## Known Issues and Gotchas

- **Moves copy, then delete.** The three folders are separate bind mounts in the container,
  so `os.rename` between them fails, and on Linux it would overwrite a target. `move` opens
  the target with `"xb"` (fails if it exists), copies and `fsync`s, then deletes the source;
  on any failure the file is left in exactly one place.
- **Crash window.** If the backend stops between the commit and the move, the receipt exists
  and the file stays in the import folder; the next run reports it as a duplicate. Nothing is
  lost; the user can move the file to the done folder by hand.
- **Duplicates stay in the import folder** and are reported again on every run until the
  user removes them.
- **Logging.** A run logs `Import started: files=N` and
  `Import finished: imported=N duplicates=N failed=N`, or
  `Import stopped: model unavailable, imported=N duplicates=N failed=N`. Unexpected errors log the exception
  type and traceback frames only, because exception messages contain file paths and file
  names stay out of the log (NFR-3).
- **Testing seams.** `ImportService` takes the engines and the reader (by default built
  from the settings, so `RRMC_ENGINES=fake` gives the fake reader), the `FileStore`, a
  repository factory, `can_write`,
  the clock, `RunHooks` and `run_in_background`; `create_app(import_service=...)` passes a
  configured service to integration tests. Production code uses the defaults.

## Related Documents

- [Receipt import spec](../../../specs/features/receipt-import.md)
- [architecture.md](../../architecture.md#import-fr-45-started-with-a-button): where import
  sits in the flow
- [datamodel.md](../../datamodel.md#receipts): the `receipts` and `receipt_lines` tables
- [glossary.md](../../glossary.md): import run, image identifier, duplicate

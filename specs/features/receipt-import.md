# Feature: Receipt import

## Overview
- **Status:** Done
- **Created:** 2026-10-28
- **Updated:** 2026-10-28: scope agreed with the user (pipeline without reading, background
  run with polling, JPEG and PNG only, unsupported files move to the failed folder);
  approved by the user; Plan added and approved; Tasks added; implemented (T1–T16), see
  [Changes during implementation](#changes-during-implementation); audited (PASS after one
  fix cycle), see [Audit](#audit)
- **Depends on:** [Project foundation](foundation.md), [Product management](product-management.md)
- **Implements:** PRD FR-1, FR-2 (resolved: JPEG and PNG), FR-3, FR-4, FR-5, FR-45, NFR-3
  and NFR-7 for import, NFR-15 for the Tuonti page; the receipt entity with its image
  identifier (first part of PRD MVP item 2, "Storage and settings for receipts").
- **Affected subsystems:** import (`docs/subsystems/import/README.md`, created by this
  feature), [storage](../../docs/subsystems/storage/README.md),
  [ui](../../docs/subsystems/ui/README.md)

## Problem Statement
The user saves receipt photos into the import folder and wants the app to take them in with
one button (PRD section 5, steps 1–2). Before OCR and parsing can be added, the app needs the
pipeline around them: find the images, recognize an image that was already imported, record
each new receipt, and move every file out of the import folder so that the folder only holds
work still to do. The user must see what happened to each file, without any receipt content
in logs.

## Current Behavior
None (new). What exists:

- The import, done and failed folders are settings, mounted into the backend container as
  `/data/import`, `/data/import_done` and `/data/import_failed`
  ([architecture.md](../../docs/architecture.md#runtime-and-deployment), @backend/app/settings.py).
- `GET /api/health` reports `checks.folders` (the three folders exist and can be written to)
  ([api-reference.md](../../docs/api-reference.md#get-apihealth)).
- The database has the catalog tables only; there is no receipt entity
  ([datamodel.md](../../docs/datamodel.md)).
- The UI has one page, Tuotteet, and no router ([ui](../../docs/subsystems/ui/README.md)).
- The planned import flow, including reading and categorization, is in
  [architecture.md](../../docs/architecture.md#import-fr-45-started-with-a-button). This spec
  builds the steps of that flow that do not read the image.

## Proposed Change

### Concepts

- An **import run** (tuontiajo) processes the files that are in the import folder when the
  user presses the button. Only one run can be active at a time.
- An **image identifier** is the SHA-256 hash of the file's bytes, as 64 lowercase
  hexadecimal characters (FR-3).
- A **duplicate** is a file whose identifier is already stored for a receipt.
- A **receipt** in this spec is the record of an imported image: identifier, file name in the
  done folder and import time. The receipt-reading spec adds the read data (OCR text, store,
  date, lines, total) and the reading step to the run.

### Parts

- **PC1 Receipt record.** A new `receipts` table holds one row per imported image: id, image
  identifier (unique), file name in the done folder, and import time (UTC ISO 8601). It is
  added as migration `0002`.
- **PC2 Finding files.** A run lists the import folder once, at its start. It takes only
  regular files directly in the folder; subfolders and their contents are ignored, and so
  are files whose name starts with `.` and the Windows system files `desktop.ini` and
  `Thumbs.db` (any case). Ignored entries are not counted and not moved. Files are processed
  in order of their name, compared case-insensitively. Files added after the listing are
  left for the next run.
- **PC3 Supported files.** A file is a supported image when its extension is `.jpg`,
  `.jpeg` or `.png` (any case) **and** its content starts with the matching signature: JPEG
  `FF D8 FF` for `.jpg` and `.jpeg`, PNG `89 50 4E 47 0D 0A 1A 0A` for `.png`. Anything
  else, including an empty file, fails with reason `unsupported_format`. The image is not
  decoded; whether it can be read is decided by the receipt-reading spec.
- **PC4 Duplicates.** The identifier is computed for each supported file. If a receipt with
  that identifier exists (also one stored earlier in the same run), the file is a duplicate:
  nothing is stored, and the file **stays in the import folder** (as in the
  [architecture flow](../../docs/architecture.md#import-fr-45-started-with-a-button)).
- **PC5 Commit, then move.** For a new image, the receipt row is committed first, then the
  file moves to the done folder (NFR-7). If the move fails, the row is deleted again, the
  file stays in the import folder, and the file fails with reason `move_failed`, so a later
  run can import it.
- **PC6 Failures.** A failed file stores nothing and moves to the failed folder. Its
  identifier is not stored, so the user can move it back and retry (FR-4). If even that move
  fails, the file stays in the import folder; it still counts as failed with its original
  reason. A failure of one file never stops the run.
- **PC7 Name collisions.** When a file with the same name exists in the target folder, the
  moved file gets the first free numbered suffix before the extension: `kuitti.jpg` →
  `kuitti (2).jpg` → `kuitti (3).jpg`. Names are compared case-insensitively, because the
  folders are on Windows. No file is overwritten. The receipt row stores the final name.
- **PC8 Background run with progress.** `POST /api/import` starts a run in the background
  and returns at once. `GET /api/import` returns the state of the current or latest run:
  progress while it runs, and the report when it has finished (FR-5). The state is kept in
  memory only: after a backend restart it is `idle`.
- **PC9 Start checks.** A run starts only when the three folders exist and can be written to.
  Otherwise the start is refused and nothing is processed. A start while a run is active is
  refused.
- **PC10 Privacy.** The backend logs one line when a run starts and one when it finishes,
  with counts only. File names and file content are never logged (NFR-3). The report shown in
  the UI contains file names, which stay on this computer, and fixed Finnish reason texts.
- **PC11 Tuonti page (Finnish UI).** The navigation gets a second link, "Tuonti", next to
  "Tuotteet". The app still opens on Tuotteet. The Tuonti page has the button "Tuo kuitit",
  progress while a run is active, and the report of the latest run with the duplicates and
  failures listed by file name. While a run is active the button is disabled and the page
  asks for the state every second. A page opened (or reloaded) during a run shows its
  progress.

### Run state (`GET /api/import`)

```json
{
  "state": "finished",
  "total": 4,
  "processed": 4,
  "imported": 1,
  "duplicates": ["b.jpg"],
  "failures": [
    {"file_name": "notes.txt", "reason": "unsupported_format", "message": "Tiedostomuotoa ei tueta. Käytä JPEG- tai PNG-kuvaa."}
  ],
  "started_at": "2026-10-28T10:00:00Z",
  "finished_at": "2026-10-28T10:00:02Z"
}
```

| Field | Meaning |
|---|---|
| `state` | `idle` (no run since the backend started), `running`, `finished` |
| `total` | Files found at the start of the run (after ignoring PC2 entries) |
| `processed` | Files handled so far: imported + duplicates + failed |
| `imported` | Files stored as new receipts and moved to the done folder |
| `duplicates` | File names of duplicates, in processing order |
| `failures` | One item per failed file, in processing order: original file name, reason code, Finnish message |
| `started_at`, `finished_at` | UTC ISO 8601; `null` when not reached |

In state `idle` all counts are 0, the lists are empty and both times are `null`.
`POST /api/import` returns `202` with the same body (state `running`, `total` set,
`processed` 0).

### Failure reasons

| `reason` | `message` | When |
|---|---|---|
| `unsupported_format` | `Tiedostomuotoa ei tueta. Käytä JPEG- tai PNG-kuvaa.` | PC3 check fails, or the file is empty |
| `read_failed` | `Tiedostoa ei voitu lukea.` | The file cannot be opened or read |
| `save_failed` | `Kuitin tallennus epäonnistui.` | Writing the receipt row fails |
| `move_failed` | `Tiedostoa ei voitu siirtää valmiiden kansioon.` | Moving to the done folder fails (PC5) |
| `internal_error` | `Odottamaton virhe. Katso lisätiedot palvelimen lokista.` | Any other error; the stack trace is logged without file name or content |

### API errors

| Method and path | Status | `error` | `message` | When |
|---|---|---|---|---|
| `POST /api/import` | 409 | `import_running` | `Tuonti on jo käynnissä.` | A run is active |
| `POST /api/import` | 503 | `folders_unavailable` | `Kuvakansioita ei löydy tai niihin ei voi kirjoittaa.` | A folder is missing or cannot be written to (PC9) |

### UI texts (Tuonti page)

| Use | Text |
|---|---|
| Navigation link and page heading | `Tuonti` |
| Instruction | `Kopioi kuittikuvat tuontikansioon ja paina Tuo kuitit.` |
| Button | `Tuo kuitit` |
| Progress | `Tuonti käynnissä: {processed}/{total}` |
| Report heading | `Edellinen tuonti` |
| Counts | `Tuotu: {n}`, `Kaksoiskappaleita: {n}`, `Epäonnistui: {n}` |
| Duplicates list heading | `Jo tuodut kuvat (jätetty tuontikansioon)` |
| Failures list heading | `Epäonnistuneet (siirretty epäonnistuneiden kansioon)` |
| Nothing to import | `Tuontikansiossa ei ollut kuvia.` |
| No run yet (`idle`) | `Tuontia ei ole vielä ajettu.` |

A failure item shows the file name and the `message`. A failed file that could not be moved
to the failed folder still appears under the failures heading; its message is the reason of
the failure (PC6).

### Out of Scope
- OCR, parsing and categorization of the image (FR-6–FR-15), and the model availability check
  before a run (FR-31). They are added to the run by the receipt-reading and categorization
  specs; the run is built so a reading step can be inserted between the duplicate check and
  the commit.
- Receipt fields other than those in PC1 (store, date, total, OCR text, review state) and
  receipt lines.
- A receipts list, a receipt view and serving the image to the UI (FR-16, FR-21).
- Watching the folder (FR-45 says the user starts the import).
- HEIC, PDF and other formats; decoding the image to check that it is valid.
- Content-based duplicate detection (PRD release "Later (candidates)").
- Cancelling a run, run history, or keeping the report over a backend restart.
- Deleting receipts, and moving duplicates out of the import folder.
- Subfolders of the import folder.

## Acceptance Criteria

Unless an AC says otherwise: the folders exist and can be written to, the database has no
receipts, and "the run finishes" means `GET /api/import` returns state `finished`. File
contents are synthetic (see [Test data](#test-data)).

### Importing

#### AC1: A new JPEG is imported
**Given** the import folder holds `a.jpg`, a valid synthetic JPEG with SHA-256 `H`
**When** the user starts an import and the run finishes
**Then** the state is `total` 1, `processed` 1, `imported` 1, `duplicates` [], `failures` [];
the database has exactly one receipt with `image_hash` `H`, `file_name` `"a.jpg"` and an
`imported_at` between the run's `started_at` and `finished_at`; `a.jpg` is in the done
folder with unchanged bytes and is no longer in the import folder

#### AC2: Supported extensions in any case
**Given** the import folder holds valid images `B.PNG`, `c.jpeg` and `d.JPG` with different contents
**When** the run finishes
**Then** `imported` is 3, three receipts exist with file names `"B.PNG"`, `"c.jpeg"`,
`"d.JPG"`, and all three files are in the done folder

#### AC3: Files are processed in name order
**Given** the import folder holds valid images `c.jpg`, `A.jpg` and `b.png`
**When** the run finishes
**Then** the receipts' ids increase in the order `A.jpg`, `b.png`, `c.jpg`

### Duplicates

#### AC4: An image imported before is a duplicate
**Given** a receipt with `image_hash` `H` exists, and the import folder holds `again.jpg` with SHA-256 `H`
**When** the run finishes
**Then** `imported` is 0, `duplicates` is `["again.jpg"]`, `failures` is [], the database
still has exactly one receipt, and `again.jpg` is still in the import folder, unchanged

#### AC5: Two identical files in one run
**Given** the import folder holds `a.jpg` and `b.jpg` with identical bytes
**When** the run finishes
**Then** `imported` is 1, `duplicates` is `["b.jpg"]`, one receipt exists with `file_name`
`"a.jpg"`, `a.jpg` is in the done folder and `b.jpg` is still in the import folder

### Unsupported files

#### AC6: Unsupported extension
**Given** the import folder holds `notes.txt` and `photo.heic`
**When** the run finishes
**Then** `imported` is 0, `failures` is
`[{"file_name": "notes.txt", "reason": "unsupported_format", ...}, {"file_name": "photo.heic", "reason": "unsupported_format", ...}]`
in name order, both with message `Tiedostomuotoa ei tueta. Käytä JPEG- tai PNG-kuvaa.`;
both files are in the failed folder; no receipt exists

#### AC7: Content does not match the extension
**Given** the import folder holds `text.jpg` (the bytes `hello`), `empty.png` (0 bytes) and
`png-as.jpg` (a valid PNG named `.jpg`)
**When** the run finishes
**Then** all three fail with reason `unsupported_format`, all three are in the failed folder,
and no receipt exists

#### AC8: Ignored entries
**Given** the import folder holds a subfolder `vanhat/` containing `x.jpg`, and the files
`.hidden.jpg`, `desktop.ini` and `THUMBS.DB`
**When** the run finishes
**Then** `total` is 0, nothing is moved, and all four entries are where they were

#### AC9: Empty import folder
**Given** the import folder is empty
**When** the run finishes
**Then** `total`, `processed` and `imported` are 0, both lists are empty, and `finished_at` is set

### Moving files

#### AC10: Name collision in the done folder
**Given** the done folder already holds `kuitti.jpg` and `KUITTI (2).jpg`, and the import
folder holds a new valid image `kuitti.jpg`
**When** the run finishes
**Then** the done folder holds `kuitti (3).jpg` with the new image's bytes, the two older
files are unchanged, and the new receipt's `file_name` is `"kuitti (3).jpg"`

#### AC11: Name collision in the failed folder
**Given** the failed folder already holds `notes.txt`, and the import folder holds another `notes.txt`
**When** the run finishes
**Then** the failed folder holds `notes.txt` (unchanged) and `notes (2).txt` (the new file),
and the failure item's `file_name` is `"notes.txt"` (the original name)

#### AC12: Move to the done folder fails
**Given** the import folder holds a new valid image `a.jpg`, and moving files into the done
folder fails (simulated)
**When** the run finishes
**Then** `imported` is 0, `failures` is `[{"file_name": "a.jpg", "reason": "move_failed", "message": "Tiedostoa ei voitu siirtää valmiiden kansioon."}]`,
no receipt exists, and `a.jpg` is still in the import folder

#### AC13: A failed image can be retried
**Given** the run of AC12 has finished, and moving into the done folder works again
**When** the user starts another import and it finishes
**Then** `imported` is 1, `duplicates` is [], and `a.jpg` is in the done folder

#### AC14: Saving the receipt fails
**Given** the import folder holds a new valid image `a.jpg`, and writing the receipt row fails (simulated)
**When** the run finishes
**Then** `failures` is `[{"file_name": "a.jpg", "reason": "save_failed", ...}]`, no receipt
exists, and `a.jpg` is in the failed folder

#### AC15: One failure does not stop the run
**Given** the import folder holds `a.jpg` (valid), `b.jpg` (cannot be read, simulated) and `c.jpg` (valid)
**When** the run finishes
**Then** `imported` is 2, `failures` has one item for `b.jpg` with reason `read_failed`, and
`b.jpg` is in the failed folder

#### AC16: Moving a failed file fails too
**Given** the import folder holds `notes.txt`, and moving files into the failed folder fails (simulated)
**When** the run finishes
**Then** `failures` has one item for `notes.txt` with reason `unsupported_format`, and
`notes.txt` is still in the import folder

#### AC17: Unexpected error
**Given** the import folder holds `a.jpg` and `b.jpg` (both valid), and processing `a.jpg`
raises an unexpected exception (simulated)
**When** the run finishes
**Then** `a.jpg` fails with reason `internal_error` and is in the failed folder, `b.jpg` is
imported, and the backend log has the stack trace but neither file name

### Run control

#### AC18: Progress while running
**Given** the import folder holds three valid images, and the run is paused after the first
file is processed (simulated)
**When** a client calls `GET /api/import`
**Then** the response is 200 with `state` `running`, `total` 3, `processed` 1, `imported` 1,
`finished_at` null

#### AC19: Start returns at once
**Given** the import folder holds one valid image, and processing is paused before the first file (simulated)
**When** a client calls `POST /api/import`
**Then** the response is 202 with `state` `running`, `total` 1, `processed` 0, `started_at`
set and `finished_at` null

#### AC20: Only one run at a time
**Given** a run is active
**When** a client calls `POST /api/import`
**Then** the response is 409 with error `import_running` and message `Tuonti on jo
käynnissä.`, and the active run's counts are not affected

#### AC21: Folders not available
**Given** the done folder does not exist (or any of the three folders is missing or cannot be written to)
**When** a client calls `POST /api/import`
**Then** the response is 503 with error `folders_unavailable` and message `Kuvakansioita ei
löydy tai niihin ei voi kirjoittaa.`, no file is moved, and `GET /api/import` returns the
same state as before the call

#### AC22: Idle before the first run
**Given** the backend has just started
**When** a client calls `GET /api/import`
**Then** the response is 200 with `state` `idle`, all counts 0, empty lists and both times `null`

#### AC23: Files added during a run
**Given** a run that found `a.jpg` is paused after listing the folder (simulated), and
`b.jpg` is then added to the import folder
**When** the run finishes
**Then** `total` is 1, only `a.jpg` is imported, and `b.jpg` is still in the import folder

### Persistence and privacy

#### AC24: Receipts survive a restart
**Given** `a.jpg` was imported
**When** the backend restarts and the user imports a copy of `a.jpg` named `copy.jpg`
**Then** `copy.jpg` is reported as a duplicate

#### AC25: No file names or content in the log
**Given** the import folder holds `secret-name.jpg` (valid) and `other-secret.txt`
**When** the run finishes
**Then** the backend log has exactly one start line and one finish line for the run; the
finish line has the counts (`imported=1 duplicates=0 failed=1`); no log line contains
`secret-name`, `other-secret` or any bytes of the files

### UI

#### AC26: Navigation has two pages
**Given** the app is opened at its start address
**When** it is rendered
**Then** the navigation "Päävalikko" has the links "Tuotteet" and "Tuonti"; "Tuotteet" is
marked as the current page and the Tuotteet page is shown; clicking "Tuonti" shows the
Tuonti page, marks "Tuonti" as current, and the status line stays visible

#### AC27: Start an import and see the report
**Given** the Tuonti page is open and `GET /api/import` returns `idle`
**When** the user clicks "Tuo kuitit", the run is first `running` with 1/4 and then
`finished` with the report of the [Run state](#run-state-get-apiimport) example
**Then** the page first shows `Tuontia ei ole vielä ajettu.`, then `Tuonti käynnissä: 1/4`
with the button disabled, then under `Edellinen tuonti`: `Tuotu: 1`, `Kaksoiskappaleita: 1`,
`Epäonnistui: 1`, the duplicate `b.jpg` under the duplicates heading, and `notes.txt` with
its message under the failures heading; the button is enabled again

#### AC28: A running import is shown on page open
**Given** `GET /api/import` returns `running` with 2/5
**When** the Tuonti page is opened
**Then** it shows `Tuonti käynnissä: 2/5` with the button disabled, and asks for the state
again about every second until the state is `finished`

#### AC29: Start errors are shown
**Given** the Tuonti page is open
**When** "Tuo kuitit" returns 409 `import_running`, 503 `folders_unavailable`, or the backend
cannot be reached
**Then** the page shows the error's Finnish `message` (or `Taustapalveluun ei saada
yhteyttä.`) next to the button with `role="alert"`, and the shown report stays as it was

#### AC30: Nothing to import
**Given** the Tuonti page is open
**When** a run finishes with `total` 0
**Then** the report shows `Tuontikansiossa ei ollut kuvia.` and no count lines

#### AC31: The page is in Finnish
**Given** the Tuonti page is open
**When** it is rendered
**Then** the heading is "Tuonti", the instruction and the button use the texts of
[UI texts](#ui-texts-tuonti-page), and no English text is visible

## Files to Modify
| File | Change |
|---|---|
| `backend/app/storage/migrations/0002_receipts.sql` | New: `receipts` table (PC1) |
| `backend/app/storage/receipt_repository.py` | New: add, get by hash, delete receipt rows |
| `backend/app/receipt_import/` | New package: file checks and moves, run service with in-memory state, routes (see [Plan](#plan)) |
| `backend/app/main.py` | Register the import router and its run service |
| `backend/app/texts.py` | Finnish texts of the import errors and failure reasons |
| `backend/tests/unit/receipt_import/`, `backend/tests/unit/storage/` | Unit tests (see Testing Strategy) |
| `backend/tests/integration/test_import_api.py` | Integration tests |
| `frontend/src/App.tsx` | Second navigation link and page switching (no router library, see [Plan](#plan)) |
| `frontend/src/api/imports.ts` | Typed client for `POST`/`GET /api/import` |
| `frontend/src/components/ImportPage.tsx` | The Tuonti page |
| `frontend/src/i18n/fi.ts` | Tuonti texts |
| `frontend/src/test/` | MSW handlers for the import endpoints |
| `frontend/e2e/import.spec.ts` | E2E journey |
| `compose.yaml` | A test-only volume shared by `backend-e2e` and `e2e` for the E2E import folder (see [Plan](#plan)) |
| `docs/subsystems/import/README.md` | New Tier 2 doc |
| `docs/datamodel.md` | `receipts` table, migration 0002 |
| `docs/api-reference.md` | Import endpoints and error codes |
| `docs/architecture.md` | Import flow: resolve the background-run `[NEEDS CLARIFICATION]`; duplicates stay in the import folder; note that reading is added later |
| `docs/subsystems/storage/README.md` | Receipt repository |
| `docs/subsystems/ui/README.md` | Navigation with two pages, Tuonti page |
| `docs/glossary.md` | Import run, image identifier, duplicate |
| `docs/content-plan.md` | Import doc row to In Progress; updated statuses |
| `specs/PRD.md` | FR-2 resolved: JPEG and PNG (HEIC and PDF not supported); open question 2 updated |
| `specs/README.md` | Row for this spec |

## Risk
- **What could break:** the app shell and its tests (a second navigation link and page
  switching), the Tuotteet E2E journeys (navigation changes), and the migration chain (first
  migration after `0001`). File moves touch real user files on Windows-mounted folders: a
  bug could move a file to the wrong folder or overwrite one. PC7 forbids overwriting, and
  the tests cover collisions.
- **Crash window:** if the backend stops between the commit and the move, the receipt exists
  and the file stays in the import folder; the next run reports it as a duplicate. No data is
  lost (NFR-7), and the user can move the file to the done folder by hand.
- **Rollback:** revert the commit. Migration 0002 stays applied; the reverted code does not
  read the `receipts` table, so the app still starts. Files already moved stay in the done or
  failed folders and can be moved back by hand. Deleting the database volume is done only by
  the user, never by an agent.
- **Dependencies:** the foundation's folder mounts and health check; no Tesseract or Ollama
  in this spec.
- **Privacy:** file names may describe a purchase; they are shown in the local UI but never
  logged. Tests use synthetic files in temporary folders only.

## Testing Strategy (MANDATORY)

Failures that cannot be produced with real files (move, save, read, unexpected error,
pausing a run) are simulated by injecting a failing or blocking file mover, repository or
hook into the run service. The Plan names the seams.

### Unit tests (backend, pytest)
| AC | Function | Case | Given | When | Then | Mocks |
|---|---|---|---|---|---|---|
| AC1 | `image_identifier` | hash | bytes `b"abc"` | compute | `ba7816bf…15ad` (64 lowercase hex) | none |
| AC2, AC6, AC7 | `check_format` | supported | `.jpg`/`.JPEG`/`.png` with matching signature | check | ok | none |
| AC6, AC7 | `check_format` | unsupported | `.txt`; `.heic`; `.jpg` with `hello`; empty `.png`; PNG bytes in `.jpg` | check | `unsupported_format` | none |
| AC3, AC8 | `list_import_files` | listing | folder with `c.jpg`, `A.jpg`, `b.png`, `vanhat/x.jpg`, `.hidden.jpg`, `desktop.ini`, `THUMBS.DB` | list | `A.jpg`, `b.png`, `c.jpg` | temp folder |
| AC10, AC11 | `free_target_name` | collisions | target has `kuitti.jpg`, `KUITTI (2).jpg` | name for `kuitti.jpg` | `kuitti (3).jpg`; for an unused name the name itself | temp folder |
| AC10 | `free_target_name` | no extension | target has `README` | name for `README` | `README (2)` | temp folder |
| AC1, AC4 | `ReceiptRepository` | add / get by hash / delete | temp DB | add `H`; get `H`; delete | row; row; none | temp SQLite |
| AC4 | `ReceiptRepository.add` | unique hash | row with `H` | add `H` again | `sqlite3.IntegrityError` | temp SQLite |
| AC1, AC4, AC5 | `ImportRun.process_file` | new / duplicate | empty DB; then same bytes | process twice | imported; duplicate, file left | temp folders, temp SQLite |
| AC12 | `ImportRun.process_file` | move fails | failing mover for done folder | process | `move_failed`, row deleted, file in import | failing mover |
| AC14 | `ImportRun.process_file` | save fails | failing repository | process | `save_failed`, file in failed folder | failing repository |
| AC15 | `ImportRun.process_file` | read fails | reader that raises `OSError` | process | `read_failed`, file in failed folder | failing reader |
| AC16 | `ImportRun.process_file` | failed-folder move fails | unsupported file, failing mover for failed folder | process | `unsupported_format`, file in import | failing mover |
| AC17 | `ImportRun.process_file` | unexpected error | step raises `RuntimeError` | process | `internal_error`, file in failed folder | raising hook |
| AC18, AC20, AC22 | `ImportService` | state machine | idle; start; start again; finish | calls | idle → running → 409 `import_running` → finished | blocking hook |
| AC21 | `ImportService.start` | folders | each folder missing or read-only in turn | start | `folders_unavailable`, state unchanged | temp folders |
| AC25 | `ImportService` | log lines | two files | run | one start and one finish line with counts; no file names | `caplog` |

### Integration tests (FastAPI TestClient, temporary SQLite file, temporary folders)
| AC | Scenario | Request / input | Expected output | Status |
|---|---|---|---|---|
| AC22 | idle | `GET /api/import` | `state` `idle`, zeros, `null` times | 200 |
| AC19 | start | `POST /api/import` with one file, paused before the first file | `running`, `total` 1, `processed` 0 | 202 |
| AC1 | import one JPEG | `POST`, then poll `GET` | report of AC1; DB row; file in done folder | 202, 200 |
| AC2, AC3 | extensions and order | `POST`, poll | 3 imported; ids in name order | 200 |
| AC4 | duplicate of stored receipt | existing row `H`, `POST`, poll | `duplicates` `["again.jpg"]`; file in import folder | 200 |
| AC5 | duplicate within run | `POST`, poll | 1 imported, `["b.jpg"]` | 200 |
| AC6, AC7 | unsupported files | `POST`, poll | five `unsupported_format` failures; files in failed folder | 200 |
| AC8, AC9 | ignored entries; empty folder | `POST`, poll | `total` 0; entries untouched | 200 |
| AC10, AC11 | collisions | `POST`, poll | `kuitti (3).jpg`; `notes (2).txt` | 200 |
| AC12, AC13 | move fails, then retry | failing mover; `POST`, poll; normal mover; `POST`, poll | `move_failed`; then imported 1 | 200 |
| AC14, AC15, AC16, AC17 | simulated failures | `POST`, poll | reasons as in the ACs; other files imported | 200 |
| AC18 | progress | paused after first file; `GET` | `running`, 1/3 | 200 |
| AC20 | second start | `POST` while paused | `import_running` | 409 |
| AC21 | folders missing | done folder removed; `POST` | `folders_unavailable`; `GET` unchanged | 503 |
| AC23 | file added during run | paused after listing; add `b.jpg`; resume | `total` 1; `b.jpg` in import folder | 200 |
| AC24 | restart | import; recreate app with same DB file; import copy | `duplicates` `["copy.jpg"]` | 200 |
| AC25 | logging | `POST`, poll, inspect log | counts only; no file names | 200 |

### Component tests (Vitest + React Testing Library, API mocked with MSW)
| AC | Component | Case | Given | When | Then |
|---|---|---|---|---|---|
| AC26 | App | navigation | health and catalog mocked | render; click "Tuonti" | two links; Tuotteet current first; then Tuonti page shown and current; status line visible |
| AC27 | ImportPage | full run | `GET` idle → running 1/4 → finished (example report) | render; click "Tuo kuitit" | texts in the order of AC27; button disabled while running, enabled after |
| AC28 | ImportPage | running on open | `GET` running 2/5, then finished | render | progress text, disabled button; a second `GET` within about 1 s (fake timers) |
| AC29 | ImportPage | start errors | `POST` 409; 503; network error | click | each Finnish message with `role="alert"`; report unchanged |
| AC30 | ImportPage | empty run | finished with `total` 0 | render | `Tuontikansiossa ei ollut kuvia.`; no count lines |
| AC31 | ImportPage | Finnish texts | idle | render | heading, instruction and button texts |
| AC27, AC29 | API client `imports.ts` | calls | 202, 200, 409 | call | typed state; `{ok:false}` with code and message |

### E2E tests (Playwright, real backend with fakes, temporary database and folders)
| AC | Journey | Steps | Expected outcome |
|---|---|---|---|
| AC1, AC4, AC6, AC26, AC27 | import from the UI | 1. place a synthetic `kuitti-<run>.jpg`, a copy of it named `kuitti-<run>_kopio.jpg` (after the original in name order, AC3) and `muistio-<run>.txt` in the E2E backend's import folder, where `<run>` is unique per run 2. open the app and click "Tuonti" 3. click "Tuo kuitit" 4. wait for the report | `Tuotu: 1`, `Kaksoiskappaleita: 1` with the copy, `Epäonnistui: 1` with the text file and its message; no error shown |
| AC26 | existing journeys | the product E2E journeys after the navigation change | still pass |

How the E2E test places files in the E2E backend's import folder is decided in the Plan.

### Coverage target
- Backend: 90 % lines for the import package and the receipt repository; duplicate
  detection, format checks, name collisions and every failure path: every branch.
- Frontend: 80 % lines for the Tuonti page, the import API client and the navigation.

### Test data
- Synthetic files only, generated in the tests: minimal JPEG and PNG byte strings (valid
  signature plus a few bytes, different per file where the AC needs different hashes),
  text files, empty files. No real receipt images.
- Each backend test uses its own temporary SQLite file and temporary import, done and
  failed folders.
- Mocks: failing or blocking mover, reader, repository and hook injected into the run
  service; MSW handlers for `POST`/`GET /api/import`.

## Related Documentation (MANDATORY)
- PRD: [specs/PRD.md](../PRD.md) sections 5, 6.1 (FR-1–FR-5, FR-45), 7.1 (NFR-3), 7.2
  (NFR-7), 7.4 (NFR-15), 9
- Specs: [Project foundation](foundation.md), [Product management](product-management.md)
- Tier 1: [architecture.md](../../docs/architecture.md#import-fr-45-started-with-a-button),
  [datamodel.md](../../docs/datamodel.md), [api-reference.md](../../docs/api-reference.md),
  [development.md](../../docs/development.md), [glossary.md](../../docs/glossary.md)
- Tier 2: [storage](../../docs/subsystems/storage/README.md),
  [ui](../../docs/subsystems/ui/README.md),
  [receipt-reading](../../docs/subsystems/receipt-reading/README.md) (adds the reading step
  later); import README (created by this feature)
- ADRs: [0001 technology stack](../../docs/adr/0001-tech-stack.md),
  [0002 Docker](../../docs/adr/0002-docker.md)
- Development rules: `AGENTS.md`; workflows: `.agents/skills/spec/SKILL.md`,
  `.agents/skills/tdd/SKILL.md`

## Open Questions
None. Resolved with the user on 2026-10-28: the pipeline is built without reading; the run
is a background task polled by the UI; JPEG and PNG only; unsupported and damaged-signature
files move to the failed folder.

## Plan

Spec approved: 2026-10-28. The plan follows [architecture.md](../../docs/architecture.md)
and the [code standards](../../docs/development.md#code-standards). No new dependencies are
needed on either side: hashing, file access and threads come from the Python standard
library, and page switching in the UI uses the browser's History API.

### Components

| Part | File | Contents | ACs |
|---|---|---|---|
| P1 Schema | `backend/app/storage/migrations/0002_receipts.sql` | Table `receipts` (see [Data model](#data-model)) | AC1, AC4, AC24 |
| P2 Repository | `backend/app/storage/receipt_repository.py` | `ReceiptRepository(connection)`: `add(image_hash, file_name, imported_at) -> ReceiptRow`, `get_by_hash(image_hash) -> ReceiptRow \| None`, `delete(receipt_id)`, `transaction()`. Frozen dataclass `ReceiptRow`. No rules | AC1, AC4, AC5, AC12, AC14 |
| P3 File rules | `backend/app/receipt_import/files.py` | Pure functions: `image_identifier(data)`, `check_format(name, data) -> bool`, `is_ignored(name)`, `free_target_name(name, taken)` | AC2, AC3, AC6–AC8, AC10, AC11 |
| P4 File store | `backend/app/receipt_import/files.py` | `FileStore` protocol and `LocalFileStore`: `list_files(folder)`, `read_bytes(path)`, `names_in(folder)`, `move(source, target)` (see [Moving a file](#moving-a-file)) | AC3, AC8, AC10–AC12, AC15, AC16, AC23 |
| P5 Run | `backend/app/receipt_import/run.py` | `process_file(...)`: the steps of one file and their failure reasons (see [Steps of one file](#steps-of-one-file)); `FileResult` | AC1, AC2, AC4–AC7, AC10–AC17 |
| P6 Service | `backend/app/receipt_import/service.py` | `ImportService`: start checks, in-memory state behind a lock, the background thread, log lines, `RunHooks` test seam | AC9, AC18–AC23, AC25 |
| P7 API | `backend/app/receipt_import/schemas.py`, `routes.py`, `errors.py`; `backend/app/main.py`; `backend/app/texts.py` | `ImportStateOut`, `FailureOut`; `create_import_router(service)`; `ImportRunningError`, `FoldersUnavailableError`; Finnish texts; `create_app` builds one `ImportService` (or takes one from tests) | AC19–AC22, AC24 |
| P8 API client | `frontend/src/api/imports.ts` | `getImport()`, `startImport()`, types `ImportState`, `ImportFailure` | AC27–AC29 |
| P9 Page | `frontend/src/components/ImportPage.tsx` | The Tuonti page (see [UI](#ui-1)) | AC27–AC31 |
| P10 Shell | `frontend/src/App.tsx`, `frontend/src/navigation.ts`, `frontend/src/i18n/fi.ts` | Two links, page switching, Tuonti texts under `fi.import` | AC26, AC31 |
| P11 E2E setup | `compose.yaml`, `frontend/e2e/import.spec.ts` | Shared test-only import folder (see [E2E files](#e2e-files)) | E2E rows |

### Data model

```sql
CREATE TABLE receipts (
    id          INTEGER PRIMARY KEY,
    image_hash  TEXT NOT NULL UNIQUE CHECK (length(image_hash) = 64),  -- SHA-256, lowercase hex
    file_name   TEXT NOT NULL,     -- name in the done folder, after any numbered suffix
    imported_at TEXT NOT NULL      -- UTC ISO 8601, e.g. 2026-10-28T10:00:01Z
);
```

- The `UNIQUE` index on `image_hash` is the duplicate lookup. The service checks first; the
  index is the safety net if two rows ever race.
- Later specs add the read data as new columns or tables in their own migrations. Receipt
  lines will reference `receipts.id`.
- Times use `YYYY-MM-DDTHH:MM:SSZ` everywhere in this feature (`imported_at`, `started_at`,
  `finished_at`), so AC1's "between" compares strings of the same form.

### Steps of one file

`process_file(path, *, store, repository, folders, now) -> FileResult`, where `now` is the
import time from the service's clock and `FileResult` is
`imported`, `duplicate`, or `failed` with a reason. The file name in the result is the
original name.

| Step | On error | Reason | File ends in |
|---|---|---|---|
| 1. `data = store.read_bytes(path)` | `OSError` | `read_failed` | failed folder |
| 2. `check_format(path.name, data)` | false | `unsupported_format` | failed folder |
| 3. `h = image_identifier(data)`; `repository.get_by_hash(h)` exists | (not an error) | duplicate | import folder |
| 4. `target = free_target_name(path.name, store.names_in(done))` | `OSError` | `move_failed` | import folder |
| 5. In one transaction: `repository.add(h, target, now)` | `sqlite3.Error` | `save_failed` | failed folder |
| 6. `store.move(path, done / target)` | `OSError` | `move_failed`; the row is deleted in a new transaction | import folder |
| any step | other `Exception` | `internal_error` | failed folder |

- "Failed folder" means: `store.move(path, failed / free_target_name(...))`. If that raises
  `OSError`, the file stays in the import folder and the result keeps its reason (PC6,
  AC16).
- The target name is chosen before the commit, because the row stores the final name. A
  race for that name (another program creates it between steps 4 and 6) ends in step 6 as
  `move_failed`, so no file is overwritten.
- If deleting the row in step 6 fails too, the error is logged (no file name) and the result
  is still `move_failed`; the next run then reports the file as a duplicate, as in the crash
  window of the [Risk](#risk) section.
- Step 3 reads the database after step 5 of the earlier files has committed, so a second
  identical file in the same run is a duplicate (AC5).
- The reading step of the receipt-reading spec goes between steps 3 and 4.

### Moving a file

The three folders are separate bind mounts in the container, so `os.rename` between them
fails with `EXDEV`, and on Linux it would overwrite an existing target. `LocalFileStore.move`
therefore copies and then deletes:

1. Open the target with mode `"xb"` (exclusive create: fails if the name exists).
2. Copy the bytes, flush and `os.fsync`.
3. Delete the source.

If step 1 fails, nothing has changed. If step 2 fails, the partial target is deleted. If
step 3 fails, the target copy is deleted, so the file is in one place only. Each case raises
`OSError`.

`names_in(folder)` returns the lower-cased names in the folder; `free_target_name` compares
lower-cased names, so `KUITTI (2).jpg` counts as taken (AC10) also on a case-sensitive test
filesystem. Suffixes: `stem (n).ext` with n = 2, 3, …; for a name without an extension
`name (n)`.

`list_files(folder)` returns the regular files directly in the folder (no symlinks followed,
no subfolders), with `is_ignored` names removed, sorted by `name.casefold()` then `name`.
`is_ignored`: the name starts with `.`, or its casefold is `desktop.ini` or `thumbs.db`.

`check_format`: the extension's casefold is `.jpg` or `.jpeg` and the data starts with
`FF D8 FF`, or it is `.png` and the data starts with the 8-byte PNG signature. An empty file
fails both.

### Service and state

```python
class ImportService:
    def __init__(self, settings: Settings, *, store: FileStore | None = None,
                 repository: Callable[[sqlite3.Connection], ReceiptRepository] = ReceiptRepository,
                 can_write: CanWrite = _can_write, clock: Callable[[], datetime] = _utc_now,
                 hooks: RunHooks | None = None,
                 run_in_background: RunInBackground = _run_in_thread) -> None: ...
    def state(self) -> ImportStateOut: ...
    def start(self) -> ImportStateOut: ...   # raises ImportRunningError, FoldersUnavailableError
```

- `start()`, under the lock: refuse with `import_running` when the state is `running`; check
  the folders with `check_folders` (reused from @backend/app/health/service.py, with the
  injected `can_write`), and refuse with `folders_unavailable` when one is not `ok` or
  `list_files` raises `OSError`; otherwise list the files, set a fresh state (`running`,
  `total`, `started_at`), log the start line, and hand `_run(files)` to
  `run_in_background`. The 202 body is the state at that moment (AC19).
- `_run(files)` opens its own database connection (closed at the end), calls
  `hooks.after_listing()`, then for each file `process_file`, updates the state under the
  lock, and `hooks.after_file(name)`. At the end it sets `finished` and `finished_at` and logs
  the finish line. AC17 is simulated with a `FileStore` whose `read_bytes` raises
  `RuntimeError`, which `process_file` turns into `internal_error`.
- If `_run` itself fails (for example the database cannot be opened), the remaining files are
  counted as `internal_error` without being moved, the run is marked `finished`, and the
  error is logged. The state never stays `running`.
- `state()` returns a copy under the lock, so `GET` never sees a half-updated state.
- `RunHooks` is a dataclass of two no-op callables, `after_listing` and `after_file`. Tests
  pass hooks that wait on a `threading.Event` to pause a run (AC18, AC19, AC20, AC23).
  Production code never sets them.
- The background thread is a daemon thread, as in `ModelLoader`. A backend stop during a run
  ends it; at most the file in progress is left in the crash window described in
  [Risk](#risk).
- Log lines (logger `app.receipt_import`): `Import started: files=3` and
  `Import finished: imported=1 duplicates=0 failed=1`. For `internal_error` the log line is
  `Unexpected error while importing a file: <exception type>` followed by the traceback
  frames from `traceback.format_tb`, without the exception message, because messages of
  `OSError` and others contain the path (AC17, AC25).

### API wiring

- `create_app(..., import_service: ImportService | None = None)`: production builds
  `ImportService(settings)`; integration tests pass one with a failing store, repository or
  hooks. This follows the existing `engines` parameter.
- `POST /api/import` → 202 `ImportStateOut`; `GET /api/import` → 200 `ImportStateOut`. Plain
  `def` routes; the work runs in the service's thread, not in the request.
- Errors are `AppError` subclasses in `receipt_import/errors.py` with texts from
  @backend/app/texts.py: `IMPORT_RUNNING`, `FOLDERS_UNAVAILABLE`, and one text per failure
  reason. `internal_error` reuses `INTERNAL_ERROR`.

### UI

- **Page switching without a router library.** @frontend/src/navigation.ts has
  `usePage()`: the current page from `location.pathname` (`/tuonti` → Tuonti, anything else
  → Tuotteet), a `go(page)` that calls `history.pushState`, and a `popstate` listener for the
  back button. The links are real `<a href="/">` and `<a href="/tuonti">`; a plain left click
  is handled with `go` and `preventDefault`. The current link has `aria-current="page"`.
  Vite's dev server answers `/tuonti` with `index.html`, so a reload on the Tuonti page stays
  there (AC28). Two pages do not justify a dependency; a router can replace this later
  without changing the pages.
- **ImportPage** loads `GET /api/import` on mount. While the state is `running` it schedules
  the next `GET` 1000 ms after the previous answer (`setTimeout`, cleared on unmount), so
  requests never overlap. "Tuo kuitit" sends `POST`; a 202 replaces the shown state and
  starts polling. A start error is shown next to the button with `role="alert"` and keeps the
  shown state (AC29); it is cleared by the next successful start. A failed `GET` while
  polling shows the same alert and polling continues.
- Rendering by state: `idle` → `Tuontia ei ole vielä ajettu.`; `running` → progress text,
  button disabled; `finished` → `Edellinen tuonti` with either `Tuontikansiossa ei ollut
  kuvia.` (`total` 0) or the three counts and the two lists (a list is shown only when it has
  items).

### E2E files

`backend-e2e` keeps `/data` on tmpfs, but its import folder becomes a named volume
`rrmc-e2e-import` mounted at `/data/import`. The `e2e` container mounts the same volume at
`/e2e-import` and gets `E2E_IMPORT_DIR=/e2e-import`. `import.spec.ts` writes its synthetic
files there with Node's `fs`, then drives the UI.

The volume only ever holds the test's synthetic files. A duplicate stays in the import
folder by design, so files of an earlier run would remain; the test therefore empties
`E2E_IMPORT_DIR` before writing its files. The done and failed folders stay on tmpfs and
start empty on every run. The volume is separate from `rrmc-data` and from the real import
folder mounted by the `backend` service, so no real data is ever reachable from the E2E run.

### Changes to existing tests

- Frontend `App.test.tsx` "AC31: the navigation opens the Tuotteet page" expects exactly one
  link. The product management spec's AC31 described the shell when it was the only page;
  this spec's AC26 replaces that with two links, Tuotteet still current at start. The test
  is updated **before** the shell changes, as part of the AC26 task, to expect
  `["Tuotteet", "Tuonti"]` with Tuotteet current; the rest of it stays. The product
  management spec gets a dated note that AC31 is superseded by this spec's AC26.
- `App.test.tsx` "AC25, AC30: shows no English text" collects only `fi` texts, so the new
  `fi.import` texts are allowed automatically; the import endpoint is mocked as `idle` in its
  `beforeEach` so the shell keeps rendering without unhandled requests.
- Backend `tests/unit/storage/test_catalog_schema.py` asserts `current_version(db) == 1` on
  a database with **every** migration applied. Migration `0002` makes that 2, although the
  catalog schema does not change. The test is updated **before** `0002` is added, as part of
  the migration task: it asserts that version 1 is the catalog migration (the
  `schema_version` row for 1 exists and the catalog tables are there), not that 1 is the
  newest. The product management spec's AC1 and AC25 still hold.
- Backend `test_startup_migrations.py` needs no change: it numbers its throwaway migrations
  after the newest real one.

### Testing approach

- Unit tests in `tests/unit/receipt_import/` use temporary folders (`tmp_path`) and the
  migrated temporary database from `tests/unit/conftest.py`. Failures are produced by
  `FailingStore` and `FailingRepository` in `tests/receipt_import_data.py`, shared with the
  integration tests.
- Unit tests of `ImportService` pass `run_in_background=lambda work: work()` where the test
  needs no concurrency, and the real thread with `RunHooks` events where it does.
- Integration tests build the app with `create_app(settings, import_service=...)` through a
  new `make_client` argument, start a run and poll `GET /api/import` with a helper that waits
  for `finished` (5 s limit, no fixed sleeps).
- A helper `tests/receipt_import_data.py` builds synthetic JPEG and PNG bytes:
  signature + a distinct suffix per name.
- Coverage: `pytest --cov=app.receipt_import --cov=app.storage` and `npm run test:coverage`.

### Decisions

No ADR. The choices (background thread with in-memory state, copy-then-delete moves,
History-API page switching, a test-only E2E volume) are local to this feature and are
recorded in the import and UI READMEs. The architecture's open point about synchronous or
background runs is resolved in [architecture.md](../../docs/architecture.md) by this spec.

### Files to Modify (refined)

Adds to the table above: `backend/app/receipt_import/files.py`, `run.py`, `service.py`,
`schemas.py`, `routes.py`, `errors.py`; `backend/tests/receipt_import_data.py`;
`backend/tests/integration/conftest.py` (`make_client` takes an import service);
`backend/tests/unit/storage/test_catalog_schema.py` (see
[Changes to existing tests](#changes-to-existing-tests));
`frontend/src/navigation.ts`; `frontend/src/App.test.tsx` (see
[Changes to existing tests](#changes-to-existing-tests));
`specs/features/product-management.md` (dated note on AC31).

### AC coverage

| AC | Parts |
|---|---|
| AC1, AC2 | P1, P2, P3, P4, P5 |
| AC3 | P3, P4 |
| AC4, AC5 | P2, P5 |
| AC6, AC7 | P3, P5 |
| AC8, AC9 | P3, P4, P6 |
| AC10, AC11 | P3, P4, P5 |
| AC12–AC17 | P4, P5 |
| AC18–AC23 | P6, P7 |
| AC24 | P1, P2, P7 |
| AC25 | P6 |
| AC26 | P10 |
| AC27–AC30 | P8, P9 |
| AC31 | P9, P10 |

### Changes during implementation

Recorded 2026-10-28; no AC changed.

- Unit test files are named `test_import_files.py`, `test_import_run.py` and
  `test_import_service.py`: the test folders have no `__init__.py`, so basenames must be
  unique, and `tests/unit/health/test_service.py` exists.
- `RunHooks` has `after_listing` and `after_file` only; AC17 is simulated through the
  `FileStore` (see [Service and state](#service-and-state)). `process_file` takes the import
  time as `now`; the service takes a `clock`, as the code standards ask.
- The failing test doubles live in `tests/receipt_import_data.py`, and the frontend test
  states in `frontend/src/test/imports.ts` (added to Files to Modify, as are
  `frontend/src/navigation.test.ts` and `docs/development.md`, which got the E2E volume note
  and a correction: `backend-e2e` keeps its database between runs while it is up).
- E2E: the copy's name sorts after the original's (`kopio.jpg` sorts before `kuitti.jpg`,
  AC3, and would have been imported first). File names and bytes are unique per run, because
  `run --rm` leaves `backend-e2e` running with its database and the previous run's report;
  with fixed names the old report would have satisfied the test (found in the audit).

## Tasks

Plan approved: 2026-10-28. Each task follows Red → Green → Refactor (`.agents/skills/tdd/SKILL.md`)
and ends with the tests, lint, format and type checks of the part it touched passing. Test
names start with the AC IDs they prove. Backend tasks come first, so the UI tasks build on a
working API.

### Backend: storage

- [x] **T1 Receipts schema** (AC1, AC4, AC24). First update
  `tests/unit/storage/test_catalog_schema.py` as described in
  [Changes to existing tests](#changes-to-existing-tests) and see it still pass on `0001`;
  then add a failing `tests/unit/storage/test_receipts_schema.py`; then
  `backend/app/storage/migrations/0002_receipts.sql`. Proof: a migrated database has table
  `receipts` and schema version 2; a second row with the same `image_hash` is refused; a hash
  that is not 64 characters is refused by the `CHECK`; the catalog schema test and
  `test_startup_migrations.py` stay green.
- [x] **T2 Receipt repository** (AC1, AC4, AC5, AC12, AC14). `backend/app/storage/receipt_repository.py`.
  Proof: `tests/unit/storage/test_receipt_repository.py`: `add` returns the row;
  `get_by_hash` finds it and returns `None` for an unknown hash; `delete` removes it; `add`
  with an existing hash raises `sqlite3.IntegrityError`.

### Backend: import

- [x] **T3 Test data helper** (test support for AC1–AC25). `backend/tests/receipt_import_data.py`:
  `jpeg(tag)` and `png(tag)` return signature + distinct bytes. Proof: used by T4–T10; a
  short test checks that two tags give different bytes with the right signatures.
- [x] **T4 File rules** (AC2, AC3, AC6–AC8, AC10, AC11). `backend/app/receipt_import/files.py`:
  `image_identifier`, `check_format`, `is_ignored`, `free_target_name`. Proof:
  `tests/unit/receipt_import/test_import_files.py`: the unit rows for these functions, including
  SHA-256 of `b"abc"`, every supported and unsupported case of AC6 and AC7, the ignored names
  of AC8 in any case, `kuitti (3).jpg` and `README (2)`.
- [x] **T5 Local file store** (AC3, AC8, AC10, AC11, AC23). `LocalFileStore` in the same
  file: `list_files`, `read_bytes`, `names_in`, `move`. Proof: same test file with temporary
  folders: listing order and ignored entries of AC3 and AC8; `names_in` lower-cased; `move`
  copies the bytes and removes the source; `move` to an existing name raises `OSError` and
  changes nothing; a failing delete of the source (simulated) removes the target copy and
  raises `OSError`.
- [x] **T6 One file: imported and duplicate** (AC1, AC2, AC4, AC5, AC10).
  `backend/app/receipt_import/run.py` `process_file`, `FileResult`. Proof:
  `tests/unit/receipt_import/test_import_run.py`: a new image gives `imported`, one row with the
  hash, the final name and the time, and the file in the done folder; the same bytes again
  give `duplicate` and leave the file; a collision gives `kuitti (3).jpg` in both the row and
  the done folder.
- [x] **T7 One file: failures** (AC6, AC7, AC11–AC17). Same function. Proof: same file, one
  test per row of [Steps of one file](#steps-of-one-file): `unsupported_format` (file in the
  failed folder, suffix on collision, original name in the result), `read_failed`,
  `save_failed`, `move_failed` with the row deleted and the file in the import folder,
  failed-folder move failing (file stays, reason kept), `internal_error` for a raised
  `RuntimeError`.
- [x] **T8 Service state and start checks** (AC9, AC19–AC22).
  `backend/app/receipt_import/service.py` `ImportService`, `RunHooks`;
  `backend/app/receipt_import/errors.py`; texts in `backend/app/texts.py`. Proof:
  `tests/unit/receipt_import/test_import_service.py`: `idle` state before a run; `start` returns
  `running` with `total` and `processed` 0; a second start while paused raises
  `import_running`; each folder missing or not writable (`can_write`) in turn raises
  `folders_unavailable` and leaves the state unchanged; an empty folder finishes with zeros
  and `finished_at` set.
- [x] **T9 Service run in the background** (AC17, AC18, AC23, AC25). Same module. Proof:
  same test file with the real thread and `RunHooks` events: progress 1/3 while paused after
  the first file; a file added after listing is not processed; a run whose database cannot be
  opened ends `finished` with `internal_error` for each file; `caplog` has exactly one start
  and one finish line with the counts, and no file name or file bytes, also for an
  `internal_error` traceback.
- [x] **T10 Import API** (AC1–AC25 end to end). `backend/app/receipt_import/schemas.py`,
  `routes.py`; `backend/app/main.py` (`import_service` parameter);
  `backend/tests/integration/conftest.py` (`make_client` passes it on). Proof:
  `tests/integration/test_import_api.py`: every row of the integration table, polling with a
  helper that waits for `finished` (5 s limit); AC24 with a second app on the same database
  file.

### Frontend

- [x] **T11 Import API client** (AC27, AC29). `frontend/src/api/imports.ts`. Proof:
  `imports.test.ts`: `getImport` and `startImport` call `GET` and `POST /api/import` and
  return the typed state; 409 gives `{ok: false}` with code and message.
- [x] **T12 Page switching and shell** (AC26). First update `frontend/src/App.test.tsx` as
  described in [Changes to existing tests](#changes-to-existing-tests) (two links;
  `GET /api/import` mocked as `idle`) and add the AC26 test; see them fail; then
  `frontend/src/navigation.ts` and `frontend/src/App.tsx`. Proof: `navigation.test.ts`:
  `/tuonti` gives Tuonti, other paths Tuotteet, `go` pushes the path, `popstate` switches
  back; `App.test.tsx`: two links, Tuotteet current at start, clicking "Tuonti" shows the
  Tuonti page and marks it current, status line visible, no English text.
- [x] **T13 Tuonti page** (AC27–AC31). `frontend/src/components/ImportPage.tsx`,
  `frontend/src/i18n/fi.ts` (`fi.import`), MSW handlers in `frontend/src/test/`. Proof:
  `ImportPage.test.tsx`: the ImportPage rows of the component table; polling checked with
  fake timers; no request after unmount.
- [x] **T14 E2E journey** (AC1, AC4, AC6, AC26, AC27). `compose.yaml` (volume
  `rrmc-e2e-import`, `E2E_IMPORT_DIR`), `frontend/e2e/import.spec.ts`. Proof:
  `docker compose --profile e2e run --rm e2e` passes the import journey and the existing
  `app.spec.ts` and `products.spec.ts` journeys; `docker compose config` shows the volume
  only on `backend-e2e` and `e2e`, not on `backend`.

### Docs and final checks

- [x] **T15 Documentation** (all). Following `.agents/skills/document/SKILL.md`: create
  `docs/subsystems/import/README.md`; update `docs/datamodel.md`, `docs/api-reference.md`,
  `docs/architecture.md` (resolve the background-run point, duplicates stay, reading added
  later), `docs/subsystems/storage/README.md`, `docs/subsystems/ui/README.md`,
  `docs/glossary.md`, `docs/content-plan.md`, and `docs/development.md` if the E2E volume
  needs a note; `specs/PRD.md` (FR-2 resolved, open question 2); a dated note on AC31 in
  `specs/features/product-management.md`. Proof: every endpoint, error code, failure reason,
  table and term of this spec appears in exactly one doc and is linked from the others; links
  resolve.
- [x] **T16 Final verification** (all). Run every command in
  [development.md](../../docs/development.md#commands), and coverage
  (`docker compose run --rm backend pytest --cov=app.receipt_import --cov=app.storage`,
  `docker compose run --rm frontend npm run test:coverage`). Proof: all green; coverage meets
  the targets in the Testing Strategy; every AC has a test whose name carries its ID. Then hand
  over to `review-audit`.

## Audit

Audited 2026-10-28, verdict PASS after one fix cycle. An independent reviewer read the code
against this spec; its findings were checked in the code before acting on them.

- Acceptance criteria: 31/31 met; every AC has a test whose name carries its ID.
- Tests: backend 309 passed, 100 % lines and branches in `app.receipt_import`, 100 % lines
  in `app.storage`; frontend 78 passed, 100 % lines in the Tuonti page, the import client and
  the navigation (99 % overall); E2E 5 passed, twice in a row; container tests passed. Lint,
  format and type checks clean.
- Security: no findings. File names come from the folder listing and suffixes reuse the stem,
  so no path traversal; symlinks are skipped; nothing is overwritten. Logs hold counts and
  exception types only. `npm audit` 0 vulnerabilities. `pip-audit` is not installed in the
  backend image and was not run.
- Fixed in the audit (see [learnings](../../docs/learnings.md)): the E2E journey could pass on
  the previous run's report; a late answer to the page's first request could hide a started
  run (AC27); an error other than `OSError` while moving to the done folder left an orphan
  receipt row. One unit test name was corrected (AC20, not AC13).
- Later: if the background thread cannot start (`Thread.start()` raises), the state stays
  `running` until a restart and every start gets 409. `App.tsx` has no test for a modified
  click (new tab) on a navigation link.
- Not part of this change: in this working copy `frontend/e2e/products.spec.ts` has CRLF
  line endings (`core.autocrlf=true`), so `npm run format:check` warns about it; Git stores
  it with LF and shows no content change.

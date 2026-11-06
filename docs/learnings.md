# Learnings

Fixed errors, newest first: context, symptom, root cause, solution, prevention.

## 2026-11-06: The import polling test failed under load

- **Context:** The monthly budget spec added five frontend test files, so more test files
  ran side by side.
- **Symptom:** `AC28: a running import is shown on page open and polled about every second`
  in @frontend/src/components/ImportPage.test.tsx failed in about one full run of five with
  `expected 1 to be 2`. It never failed in serial runs, and the page had not changed.
- **Root cause:** Advancing the fake clock fires the poll timer, which only starts the
  request. MSW answers it on real time, so the count read right after the clock moved could
  still be the old one. The test depended on the machine being idle.
- **Solution:** the test counts the `fetch` calls, which the timer starts at once, instead of
  the requests MSW has seen. A first fix with `vi.waitFor` was withdrawn: under fake timers
  `vi.waitFor` moves the clock on every check, so a slower poll passed the test.
- **Prevention:** to check a timer, count what it starts synchronously. Do not use `vi.waitFor`
  around a check of timing under fake timers. Wait with `findBy` only for what the answer shows.

## 2026-11-04: The backend answered any Host header

- **Context:** Writing `docs/security.md`, checking what CORS stops.
- **Symptom:** a request with `Host: evil.example` got normal data with status 200.
- **Root cause:** CORS works on the `Origin` header. After DNS rebinding a page is the same
  origin as the backend for the browser, so CORS does not apply.
- **Solution:** @backend/app/host_check.py answers 400 `invalid_host` for an unknown name.
  Vite's proxy sends the Compose service name, so `backend` and `backend-e2e` are allowed.
  Regression tests in @backend/tests/integration/test_host_check.py. Tests now use the base
  URL `http://127.0.0.1`.
- **Prevention:** a new way to reach the backend, such as a new Compose service name, must
  be added to the known names.

## 2026-11-04: A very large catalog id gave a server error

- **Context:** The doc scan of the API reference against the code, categories and products.
- **Symptom:** an id outside SQLite's integer range answered 500 `internal_error` instead of
  `not_found`, in the path of `/api/categories/{id}` and `/api/products/{id}`. The same
  happened with `category_id` and `parent_id`, in a body or in the product filter.
- **Root cause:** Python's `int` has no limit, and binding a value outside 64 bits raises
  `OverflowError`. Line editing added the check for receipts and lines only, in the review
  service (`_require_ids`).
- **Solution:** `CatalogRepository.get_category` and `get_product` return `None` for such an
  id (@backend/app/storage/catalog_repository.py), so every route gives its usual "does not
  exist" error. Regression tests `test_*_outside_sqlite_range_*` in
  @backend/tests/integration/test_categories_api.py and test_products_api.py.
- **Prevention:** a new id from a request needs a test with `2**63` and `-(2**63) - 1`.

## 2026-11-03: A line's delete confirmation wrapped on the receipt page

- **Context:** Deleting a line on the receipt page on a wide window (line editing, styling
  specs).
- **Symptom:** after the line's `Poista`, the question `Poistetaanko?` and the buttons
  `Poista` and `Peruuta` were not on one row.
- **Root cause:** the line table is fitted to its box (2026-11-02 fix below), so its last
  column is narrow; the confirmation is inline text and buttons, and the browser wrapped it
  at its spaces.
- **Solution:** the confirmation `span` has the class `confirm-delete` with
  `white-space: nowrap` (@frontend/src/components/ConfirmDelete.tsx,
  @frontend/src/styles.css); the name field shrinks instead. Regression test
  `styling AC14: a line's delete confirmation stays on one row and in sight`.
- **Prevention:** a layout test of a control that changes its content (a confirmation, an
  error) must check the changed state too, not only the first render.

## 2026-11-03: A failed image name with a NUL character gave a server error

- **Context:** receipt-management audit (T26), failed images preview and manual receipts.
- **Symptom:** `GET /api/failed-images/image?name=a%00.jpg`, or the same name as
  `image_file_name` in `POST /api/receipts`, answered 500 `internal_error` instead of
  `image_not_found`.
- **Root cause:** the name passed the name and suffix checks, and `Path.resolve()` raises
  `ValueError` ("embedded null character"), not `OSError`, which was the only error caught.
- **Solution:** `FailedFolder._path` catches `ValueError` too
  (@backend/app/review/failed_images.py); regression cases `a\x00.jpg` in the AC19 and AC23
  tests.
- **Prevention:** test a path built from a request with a NUL character as well as with
  `..` and path separators.

## 2026-11-02: A line's delete button was out of sight on the receipt page

- **Context:** Using the receipt page on a wide window (line editing, styling specs).
- **Symptom:** the user could not see a line's `Poista` button together with the rest of
  the line; it showed only after scrolling the line table sideways.
- **Root cause:** beside the image the lines got 3/5 of the content width (about 700 px at
  1280 px). The name input, amount input, checkbox, category select and delete button kept
  their natural widths, so the table was 74 px wider than its box and the `.table-box`
  scrolled, hiding the last column.
- **Solution:** the lines get 2/3 of the width (`minmax(0, 1fr) minmax(0, 2fr)`), and the
  inputs and the select in the line table shrink with their column (`width: 100%`), the
  amount input keeping at least `6em` (@frontend/src/styles.css); regression test
  `styling AC14: every line's delete button is in sight beside the image`.
- **Prevention:** a layout test of a table with controls must check that its box does not
  overflow at a common window width (1280 px), not only where the table starts.

## 2026-11-02: E2E download canceled with a new endpoint

- **Context:** CSV export spec, E2E test of the download links (T10).
- **Symptom:** Playwright reported `download.path: canceled`; the backend answered 404 for
  `/api/export/totals`, although the integration tests passed.
- **Root cause:** `backend-e2e` stays running after `run --rm` and does not reload code, so
  it served the app as it was when it started, without the new routes.
- **Solution:** `docker compose restart backend-e2e`, then the E2E run passed twice.
- **Prevention:** restart `backend-e2e` after a backend change before the E2E run
  ([development.md](development.md#e2e-tests)).

## 2026-10-31: A field lost text typed while its save waited

- **Context:** Audit of the line-editing spec (PC12, AC32).
- **Symptom:** none seen; found in review. Typing in a field after Enter, while the save
  waited, was wiped when the answer arrived, and the new text was never sent.
- **Root cause:** `EditableField` cleared its draft after every successful save, whatever
  the draft was by then.
- **Solution:** the draft is cleared only while it still equals the text that was sent
  (@frontend/src/components/EditableField.tsx); regression test `line-editing AC32: text
  typed while a save waits is kept when the answer arrives`.
- **Prevention:** state set after an `await` must check that the state it replaces did not
  change during the wait.

## 2026-10-30: A proxy test could not fail

- **Context:** Audit of the receipt-reading spec (AC23).
- **Symptom:** none seen; found in review. `test_ac23_proxy_settings_are_ignored` passed a
  `httpx2.MockTransport` and checked that the request reached it.
- **Root cause:** `httpx2` sends to a given transport even with `trust_env=True`, so the test
  passed whatever the client's setting was. Checked in the backend container.
- **Solution:** the test builds `OllamaReceiptModel` without a transport and checks that its
  client has `trust_env` off; a mutation (`trust_env=True`) makes it fail
  (@backend/tests/unit/engines/test_model.py).
- **Prevention:** a test of a safety setting must be seen failing once with the setting
  wrong. The evaluation tool's `test_ac19_proxy_settings_are_ignored` has the same
  weakness and is still open.

## 2026-10-29: Phone photos were read on their side

- **Context:** The first real model evaluation, 25 phone photos of receipts.
- **Symptom:** every `ocr:` variant had 0 % `total` and `date`, while the `vision:` variant
  had 100 % `total`. Nine OCR texts were empty and most others had only a few digits.
- **Root cause:** phones store the photo on its side (4000 × 3000) and record the turn in
  the EXIF orientation tag (6 on all 25). `preprocess` converted the image to grayscale,
  which dropped the tag, so Tesseract got the receipt sideways.
- **Solution:** `preprocess` turns the image with `ImageOps.exif_transpose` first; then
  Tesseract's orientation detection (`--psm 0`) turns it when the tag is missing or wrong
  and the confidence is at least 2.0; `vision:` images are turned from EXIF too. The detail
  file records what was applied (@backend/evaluation/ocr.py, @backend/evaluation/runner.py).
- **Prevention:** `test_ac22_exif_orientation_turns_the_image_upright`,
  `test_ac24_real_osd_turns_a_receipt_on_its_side_upright`. Synthetic test images must
  include photos with an EXIF orientation tag, not only upright images. The receipt-reading
  spec needs the same step.

## 2026-10-28: The evaluation tool could leak a file name or lose a long run

- **Context:** Audit of the model evaluation tool.
- **Symptom:** none seen; found in review. A `vision:` image that could not be read, any
  unexpected error, or the same variant given twice stopped the run with a traceback. The
  traceback could print a receipt's file name, and a repeated variant failed only after the
  first variant had run, without writing `summary.md`.
- **Root cause:** only model and OCR errors were caught per receipt; `main` let other
  exceptions escape; variants were not checked for a shared detail folder.
- **Solution:** a receipt's image read failure is `image_error`; `main` prints only
  `Evaluation failed: <error type>` with exit code 3 (AC21); a repeated variant is refused
  before Ollama is called (AC9) (@backend/evaluation/runner.py, @backend/evaluation/cli.py).
- **Prevention:** `test_ac21_unexpected_error_prints_only_its_type`,
  `test_ac9_repeated_variant_is_refused_before_ollama`,
  `test_ac12_image_file_that_cannot_be_read_is_an_image_error`. A tool that handles private
  data must never print an exception's message or traceback.

## 2026-10-28: Proxy variables could send evaluation prompts to another host

- **Context:** Audit of the model evaluation tool (AC19).
- **Symptom:** none seen; found in review. `httpx2.Client` reads `HTTP_PROXY` and
  `ALL_PROXY` by default, so a proxy set in the environment would receive OCR text and
  images.
- **Root cause:** the client's default `trust_env=True`.
- **Solution:** `OllamaReader` builds its client with `trust_env=False`
  (@backend/evaluation/ollama.py).
- **Prevention:** `test_ac19_proxy_settings_are_ignored`. Clients that carry receipt data
  set `trust_env=False`.

## 2026-10-28: Rounded percentages could meet a 100 % criterion

- **Context:** Audit of the model evaluation tool.
- **Symptom:** none seen; found in review. 199 valid answers of 200 showed `valid 100 %`
  and `meets criteria: yes`.
- **Root cause:** the criteria compared the rounded percentages.
- **Solution:** the criteria compare exact counts (@backend/evaluation/scoring.py).
- **Prevention:** `test_ac17_criteria_use_exact_shares_not_rounded_percentages`. Compare
  thresholds on exact values; round only for display.

## 2026-10-28: The import E2E test could pass on the previous run's report

- **Context:** Audit of the receipt import feature.
- **Symptom:** none seen; found in review. The import journey wrote fixed file names and
  checked the report's counts and names, which the previous run's report already showed.
- **Root cause:** `docker compose --profile e2e run --rm e2e` leaves `backend-e2e` running,
  so its database and the in-memory import state survive between E2E runs. A failed start
  (for example 503) keeps the old report on the page, and the test would still pass.
- **Solution:** file names and bytes are unique per run, and the test asserts that no error
  is shown (@frontend/e2e/import.spec.ts).
- **Prevention:** E2E journeys must not depend on `backend-e2e` being new; check for values
  that only the current run can produce.

## 2026-10-28: A late first answer hid a started import

- **Context:** Audit of the receipt import feature.
- **Symptom:** none seen; found in review. Clicking "Tuo kuitit" before the Tuonti page's
  first `GET /api/import` had answered could show `Tuontia ei ole vielä ajettu.` with the
  button enabled while a run was active, and polling stopped.
- **Root cause:** the answer to the first `GET` replaced the newer state from `POST`.
- **Solution:** after a successful start, the page ignores the first `GET`'s answer
  (@frontend/src/components/ImportPage.tsx).
- **Prevention:** `AC27: a late answer to the first request does not hide a started run` in
  `ImportPage.test.tsx`. When two requests can set the same state, decide which answer wins.

## 2026-10-28: An unexpected error after the commit left a receipt without its file

- **Context:** Audit of the receipt import feature.
- **Symptom:** none seen; found in review. If moving a file to the done folder raised an
  error other than `OSError`, the file went to the failed folder but its receipt row stayed,
  so the image was later reported as a duplicate.
- **Root cause:** `_import` deleted the row only for `OSError` from the move.
- **Solution:** the row is deleted for any error from the move, then the error goes on to
  the `internal_error` handling (@backend/app/receipt_import/run.py).
- **Prevention:** `test_ac17_unexpected_error_in_move_to_done_deletes_the_row`. After a
  commit, every failure path must undo what the commit promised.

## 2026-10-27: A group could become a category inside itself

- **Context:** Audit of the product management feature.
- **Symptom:** `PATCH /api/categories/{id}` with `{"kind": "category", "parent_id": <own id>}`
  on an empty group answered 200. The item then disappeared from `GET /api/categories`,
  because it was a category whose parent was not a group, but it was still accepted as a
  product category.
- **Root cause:** the service checks the resulting state, but it read the parent's kind from
  the database before the update. For the item itself, that is its old kind, `group`.
- **Solution:** `CategoryService.update` refuses an item as its own parent with
  `invalid_parent` (@backend/app/categorization/service.py).
- **Prevention:** `test_ac10_group_cannot_become_a_category_inside_itself` (unit) and
  `test_ac10_item_cannot_be_its_own_parent` (integration). When a rule checks a resulting
  state, any row read from the database that the same update changes must be the new value.

## 2026-10-27: SQLite connection used from another thread

- **Context:** Product management E2E tests, with the backend running in Uvicorn.
- **Symptom:** `GET /api/categories` and other catalog requests answered 500
  `internal_error`. The backend log showed `sqlite3.ProgrammingError: SQLite objects created
  in a thread can only be used in that same thread`. The integration tests passed.
- **Root cause:** FastAPI runs a sync dependency and a sync route in its threadpool, not
  always in the same thread. The connection opened in the dependency was used by the route in
  another thread, and Python's `sqlite3` refuses that by default (`check_same_thread=True`).
  `TestClient` usually reuses one thread, which hid the error.
- **Solution:** `connect()` in @backend/app/storage/db.py opens connections with
  `check_same_thread=False`. That is safe here because a connection belongs to one request
  and is used by one thread at a time.
- **Prevention:** the regression test
  `test_connection_can_be_used_in_another_thread` in `backend/tests/unit/storage/test_db.py`.
  Never share one connection between requests.

## Related Documents

- [storage](subsystems/storage/README.md)
- [development.md](development.md)

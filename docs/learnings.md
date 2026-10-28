# Learnings

Fixed errors, newest first: context, symptom, root cause, solution, prevention.

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

# Learnings

Fixed errors, newest first: context, symptom, root cause, solution, prevention.

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

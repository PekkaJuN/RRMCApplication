-- Receipts: one row per imported image. The read data (store, date, lines, total, OCR text)
-- is added by later migrations.

CREATE TABLE receipts (
    id          INTEGER PRIMARY KEY,
    image_hash  TEXT NOT NULL UNIQUE CHECK (length(image_hash) = 64),  -- SHA-256, lowercase hex
    file_name   TEXT NOT NULL,     -- name in the done folder, after any numbered suffix
    imported_at TEXT NOT NULL      -- UTC ISO 8601, e.g. 2026-10-28T10:00:01Z
);

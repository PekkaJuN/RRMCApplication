-- Manual receipts (receipt-management spec, FR-47): a receipt typed in by the user may have
-- no image, so image_hash and file_name become nullable, both or neither. SQLite cannot drop
-- NOT NULL in place, so the table is rebuilt. The runner turns foreign keys off around this
-- file; with them on, DROP TABLE would cascade-delete every receipt line. The ids are copied,
-- so the lines still point at the same receipts. AUTOINCREMENT keeps a deleted receipt's id
-- from being given to the next one, so an old link cannot open another receipt.

CREATE TABLE receipts_new (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,  -- never reused after a delete
    image_hash    TEXT UNIQUE         -- SHA-256, lowercase hex; NULL for a receipt without an image
        CHECK (image_hash IS NULL OR length(image_hash) = 64),
    file_name     TEXT,               -- name in the done folder; NULL without an image
    imported_at   TEXT NOT NULL,      -- UTC ISO 8601; the creation time for a manual receipt
    store         TEXT,
    purchase_date TEXT
        CHECK (purchase_date IS NULL
            OR purchase_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    total_cents   INTEGER,
    ocr_text      TEXT,               -- NULL for a manual receipt
    reviewed      INTEGER NOT NULL DEFAULT 0 CHECK (reviewed IN (0, 1)),
    CHECK ((image_hash IS NULL) = (file_name IS NULL))
);

INSERT INTO receipts_new (id, image_hash, file_name, imported_at, store, purchase_date,
    total_cents, ocr_text, reviewed)
SELECT id, image_hash, file_name, imported_at, store, purchase_date, total_cents, ocr_text,
    reviewed
FROM receipts;

DROP TABLE receipts;

ALTER TABLE receipts_new RENAME TO receipts;

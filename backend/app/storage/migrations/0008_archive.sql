-- Archive (archiving spec P2, FR-40): a finished year's receipts and lines move here. No
-- column refers to the active tables, so later catalog changes (FR-36, FR-37) never touch
-- archived lines: their product, category and group are stored as names. The ids are the
-- active ids, copied: active ids are AUTOINCREMENT and never reused, so they cannot collide.
-- Every archived receipt was reviewed, so the review state is not stored.

CREATE TABLE archived_receipts (
    id            INTEGER PRIMARY KEY,  -- the active receipt's id
    year          INTEGER NOT NULL CHECK (year BETWEEN 2000 AND 9999),
    purchase_date TEXT NOT NULL
        CHECK (purchase_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    store         TEXT,
    total_cents   INTEGER,
    image_hash    TEXT UNIQUE           -- still a duplicate for import (FR-42)
        CHECK (image_hash IS NULL OR length(image_hash) = 64),
    file_name     TEXT,                 -- name in the archive folder after the move
    imported_at   TEXT NOT NULL,
    archived_at   TEXT NOT NULL,        -- UTC ISO 8601 with seconds
    CHECK ((image_hash IS NULL) = (file_name IS NULL)),
    CHECK (CAST(substr(purchase_date, 1, 4) AS INTEGER) = year)
);

CREATE INDEX archived_receipts_year ON archived_receipts (year);

CREATE TABLE archived_lines (
    id                INTEGER PRIMARY KEY,  -- the active line's id
    receipt_id        INTEGER NOT NULL REFERENCES archived_receipts (id) ON DELETE CASCADE,
    position          INTEGER NOT NULL CHECK (position >= 1),
    name              TEXT NOT NULL,
    product_name      TEXT NOT NULL,        -- the linked product's name, else the line's name
    amount_cents      INTEGER NOT NULL,
    is_deposit_refund INTEGER NOT NULL CHECK (is_deposit_refund IN (0, 1)),
    category_name     TEXT,
    group_name        TEXT,
    UNIQUE (receipt_id, position),
    CHECK (group_name IS NULL OR category_name IS NOT NULL),
    CHECK (is_deposit_refund = 0 OR category_name IS NULL)
);

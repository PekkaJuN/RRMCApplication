-- Read receipt data and receipt lines (receipt-reading spec). Receipts imported before this
-- migration keep NULL in the read columns.

ALTER TABLE receipts ADD COLUMN store TEXT;            -- as read; '' when the model found none
ALTER TABLE receipts ADD COLUMN purchase_date TEXT     -- YYYY-MM-DD; NULL when not read
    CHECK (purchase_date IS NULL
        OR purchase_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]');
ALTER TABLE receipts ADD COLUMN total_cents INTEGER;   -- integer cents (NFR-6)
ALTER TABLE receipts ADD COLUMN ocr_text TEXT;         -- raw Tesseract output (FR-10)

CREATE TABLE receipt_lines (
    id                INTEGER PRIMARY KEY,
    receipt_id        INTEGER NOT NULL REFERENCES receipts (id) ON DELETE CASCADE,
    position          INTEGER NOT NULL CHECK (position >= 1),  -- printed order, from 1
    name              TEXT NOT NULL CHECK (trim(name) <> ''),  -- as read
    amount_cents      INTEGER NOT NULL,  -- after any discount, including any deposit (FR-9)
    is_deposit_refund INTEGER NOT NULL CHECK (is_deposit_refund IN (0, 1)),
    CHECK (is_deposit_refund = 0 OR amount_cents < 0),
    UNIQUE (receipt_id, position)
);

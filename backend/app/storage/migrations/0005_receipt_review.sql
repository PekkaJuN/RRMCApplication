-- Review state of a receipt (receipt-review spec, FR-21): 0 unreviewed, 1 confirmed. Receipts
-- imported before this migration start unreviewed.

ALTER TABLE receipts ADD COLUMN reviewed INTEGER NOT NULL DEFAULT 0 CHECK (reviewed IN (0, 1));

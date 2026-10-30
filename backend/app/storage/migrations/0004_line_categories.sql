-- Line categories (categorization spec). Lines stored before this migration keep NULL in all
-- three columns: they have no category.

ALTER TABLE receipt_lines ADD COLUMN category_id INTEGER
    REFERENCES categories (id) ON DELETE RESTRICT;
-- Where the category came from (FR-15); a deposit refund never has a category (FR-44).
ALTER TABLE receipt_lines ADD COLUMN category_source TEXT
    CHECK (category_source IN ('remembered', 'model', 'user'))
    CHECK ((category_source IS NULL) = (category_id IS NULL))
    CHECK (category_id IS NULL OR is_deposit_refund = 0);
-- Deleting a product removes the link and keeps the line's category (FR-36).
ALTER TABLE receipt_lines ADD COLUMN product_id INTEGER
    REFERENCES products (id) ON DELETE SET NULL
    CHECK (product_id IS NULL OR category_id IS NOT NULL);

CREATE INDEX receipt_lines_category ON receipt_lines (category_id);
CREATE INDEX receipt_lines_product ON receipt_lines (product_id);

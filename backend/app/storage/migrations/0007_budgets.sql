-- Monthly budgets (budget spec, P1). A row exists only for a saved or moved amount; a missing
-- row means 0. There is no upper limit here: a moved budget may exceed AMOUNT_LIMIT.

CREATE TABLE budgets (
    category_id  INTEGER PRIMARY KEY REFERENCES categories (id) ON DELETE CASCADE,
    amount_cents INTEGER NOT NULL CHECK (amount_cents >= 0)
);

-- Groups and categories share one table and one name namespace (product-management spec).
-- "Parent is a group" and "a product's category is not a group" need another row, which
-- a CHECK cannot read, so the categorization services enforce them.
CREATE TABLE categories (
    id        INTEGER PRIMARY KEY,
    name      TEXT NOT NULL,
    name_key  TEXT NOT NULL UNIQUE,
    kind      TEXT NOT NULL CHECK (kind IN ('group', 'category')),
    parent_id INTEGER REFERENCES categories (id) ON DELETE RESTRICT,
    CHECK (kind = 'category' OR parent_id IS NULL)
);
CREATE INDEX categories_parent_id ON categories (parent_id);

CREATE TABLE products (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    name_key    TEXT NOT NULL UNIQUE,
    category_id INTEGER NOT NULL REFERENCES categories (id) ON DELETE RESTRICT
);
CREATE INDEX products_category_id ON products (category_id);

-- One-time facts about the database; 'catalog_seeded_at' marks that the default list ran.
CREATE TABLE app_state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

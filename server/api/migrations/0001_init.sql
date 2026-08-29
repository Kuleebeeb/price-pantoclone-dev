-- Cong tu bang quotations cua ban SQLite (Z:\1\database.py) sang Postgres.
-- Giu nguyen ten cot de moi truong JSON snapshot cua ban desktop nap lai duoc.

CREATE TABLE IF NOT EXISTS quotations (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    quote_ref           TEXT        NOT NULL UNIQUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    quote_date          DATE        NOT NULL,
    customer            TEXT        NOT NULL,
    customer_code       TEXT        NOT NULL DEFAULT '',
    item_description    TEXT        NOT NULL DEFAULT '',
    product_reference   TEXT        NOT NULL DEFAULT '',
    product_image_path  TEXT        NOT NULL DEFAULT '',
    revised_from_ref    TEXT        NOT NULL DEFAULT '',
    product_key         TEXT        NOT NULL,
    product_label       TEXT        NOT NULL,
    size_text           TEXT        NOT NULL,
    length_reference    TEXT        NOT NULL DEFAULT '',
    inputs_json         JSONB       NOT NULL,
    formulas_json       JSONB       NOT NULL,
    results_json        JSONB       NOT NULL,
    unit_price          NUMERIC(18,6) NOT NULL,
    total_price         NUMERIC(18,6) NOT NULL,
    grams_per_item      NUMERIC(18,6) NOT NULL,
    pack_quantity       NUMERIC(18,6) NOT NULL DEFAULT 0,
    pack_weight_kg      NUMERIC(18,6) NOT NULL DEFAULT 0,
    sack_quantity       NUMERIC(18,6) NOT NULL DEFAULT 0,
    sack_weight_kg      NUMERIC(18,6) NOT NULL DEFAULT 0,

    CONSTRAINT quotations_product_key_known CHECK (
        product_key IN ('flat','opaque','gusset','roll','cover')
    ),
    CONSTRAINT quotations_grams_positive CHECK (grams_per_item > 0),
    CONSTRAINT quotations_prices_not_negative CHECK (unit_price >= 0 AND total_price >= 0)
);

CREATE INDEX IF NOT EXISTS idx_quotes_customer ON quotations (customer);
CREATE INDEX IF NOT EXISTS idx_quotes_customer_code ON quotations (customer_code);
CREATE INDEX IF NOT EXISTS idx_quotes_date ON quotations (quote_date DESC);
CREATE INDEX IF NOT EXISTS idx_quotes_product ON quotations (product_key);
CREATE INDEX IF NOT EXISTS idx_quotes_size ON quotations (size_text);
CREATE INDEX IF NOT EXISTS idx_quotes_reference ON quotations (product_reference);

-- Ban desktop cap so bang SELECT MAX()+1 (database.py:147). Hai nguoi bam Luu
-- cung luc la trung so. Bang dem + UPDATE ... RETURNING cap so trong MOT cau,
-- Postgres khoa dong do lai, nen khong the trung. Dinh dang so giu NGUYEN:
-- QT-YYYYMMDD-NNNN.
CREATE TABLE IF NOT EXISTS quotation_counters (
    counter_date DATE   PRIMARY KEY,
    last_number  INTEGER NOT NULL DEFAULT 0 CHECK (last_number >= 0)
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

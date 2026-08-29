-- Ba thu bien mot may chu tinh gia thanh mot san pham nhieu nguoi dung chung:
-- tai khoan, ban ve, va du dau vet de dong bo lai duoc tu may khong co mang.

-- ---------------------------------------------------------------- tai khoan
CREATE TABLE IF NOT EXISTS users (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email         TEXT        NOT NULL UNIQUE,
    full_name     TEXT        NOT NULL DEFAULT '',
    password_hash TEXT        NOT NULL,
    is_active     BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT users_email_lower CHECK (email = lower(email))
);

-- ------------------------------------------------------------- dong bo
-- client_uid la CAN CUOC do may tram sinh ra luc bam Luu, truoc khi co mang.
-- Nho no, gui lai lan thu hai khong tao ban ghi thu hai: may chu tra ve dung
-- so cu. Khong co no thi mot lan mat song giua chung la mot to bao gia doi.
ALTER TABLE quotations ADD COLUMN IF NOT EXISTS client_uid TEXT;
ALTER TABLE quotations ADD COLUMN IF NOT EXISTS device_name TEXT NOT NULL DEFAULT '';
ALTER TABLE quotations ADD COLUMN IF NOT EXISTS created_by BIGINT REFERENCES users(id);
ALTER TABLE quotations ADD COLUMN IF NOT EXISTS saved_at TIMESTAMPTZ;

CREATE UNIQUE INDEX IF NOT EXISTS idx_quotes_client_uid
    ON quotations (client_uid) WHERE client_uid IS NOT NULL;

-- ------------------------------------------------------------- ban ve
-- Guong cua bang drawings trong may tram (database.py, 27-08-2026).
CREATE TABLE IF NOT EXISTS drawings (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    doc_no        TEXT        NOT NULL UNIQUE,
    client_uid    TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    drawing_date  DATE        NOT NULL,
    revision      TEXT        NOT NULL DEFAULT 'A',
    amended_from  TEXT        NOT NULL DEFAULT '',
    customer      TEXT        NOT NULL,
    customer_code TEXT        NOT NULL DEFAULT '',
    title         TEXT        NOT NULL,
    part_no       TEXT        NOT NULL DEFAULT '',
    product_key   TEXT        NOT NULL,
    length_datum  TEXT        NOT NULL DEFAULT '',
    display_unit  TEXT        NOT NULL DEFAULT 'mm',
    width_mm      NUMERIC(14,4) NOT NULL,
    length_mm     NUMERIC(14,4) NOT NULL,
    height_mm     NUMERIC(14,4) NOT NULL DEFAULT 0,
    gusset_mm     NUMERIC(14,4) NOT NULL DEFAULT 0,
    thickness_mm  NUMERIC(14,4) NOT NULL DEFAULT 0,
    quote_ref     TEXT        NOT NULL DEFAULT '',
    spec_json     JSONB       NOT NULL,
    device_name   TEXT        NOT NULL DEFAULT '',
    created_by    BIGINT      REFERENCES users(id),

    CONSTRAINT drawings_positive CHECK (width_mm > 0 AND length_mm > 0),
    CONSTRAINT drawings_datum CHECK (length_datum IN ('', 'opening_to_seal', 'opening_to_bottom'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_drawings_client_uid
    ON drawings (client_uid) WHERE client_uid IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_drawings_customer ON drawings (customer);
CREATE INDEX IF NOT EXISTS idx_drawings_quote ON drawings (quote_ref);

-- Cung cach cap so nhu bang bao gia: MOT cau UPDATE ... RETURNING, khong bao
-- gio MAX()+1. So ban ve la DFA-YYYY-NNNN, dem theo NAM.
CREATE TABLE IF NOT EXISTS drawing_counters (
    counter_year TEXT    PRIMARY KEY,
    last_number  INTEGER NOT NULL DEFAULT 0 CHECK (last_number >= 0)
);

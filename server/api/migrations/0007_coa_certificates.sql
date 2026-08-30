CREATE TABLE IF NOT EXISTS coa_counters (
    counter_month DATE PRIMARY KEY,
    last_number INTEGER NOT NULL DEFAULT 0 CHECK (last_number >= 0)
);

CREATE TABLE IF NOT EXISTS coa_certificates (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    certificate_no TEXT UNIQUE,
    status TEXT NOT NULL DEFAULT 'DRAFT'
        CHECK (status IN ('DRAFT','WAITING_FOR_INSPECTION','WAITING_FOR_APPROVAL','FINAL')),
    quote_ref TEXT NOT NULL REFERENCES quotations(quote_ref),
    customer TEXT NOT NULL,
    customer_code TEXT NOT NULL DEFAULT '',
    po_no TEXT NOT NULL DEFAULT '',
    part_no TEXT NOT NULL DEFAULT '',
    product TEXT NOT NULL,
    lot_no TEXT NOT NULL DEFAULT '',
    production_date DATE,
    inspection_date DATE,
    issue_date DATE,
    quantity TEXT NOT NULL DEFAULT '',
    material TEXT NOT NULL DEFAULT 'POLYETHYLENE',
    color TEXT NOT NULL DEFAULT '-',
    printing TEXT NOT NULL DEFAULT '-',
    width_mm NUMERIC(18,4) NOT NULL,
    length_mm NUMERIC(18,4) NOT NULL,
    thickness_mm NUMERIC(18,4) NOT NULL,
    thickness_mode TEXT NOT NULL DEFAULT 'pair' CHECK (thickness_mode IN ('side','pair')),
    width_tolerance_mm NUMERIC(18,4) NOT NULL DEFAULT 10,
    length_tolerance_mm NUMERIC(18,4) NOT NULL DEFAULT 10,
    thickness_tolerance_mm NUMERIC(18,4) NOT NULL DEFAULT 0.01,
    actual_width_mm NUMERIC(18,4),
    actual_length_mm NUMERIC(18,4),
    actual_thickness_mm NUMERIC(18,4),
    result TEXT NOT NULL DEFAULT '' CHECK (result IN ('','PASS','FAIL')),
    remarks TEXT NOT NULL DEFAULT '',
    checked_by TEXT NOT NULL DEFAULT '',
    approved_by TEXT NOT NULL DEFAULT '',
    revision INTEGER NOT NULL DEFAULT 1,
    created_by TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_coa_quote_ref ON coa_certificates (quote_ref);
CREATE INDEX IF NOT EXISTS idx_coa_customer ON coa_certificates (customer);
CREATE INDEX IF NOT EXISTS idx_coa_status ON coa_certificates (status);

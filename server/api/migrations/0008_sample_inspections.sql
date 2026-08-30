CREATE TABLE IF NOT EXISTS sample_inspections (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    report_no TEXT NOT NULL UNIQUE,
    quote_ref TEXT NOT NULL REFERENCES quotations(quote_ref),
    customer TEXT NOT NULL,
    customer_code TEXT NOT NULL DEFAULT '',
    part_no TEXT NOT NULL DEFAULT '',
    product TEXT NOT NULL,
    inspection_date DATE NOT NULL,
    product_key TEXT NOT NULL,
    width_mm NUMERIC(18,4) NOT NULL,
    length_mm NUMERIC(18,4) NOT NULL,
    thickness_mm NUMERIC(18,4) NOT NULL,
    thickness_mode TEXT NOT NULL CHECK (thickness_mode IN ('side','pair')),
    gusset_mm NUMERIC(18,4) NOT NULL DEFAULT 0,
    tolerance_width_mm NUMERIC(18,4) NOT NULL DEFAULT 0,
    tolerance_length_mm NUMERIC(18,4) NOT NULL DEFAULT 0,
    tolerance_thickness_mm NUMERIC(18,4) NOT NULL DEFAULT 0,
    tolerance_gusset_left_mm NUMERIC(18,4) NOT NULL DEFAULT 0,
    tolerance_gusset_right_mm NUMERIC(18,4) NOT NULL DEFAULT 0,
    results_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    display_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    overall_result TEXT NOT NULL DEFAULT '' CHECK (overall_result IN ('','PASS','FAIL')),
    remarks TEXT NOT NULL DEFAULT '',
    checked_by TEXT NOT NULL DEFAULT '',
    approved_by TEXT NOT NULL DEFAULT '',
    revision INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_sample_inspection_quote ON sample_inspections(quote_ref);
CREATE INDEX IF NOT EXISTS idx_sample_inspection_customer ON sample_inspections(customer);

CREATE TABLE IF NOT EXISTS sample_inspection_counters (
    counter_date DATE PRIMARY KEY,
    last_number INTEGER NOT NULL DEFAULT 0 CHECK (last_number >= 0)
);

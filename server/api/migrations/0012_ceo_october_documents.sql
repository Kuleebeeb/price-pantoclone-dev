-- CEO 08-10-2026: edits retain identity; issued documents retain their source.
ALTER TABLE quotations ADD COLUMN version BIGINT NOT NULL DEFAULT 1 CHECK (version > 0);
ALTER TABLE quotations ADD COLUMN updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

CREATE TABLE document_audit (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    action TEXT NOT NULL,
    before_json JSONB,
    after_json JSONB,
    actor_id BIGINT,
    actor_name TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX document_audit_entity ON document_audit(entity_type, entity_id, id);

CREATE TABLE document_save_requests (
    scope TEXT NOT NULL,
    actor_key TEXT NOT NULL,
    request_id TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    response_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY(scope, actor_key, request_id)
);

ALTER TABLE sample_inspections ADD COLUMN source_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE sample_inspections ADD COLUMN length_datum TEXT
    CHECK (length_datum IN ('opening_to_bottom','opening_to_seal'));
ALTER TABLE sample_inspections ADD COLUMN deleted_at TIMESTAMPTZ;
ALTER TABLE sample_inspections ADD COLUMN deleted_by TEXT;
ALTER TABLE sample_inspections DROP CONSTRAINT sample_inspections_overall_result_check;
ALTER TABLE sample_inspections ADD CONSTRAINT sample_inspections_overall_result_check
    CHECK (overall_result IN ('','WAITING','PASS','FAIL'));

-- Backfill ONLY from each report's saved values. Never read today's quotation:
-- it may already differ from the document the customer received.
UPDATE sample_inspections s SET source_snapshot = jsonb_build_object(
    'quote_ref',s.quote_ref,'customer',s.customer,'customer_code',s.customer_code,
    'part_no',s.part_no,'product',s.product,'product_key',s.product_key,
    'width_mm',s.width_mm,'length_mm',s.length_mm,'thickness_mm',s.thickness_mm,
    'thickness_mode',s.thickness_mode,'gusset_mm',s.gusset_mm,
    'tolerance_width_mm',s.tolerance_width_mm,'tolerance_length_mm',s.tolerance_length_mm,
    'tolerance_thickness_mm',s.tolerance_thickness_mm,
    'tolerance_gusset_left_mm',s.tolerance_gusset_left_mm,
    'tolerance_gusset_right_mm',s.tolerance_gusset_right_mm
) || s.display_json;

-- SI has its own series; old SIR numbers and counters are not renamed/reused.
CREATE TABLE sample_daily_counters (
    counter_date DATE PRIMARY KEY,
    last_number INTEGER NOT NULL DEFAULT 0 CHECK (last_number >= 0)
);

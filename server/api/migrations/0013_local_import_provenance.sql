-- A quotation identity outlives its visibility. Issued Sample reports retain
-- their saved snapshot when an imported source quotation is in the trash.
-- Normal API creation still requires an active quotation and a matching version.
CREATE TABLE quotation_identities (
    quote_ref TEXT PRIMARY KEY,
    registered_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO quotation_identities(quote_ref)
SELECT quote_ref FROM quotations UNION SELECT quote_ref FROM quotation_trash;

CREATE FUNCTION retain_quotation_identity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO quotation_identities(quote_ref) VALUES (NEW.quote_ref)
    ON CONFLICT DO NOTHING;
    RETURN NEW;
END;
$$;
CREATE TRIGGER quotations_retain_identity AFTER INSERT OR UPDATE OF quote_ref
ON quotations FOR EACH ROW EXECUTE FUNCTION retain_quotation_identity();
CREATE TRIGGER quotation_trash_retain_identity AFTER INSERT OR UPDATE OF quote_ref
ON quotation_trash FOR EACH ROW EXECUTE FUNCTION retain_quotation_identity();
ALTER TABLE sample_inspections DROP CONSTRAINT sample_inspections_quote_ref_fkey;
ALTER TABLE sample_inspections ADD CONSTRAINT sample_inspections_quote_ref_fkey
FOREIGN KEY (quote_ref) REFERENCES quotation_identities(quote_ref);

-- These are import metadata, not invented historical events. Historical event
-- time is nullable on each source row; raw files also permit byte-exact recovery.
CREATE TABLE local_import_batches (
    batch_sha256 TEXT PRIMARY KEY CHECK (length(batch_sha256) = 64),
    mapping_version TEXT NOT NULL,
    importer_sha256 TEXT NOT NULL,
    manifest_json JSONB NOT NULL,
    report_json JSONB NOT NULL,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE local_import_files (
    batch_sha256 TEXT NOT NULL REFERENCES local_import_batches(batch_sha256),
    source_file TEXT NOT NULL,
    sha256 TEXT NOT NULL CHECK (length(sha256) = 64),
    byte_count BIGINT NOT NULL CHECK (byte_count >= 0),
    raw_bytes BYTEA NOT NULL,
    PRIMARY KEY(batch_sha256, source_file)
);
CREATE TABLE local_import_rows (
    batch_sha256 TEXT NOT NULL REFERENCES local_import_batches(batch_sha256),
    source_collection TEXT NOT NULL,
    source_key TEXT NOT NULL,
    raw_json JSONB NOT NULL,
    source_event_at TIMESTAMPTZ,
    target_table TEXT,
    target_identity TEXT,
    target_id BIGINT,
    PRIMARY KEY(batch_sha256, source_collection, source_key)
);
CREATE INDEX local_import_rows_target ON local_import_rows(target_table, target_identity);

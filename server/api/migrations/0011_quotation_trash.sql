-- Delete in History moves a quotation to a trash it can be brought back from
-- (CEO 02-10-2026: "ย้ายไปถังขยะ ... กู้คืนได้ ไม่ลบถาวร"). Until today the
-- button ran DELETE FROM quotations and the price the customer was given was
-- gone for good, with nothing saying who removed it or why.
--
-- The whole row leaves `quotations` as one JSON document instead of gaining a
-- deleted flag: every query that reads quotations (history, the folder tree,
-- related companies, planning, COA and sample sources, the desktop sync) then
-- stays exactly as it is, and none of them can forget a filter and show a
-- deleted price again.
--
-- Rows are never removed from here. A restore stamps restored_at, so the trash
-- is also the log of every delete and every restore.
CREATE TABLE IF NOT EXISTS quotation_trash (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    quote_ref           TEXT        NOT NULL,
    row_json            JSONB       NOT NULL,
    reason              TEXT        NOT NULL CHECK (length(btrim(reason)) BETWEEN 1 AND 1000),
    -- The name typed into the dialog. The account below is who it really was
    -- (LAW K2); this is kept because the CEO's screen asks for it.
    typed_actor         TEXT        NOT NULL DEFAULT '' CHECK (length(typed_actor) <= 200),
    deleted_by_user_id  BIGINT      REFERENCES users(id),
    deleted_by          TEXT        NOT NULL,
    deleted_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    restored_by_user_id BIGINT      REFERENCES users(id),
    restored_by         TEXT,
    restored_at         TIMESTAMPTZ
);

-- NOT unique: a paper-book reference re-imported after its delete, then
-- deleted again, is two open entries for one reference. Restore takes the
-- newest; the older then answers "already in history" instead of a 500.
CREATE INDEX IF NOT EXISTS quotation_trash_open_ref
    ON quotation_trash (quote_ref) WHERE restored_at IS NULL;

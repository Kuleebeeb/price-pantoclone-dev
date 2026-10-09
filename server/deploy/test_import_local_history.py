"""Synthetic fixtures only. Optional PostgreSQL tests use an isolated schema.

Set LOCAL_IMPORT_TEST_DATABASE_URL to a disposable localhost *_smoke database.
No private export files or production credentials are needed by these tests.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
import uuid
from contextlib import closing

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.conninfo import conninfo_to_dict

import import_local_history as importer


def fixture(directory):
    source = directory / "01_PantongOne"
    source.mkdir()
    path = source / "pantongone-history.sqlite3"
    with closing(sqlite3.connect(path)) as conn:
        conn.executescript("""
        CREATE TABLE records(id INTEGER PRIMARY KEY,date TEXT,data TEXT,result TEXT,quote_no INTEGER,revision INTEGER);
        CREATE TABLE quote_series(quote_no INTEGER PRIMARY KEY,quote_date TEXT,sequence INTEGER,document_no TEXT);
        CREATE TABLE cancellation(record_id INTEGER PRIMARY KEY,reason TEXT,cancelled_at TEXT);
        CREATE TABLE cancellation_log(id INTEGER PRIMARY KEY,record_id INTEGER,action TEXT,reason TEXT,stamp TEXT);
        CREATE TABLE save_requests(request_id TEXT PRIMARY KEY,fingerprint TEXT,record_id INTEGER);
        CREATE TABLE save_fingerprints(fingerprint TEXT PRIMARY KEY,record_id INTEGER);
        """)
        data = {"customer": "Synthetic customer", "customer_code": "SYN", "item": "Synthetic item", "item_code": "PART",
                "product": "flat", "width": "4", "width_unit": "inch", "length": "12", "length_unit": "inch",
                "thickness": ".1", "thickness_unit": "mm", "basis": "pair", "sale": "piece", "qty": "5",
                "density": ".92", "material": "20", "pricekg": "30", "final": "123", "pack": "10", "quote_date": "2026-01-01"}
        result = {"kg": .0123, "final": 123, "finalpiece": 123, "finalkg": 10000, "total": 615,
                  "items": 81.3, "pricing_items": 73.17, "suggested": 136.67, "requiredkg": .0615,
                  "packkg": .123, "sackkg": 0, "formula": "synthetic_saved_formula", "sales_deduction_percent": 10}
        conn.execute("INSERT INTO records VALUES(1,?,?,?,?,?)", ("2026-01-01T23:59:01", json.dumps(data), json.dumps(result), 1, 0))
        conn.execute("INSERT INTO records VALUES(2,?,?,?,?,?)", ("2026-01-02T00:00:01", json.dumps({**data, "revised_from": "1"}), json.dumps(result), 1, 1))
        conn.execute("INSERT INTO quote_series VALUES(1,'2026-01-01',40,'QT-20260101-0040')")
        conn.execute("INSERT INTO cancellation VALUES(2,'Synthetic cancellation','2026-01-03T12:00:00')")
        conn.execute("INSERT INTO cancellation_log VALUES(1,2,'cancel','Synthetic cancellation','2026-01-03T12:00:00')")
        conn.execute("INSERT INTO save_requests VALUES('retry-original','fingerprint',1)")
        conn.execute("INSERT INTO save_fingerprints VALUES('fingerprint',1)")
        conn.commit()
    ref = "LOCAL-QT-20260102-0004"
    measure = {"value": 10, "unit": "ซม."}
    thick = {"value": .1, "unit": "มม.", "mode": "side"}
    visual = [{"id": 77, "quote_ref": ref, "created_at": "2026-01-02T01:00:00", "updated_at": "2026-01-02T02:00:00",
               "body": {"customer": "Synthetic customer", "customer_code": "SYN", "quote_date": "2026-01-02", "item_description": "Synthetic bag",
                        "revised_from_ref": "QT-20260101-0040", "calc": {"product_key": "flat", "width": measure, "length": measure,
                            "thickness": thick, "sale_basis": "piece", "order_quantity": 5}},
               "edit_history": [{"saved_at": "2026-01-02T01:30:00", "body": {"synthetic_before": True}}]}]
    sample = {"id": 88, "report_no": "SI-20260102-0009", "quote_ref": ref, "customer": "Synthetic customer", "customer_code": "SYN",
        "part_no": "PART", "product": "Synthetic bag", "product_key": "flat", "inspection_date": "2025-01-01", "thickness_mode": "side",
        "width_mm": 100, "length_mm": 100, "thickness_mm": .1, "gusset_mm": 0,
        "tolerance_width_mm": 1, "tolerance_length_mm": 1, "tolerance_thickness_mm": .01,
        "tolerance_gusset_left_mm": 0, "tolerance_gusset_right_mm": 0,
        "results_json": [{"width": None, "length": None, "thickness": None} for _ in range(3)],
        "overall_result": "WAITING", "remarks": "", "checked_by": "", "approved_by": "",
        "source_snapshot": {"quote_ref": ref, "width_mm": 100, "length_mm": 100, "unknown_standard": None},
        "width_original": measure, "length_original": measure, "thickness_original": thick, "size_text": "Synthetic size"}
    drawing = {"doc_no": "DFA-20260102-0020", "quote_ref": ref, "drawing_date": "2026-01-02", "customer": "Synthetic customer", "title": "Synthetic drawing",
               "width": {"value": 4, "unit": "นิ้ว"}, "length": measure, "thickness": thick, "product_key": "flat", "length_datum": "opening_to_bottom"}
    actions = {"deleted_quotes": [ref], "drawings": [drawing], "samples": [sample], "sample_daily_counters": {"2026-01-02": 12},
        "audit": [{"action": "hide-quotation", "identity": ref, "actor": "Typed source actor", "account": "Source account", "reason": "Synthetic hide", "time": "2026-01-03T00:00:00Z"},
                  {"action": "sample-before-edit", "body": sample}, {"action": "save-sample", "identity": 88, "time": "2026-01-02T02:00:00Z"},
                  {"action": "save-drawing", "identity": drawing["doc_no"], "time": "2026-01-02T02:00:00Z"}]}
    for name, value in (("visual-review-saved.json", visual), ("history-actions.json", actions), ("history-actions.previous.json", actions)):
        (source / name).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    manifest = directory / "manifest.json"
    refresh_manifest(source, manifest)
    return source, manifest


def refresh_manifest(source, manifest):
    files = [{"file": source.name + "\\" + p.name, "bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
             for p in sorted(source.iterdir()) if p.is_file()]
    manifest.write_text(json.dumps({"files": files}), encoding="utf-8")


class MappingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.source, self.manifest = fixture(Path(self.temp.name))

    def tearDown(self):
        self.temp.cleanup()

    def test_source_mapping_preserves_records_and_unknowns(self):
        plan = importer.plan_import(self.source, self.manifest)
        self.assertEqual((plan["report"]["active"], plan["report"]["trash"]), (1, 2))
        saved = plan["quotes"][0]
        self.assertEqual(saved["unit_price"], 123)
        self.assertEqual(saved["grams_per_item"], 12.3)
        self.assertEqual(saved["inputs_json"]["width"], {"value": 4, "unit": "นิ้ว"})
        self.assertAlmostEqual(saved["inputs_json"]["normalized"]["width_cm"], 10.16)
        self.assertEqual(saved["created_at"].utcoffset().total_seconds(), 25200)
        self.assertEqual(plan["quotes"][1]["revised_from_ref"], saved["quote_ref"])
        self.assertEqual(plan["quotes"][2]["results_json"]["import_result_origin"], "derived_not_stored")
        self.assertIsNone(plan["samples"][0]["length_datum"])
        self.assertEqual(plan["samples"][0]["overall_result"], "WAITING")
        self.assertEqual(plan["drawings"][0]["spec_json"]["original_measures"]["width"]["unit"], "นิ้ว")
        missing = [r for r in plan["rows"] if r["source_collection"] == "actions.audit" and r["source_key"] == "1"]
        self.assertIsNone(missing[0]["source_event_at"])
        self.assertEqual(importer.counter_highwater(plan)["sample_daily_counters"][importer.day("2026-01-02")], 12)

    def test_checksum_tamper_rejected_before_mapping(self):
        with (self.source / "history-actions.json").open("ab") as handle:
            handle.write(b" ")
        with self.assertRaisesRegex(importer.ImportRejected, "Checksum"):
            importer.plan_import(self.source, self.manifest)

    def test_kg_price_and_suggested_are_not_mislabeled(self):
        result = importer.mapped_legacy_result({"kg": .05, "final": 200, "finalpiece": 10, "finalkg": 200,
            "suggested": 3, "total": 1000, "items": 20, "no_deduction": True})
        self.assertEqual(result["unit_price"], 10)
        self.assertEqual(result["total_price"], 1000)
        self.assertEqual(result["selling_price_per_kg"], 200)
        self.assertEqual(result["legacy_suggested"], 3)
        self.assertEqual(result["calculated_price_per_piece_from_kg"], 10)
        old_inputs = importer.legacy_inputs({"product": "flat", "width": 4, "length": 10}, {"no_deduction": True})
        self.assertFalse(old_inputs["apply_deduction"])
        self.assertEqual(old_inputs["deduction_percent"], 0)

    def test_legacy_repricing_semantics_are_flagged_without_changing_answers(self):
        data = {"product": "flat", "width": 10, "length": 20, "thickness": .1, "basis": "pair",
                "density": .92, "material": 20, "sale": "piece", "qty": 5, "final": 2, "pricekg": 30}
        inputs = importer.legacy_inputs(data, {"sales_deduction_percent": 10, "no_deduction": False})
        current = importer.api.run_calculation(importer.api.CalcRequest.model_validate(inputs))["results"]
        saved = {"kg": current["grams_per_item"] / 1000, "finalpiece": current["unit_price"], "total": current["total_price"]}
        importer.assess_legacy_compatibility(inputs, data, saved)
        self.assertTrue(inputs["import_provenance"]["calculator_compatible"])

        kg_data = {**data, "sale": "kg"}
        kg_inputs = importer.legacy_inputs(kg_data, {"no_deduction": True})
        kg_current = importer.api.run_calculation(importer.api.CalcRequest.model_validate(kg_inputs))["results"]
        kg_saved = {"kg": kg_current["grams_per_item"] / 1000, "finalpiece": kg_current["unit_price"],
                    "finalkg": 30, "total": 150}
        original = copy.deepcopy(kg_saved)
        importer.assess_legacy_compatibility(kg_inputs, kg_data, kg_saved)
        self.assertFalse(kg_inputs["import_provenance"]["calculator_compatible"])
        self.assertIn("legacy_quantity_kg_vs_current_quantity_items", kg_inputs["import_provenance"]["compatibility_reasons"])
        self.assertIn("total_price", kg_inputs["import_provenance"]["compatibility_mismatched_fields"])
        self.assertEqual(kg_inputs["order_quantity"], 5)
        self.assertEqual(kg_saved, original)

        zero_data = {**data, "final": 0, "pricekg": 0}
        zero_inputs = importer.legacy_inputs(zero_data, {"no_deduction": True})
        zero_current = importer.api.run_calculation(importer.api.CalcRequest.model_validate(zero_inputs))["results"]
        zero_saved = {"kg": zero_current["grams_per_item"] / 1000, "finalpiece": 0, "total": 0}
        importer.assess_legacy_compatibility(zero_inputs, zero_data, zero_saved)
        self.assertFalse(zero_inputs["import_provenance"]["calculator_compatible"])
        self.assertIn("legacy_zero_price_vs_current_calculated_price", zero_inputs["import_provenance"]["compatibility_reasons"])
        self.assertEqual(zero_saved["finalpiece"], 0)
        self.assertEqual(zero_saved["total"], 0)

    def test_missing_file_manifest_and_duplicate_identity_fail(self):
        path = self.source / "visual-review-saved.json"
        rows = json.loads(path.read_text(encoding="utf-8"))
        rows.append(rows[0])
        path.write_text(json.dumps(rows), encoding="utf-8")
        refresh_manifest(self.source, self.manifest)
        with self.assertRaisesRegex(importer.ImportRejected, "Duplicate"):
            importer.plan_import(self.source, self.manifest)
        (self.source / "unlisted.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(importer.ImportRejected, "Manifest"):
            importer.plan_import(self.source, self.manifest)


@unittest.skipUnless(os.environ.get("LOCAL_IMPORT_TEST_DATABASE_URL"), "Opt-in disposable PostgreSQL URL required")
class PostgresTests(MappingTests):
    def setUp(self):
        super().setUp()
        url = os.environ["LOCAL_IMPORT_TEST_DATABASE_URL"]
        options = conninfo_to_dict(url)
        if options.get("host") not in ("localhost", "127.0.0.1", "::1") or not options.get("dbname", "").endswith("_smoke"):
            self.fail("Tests require localhost and a *_smoke database")
        self.conn = psycopg.connect(url, autocommit=True, row_factory=dict_row)
        self.schema = "import_test_" + uuid.uuid4().hex
        self.conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(self.schema)))
        self.conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(self.schema)))
        for migration in sorted((importer.SERVER / "api" / "migrations").glob("*.sql")):
            self.conn.execute(migration.read_text(encoding="utf-8"), prepare=False)

    def tearDown(self):
        if hasattr(self, "conn"):
            self.conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(self.schema)))
            self.conn.close()
        super().tearDown()

    def counts(self):
        tables = ("quotations", "quotation_trash", "drawings", "sample_inspections", "local_import_batches", "local_import_files", "local_import_rows", "quotation_identities")
        return {table: self.conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"] for table in tables}

    def test_atomic_apply_dry_run_replay_and_hidden_fk(self):
        plan = importer.plan_import(self.source, self.manifest)
        before = self.counts()
        self.assertEqual(importer.execute_plan(self.conn, plan)["status"], "dry_run_ready")
        self.assertEqual(self.counts(), before)
        report = importer.execute_plan(self.conn, plan, True)
        self.assertEqual(report["status"], "applied")
        self.assertEqual(self.counts()["quotations"], 1)
        self.assertEqual(self.counts()["quotation_trash"], 2)
        self.assertEqual(self.counts()["quotation_identities"], 3)
        self.assertEqual(self.counts()["local_import_files"], 4)
        self.assertEqual(self.counts()["local_import_rows"], len(plan["rows"]))
        moved = self.conn.execute("SELECT target_table,target_id FROM local_import_rows WHERE source_collection='sqlite.records' AND source_key='2'").fetchone()
        self.assertEqual(moved["target_table"], "quotation_trash")
        self.assertIsNotNone(self.conn.execute("SELECT 1 FROM quotation_trash WHERE id=%s", (moved["target_id"],)).fetchone())
        sample = self.conn.execute("SELECT * FROM sample_inspections").fetchone()
        self.assertEqual(sample["source_snapshot"], plan["samples"][0]["source_snapshot"])
        self.assertIsNone(sample["length_datum"])
        self.assertEqual(sample["overall_result"], "WAITING")
        self.assertEqual(sample["results_json"], plan["samples"][0]["results_json"])
        self.assertEqual(self.conn.execute("SELECT count(*) AS n FROM quotations WHERE quote_ref=%s", (sample["quote_ref"],)).fetchone()["n"], 0)
        self.assertEqual(self.conn.execute("SELECT last_number FROM quotation_counters WHERE counter_date='2026-01-01'").fetchone()["last_number"], 40)
        self.assertEqual(self.conn.execute("SELECT last_number FROM sample_daily_counters").fetchone()["last_number"], 12)
        self.assertEqual(self.conn.execute("SELECT last_number FROM drawing_counters").fetchone()["last_number"], 20)
        raw = self.conn.execute("SELECT raw_bytes FROM local_import_files WHERE source_file='pantongone-history.sqlite3'").fetchone()["raw_bytes"]
        self.assertEqual(raw, (self.source / "pantongone-history.sqlite3").read_bytes())
        unknown = self.conn.execute("SELECT source_event_at FROM local_import_rows WHERE source_collection='actions.audit' AND source_key='1'").fetchone()
        self.assertIsNone(unknown["source_event_at"])
        # Replay does not overwrite a legitimate edit made after import.
        self.conn.execute("UPDATE quotations SET item_description='Edited after import'")
        before = self.counts()
        self.assertEqual(importer.execute_plan(self.conn, plan, True)["status"], "already_applied")
        self.assertEqual(self.counts(), before)
        self.assertEqual(self.conn.execute("SELECT item_description FROM quotations").fetchone()["item_description"], "Edited after import")
        altered = copy.deepcopy(plan)
        altered["batch"] = "f" * 64
        with self.assertRaisesRegex(importer.ImportRejected, "conflict"):
            importer.execute_plan(self.conn, altered, True)
        self.assertEqual(self.counts(), before)
        self.conn.execute("UPDATE local_import_batches SET mapping_version='old-mapping'")
        with self.assertRaisesRegex(importer.ImportRejected, "different mapping version"):
            importer.execute_plan(self.conn, plan, True)
        self.assertEqual(self.counts(), before)

    def test_late_constraint_failure_rolls_back_every_row_and_counter(self):
        plan = importer.plan_import(self.source, self.manifest)
        plan["samples"][0]["overall_result"] = "INVALID"
        before = self.counts()
        with self.assertRaises(psycopg.errors.CheckViolation):
            importer.execute_plan(self.conn, plan, True)
        self.assertEqual(self.counts(), before)
        self.assertEqual(self.conn.execute("SELECT count(*) AS n FROM quotation_counters").fetchone()["n"], 0)

    def test_busy_live_table_fails_without_partial_import(self):
        plan = importer.plan_import(self.source, self.manifest)
        before = self.counts()
        with psycopg.connect(os.environ["LOCAL_IMPORT_TEST_DATABASE_URL"], autocommit=True) as writer:
            writer.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(self.schema)))
            with writer.transaction():
                writer.execute("LOCK TABLE quotation_counters IN ROW EXCLUSIVE MODE")
                with self.assertRaises(psycopg.errors.LockNotAvailable):
                    importer.execute_plan(self.conn, plan, True)
        self.assertEqual(self.counts(), before)

    def test_existing_counter_floor_and_normal_quote_identity_are_preserved(self):
        plan = importer.plan_import(self.source, self.manifest)
        row = copy.deepcopy(plan["quotes"][0])
        row["quote_ref"] = "NORMAL-QT-UNRELATED"
        inserted = importer.insert_row(self.conn, "quotations", row)
        self.assertIsNotNone(self.conn.execute("SELECT 1 FROM quotation_identities WHERE quote_ref=%s", (row["quote_ref"],)).fetchone())
        self.conn.execute("INSERT INTO sample_daily_counters VALUES('2026-01-02',99)")
        importer.execute_plan(self.conn, plan, True)
        self.assertEqual(self.conn.execute("SELECT last_number FROM sample_daily_counters").fetchone()["last_number"], 99)
        self.assertEqual(self.conn.execute("SELECT * FROM quotations WHERE id=%s", (inserted["id"],)).fetchone(), inserted)


if __name__ == "__main__":
    unittest.main()

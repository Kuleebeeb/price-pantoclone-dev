"""Import an explicitly supplied CEO local export, never the local mock server.

Run from the deployed server image (DATABASE_URL is inherited):
  python deploy/import_local_history.py /private/01_PantongOne --manifest /private/manifest.json
  python deploy/import_local_history.py /private/01_PantongOne --manifest /private/manifest.json --apply

Default is a read-only database rehearsal. Apply is one locked transaction;
existing identities are never overwritten. A byte-identical bundle is a replay.
Source files and every source row are retained privately in PostgreSQL. Reports
contain counts and identities only, not prices, customers, credentials or paths.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import sys
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

SERVER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER / "api"))
# This imports trusted production pure mapping/calculation functions. FastAPI
# startup (database migration/bootstrap) is NOT called by importing the module.
import main as api  # noqa: E402

MAPPING_VERSION = "ceo-local-v2"
BANGKOK = timezone(timedelta(hours=7))
REQUIRED = {"pantongone-history.sqlite3", "visual-review-saved.json",
            "history-actions.json", "history-actions.previous.json"}
SQLITE_TABLES = ("records", "quote_series", "cancellation", "cancellation_log",
                 "save_requests", "save_fingerprints")
UNITS = {"cm": "ซม.", "mm": "มม.", "inch": "นิ้ว", "in": "นิ้ว",
         "m": "เมตร", "meter": "เมตร", "micron": "ไมครอน", "um": "ไมครอน", "µm": "ไมครอน"}
PRODUCTS = {"flat": "flat", "bag": "flat", "tube_bag": "flat", "sleeve": "sleeve",
            "open_ended_sleeve": "sleeve", "sheet": "opaque", "opaque": "opaque",
            "gusset": "gusset", "roll": "roll", "cover": "cover"}


class ImportRejected(ValueError):
    """Safe, non-payload diagnostic intended for the operator."""


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False, default=lambda v: v.isoformat()).encode("utf-8")


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def number(value, default=0.0):
    out = float(default if value in (None, "") else value)
    if not math.isfinite(out):
        raise ImportRejected("Non-finite number in source")
    return out


def timestamp(value):
    """Naive desktop timestamps were local Bangkok time; absence remains NULL."""
    if value in (None, ""):
        return None
    out = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return out if out.tzinfo else out.replace(tzinfo=BANGKOK)


def day(value):
    if value in (None, ""):
        raise ImportRejected("Missing required source document date")
    return date.fromisoformat(str(value)[:10])


def unit(value, fallback="cm"):
    value = str(value or fallback)
    result = UNITS.get(value, value)
    if result not in set(api.DIMENSION_FACTORS_TO_CM) | set(api.THICKNESS_FACTORS_TO_MM):
        raise ImportRejected("Unknown source measurement unit")
    return result


def unique(rows, key, label):
    values = [str(row[key]) for row in rows]
    if len(values) != len(set(values)) or any(not v for v in values):
        raise ImportRejected("Duplicate or empty " + label)


def checked_files(source: Path, manifest_path: Path):
    source = source.resolve(strict=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    entries = manifest.get("files")
    if not isinstance(entries, list):
        raise ImportRejected("Manifest must contain a files array")
    files = {}
    for entry in entries:
        rel = PurePosixPath(str(entry.get("file", "")).replace("\\", "/"))
        if rel.is_absolute() or ".." in rel.parts:
            raise ImportRejected("Unsafe manifest path")
        if not rel.parts or rel.parts[0] != source.name:
            continue
        local = PurePosixPath(*rel.parts[1:]).as_posix()
        if not local or local in files:
            raise ImportRejected("Duplicate or empty manifest file")
        path = (source / local).resolve(strict=True)
        if not path.is_relative_to(source) or not path.is_file():
            raise ImportRejected("Source file escapes private export directory")
        raw = path.read_bytes()
        sha = digest(raw)
        if sha != str(entry.get("sha256", "")).lower() or len(raw) != entry.get("bytes"):
            raise ImportRejected("Checksum or size mismatch: " + local)
        files[local] = {"raw": raw, "sha256": sha, "bytes": len(raw)}
    actual = {p.relative_to(source).as_posix() for p in source.rglob("*") if p.is_file()}
    if not REQUIRED <= files.keys() or actual != files.keys():
        raise ImportRejected("Manifest must cover every source file and all four required data files")
    # Unsupported assets must not silently be mapped to missing public URLs.
    if set(files) != REQUIRED:
        raise ImportRejected("Unexpected source assets require an explicit asset mapping")
    fingerprint = digest(canonical({k: v["sha256"] for k, v in sorted(files.items())}))
    return files, manifest, fingerprint


def read_sqlite(raw: bytes):
    # Deserialize verified bytes in memory, not a path that could change after
    # hashing; queries are whitelisted, and no extension or source code is run.
    with closing(sqlite3.connect(":memory:")) as conn:
        conn.deserialize(raw)
        conn.execute("PRAGMA trusted_schema=OFF")
        conn.execute("PRAGMA query_only=ON")
        conn.row_factory = sqlite3.Row
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ImportRejected("SQLite integrity check failed")
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if tables - set(SQLITE_TABLES) - {"sqlite_sequence"} or not set(SQLITE_TABLES) <= tables:
            raise ImportRejected("Unrecognized SQLite schema")
        return {name: [dict(r) for r in conn.execute('SELECT * FROM "' + name + '"')]
                for name in SQLITE_TABLES}


def legacy_ref(row, series):
    base = series.get(row.get("quote_no"), {}).get("document_no") or f"TEST #{row.get('quote_no') or row['id']}"
    revision = int(row.get("revision") or 0)
    return f"{base} / Revise Price {revision:02d}" if revision else base


def legacy_inputs(data, result):
    kind = PRODUCTS.get(str(data.get("product") or "flat"))
    if kind is None:
        raise ImportRejected("Unmapped SQLite product type")
    inputs = {"product_key": kind}
    for name in ("width", "length", "height", "gusset"):
        inputs[name] = {"value": number(data.get(name)),
                        "unit": unit(data.get(name + "_unit"), data.get("unit") or "cm")}
    inputs["sold_length"] = {"value": number(data.get("meters")), "unit": unit(data.get("sold_length_unit"), "m")}
    inputs["bottom_allowance"] = {"value": number(data.get("allowance")), "unit": unit(data.get("unit"), "cm")}
    inputs["thickness"] = {"value": number(data.get("thickness")), "unit": unit(data.get("thickness_unit"), "mm"),
                           "mode": "side" if data.get("basis") == "side" else "pair"}
    inputs["sale_basis"] = "piece" if data.get("sale") in ("piece", "pc", "pcs", "ใบ") else "kg"
    aliases = {"density_g_cm3": "density", "material_price_per_kg": "material",
               "order_quantity": "qty", "pack_quantity": "pack", "sack_quantity": "sack",
               "selling_price_per_piece_override": "final", "selling_price_per_kg_override": "pricekg"}
    for name, original in aliases.items():
        if data.get(original) not in (None, ""):
            inputs[name] = number(data[original])
    deduction = result.get("sales_deduction_percent")
    if deduction is not None:
        inputs["deduction_percent"] = number(deduction)
        inputs["apply_deduction"] = not bool(result.get("no_deduction")) and number(deduction) > 0
    elif result.get("no_deduction") is True:
        inputs["deduction_percent"] = 0
        inputs["apply_deduction"] = False
    inputs["length_reference"] = str(data.get("length_reference") or "")
    if data.get("moq") not in (None, ""):
        inputs["moq_quantity"] = str(data["moq"])
        inputs["moq_unit"] = inputs["sale_basis"]
    # Unit conversion only. Never run today's calculator over stored answers.
    normalized = {name + "_cm": api.to_cm(inputs[name]["value"], inputs[name]["unit"])
                  for name in ("width", "length", "height", "gusset")}
    normalized.update(sold_length_m=api.to_cm(inputs["sold_length"]["value"], inputs["sold_length"]["unit"]) / 100,
                      thickness_input_mm=api.thickness_to_mm(inputs["thickness"]["value"], inputs["thickness"]["unit"]),
                      bottom_allowance_cm=api.to_cm(inputs["bottom_allowance"]["value"], inputs["bottom_allowance"]["unit"]))
    inputs["normalized"] = normalized
    inputs["import_provenance"] = {"source_kind": "sqlite", "result_origin": "stored",
        "calculator_compatible": kind != "cover", "original_product": data.get("product"),
        "missing_input_fields": [k for k in ("width_unit", "length_unit", "thickness_unit", "length_reference") if not data.get(k)],
        "legacy_cover_model": "film_roof_and_body_thickness" if kind == "cover" else None}
    return inputs


def assess_legacy_compatibility(inputs, data, raw_result):
    """Rehearse editing only to flag mismatches; never replace stored answers.

    The old kg quantity was kilograms, while today's calculator order quantity
    is items. It also treated an entered zero as a stored selling price; the
    current form treats zero as no override. Neither can be silently repriced.
    """
    provenance = inputs["import_provenance"]
    reasons, mismatches = [], []
    if inputs["product_key"] == "cover":
        reasons.append("legacy_film_cover_vs_current_gsm_model")
    else:
        if inputs["sale_basis"] == "kg":
            reasons.append("legacy_quantity_kg_vs_current_quantity_items")
        try:
            candidate = api.run_calculation(api.CalcRequest.model_validate({**inputs,
                "weight_formula": str(raw_result.get("formula") or ""),
                "price_formula": str(data.get("price_formula") or "")}))["results"]
            recorded = {"grams_per_item": number(raw_result.get("kg")) * 1000,
                        "unit_price": number(raw_result.get("finalpiece")),
                        "total_price": number(raw_result.get("total"))}
            mismatches = [key for key, value in recorded.items()
                          if not math.isclose(value, candidate[key], rel_tol=1e-6, abs_tol=1e-6)]
            if "unit_price" in mismatches and recorded["unit_price"] == 0:
                reasons.append("legacy_zero_price_vs_current_calculated_price")
            if mismatches:
                reasons.append("stored_results_differ_from_current_calculator")
        except (ValueError, api.FormulaError, ZeroDivisionError, KeyError):
            reasons.append("legacy_inputs_not_supported_by_current_calculator")
    provenance.update(calculator_compatible=not reasons, compatibility_reasons=reasons,
                      compatibility_mismatched_fields=mismatches, mapping_version=MAPPING_VERSION)


def mapped_legacy_result(raw):
    fields = {"unit_price": "finalpiece", "total_price": "total", "selling_price_per_kg": "finalkg",
              "legacy_suggested": "suggested", "legacy_final_by_sale_basis": "final", "items_per_kg": "items",
              "production_items_per_kg": "pricing_items", "pack_weight_kg": "packkg",
              "sack_weight_kg": "sackkg", "required_kg": "requiredkg"}
    result = {key: number(raw[value]) for key, value in fields.items() if value in raw}
    result["grams_per_item"] = number(raw.get("kg")) * 1000
    adjusted = number(raw.get("pricing_items"))
    if not adjusted and raw.get("no_deduction") is True:
        adjusted = number(raw.get("items"))
        result["production_items_per_kg"] = adjusted
    if adjusted > 0 and number(raw.get("finalkg")) > 0:
        result["calculated_price_per_piece_from_kg"] = number(raw["finalkg"]) / adjusted
        result["import_derived_fields"] = {"calculated_price_per_piece_from_kg": "stored_finalkg_divided_by_stored_adjusted_items"}
    # Legacy formula names its area variables in square metres.
    for target, source in (("roof_area_cm2", "roofarea"), ("mesh_area_cm2", "bodyarea")):
        if source in raw:
            result[target] = number(raw[source]) * 10000
    result["import_result_origin"] = "stored"
    return result


def quote_record(ref, body, inputs, results, formulas, created_at, updated_at, origin):
    kind = inputs["product_key"]
    size_parts = [f"{api.g(inputs[name]['value'])} {inputs[name]['unit']}" for name in ("width", "length")]
    return {"quote_ref": ref, "quote_date": day(body["quote_date"]),
        "created_at": created_at, "updated_at": updated_at or created_at, "saved_at": created_at,
        "customer": str(body.get("customer") or ""), "customer_code": str(body.get("customer_code") or ""),
        "item_description": str(body.get("item_description") or ""), "product_reference": str(body.get("product_reference") or ""),
        "product_image_path": str(body.get("product_image_path") or ""),
        "revised_from_ref": str(body.get("revised_from_ref") or ""),
        "product_key": kind, "product_label": api.PRODUCTS[kind], "size_text": " x ".join(size_parts),
        "length_reference": inputs.get("length_reference", ""), "inputs_json": inputs,
        "results_json": results, "formulas_json": formulas,
        "unit_price": number(results.get("unit_price")), "total_price": number(results.get("total_price")),
        "grams_per_item": number(results.get("grams_per_item")),
        "pack_quantity": number(inputs.get("pack_quantity")), "pack_weight_kg": number(results.get("pack_weight_kg")),
        "sack_quantity": number(inputs.get("sack_quantity")), "sack_weight_kg": number(results.get("sack_weight_kg")),
        "import_source": origin}


def plan_import(source, manifest_path):
    files, manifest, batch = checked_files(source, manifest_path)
    data = read_sqlite(files["pantongone-history.sqlite3"]["raw"])
    visual = json.loads(files["visual-review-saved.json"]["raw"])
    actions = json.loads(files["history-actions.json"]["raw"])
    previous = json.loads(files["history-actions.previous.json"]["raw"])
    if set(actions) != {"deleted_quotes", "drawings", "samples", "audit", "sample_daily_counters"}:
        raise ImportRejected("Unrecognized history action collections")
    series = {r["quote_no"]: r for r in data["quote_series"]}
    refs = {r["id"]: legacy_ref(r, series) for r in data["records"]}
    cancelled = {r["record_id"]: r for r in data["cancellation"]}
    if not cancelled.keys() <= refs.keys():
        raise ImportRejected("Orphan SQLite cancellation")
    rows, quotes, trash, drawings, samples = [], [], {}, [], []
    origin = "ceo-local:" + batch

    def ledger(collection, key, raw, event_at=None, table=None, identity=None):
        rows.append({"source_collection": collection, "source_key": str(key), "raw_json": raw,
                     "source_event_at": event_at, "target_table": table, "target_identity": identity})

    for table, records in data.items():
        for index, raw in enumerate(records):
            key = raw.get("id", raw.get("record_id", raw.get("quote_no", raw.get("request_id", raw.get("fingerprint", index)))))
            ledger("sqlite." + table, key, raw, timestamp(raw.get("stamp") or raw.get("cancelled_at") or raw.get("date")),
                   "quotations" if table == "records" else None, refs.get(raw.get("id")) if table == "records" else None)
    for raw in data["records"]:
        d, r = json.loads(raw["data"]), json.loads(raw["result"])
        inputs = legacy_inputs(d, r)
        assess_legacy_compatibility(inputs, d, r)
        prior = d.get("revised_from")
        if prior not in (None, ""):
            if int(prior) not in refs:
                raise ImportRejected("Unresolved SQLite revision parent")
            parent = refs[int(prior)]
        else:
            parent = ""
        body = {"customer": d.get("customer"), "customer_code": d.get("customer_code"),
                "item_description": d.get("item"), "product_reference": d.get("item_code"),
                "quote_date": d.get("quote_date") or raw["date"], "revised_from_ref": parent}
        record = quote_record(refs[raw["id"]], body, inputs, mapped_legacy_result(r),
                              {"weight": str(r.get("formula") or ""), "price": str(d.get("price_formula") or "")},
                              timestamp(raw["date"]), timestamp(raw["date"]), origin)
        quotes.append(record)
        if raw["id"] in cancelled:
            c = cancelled[raw["id"]]
            trash[record["quote_ref"]] = {"reason": str(c.get("reason") or "Imported cancellation; reason not recorded"),
                "typed_actor": "", "deleted_by": "Legacy source; account not recorded",
                "deleted_at": timestamp(c.get("cancelled_at"))}
    unique(visual, "id", "visual id")
    unique(visual, "quote_ref", "visual quotation reference")
    for raw in visual:
        body = raw["body"]
        calc = api.CalcRequest.model_validate(body["calc"])
        out = api.run_calculation(calc)
        inputs = out["request"].model_dump(mode="json")
        inputs.update(normalized=out["normalized"], price_basis=out["price_basis"], human_summary=out["human_summary"],
                      moq_quantity=str(body.get("moq_quantity") or ""), moq_unit=str(body.get("moq_unit") or ""))
        inputs["import_provenance"] = {"source_kind": "visual", "result_origin": "derived_not_stored",
            "calculator_compatible": True, "mapping_version": MAPPING_VERSION}
        result = {**out["results"], "import_result_origin": "derived_not_stored"}
        record = quote_record(raw["quote_ref"], body, inputs, result, out["formulas"],
                              timestamp(raw.get("created_at")), timestamp(raw.get("updated_at")), origin)
        record["size_text"] = out["display"]["size_text"]
        record["version"] = 1 + len(raw.get("edit_history") or [])
        quotes.append(record)
        ledger("visual.quotations", raw["id"], raw, timestamp(raw.get("created_at")), "quotations", raw["quote_ref"])
        for index, event in enumerate(raw.get("edit_history") or []):
            ledger("visual.edit_history", str(raw["id"]) + ":" + str(index), event,
                   timestamp(event.get("time") or event.get("updated_at") or event.get("edited_at") or event.get("saved_at")))
    unique(quotes, "quote_ref", "combined quotation reference")
    all_refs = {q["quote_ref"] for q in quotes}
    if any(q["revised_from_ref"] and q["revised_from_ref"] not in all_refs for q in quotes):
        raise ImportRejected("Unresolved revision lineage")
    # Missing event timestamps stay NULL in the provenance ledger. Import time
    # is allowed only as target storage metadata when no recorded time exists.
    for index, event in enumerate(actions["audit"]):
        ledger("actions.audit", index, event, timestamp(event.get("time")))
    for index, event in enumerate(previous.get("audit", [])):
        ledger("previous.audit", index, event, timestamp(event.get("time")))
    for index, ref in enumerate(actions["deleted_quotes"]):
        matches = [e for e in actions["audit"] if e.get("action") == "hide-quotation" and e.get("identity") == ref]
        if ref not in all_refs or ref in trash or not matches:
            raise ImportRejected("Unresolved or duplicate hidden quotation")
        event = matches[-1]
        trash[ref] = {"reason": str(event.get("reason") or "Imported hide; reason not recorded"),
            "typed_actor": str(event.get("actor") or ""), "deleted_by": str(event.get("account") or "Legacy source; account not recorded"),
            "deleted_at": timestamp(event.get("time"))}
        ledger("actions.deleted_quotes", index, ref, timestamp(event.get("time")), "quotation_trash", ref)

    def document_times(action, identity):
        times = [timestamp(e.get("time")) for e in actions["audit"] if e.get("action") == action and str(e.get("identity")) == str(identity) and e.get("time")]
        return (min(times), max(times)) if times else (None, None)

    unique(actions["drawings"], "doc_no", "drawing number")
    for index, raw in enumerate(actions["drawings"]):
        req = api.DrawingSaveRequest.model_validate(raw)
        if req.quote_ref and req.quote_ref not in all_refs:
            raise ImportRejected("Unresolved drawing source")
        created, _ = document_times("save-drawing", req.doc_no)
        record = {k: getattr(req, k) for k in ("doc_no", "quote_ref", "drawing_date", "revision", "customer", "customer_code",
                                              "title", "part_no", "product_key", "length_datum", "display_unit")}
        record["drawing_date"] = day(record["drawing_date"])
        record["created_at"] = created
        record.update({name + "_mm": api._to_mm(getattr(req, name)) for name in ("width", "length", "height", "gusset")})
        record["thickness_mm"] = api.thickness_to_mm(req.thickness.value, req.thickness.unit) / (2 if req.thickness.mode == "pair" else 1)
        record["spec_json"] = {k: getattr(req, k) for k in ("material", "color", "printing", "tol_dim_lo", "tol_dim_hi",
            "tol_thickness", "holes_count", "holes_dia", "label_w", "label_h", "extra_notes", "drawing_view")}
        record["spec_json"].update(original_measures={name: getattr(req, name).model_dump() for name in ("width", "length", "height", "gusset", "thickness")},
                                   dimension_units=api._drawing_units(req), import_created_at_origin="source_audit" if created else "import_metadata")
        drawings.append(record)
        ledger("actions.drawings", index, raw, created, "drawings", req.doc_no)
    unique(actions["samples"], "id", "sample source id")
    unique(actions["samples"], "report_no", "sample report number")
    sample_fields = ("report_no", "quote_ref", "customer", "customer_code", "part_no", "product", "product_key", "thickness_mode",
        "width_mm", "length_mm", "thickness_mm", "gusset_mm", "tolerance_width_mm", "tolerance_length_mm", "tolerance_thickness_mm",
        "tolerance_gusset_left_mm", "tolerance_gusset_right_mm", "results_json", "overall_result", "remarks", "checked_by", "approved_by", "source_snapshot")
    for raw in actions["samples"]:
        if raw["quote_ref"] not in all_refs or raw["source_snapshot"].get("quote_ref") != raw["quote_ref"]:
            raise ImportRejected("Invalid immutable Sample source snapshot")
        record = {k: copy.deepcopy(raw[k]) for k in sample_fields}
        if len(record["results_json"]) != 3:
            raise ImportRejected("Sample must contain three saved rows")
        # Keep stored result/WAITING and exact snapshot. Never evaluate using a
        # current quote or fill old unknown datum/tolerance with new standards.
        record["inspection_date"] = day(raw["inspection_date"])
        record["length_datum"] = raw.get("length_datum") or None
        record["display_json"] = {k: copy.deepcopy(raw[k]) for k in ("size_text", "special_requirements", "width_original", "length_original", "thickness_original", "gusset_original") if k in raw}
        created, updated = document_times("save-sample", raw["id"])
        record.update(created_at=created, updated_at=updated)
        record["display_json"]["import_created_at_origin"] = "source_audit" if created else "import_metadata"
        samples.append(record)
        ledger("actions.samples", raw["id"], raw, created, "sample_inspections", raw["report_no"])
    for key, value in actions["sample_daily_counters"].items():
        ledger("actions.sample_daily_counters", key, value)
    # Other previous collections are preserved too; do not issue duplicate docs.
    for name, values in previous.items():
        if name == "audit":
            continue
        for key, value in (values.items() if isinstance(values, dict) else enumerate(values)):
            ledger("previous." + name, key, value)
    report = {"batch_sha256": batch, "mapping_version": MAPPING_VERSION,
        "quotations": len(quotes), "active": len(quotes) - len(trash), "trash": len(trash),
        "stored_result_quotations": len(data["records"]), "derived_result_quotations": len(visual),
        "drawings": len(drawings), "samples": len(samples), "source_audit_events": len(actions["audit"]),
        "source_audit_without_time": sum(e.get("time") in (None, "") for e in actions["audit"]),
        "ledger_rows": len(rows), "legacy_cover_model_count": sum(q["inputs_json"]["import_provenance"].get("legacy_cover_model") is not None for q in quotes),
        "legacy_cover_model_active": sum(q["inputs_json"]["import_provenance"].get("legacy_cover_model") is not None and q["quote_ref"] not in trash for q in quotes),
        "calculator_incompatible_count": sum(not q["inputs_json"]["import_provenance"]["calculator_compatible"] for q in quotes),
        "calculator_incompatible_active": sum(not q["inputs_json"]["import_provenance"]["calculator_compatible"] and q["quote_ref"] not in trash for q in quotes),
        "sample_with_hidden_source": sum(s["quote_ref"] in trash for s in samples),
        "source_naive_timezone": "Asia/Bangkok", "warnings": ["Visual results are derived; no result snapshot existed.",
            "Legacy film cover formulas differ from the current cover calculator; stored answers remain authoritative.",
            "Legacy kg quantity and zero-price behavior can differ; incompatible quotes retain saved answers and cannot be silently recalculated.",
            "Missing historical audit time is NULL; missing document creation time uses labelled import metadata."]}
    return {"files": files, "manifest": manifest, "batch": batch, "rows": rows, "quotes": quotes, "trash": trash,
            "drawings": drawings, "samples": samples, "counters": actions["sample_daily_counters"], "report": report}


def insert_row(conn, table, row):
    # Identifiers only originate from literal mapper dictionaries, never source.
    from psycopg import sql
    row = {k: v for k, v in row.items() if not (k in ("created_at", "updated_at", "deleted_at") and v is None)}
    keys = list(row)
    query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING *").format(sql.Identifier(table),
        sql.SQL(",").join(map(sql.Identifier, keys)), sql.SQL(",").join(sql.Placeholder() for _ in keys))
    return conn.execute(query, [Jsonb(row[k]) if k.endswith("_json") or isinstance(row[k], (dict, list)) else row[k] for k in keys]).fetchone()


def counter_highwater(plan):
    counters = {"quotation_counters": {}, "drawing_counters": {}, "sample_daily_counters": {day(k): int(v) for k, v in plan["counters"].items()}}
    for q in plan["quotes"]:
        match = re.match(r"^(?:LOCAL-)?QT-(\d{8})-(\d+)(?: / Revise Price \d+)?$", q["quote_ref"])
        if match:
            key, value = datetime.strptime(match[1], "%Y%m%d").date(), int(match[2])
            counters["quotation_counters"][key] = max(value, counters["quotation_counters"].get(key, 0))
    for d in plan["drawings"]:
        match = re.fullmatch(r"DFA-(\d{4})(?:\d{4})?-(\d+)", d["doc_no"])
        if match:
            counters["drawing_counters"][match[1]] = max(int(match[2]), counters["drawing_counters"].get(match[1], 0))
        else:
            raise ImportRejected("Unsupported drawing counter format")
    for s in plan["samples"]:
        match = re.fullmatch(r"SI-(\d{8})-(\d+)", s["report_no"])
        if not match:
            raise ImportRejected("Unsupported Sample counter format")
        key = datetime.strptime(match[1], "%Y%m%d").date()
        counters["sample_daily_counters"][key] = max(int(match[2]), counters["sample_daily_counters"].get(key, 0))
    if any(value < 0 for items in counters.values() for value in items.values()):
        raise ImportRejected("Negative source counter")
    return counters


def execute_plan(conn, plan, apply=False):
    report = copy.deepcopy(plan["report"])
    counters = counter_highwater(plan)
    with conn.transaction():
        if not apply:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        else:
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended('ceo-local-history-import',0))")
            # Serialize with ordinary app writes as well as other importers.
            conn.execute("SET LOCAL statement_timeout='60s'")
            conn.execute("LOCK TABLE quotations, quotation_trash, drawings, sample_inspections, quotation_counters, drawing_counters, sample_daily_counters, quotation_identities IN SHARE ROW EXCLUSIVE MODE NOWAIT")
        old = conn.execute("SELECT report_json,mapping_version FROM local_import_batches WHERE batch_sha256=%s", (plan["batch"],)).fetchone()
        if old:
            if old["mapping_version"] != MAPPING_VERSION:
                raise ImportRejected("This bundle was imported with a different mapping version; review explicitly instead of overwriting it")
            return {**old["report_json"], "status": "already_applied", "mutated": False}
        collisions = {}
        for table, column, records in (("quotation_identities", "quote_ref", plan["quotes"]),
                                        ("drawings", "doc_no", plan["drawings"]), ("sample_inspections", "report_no", plan["samples"])):
            values = [r[column] for r in records]
            found = conn.execute(f"SELECT {column} FROM {table} WHERE {column}=ANY(%s)", (values,)).fetchall()
            if found:
                collisions[table] = [r[column] for r in found]
        if collisions:
            raise ImportRejected("Existing identities conflict; no overwrite allowed: " + json.dumps(collisions, ensure_ascii=False))
        report.update(status="applied" if apply else "dry_run_ready", mutated=apply,
                      counters_advanced={k: len(v) for k, v in counters.items()})
        if not apply:
            return report
        conn.execute("INSERT INTO local_import_batches(batch_sha256,mapping_version,importer_sha256,manifest_json,report_json) VALUES(%s,%s,%s,%s,%s)",
                     (plan["batch"], MAPPING_VERSION, digest(Path(__file__).read_bytes()), Jsonb(plan["manifest"]), Jsonb(report)))
        for name, file in plan["files"].items():
            conn.execute("INSERT INTO local_import_files(batch_sha256,source_file,sha256,byte_count,raw_bytes) VALUES(%s,%s,%s,%s,%s)",
                         (plan["batch"], name, file["sha256"], file["bytes"], file["raw"]))
        target_ids = {}
        for row in plan["quotes"]:
            inserted = insert_row(conn, "quotations", row)
            target_ids[("quotations", row["quote_ref"])] = inserted["id"]
            if row["quote_ref"] in plan["trash"]:
                trash = insert_row(conn, "quotation_trash", {**plan["trash"][row["quote_ref"]],
                    "quote_ref": row["quote_ref"], "row_json": api.db._jsonable(inserted)})
                target_ids[("quotation_trash", row["quote_ref"])] = trash["id"]
                conn.execute("DELETE FROM quotations WHERE id=%s", (inserted["id"],))
        for table, key, rows in (("drawings", "doc_no", plan["drawings"]), ("sample_inspections", "report_no", plan["samples"])):
            for row in rows:
                inserted = insert_row(conn, table, row)
                target_ids[(table, row[key])] = inserted["id"]
        for row in plan["rows"]:
            target_table = row["target_table"]
            if target_table == "quotations" and row["target_identity"] in plan["trash"]:
                target_table = "quotation_trash"
            insert_row(conn, "local_import_rows", {**row, "target_table": target_table, "batch_sha256": plan["batch"],
                "target_id": target_ids.get((target_table, row["target_identity"]))})
        for table, entries in counters.items():
            key = "counter_year" if table == "drawing_counters" else "counter_date"
            for value, count in entries.items():
                conn.execute(f"INSERT INTO {table}({key},last_number) VALUES(%s,%s) ON CONFLICT({key}) DO UPDATE SET last_number=GREATEST({table}.last_number,EXCLUDED.last_number)", (value, count))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="Commit the import transaction (default: read-only)")
    parser.add_argument("--report", type=Path, help="Write a count-only report outside the web root")
    parser.add_argument("--validate-only", action="store_true", help="Validate source and mappings without connecting to a database")
    args = parser.parse_args()
    if args.apply and args.validate_only:
        parser.error("--apply and --validate-only cannot be combined")
    try:
        plan = plan_import(args.source_dir, args.manifest)
        counter_highwater(plan)
        if args.validate_only:
            report = {**plan["report"], "status": "source_validated", "mutated": False}
        else:
            if not os.environ.get("DATABASE_URL"):
                raise ImportRejected("DATABASE_URL must be supplied by the target environment")
            with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True, row_factory=dict_row) as conn:
                report = execute_plan(conn, plan, args.apply)
        output = json.dumps(report, ensure_ascii=False, indent=2)
        if args.report:
            args.report.write_text(output + "\n", encoding="utf-8")
        print(output)
        return 0
    except ImportRejected as exc:
        print("Import rejected: " + str(exc), file=sys.stderr)
    except Exception as exc:
        # Database and validation exceptions can embed entire private rows.
        # Keep normal output safe; operator can debug in the private rehearsal.
        print("Import failed safely (" + type(exc).__name__ + "); transaction rolled back. Inspect mappings in a private rehearsal.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

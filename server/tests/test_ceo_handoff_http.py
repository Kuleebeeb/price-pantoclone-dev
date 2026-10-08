"""Opt-in PostgreSQL/HTTP regressions for the CEO handoff of 08 October 2026."""
import copy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from uuid import uuid4


BASE = os.environ.get("BASE", "").rstrip("/")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
db_url = urllib.parse.urlparse(DATABASE_URL)
api_url = urllib.parse.urlparse(BASE)
if (os.environ.get("PANTONGONE_DISPOSABLE_TEST") != "1"
        or "smoke" not in db_url.path.lower()
        or api_url.scheme != "http"
        or api_url.hostname not in {"localhost", "127.0.0.1", "::1", "api"}):
    sys.exit("REFUSED: explicitly set PANTONGONE_DISPOSABLE_TEST=1, a smoke DATABASE_URL, and a local BASE.")

import psycopg
from psycopg.rows import dict_row


TOKEN = ""
bad = []
checks = 0
RUN = uuid4().hex[:10]
CUSTOMER = "ZZ-HANDOFF-" + RUN


def call(method, path, body=None):
    req = urllib.request.Request(
        BASE + path, method=method,
        data=None if body is None else json.dumps(body).encode(),
        headers={"content-type": "application/json",
                 **({"authorization": f"Bearer {TOKEN}"} if TOKEN else {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            raw = response.read().decode()
            return response.status, json.loads(raw)
    except urllib.error.HTTPError as error:
        raw = error.read().decode()
        try:
            return error.code, json.loads(raw)
        except ValueError:
            return error.code, raw


def check(name, ok, detail=""):
    global checks
    checks += 1
    print(("  ok  " if ok else "  FAIL ") + name + ("" if ok else f" -> {str(detail)[:350]}"))
    if not ok:
        bad.append(name)


def required(name, status, response, key):
    check(name, status == 200 and bool(response.get(key)), (status, response))
    if status != 200 or not response.get(key):
        sys.exit(1)
    return response[key]


def sql(query, params=()):
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as connection:
        return connection.execute(query, params).fetchall()


def enc(value):
    return urllib.parse.quote(str(value), safe="")


def quote_form(ref):
    status, response = call("GET", f"/api/quotations/{enc(ref)}/form")
    check("quotation form loads", status == 200, (status, response))
    return response


def sample_rows():
    status, response = call("GET", "/api/sample-inspections?limit=1000")
    check("sample register loads", status == 200, status)
    return response.get("rows", [])


def stable_print(html):
    return re.sub(r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}", "PRINT-TIME", html)


status, response = call("POST", "/api/auth/login", {
    "email": os.environ.get("BOOTSTRAP_EMAIL", "smoke@test.local"),
    "password": os.environ.get("BOOTSTRAP_PASSWORD", "smoke-pass-1234"),
})
TOKEN = required("login to disposable API", status, response, "token")

calc = {
    "product_key": "flat", "width": {"value": 4, "unit": "นิ้ว"},
    "length": {"value": 12, "unit": "นิ้ว"},
    "thickness": {"value": 0.16, "unit": "มม.", "mode": "pair"},
    "density_g_cm3": 0.92, "material_price_per_kg": 65,
    "sale_basis": "kg", "selling_price_per_kg_override": 85,
    "pack_quantity": 100, "sack_quantity": 1000, "order_quantity": 1000,
    "length_reference": "opening_to_seal", "bottom_allowance": {"value": 1, "unit": "ซม."},
    "tolerance_width": {"value": 10, "unit": "มม."},
    "tolerance_length": {"value": 10, "unit": "มม."},
    "tolerance_thickness": {"value": 0.01, "unit": "มม."},
}
save = {"calc": calc, "quote_date": "2026-10-08", "customer": CUSTOMER,
        "customer_code": RUN, "item_description": "PE BAG HANDOFF",
        "product_reference": "PART-" + RUN, "product_image_path": "qa-images/" + RUN + ".png",
        "request_id": str(uuid4())}
status, created = call("POST", "/api/quotations", save)
ref = required("create quotation", status, created, "quote_ref")
status, retried = call("POST", "/api/quotations", save)
check("create retry returns same REF and version", status == 200 and
      retried.get("quote_ref") == ref and retried.get("version") == created.get("version"), retried)
check("quotation create retry returns exactly the same response", status == 200 and retried == created, (created, retried))
check("create retry stores only one quotation", sql("SELECT count(*) AS n FROM quotations WHERE customer=%s", (CUSTOMER,))[0]["n"] == 1)
status, response = call("POST", "/api/quotations", dict(save, item_description="changed retry"))
check("same request key with another payload is rejected", status == 409, (status, response))
form = quote_form(ref)
check("form retains inch width, inch length, and pair thickness", form.get("form", {}).get("width") == "4"
      and form["form"].get("width_unit") == "นิ้ว" and form["form"].get("length") == "12"
      and form["form"].get("length_unit") == "นิ้ว" and form["form"].get("thickness_mode") == "pair", form)
status, history = call("GET", "/api/history?customer=" + enc(CUSTOMER))
history_row = next((row for row in history.get("rows", []) if row["ref"] == ref), {})
check("history shows saved original size and thickness basis", status == 200 and
      "นิ้ว" in history_row.get("size", "") and "12" in history_row.get("size", "")
      and "0.16" in history_row.get("size", "") and "ต่อคู่" in history_row.get("size", "")
      and "101.6" not in history_row.get("size", ""), history_row)
check("history input details retain original value, unit and basis", "4.0 นิ้ว" in history_row.get("_input_details", "")
      and "0.16 มม. ต่อคู่" in history_row.get("_input_details", ""), history_row.get("_input_details"))
initial_quote = sql("SELECT to_jsonb(q) AS row FROM quotations q WHERE quote_ref=%s", (ref,))[0]["row"]

drawing = {
    "quote_ref": ref, "drawing_date": "2026-10-08", "customer": CUSTOMER,
    "customer_code": RUN, "title": "APPROVED DRAWING " + RUN, "part_no": "PART-" + RUN,
    "product_key": "flat", "revision": "A", "length_datum": "opening_to_bottom", "display_unit": "mm",
    "width": {"value": 4, "unit": "นิ้ว"}, "length": {"value": 30.48, "unit": "ซม."},
    "height": {"value": 0, "unit": "มม."}, "gusset": {"value": 0, "unit": "นิ้ว"},
    "thickness": {"value": 0.08, "unit": "มม.", "mode": "side"},
    "extra_notes": ["Issued drawing snapshot " + RUN],
}
status, response = call("POST", "/api/drawings", drawing)
doc_no = required("save drawing with mixed original units", status, response, "doc_no")
status, drawing_before = call("GET", f"/api/drawings/{enc(doc_no)}")
df = drawing_before.get("form", {})
check("drawing reopens original units and values", status == 200 and df.get("width") == "4"
      and df.get("width_unit") == "นิ้ว" and float(df.get("length") or 0) == 30.48
      and df.get("length_unit") == "ซม." and df.get("length_datum") == "opening_to_bottom", drawing_before)
render = dict(drawing, doc_no=doc_no, date=drawing["drawing_date"])
status, drawing_print = call("POST", "/api/drawing/html", render)
check("drawing prints with original units", status == 200 and "<svg" in drawing_print.get("html", "")
      and "4.00" in drawing_print.get("html", ""), (status, drawing_print.get("html", "")[-350:]))
reopened_render = dict(render, **{key: {"value": float(df.get(key) or 0), "unit": df.get(key + "_unit", "มม.")}
                                for key in ("width", "length", "height", "gusset")})
status, reopened_print = call("POST", "/api/drawing/html", reopened_render)
check("drawing print remains identical after save and reopen", status == 200 and
      stable_print(reopened_print.get("html", "")) == stable_print(drawing_print.get("html", "")))

sample = {
    "quote_ref": ref, "expected_quote_version": created["version"],
    "inspection_date": "2020-01-02", "length_datum": "opening_to_bottom",
    "tolerance_width_mm": 10, "tolerance_length_mm": 10, "tolerance_thickness_mm": 0.01,
    "tolerance_gusset_left_mm": 1, "tolerance_gusset_right_mm": 1,
    "measurements": [{"width": 101.6, "length": 304.8, "thickness": 0.16} for _ in range(3)],
    "remarks": "snapshot " + RUN, "checked_by": "QC", "approved_by": "CEO",
    "request_id": str(uuid4()),
}
status, response = call("POST", "/api/sample-inspections", sample)
sample_before = required("save complete sample", status, response, "row")
sample_id = sample_before["id"]
check("complete sample PASS and saves datum/snapshot", sample_before.get("overall_result") == "PASS"
      and sample_before.get("length_datum") == "opening_to_bottom"
      and sample_before.get("source_snapshot", {}).get("quote_ref") == ref, sample_before)
day = datetime.now(timezone(timedelta(hours=7))).strftime("%Y%m%d")
check("new number uses SI and Bangkok creation day, not inspection day",
      sample_before.get("report_no", "").startswith(f"SI-{day}-"), sample_before.get("report_no"))
status, response = call("POST", "/api/sample-inspections", sample)
check("sample retry keeps ID, number and revision", status == 200 and all(
      response.get("row", {}).get(key) == sample_before.get(key) for key in ("id", "report_no", "revision")), response)
check("sample create retry returns exactly the same response", status == 200 and response == {"row": sample_before}, response)
status, response = call("POST", "/api/sample-inspections", dict(sample, remarks="changed request"))
check("sample key cannot accept changed payload", status == 409, (status, response))
status, sample_print_before = call("GET", f"/api/sample-inspections/{sample_id}/print")
check("sample print loads", status == 200, status)
sample_list_before = next((row for row in sample_rows() if row["id"] == sample_id), {})
numeric_fields = ("width_mm", "length_mm", "thickness_mm", "tolerance_width_mm", "tolerance_length_mm", "tolerance_thickness_mm")
check("sample register returns numeric standards and tolerances", all(
      isinstance(sample_list_before.get(key), (int, float)) for key in numeric_fields),
      {key: type(sample_list_before.get(key)).__name__ for key in numeric_fields})
check("sample register preserves saved source and measured numbers", sample_list_before.get("source_snapshot") == sample_before.get("source_snapshot")
      and sample_list_before.get("results_json") == sample_before.get("results_json"))
sample_db_before = sql("SELECT to_jsonb(s) AS row FROM sample_inspections s WHERE id=%s", (sample_id,))[0]["row"]

coa = {
    "quote_ref": ref, "status": "FINAL", "po_no": "PO-" + RUN, "lot_no": "LOT-" + RUN,
    "inspection_date": "2026-10-08", "width_tolerance_mm": 10, "length_tolerance_mm": 10,
    "thickness_tolerance_mm": 0.01, "actual_width_mm": 101.6, "actual_length_mm": 304.8,
    "actual_thickness_mm": 0.16, "result": "PASS", "checked_by": "QC", "approved_by": "CEO",
}
status, response = call("POST", "/api/coa", coa)
coa_before = required("issue FINAL COA", status, response, "row")
status, coa_print_before = call("GET", f"/api/coa/{coa_before['id']}/print")
check("FINAL COA prints", status == 200, status)

edit = dict(save, update_ref=ref, expected_version=form.get("version"), request_id=str(uuid4()),
            calc=dict(calc, width={"value": 5, "unit": "นิ้ว"}), item_description="PE BAG EDITED")
edit.pop("product_image_path")
status, edited = call("POST", "/api/quotations", edit)
check("edit linked quotation keeps REF", status == 200 and edited.get("quote_ref") == ref, (status, edited))
latest = quote_form(ref)
check("edit advances version and persists new input", latest.get("version") != form.get("version")
      and latest.get("form", {}).get("width") == "5", latest)
after_quote = sql("SELECT to_jsonb(q) AS row FROM quotations q WHERE quote_ref=%s", (ref,))[0]["row"]
check("edit preserves database ID and creation time", all(after_quote[key] == initial_quote[key] for key in ("id", "created_at", "quote_ref")))
check("omitted image path on same-REF edit preserves stored attachment", after_quote["product_image_path"] == initial_quote["product_image_path"]
      and after_quote["product_image_path"] == save["product_image_path"], after_quote["product_image_path"])
audit = sql("SELECT * FROM document_audit WHERE entity_type='quotation' AND entity_id=%s AND action='update' ORDER BY id", (ref,))
check("edit audit preserves original and new inputs with actor", len(audit) == 1
      and audit[0]["before_json"]["inputs_json"] == initial_quote["inputs_json"]
      and audit[0]["after_json"]["inputs_json"] == after_quote["inputs_json"]
      and bool(audit[0]["actor_id"]) and bool(audit[0]["actor_name"]), audit)
status, response = call("POST", "/api/quotations", edit)
check("edit retry returns original response without another version", status == 200 and response.get("version") == edited.get("version"), response)
check("quotation edit retry returns exactly the same response", status == 200 and response == edited, (edited, response))
status, response = call("POST", "/api/quotations", dict(edit, product_image_path=""))
check("retry key distinguishes omitted attachment from explicit clear", status == 409, (status, response))
status, response = call("POST", "/api/quotations", dict(edit, request_id=str(uuid4())))
check("stale quotation edit rejected", status == 409, (status, response))
missing_version = dict(edit, request_id=str(uuid4()))
missing_version.pop("expected_version")
status, response = call("POST", "/api/quotations", missing_version)
check("missing quotation version rejected", status == 409, (status, response))

sample_count = sql("SELECT count(*) AS n FROM sample_inspections WHERE quote_ref=%s", (ref,))[0]["n"]
counter_before = sql("SELECT counter_date,last_number FROM sample_daily_counters ORDER BY counter_date")
stale_source = dict(sample, request_id=str(uuid4()))
status, response = call("POST", "/api/sample-inspections", stale_source)
check("new sample refuses a selected quotation version that was edited", status == 409, (status, response))
missing_source_version = dict(stale_source, request_id=str(uuid4()))
missing_source_version.pop("expected_quote_version")
status, response = call("POST", "/api/sample-inspections", missing_source_version)
check("new sample without version cannot silently use an edited source", status == 409, (status, response))
check("rejected stale source inserts no sample and consumes no number",
      sql("SELECT count(*) AS n FROM sample_inspections WHERE quote_ref=%s", (ref,))[0]["n"] == sample_count
      and sql("SELECT counter_date,last_number FROM sample_daily_counters ORDER BY counter_date") == counter_before)
status, response = call("POST", "/api/sample-inspections", sample)
check("original sample retry stays exact even after source quotation changes", status == 200 and response == {"row": sample_before}, response)
current_source = dict(sample, request_id=str(uuid4()), expected_quote_version=latest["version"],
                      measurements=[dict(measurement, width=127) for measurement in sample["measurements"]])
status, response = call("POST", "/api/sample-inspections", current_source)
check("new sample accepts current selected version and snapshots its standards", status == 200
      and response.get("row", {}).get("source_snapshot", {}).get("quote_version") == latest["version"]
      and response.get("row", {}).get("source_snapshot", {}).get("width_mm") == 127
      and response.get("row", {}).get("overall_result") == "PASS", (status, response))

status, drawing_after = call("GET", f"/api/drawings/{enc(doc_no)}")
check("linked drawing unchanged after quote edit", status == 200 and drawing_after == drawing_before)
row = next((row for row in sample_rows() if row["id"] == sample_id), {})
check("linked sample and its source snapshot unchanged after quote edit", row == sample_list_before, row)
check("persisted issued sample unchanged after quote edit",
      sql("SELECT to_jsonb(s) AS row FROM sample_inspections s WHERE id=%s", (sample_id,))[0]["row"] == sample_db_before)
status, sample_print_after = call("GET", f"/api/sample-inspections/{sample_id}/print")
check("sample reprint keeps issued standards", status == 200 and stable_print(sample_print_after.get("html", "")) == stable_print(sample_print_before.get("html", "")))
status, response = call("GET", "/api/coa?limit=1000")
check("FINAL COA unchanged after quote edit", status == 200 and
      next((row for row in response.get("rows", []) if row["id"] == coa_before["id"]), {}) == coa_before)
status, coa_print_after = call("GET", f"/api/coa/{coa_before['id']}/print")
check("FINAL COA reprint keeps issued standards", status == 200 and stable_print(coa_print_after.get("html", "")) == stable_print(coa_print_before.get("html", "")))

sample_edit = dict(sample, id=sample_id, expected_revision=sample_before["revision"],
                   request_id=str(uuid4()), remarks="edited note " + RUN)
status, response = call("POST", "/api/sample-inspections", sample_edit)
sample_edited = response.get("row", {})
check("sample edit retains issued source, datum and number", status == 200
      and sample_edited.get("source_snapshot") == sample_before.get("source_snapshot")
      and sample_edited.get("length_datum") == sample_before.get("length_datum")
      and sample_edited.get("report_no") == sample_before.get("report_no")
      and sample_edited.get("overall_result") == "PASS", (status, response))
status, response = call("POST", "/api/sample-inspections", sample_edit)
check("sample edit retry returns exactly the same response", status == 200 and response == {"row": sample_edited}, response)
status, response = call("POST", "/api/sample-inspections", dict(sample_edit, request_id=str(uuid4())))
check("stale sample edit rejected", status == 409, (status, response))

race_version = quote_form(ref).get("version")
race = [dict(edit, expected_version=race_version, request_id=str(uuid4()),
             calc=dict(calc, width={"value": value, "unit": "นิ้ว"})) for value in (6, 7)]
with ThreadPoolExecutor(max_workers=2) as executor:
    outcomes = list(executor.map(lambda body: call("POST", "/api/quotations", body), race))
check("concurrent edits have one winner and one stale refusal", sorted(status for status, _ in outcomes) == [200, 409], outcomes)
version_after_race = quote_form(ref).get("version")
status, response = call("POST", "/api/quotations", edit)
check("late retry is safe after another edit", status == 200 and quote_form(ref).get("version") == version_after_race, response)
clear_image = dict(edit, expected_version=version_after_race, request_id=str(uuid4()), product_image_path="")
status, response = call("POST", "/api/quotations", clear_image)
check("explicit empty image path clears the stored attachment", status == 200 and
      sql("SELECT product_image_path FROM quotations WHERE quote_ref=%s", (ref,))[0]["product_image_path"] == "", (status, response))

status, response = call("POST", "/api/quotations", dict(save, request_id=str(uuid4())))
quality_ref = required("create separate quality fixture", status, response, "quote_ref")
quality = dict(sample, quote_ref=quality_ref)
partial = copy.deepcopy(quality)
partial.update(request_id=str(uuid4()))
partial["measurements"][2]["thickness"] = None
status, response = call("POST", "/api/sample-inspections", partial)
check("one blank required measurement means WAITING", status == 200 and response.get("row", {}).get("overall_result") == "WAITING", (status, response))
for count in (0, 1, 2, 4):
    status, response = call("POST", "/api/sample-inspections", dict(quality, request_id=str(uuid4()), measurements=[quality["measurements"][0]] * count))
    check(f"{count} measurement rows rejected", status in (400, 422), (status, response))
for value in (-1, "NaN", "Infinity", "-Infinity"):
    invalid = copy.deepcopy(quality)
    invalid["request_id"] = str(uuid4())
    invalid["measurements"][0]["width"] = value
    status, response = call("POST", "/api/sample-inspections", invalid)
    check(f"invalid measurement {value} rejected", status in (400, 422), (status, response))
    status, response = call("POST", "/api/sample-inspections", dict(quality, request_id=str(uuid4()), tolerance_width_mm=value))
    check(f"invalid tolerance {value} rejected", status in (400, 422), (status, response))
edge = dict(quality, request_id=str(uuid4()), measurements=[
    {"width": 111.6, "length": 294.8, "thickness": 0.17},
    {"width": 91.6, "length": 314.8, "thickness": 0.15},
    {"width": 101.6, "length": 304.8, "thickness": 0.16},
])
status, response = call("POST", "/api/sample-inspections", edge)
check("upper/lower tolerance boundaries PASS without float error", status == 200 and response.get("row", {}).get("overall_result") == "PASS", (status, response))

status, response = call("POST", "/api/quotations", dict(save, request_id=str(uuid4()),
    calc=dict(calc, product_key="gusset", gusset={"value": 2, "unit": "นิ้ว"})))
gusset_ref = required("create gusset quotation", status, response, "quote_ref")
gusset = dict(quality, quote_ref=gusset_ref, request_id=str(uuid4()), measurements=[
    dict(measure, gusset_left=50.8, gusset_right=50.8) for measure in quality["measurements"]])
status, response = call("POST", "/api/sample-inspections", gusset)
check("both measured gussets PASS", status == 200 and response.get("row", {}).get("overall_result") == "PASS", (status, response))
for field in ("gusset_left", "gusset_right"):
    body = copy.deepcopy(gusset)
    body["request_id"] = str(uuid4())
    body["measurements"][1][field] = 53
    status, response = call("POST", "/api/sample-inspections", body)
    check(field + " beyond tolerance causes FAIL", status == 200 and response.get("row", {}).get("overall_result") == "FAIL", (status, response))
    body["request_id"] = str(uuid4())
    body["measurements"][1][field] = None
    status, response = call("POST", "/api/sample-inspections", body)
    check(field + " missing causes WAITING", status == 200 and response.get("row", {}).get("overall_result") == "WAITING", (status, response))

day_before = datetime.now(timezone(timedelta(hours=7))).strftime("%Y%m%d")
bodies = [dict(quality, request_id=str(uuid4())) for _ in range(6)]
with ThreadPoolExecutor(max_workers=6) as executor:
    outcomes = list(executor.map(lambda body: call("POST", "/api/sample-inspections", body), bodies))
day_after = datetime.now(timezone(timedelta(hours=7))).strftime("%Y%m%d")
reports = [response.get("row", {}) for status, response in outcomes if status == 200]
numbers = [row.get("report_no", "") for row in reports]
check("parallel sample creation yields six distinct numbers", len(numbers) == 6 and len(set(numbers)) == 6, outcomes)
check("parallel report dates use Bangkok creation day", all(any(number.startswith("SI-" + day + "-") for day in (day_before, day_after)) for number in numbers), numbers)
with ThreadPoolExecutor(max_workers=4) as executor:
    retries = list(executor.map(lambda _: call("POST", "/api/sample-inspections", bodies[0]), range(4)))
check("parallel retries all return one existing report", all(status == 200 and response.get("row", {}).get("id") == reports[0].get("id") for status, response in retries), retries)
deleted = reports[-1]
status, response = call("DELETE", f"/api/sample-inspections/{deleted['id']}")
check("delete sample succeeds", status == 200, (status, response))
check("deleted sample absent from register", all(row["id"] != deleted["id"] for row in sample_rows()))
stored = sql("SELECT * FROM sample_inspections WHERE id=%s", (deleted["id"],))
check("deleted sample stays in database for audit", len(stored) == 1 and stored[0]["report_no"] == deleted["report_no"])
check("sample deletion recorded with before snapshot and actor", bool(sql(
    "SELECT 1 FROM document_audit WHERE entity_type='sample' AND entity_id=%s AND action='delete' AND before_json IS NOT NULL AND actor_id IS NOT NULL",
    (str(deleted["id"]),))))
status, response = call("GET", f"/api/sample-inspections/{deleted['id']}/print")
check("deleted report cannot be printed", status == 404, status)
status, response = call("POST", "/api/sample-inspections", dict(quality, request_id=str(uuid4())))
check("deleted report number never reused", status == 200 and response.get("row", {}).get("report_no") not in numbers, response)

legacy = reports[0]
legacy_number = f"SIR-20200102-{legacy['id']:04d}"
sql("UPDATE sample_inspections SET report_no=%s WHERE id=%s RETURNING id", (legacy_number, legacy["id"]))
legacy_edit = dict(quality, id=legacy["id"], expected_revision=legacy["revision"], request_id=str(uuid4()), remarks="legacy number retained")
status, response = call("POST", "/api/sample-inspections", legacy_edit)
check("editing a legacy SIR report never renumbers it", status == 200 and response.get("row", {}).get("report_no") == legacy_number, (status, response))

print(f"\n{checks - len(bad)}/{checks} passed; {len(bad)} failed")
sys.exit(1 if bad else 0)

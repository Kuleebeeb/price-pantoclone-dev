# -*- coding: utf-8 -*-
"""INTEGRATION (HTTP): the CEO's September 2026 screens, sent the way the React
screens send them, against the REAL API (the CEO built them on dev_mock_api.py).

Six products incl. the open-ended sleeve (2 layers, no bottom seal) and the
SHIMOHIRA cover formula -> save -> Edit = linked revision, original untouched
-> the revision as a Sample Inspection source in the customer's own unit ->
blank sample report + print -> drawings 2d / 3d / both, OPEN TOP / OPEN BOTTOM
-> planning source without prices -> blown / cutting work orders with the
product type.

Needs DATABASE_URL -> a THROWAWAY Postgres (the URL must contain 'smoke')
and the API on BASE (default http://127.0.0.1:8145) started against it with
BOOTSTRAP_EMAIL / BOOTSTRAP_PASSWORD so a local account exists.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

if not os.environ.get("DATABASE_URL") or "smoke" not in os.environ["DATABASE_URL"]:
    print("HONG: DATABASE_URL phai tro vao Postgres TAM (co chu 'smoke').")
    sys.exit(1)

BASE = os.environ.get("BASE", "http://127.0.0.1:8145")
EMAIL = os.environ.get("BOOTSTRAP_EMAIL", "smoke@test.local")
PASSWORD = os.environ.get("BOOTSTRAP_PASSWORD", "smoke-pass-1234")
TOKEN = ""
bad = []

def call(method, path, body=None):
    req = urllib.request.Request(BASE + path, method=method,
                                 data=None if body is None else json.dumps(body).encode(),
                                 headers={"content-type": "application/json",
                                          **({"authorization": f"Bearer {TOKEN}"} if TOKEN else {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode()
            return r.status, (json.loads(raw) if raw[:1] in "{[" else raw)
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw
    except urllib.error.URLError as e:
        print("HONG: khong noi duoc API o", BASE, "-", e)
        sys.exit(1)


def check(name, ok, detail=""):
    print(("  ok  " if ok else "  FAIL ") + name + ("" if ok else f"  -> {str(detail)[:300]}"))
    if not ok:
        bad.append(name)


s, r = call("POST", "/api/auth/login", {"email": EMAIL, "password": PASSWORD})
TOKEN = r.get("token", "") if isinstance(r, dict) else ""
check("login", s == 200 and TOKEN, r)

s, meta = call("GET", "/api/meta")
check("meta lists the sleeve product", s == 200 and "sleeve" in meta.get("products", {}), meta.get("products"))
check("meta has a default weight formula for sleeve", "sleeve" in meta.get("default_weight_formulas", {}),
      list(meta.get("default_weight_formulas", {})))

COVER_F = "(roof_area_cm2 + mesh_area_cm2) / (2.54 * 2.54) * thickness_side_mm / 1800 * 1000"
base = dict(width={"value": 4, "unit": "นิ้ว"}, length={"value": 12, "unit": "นิ้ว"},
            height={"value": 10, "unit": "นิ้ว"}, gusset={"value": 2, "unit": "นิ้ว"},
            sold_length={"value": 100, "unit": "เมตร"}, bottom_allowance={"value": 1, "unit": "นิ้ว"},
            thickness={"value": 0.08, "unit": "มม.", "mode": "side"}, density_g_cm3=0.92,
            material_price_per_kg=65, sale_basis="kg", pack_quantity=100, sack_quantity=1000,
            order_quantity=1000, tolerance_width={"value": 10, "unit": "มม."},
            tolerance_length={"value": 10, "unit": "มม."}, tolerance_thickness={"value": 0.01, "unit": "มม."},
            special_requirements="ซีลก้นตรงและแข็งแรง")
calcs = {}
for key in ["flat", "gusset", "sleeve", "opaque", "roll", "cover"]:
    body = dict(base, product_key=key)
    if key == "cover":
        body.update(weight_formula=COVER_F, deduction_percent=10, apply_deduction=False)
    s, r = call("POST", "/api/calculate", body)
    g = (r.get("results") or {}).get("grams_per_item") if isinstance(r, dict) else None
    check(f"calculate {key}", s == 200 and g not in (None, "", 0, "0"), r)
    calcs[key] = body

# sleeve: two layers like a bag, no bottom seal allowance
s, fl = call("POST", "/api/calculate", dict(calcs["flat"], length_reference="opening_to_bottom",
                                           bottom_allowance={"value": 0, "unit": "นิ้ว"}))
s2, sl = call("POST", "/api/calculate", calcs["sleeve"])
check("sleeve weighs like a flat bag with no bottom allowance",
      fl.get("results", {}).get("grams_per_item") == sl.get("results", {}).get("grams_per_item"),
      (fl.get("results", {}).get("grams_per_item"), sl.get("results", {}).get("grams_per_item")))

# save, revise, reload the form - the CEO's Edit flow
save = {"calc": calcs["sleeve"], "quote_date": "2026-09-30", "customer": "CSK Plasatic Co.,Ltd",
        "customer_code": "CSK", "item_description": "PE SLEEVE 4 x 12 inch", "product_reference": "4P-SLV"}
s, q1 = call("POST", "/api/quotations", save)
check("save a sleeve quotation", s == 200 and q1.get("quote_ref"), q1)
ref = q1.get("quote_ref", "")
s, f1 = call("GET", f"/api/quotations/{ref}/form")
check("reload its form for Edit", s == 200 and f1.get("form", {}).get("product_key") == "sleeve", f1)
save2 = dict(save, revised_from_ref=ref, calc=dict(calcs["sleeve"], thickness={"value": 0.10, "unit": "มม.", "mode": "side"}))
s, q2 = call("POST", "/api/quotations", save2)
check("save the edit as a linked revision", s == 200 and q2.get("quote_ref") not in ("", ref), q2)
ref2 = q2.get("quote_ref", "")
s, f2 = call("GET", f"/api/quotations/{ref2}/form")
check("the revision holds the new thickness", s == 200 and str(f2.get("form", {}).get("thickness")) in ("0.1", "0.10"), f2.get("form", {}).get("thickness"))
s, f0 = call("GET", f"/api/quotations/{ref}/form")
check("the original is untouched", str(f0.get("form", {}).get("thickness")) in ("0.08",), f0.get("form", {}).get("thickness"))
s, h = call("GET", "/api/history?q=CSK")
refs = [row.get("ref") for row in h.get("rows", [])] if isinstance(h, dict) else []
check("history shows both", ref in refs and ref2 in refs, refs)

# sample inspection from the edited quotation (T195)
s, src = call("GET", f"/api/sample-inspections/sources?q={ref2}")
rows = src.get("rows", []) if isinstance(src, dict) else []
check("edited quotation is a sample-inspection source", any(r.get("quote_ref") == ref2 for r in rows), src)
one = next((r for r in rows if r.get("quote_ref") == ref2), {})
check("source keeps the customer's inch units", (one.get("width_original") or {}).get("unit") == "นิ้ว", one.get("width_original"))
meas = {"width": None, "length": None, "thickness": None, "gusset_left": None, "gusset_right": None}
s, si = call("POST", "/api/sample-inspections", {"quote_ref": ref2, "inspection_date": "2026-09-30",
             "tolerance_width_mm": 10, "tolerance_length_mm": 10, "tolerance_thickness_mm": 0.01,
             "tolerance_gusset_left_mm": 0, "tolerance_gusset_right_mm": 0, "measurements": [meas, meas, meas],
             "remarks": "", "checked_by": "", "approved_by": ""})
check("save a blank sample report (nothing measured yet)", s == 200, si)
rid = (si.get("row") or {}).get("id") if isinstance(si, dict) else None
s, sp = call("GET", f"/api/sample-inspections/{rid}/print")
check("print the sample report", s == 200 and "html" in sp, sp)

# drawing for the sleeve and a 3D flat bag
for key, view in [("sleeve", "2d"), ("flat", "3d"), ("gusset", "both")]:
    d = {"product_key": key, "customer": "CSK", "title": f"PE {key}", "width": {"value": 4, "unit": "นิ้ว"},
         "length": {"value": 12, "unit": "นิ้ว"}, "gusset": {"value": 2, "unit": "นิ้ว"},
         "thickness": {"value": 0.08, "unit": "มม.", "mode": "side"}, "display_unit": "inch",
         "length_datum": "opening_to_seal", "drawing_view": view}
    s, sv = call("POST", "/api/drawing", d)
    check(f"drawing svg {key}/{view}", s == 200 and "<svg" in str(sv.get("svg", "")), sv)
    s, hv = call("POST", "/api/drawing/html", d)
    check(f"drawing html {key}/{view}", s == 200 and "<html" in str(hv.get("html", "")).lower(), str(hv)[:200])
s, sv = call("POST", "/api/drawing", {"product_key": "sleeve", "width": {"value": 4, "unit": "นิ้ว"},
                                      "length": {"value": 12, "unit": "นิ้ว"}})
check("sleeve drawing says OPEN TOP / OPEN BOTTOM", "OPEN BOTTOM" in str(sv.get("svg", "")), "")
s, dsave = call("POST", "/api/drawings", {"doc_no": "", "quote_ref": ref2, "drawing_date": "2026-09-30", "revision": "A",
                                          "customer": "CSK Plasatic Co.,Ltd", "customer_code": "CSK", "part_no": "4P-SLV",
                                          "length_datum": "opening_to_bottom", "display_unit": "inch",
                                          "height": {"value": 0, "unit": "นิ้ว"}, "gusset": {"value": 0, "unit": "นิ้ว"},
                                          "product_key": "sleeve", "title": "PE SLEEVE",
                                          "width": {"value": 4, "unit": "นิ้ว"}, "length": {"value": 12, "unit": "นิ้ว"},
                                          "thickness": {"value": 0.08, "unit": "มม.", "mode": "side"}})
check("save a sleeve drawing", s == 200, dsave)

# planning + work orders carry the product type
s, ps = call("GET", f"/api/planning/sources?q={ref2}")
check("planning lists the revision", s == 200 and any(r.get("quote_ref") == ref2 for r in ps.get("rows", [])), ps)
line = next((r.get("line") for r in ps.get("rows", []) if r.get("quote_ref") == ref2), ref2)
s, pl = call("GET", "/api/planning/source?selected=" + urllib.parse.quote(line))
check("planning source loads the real quote, no price", s == 200 and "price" not in json.dumps(pl).lower().replace("price_", "x"), str(pl)[:300])
for dep in ("blown", "cutting"):
    s, wo = call("POST", "/api/work-orders/html", {"department": dep, "source": ref2, "product_type": "ปลอกพลาสติกเปิดสองด้าน / Open-Ended Plastic Sleeve",
                                                   "quantity": "1000", "production": {}})
    check(f"{dep} work order prints the product type", s == 200 and "Open-Ended Plastic Sleeve" in str(wo.get("html", "")), str(wo)[:300])

# --- the three faults the browser check found on the real API (30-09-2026) ---
# A flat bag keeps the default 1 cm bottom allowance: that centimetre is material
# below the seal (calculator.py: "Quoted/spec length remains untouched"), so a
# 12-inch bag is inspected at 304.8 mm - what the mock showed the CEO.
flat = dict(base, product_key="flat", length_reference="opening_to_seal",
            bottom_allowance={"value": 1, "unit": "ซม."},
            thickness={"value": 0.16, "unit": "มม.", "mode": "pair"})
s, qf = call("POST", "/api/quotations", {"calc": flat, "quote_date": "2026-09-30", "customer": "CSK Plasatic Co.,Ltd",
                                        "customer_code": "CSK", "item_description": "PE BAG 4 x 12 inch",
                                        "product_reference": "4P677198-1"})
fref = qf.get("quote_ref", "")
check("save a flat bag with the 1 cm bottom allowance", s == 200 and fref, qf)
s, src = call("GET", f"/api/sample-inspections/sources?q={fref}")
one = next((r for r in src.get("rows", []) if r.get("quote_ref") == fref), {})
check("sample source: 12 inch is inspected at 304.8 mm, not the 314.8 mm material length",
      abs(float(one.get("length_mm", 0)) - 304.8) < 1e-6, one.get("length_mm"))
s, csrc = call("GET", f"/api/coa/sources?q={fref}")
one = next((r for r in csrc.get("rows", []) if r.get("quote_ref") == fref), {})
check("COA source: the same 304.8 mm", abs(float(one.get("length_mm", 0)) - 304.8) < 1e-6, one.get("length_mm"))

# A sample exactly on every limit passes - 0.17 - 0.16 is 0.010000000000000009
# in floating point, and a micrometer that reads 0.17 is on the limit.
lim = {"width": 111.6, "length": 294.8, "thickness": 0.17, "gusset_left": None, "gusset_right": None}
lim2 = {"width": 91.6, "length": 314.8, "thickness": 0.15, "gusset_left": None, "gusset_right": None}
s, si = call("POST", "/api/sample-inspections", {"quote_ref": fref, "inspection_date": "2026-09-30",
             "tolerance_width_mm": 10, "tolerance_length_mm": 10, "tolerance_thickness_mm": 0.01,
             "tolerance_gusset_left_mm": 0, "tolerance_gusset_right_mm": 0, "measurements": [lim, lim2],
             "remarks": "", "checked_by": "QC", "approved_by": ""})
row = si.get("row", {}) if isinstance(si, dict) else {}
check("sample on every limit -> PASS", s == 200 and row.get("overall_result") == "PASS", (s, row.get("overall_result"), row.get("results_json")))

coa = {"status": "FINAL", "quote_ref": fref, "po_no": "PO-LIM", "lot_no": "L-LIM", "inspection_date": "2026-09-30",
       "width_tolerance_mm": 10, "length_tolerance_mm": 10, "thickness_tolerance_mm": 0.01,
       "actual_width_mm": 111.6, "actual_length_mm": 294.8, "actual_thickness_mm": 0.17,
       "result": "PASS", "checked_by": "QC", "approved_by": "QA"}
s, cf = call("POST", "/api/coa", coa)
crow = cf.get("row", {}) if isinstance(cf, dict) else {}
check("COA on every limit (0.17 vs 0.16 +/- 0.01) -> PASS", s == 200 and crow.get("result") == "PASS", (s, crow.get("result")))
s, cf2 = call("POST", "/api/coa", dict(coa, status="DRAFT", lot_no="L-OUT", actual_thickness_mm=0.171))
check("COA just past the limit (0.171) -> FAIL", s == 200 and (cf2.get("row") or {}).get("result") == "FAIL", cf2)

# Deleting a quotation a FINAL COA points at is refused with the reason, not a 500.
s, d = call("DELETE", "/api/quotations/" + urllib.parse.quote(fref, safe=""))
check("delete a quotation a COA uses -> 409 naming the COA", s == 409 and str(crow.get("certificate_no", "?")) in str(d), (s, d))
s, f3 = call("GET", f"/api/quotations/{fref}/form")
check("the quotation is still there", s == 200, (s, f3))

print("\nHONG - %d buoc sai: %s" % (len(bad), bad) if bad else "\nKHOP - moi luong thang 9 cua CEO chay tren may chu that")
sys.exit(1 if bad else 0)

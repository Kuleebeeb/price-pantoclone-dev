# -*- coding: utf-8 -*-
"""INTEGRATION (HTTP): the CEO's 2026-08-30 flow end to end, through the real API.

Quotation -> COA (draft, delete, FINAL number, FINAL refuses delete, print)
-> Sample Inspection (quoted unit before mm, PASS / FAIL, print, delete)
-> Planning (prefill without prices, equal-count weight compare)
-> cutting work order -> drawing print.  Every printed sheet must carry
"Printed: <Bangkok time> • Page 1 of 1" (CEO print standard).

Needs DATABASE_URL -> a THROWAWAY Postgres (the URL must contain 'smoke')
and the API on BASE (default http://127.0.0.1:8145) started against it with
BOOTSTRAP_EMAIL / BOOTSTRAP_PASSWORD so a local account exists.
"""
from __future__ import annotations

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
TOKEN = None
fails = 0


def call(method, path, body=None, raw=False):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode()
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("content-type", "application/json")
    if TOKEN:
        req.add_header("authorization", "Bearer " + TOKEN)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            txt = r.read().decode()
            return r.status, (txt if raw else (json.loads(txt) if txt else {}))
    except urllib.error.HTTPError as e:
        txt = e.read().decode()
        try:
            return e.code, json.loads(txt)
        except Exception:
            return e.code, txt
    except urllib.error.URLError as e:
        print("HONG: khong noi duoc API o", BASE, "-", e)
        sys.exit(1)


def check(name, ok, detail=""):
    global fails
    print(("  ok   " if ok else "  FAIL ") + name + (("  -> " + str(detail)[:220]) if detail else ""))
    if not ok:
        fails += 1


s, r = call("GET", "/api/health")
check("health", s == 200, r)

s, r = call("POST", "/api/auth/login", {"email": EMAIL, "password": PASSWORD})
TOKEN = (r.get("token") or r.get("access_token")) if isinstance(r, dict) else None
check("login gives a token", s == 200 and bool(TOKEN), (s, r if not TOKEN else "token ok"))

# 1. Quotation with source tolerances + special requirements (the one place they are typed)
calc = {
    "product_key": "flat",
    "width": {"value": 4, "unit": "นิ้ว"}, "length": {"value": 12, "unit": "นิ้ว"},
    "thickness": {"value": 0.16, "unit": "มม.", "mode": "pair"},
    "tolerance_width": {"value": 10, "unit": "มม."}, "tolerance_length": {"value": 10, "unit": "มม."},
    "tolerance_thickness": {"value": 0.01, "unit": "มม."},
    "special_requirements": "ซีลก้นตรงและแข็งแรง\nปากถุงเปิดง่าย",
    "pack_quantity": 100, "sack_quantity": 500, "order_quantity": 5000,
}
s, r = call("POST", "/api/quotations", {"calc": calc, "quote_date": "2026-08-30", "customer": "CEO-FLOW-TEST Co.,Ltd",
                                        "customer_code": "CEOFLOW", "item_description": "PE BAG 4 x 12 inch",
                                        "product_reference": "4P677198-1"})
check("save quotation", s == 200 and "quote_ref" in r, (s, r))
QT = r.get("quote_ref", "") if isinstance(r, dict) else ""
print("     quote_ref =", QT)

s, r = call("GET", "/api/quotations/" + urllib.parse.quote(QT, safe="") + "/print", raw=True)
check("quotation print carries Printed + Page 1 of 1", s == 200 and "Printed:" in r and "Page 1 of 1" in r, s)

# 2. COA: sources carry the quotation's tolerances; DRAFT deletes; FINAL numbers and refuses delete
s, r = call("GET", "/api/coa/sources?q=CEOFLOW")
rows = r.get("rows", []) if isinstance(r, dict) else []
src = next((x for x in rows if x.get("quote_ref") == QT), None)
check("coa/sources finds the quotation", s == 200 and src is not None, (s, [x.get("quote_ref") for x in rows][:5]))
if src:
    check("coa source carries tolerances + special requirements from the quotation",
          float(src.get("tolerance_width_mm", 0) or 0) == 10 and float(src.get("tolerance_thickness_mm", 0) or 0) == 0.01
          and "ซีลก้น" in str(src.get("special_requirements", "")),
          {k: src.get(k) for k in src if "toler" in k or k == "special_requirements"})

s, r = call("POST", "/api/coa", {"quote_ref": QT, "status": "DRAFT", "po_no": "PO-2026-001", "lot_no": "L-001"})
draft = r.get("row", {}) if isinstance(r, dict) else {}
check("COA draft saved without a number", s == 200 and draft.get("id") and not draft.get("certificate_no"), (s, r))
s, r = call("DELETE", f"/api/coa/{draft.get('id')}")
check("COA draft can be deleted", s == 200 and r.get("deleted") == draft.get("id"), (s, r))
s, r = call("GET", "/api/coa")
check("deleted draft is gone from the list", s == 200 and all(x.get("id") != draft.get("id") for x in r.get("rows", [])), s)

s, r = call("POST", "/api/coa", {"quote_ref": QT, "status": "FINAL", "po_no": "PO-2026-001", "lot_no": "L-002",
                                 "issue_date": "2026-08-30", "inspection_date": "2026-08-30", "quantity": "5,000 pcs",
                                 "actual_width_mm": 101.6, "actual_length_mm": 304.8, "actual_thickness_mm": 0.17,
                                 "result": "PASS", "checked_by": "QC", "approved_by": "CEO"})
final = r.get("row", {}) if isinstance(r, dict) else {}
check("COA thickness exactly on the limit (0.17 vs 0.16 ± 0.01) keeps PASS", final.get("result") == "PASS", final.get("result"))
check("COA FINAL gets COA-YYYYMM-NNNN", s == 200 and str(final.get("certificate_no", "")).startswith("COA-202608-"),
      (s, final.get("certificate_no"), r if s != 200 else ""))
s, r = call("DELETE", f"/api/coa/{final.get('id')}")
check("FINAL COA refuses delete (409)", s == 409, (s, r))
s, r = call("GET", f"/api/coa/{final.get('id')}/print")
html = r.get("html", "") if isinstance(r, dict) else ""
check("COA print: Printed + Page + number + company header", s == 200 and "Printed:" in html and "Page 1 of 1" in html
      and str(final.get("certificate_no")) in html and "PANTONG THAI PACK CO., LTD." in html, s)
check("COA print thickness is labelled per pair", "pair" in html, "")

# 3. Sample inspection: quoted unit before mm, PASS, SIR number, print, FAIL, delete
s, r = call("GET", "/api/sample-inspections/sources?q=CEOFLOW")
srows = r.get("rows", []) if isinstance(r, dict) else []
ssrc = next((x for x in srows if x.get("quote_ref") == QT), None)
check("sample sources find the quotation", s == 200 and ssrc is not None, s)
if ssrc:
    check("sample source keeps the customer's inch unit", str(ssrc.get("width_original", {}).get("unit", "")) == "นิ้ว", ssrc.get("width_original"))
s, r = call("POST", "/api/sample-inspections", {
    "quote_ref": QT, "inspection_date": "2026-08-30", "tolerance_width_mm": 10, "tolerance_length_mm": 10,
    "tolerance_thickness_mm": 0.01, "tolerance_gusset_left_mm": 0, "tolerance_gusset_right_mm": 0,
    "measurements": [{"width": 101.6, "length": 304.8, "thickness": 0.16}], "remarks": "", "checked_by": "QC", "approved_by": "CEO"})
sir = r.get("row", {}) if isinstance(r, dict) else {}
check("sample inspection saved as SIR-YYYYMMDD-NNNN with PASS",
      s == 200 and str(sir.get("report_no", "")).startswith("SIR-") and sir.get("overall_result") == "PASS",
      (s, sir.get("report_no"), sir.get("overall_result"), r if s != 200 else ""))
s, r = call("GET", f"/api/sample-inspections/{sir.get('id')}/print")
html = r.get("html", "") if isinstance(r, dict) else ""
check("sample print: Printed + Page + SAMPLE INSPECTION REPORT",
      s == 200 and "Printed:" in html and "Page 1 of 1" in html and "SAMPLE INSPECTION REPORT" in html, s)
s, r = call("POST", "/api/sample-inspections", {
    "quote_ref": QT, "inspection_date": "2026-08-30", "tolerance_width_mm": 10, "tolerance_length_mm": 10,
    "tolerance_thickness_mm": 0.01, "measurements": [{"width": 130, "length": 304.8, "thickness": 0.16}], "checked_by": "QC"})
failed_id = r.get("row", {}).get("id") if isinstance(r, dict) else None
check("out-of-tolerance width -> FAIL", s == 200 and r.get("row", {}).get("overall_result") == "FAIL", (s, r.get("row", {}).get("overall_result")))
# 0.17 - 0.16 is 0.010000000000000009 in floating point; the micrometer says it is on the limit
s, r = call("POST", "/api/sample-inspections", {
    "quote_ref": QT, "inspection_date": "2026-08-30", "tolerance_width_mm": 10, "tolerance_length_mm": 10,
    "tolerance_thickness_mm": 0.01, "measurements": [{"width": 111.6, "length": 294.8, "thickness": 0.17}], "checked_by": "QC"})
edge_id = r.get("row", {}).get("id") if isinstance(r, dict) else None
check("sample exactly on every limit -> PASS (no floating-point FAIL)",
      s == 200 and r.get("row", {}).get("overall_result") == "PASS", (s, r.get("row", {}).get("overall_result")))
for rid in (sir.get("id"), failed_id, edge_id):
    s, r = call("DELETE", f"/api/sample-inspections/{rid}")
    check(f"sample inspection {rid} delete", s == 200, (s, r))

# 4. Planning: prefill without prices, equal-count compare, cutting work order with the print stamp
s, r = call("GET", "/api/planning/sources")
check("planning sources list", s == 200 and any(QT in json.dumps(x, ensure_ascii=False) for x in r.get("rows", [])), s)
s, r = call("GET", "/api/planning/source?selected=" + urllib.parse.quote(QT))
check("planning source prefill", s == 200, (s, str(r)[:200]))
blob = json.dumps(r, ensure_ascii=False) if isinstance(r, dict) else ""
check("planning prefill carries special requirements + tolerances", "ซีลก้น" in blob and "10" in blob, "")
check("planning prefill shows no selling price", not any(k in blob for k in ("unit_price", "total_price", "selling_price")),
      [k for k in ("unit_price", "total_price", "selling_price") if k in blob])
s, r = call("POST", "/api/planning/compare", {"quote_ref": QT, "quantity": "500", "width": "10.16", "length": "30.48",
                                              "thickness": "0.17", "gusset": "", "sack_quantity": "500"})
check("planning compare (equal count weight)", s == 200 and "grams_per_item" in r, (s, str(r)[:300]))
s, r = call("POST", "/api/work-orders/html", {"department": "cutting", "source": QT, "width": "10.16 ซม.", "length": "30.48 ซม.",
                                              "thickness": "0.16 มม./คู่", "sack_quantity": "500", "special_features": "ซีลก้นตรง",
                                              "tolerance_width": "10", "tolerance_length": "10", "tolerance_thickness": "0.01"})
html = r.get("html", "") if isinstance(r, dict) else ""
check("cutting work order: Printed + Page", s == 200 and "Printed:" in html and "Page 1 of 1" in html, (s, str(r)[:200] if s != 200 else ""))

# 5. Drawing print carries the print stamp footer
s, r = call("POST", "/api/drawing/html", {"product_key": "flat", "doc_no": "DWG-CEOFLOW-1", "title": "PE BAG 4 x 12 inch",
                                          "customer": "CEO-FLOW-TEST Co.,Ltd", "customer_code": "CEOFLOW",
                                          "width": {"value": 4, "unit": "นิ้ว"}, "length": {"value": 12, "unit": "นิ้ว"},
                                          "thickness": {"value": 0.16, "unit": "มม.", "mode": "pair"}})
html = r.get("html", "") if isinstance(r, dict) else ""
check("drawing print: Printed + Page 1 of 1", s == 200 and "Printed:" in html and "Page 1 of 1" in html, (s, str(r)[:300] if s != 200 else ""))

# 6. A quotation with an issued COA cannot be deleted - and the answer is a reason, not a 500
s, r = call("DELETE", "/api/quotations/" + urllib.parse.quote(QT, safe=""))
check("quotation referenced by a FINAL COA refuses delete (409)", s == 409 and "COA" in str(r), (s, str(r)[:160]))
s, r = call("POST", "/api/quotations", {"calc": calc, "quote_date": "2026-08-30", "customer": "CEO-FLOW-TEST Co.,Ltd",
                                        "customer_code": "CEOFLOW", "item_description": "PE BAG 4 x 12 inch (unreferenced)"})
QT2 = r.get("quote_ref", "") if isinstance(r, dict) else ""
s, r = call("DELETE", "/api/quotations/" + urllib.parse.quote(QT2, safe=""))
check("quotation nothing points at still deletes (200)", s == 200 and r.get("deleted") == QT2, (s, r))

print()
print("KHOP - luong CEO 30-08-2026 di het tung cua, moi to in co dau gio va so trang" if fails == 0 else f"HONG - {fails} buoc sai")
sys.exit(1 if fails else 0)

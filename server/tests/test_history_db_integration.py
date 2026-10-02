# -*- coding: utf-8 -*-
"""INTEGRATION: every kind of history row must come back out, whole.

The book holds three breeds of row and they are not the same animal:

  1. PAPER  - read out of the old books (store.import_quotations). No inputs,
              no results, grams 0, and a reference LIKE "ZZHIST/09-01" - with
              a slash, because that is the number the customer has been
              holding since before this system existed.
  2. EXE    - synced from the CEO's desktop (store.sync_quotations). Inputs in
              the desktop's own shape: sizes under `dimensions`, the sale
              basis as its Thai label, the price basis inside results.
  3. WEB    - saved by this screen (db.save_quotation). Flat CalcRequest shape.

This script SEEDS one of each straight into a throwaway Postgres, then pulls
every one of them back out THROUGH REAL HTTP - the table, the Details window,
the Edit prefill, the reprint, the planning loader - because "every row can be
extracted" is a promise about the whole pipe, not about one function.

Needs: DATABASE_URL pointing at a THROWAWAY database (never the real one),
and the API running against it (BASE, default http://127.0.0.1:8145).
Run:  .venv/Scripts/python.exe tests/test_history_db_integration.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "core"))
sys.path.insert(0, str(HERE / "api"))

if not os.environ.get("DATABASE_URL"):
    print("HONG: can DATABASE_URL tro vao mot Postgres TAM (khong bao gio DB that).")
    sys.exit(1)

import db  # noqa: E402
import store  # noqa: E402

BASE = os.environ.get("BASE", "http://127.0.0.1:8145")
EMAIL = os.environ.get("BOOTSTRAP_EMAIL", "smoke@test.local")
PASSWORD = os.environ.get("BOOTSTRAP_PASSWORD", "smoke-pass-1234")

token = None
failures: list[str] = []


def call(method: str, path: str, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("content-type", "application/json")
    if token:
        req.add_header("authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def check(name: str, cond: bool, detail="") -> None:
    if cond:
        print("  ok  " + name)
    else:
        failures.append(name)
        print("  BAD " + name + "  " + str(detail)[:240])


# ----------------------------------------------------------------- seed 3 rows
PAPER_REF = "ZZHIST/09-01"

print("Seed - one row of each breed, straight into the throwaway book")
store.import_quotations(
    [
        {
            "quote_ref": PAPER_REF,
            "quote_date": "2021-05-10",
            "customer": "ZZHIST Paper Co., Ltd.",
            "customer_code": "",
            "item_description": "ถุงเก่าจากสมุด",
            "product_reference": "PB-77",
            "product_key": "gusset",
            "product_label": "ถุงพับข้าง (Gusset Bag)",
            "size_text": "",
            "unit_price": 3.5,
            "grams_per_item": 0,
            "import_source": "zzhist-test-books",
        }
    ]
)

with db.pool().connection() as conn:
    user_row = conn.execute("SELECT id FROM users ORDER BY id LIMIT 1").fetchone()
exe_out = store.sync_quotations(
    [
        {
            "client_uid": "zzhist-exe-0001",
            "quote_date": "2026-08-27",
            "customer": "ZZHIST Desk Co., Ltd.",
            "customer_code": "ZD-1",
            "item_description": "desk bag",
            "product_reference": "DK-1",
            "product_key": "flat",
            "product_label": "ถุงพลาสติกเปิดปากตรง (Plastic Bag)",
            "size_text": "กว้าง/Width 30 ซม. × ยาว/Length 40 ซม.",
            "length_reference": "ปากถึงแนวซีล / Opening to Seal",
            "inputs": {
                "dimensions": {
                    "width": {"value": 30, "unit": "ซม."},
                    "length": {"value": 40, "unit": "ซม."},
                },
                "thickness": {"value": 0.06, "unit": "มม.", "mode": "pair"},
                "sale_basis": "ขายเป็นกิโลกรัม / Sell by kg",
                "deduction_percent": 10,
                "apply_deduction": True,
                "normalized": {"width_cm": 30.0, "length_cm": 40.0, "gusset_cm": 0.0},
                "selling_price_per_kg_override": 60,
                "order_quantity": 500,
            },
            "formulas": {"weight": "w", "price": "p"},
            "results": {
                "material_length_cm": 41.0,
                "items_per_kg": 88.1,
                "production_items_per_kg": 79.29,
                "selling_price_per_kg": 60.0,
                "calculated_price_per_kg": 59.4675,
                "calculated_price_per_piece_from_kg": 0.7567,
                "price_basis_summary": "60.000 บาท/กก. ÷ 79.29 ชิ้น/กก.",
                "verification_summary": "exe verification line",
                "control_status": "-",
            },
            "unit_price": 0.7567,
            "total_price": 378.35,
            "grams_per_item": 11.352,
        }
    ],
    user_id=user_row["id"],
    device_name="zzhist-station",
)
EXE_REF = exe_out[0]["quote_ref"]

web_row = db.save_quotation(
    {
        # A date OBJECT, as the API layer always hands one over (pydantic
        # parses it before db.save_quotation ever sees it).
        "quote_date": date(2026, 8, 27),
        "customer": "ZZHIST Web Co., Ltd.",
        "customer_code": "ZW-1",
        "item_description": "web bag",
        "product_reference": "WB-1",
        "product_image_path": "",
        "revised_from_ref": PAPER_REF,
        "product_key": "flat",
        "product_label": "ถุงพลาสติกเปิดปากตรง (Plastic Bag)",
        "size_text": "กว้าง/Width 45 ซม. × ยาว/Length 60 ซม.",
        "length_reference": "ปากถึงแนวซีล / Opening to Seal",
        "inputs": {
            "sale_basis": "kg",
            "thickness": {"value": 0.08, "unit": "มม.", "mode": "pair"},
            "deduction_percent": 10,
            "apply_deduction": True,
            "pack_quantity": 100,
            "order_quantity": 1000,
            "selling_price_per_kg_override": 53,
            "price_basis": "ราคาขายที่กรอก 53.000 บาท/กก. / Entered final price per kg",
            "human_summary": "web verification line",
            "normalized": {"width_cm": 45.0, "length_cm": 60.0, "gusset_cm": 0.0},
        },
        "formulas": {"weight": "w", "price": "p"},
        "results": {
            "material_length_cm": 61.0,
            "items_per_kg": 49.497,
            "production_items_per_kg": 44.547,
            "selling_price_per_kg": 53.0,
            "calculated_price_per_piece_from_kg": 1.1898,
            "control_status": "-",
        },
        "unit_price": 1.1898,
        "total_price": 1189.744,
        "grams_per_item": 20.2032,
        "pack_quantity": 100,
        "pack_weight_kg": 2.0203,
    }
)
WEB_REF = web_row["quote_ref"]
print("  ok  seeded: " + PAPER_REF + " · " + EXE_REF + " · " + WEB_REF)

# --------------------------------------------------------------------- sign in
s, r = call("POST", "/api/auth/login", {"email": EMAIL, "password": PASSWORD})
token = r.get("token")
check("sign in", s == 200 and bool(token), r)

# --------------------------------------------------- the table shows all three
print("The table - fifteen cells for every breed, none blank by accident")
s, h = call("GET", "/api/history?customer=ZZHIST")
rows = {row["ref"]: row for row in h.get("rows", [])}
check("all three breeds listed", s == 200 and len(rows) == 3, sorted(rows))

paper = rows.get(PAPER_REF, {})
check("paper: the slash survives into the cell", paper.get("ref") == PAPER_REF, paper.get("ref"))
check("paper: thickness reads N/A", paper.get("thickness") == "ไม่ใช้ / N/A", paper.get("thickness"))
check("paper: grams prints 0.000, not a crash", paper.get("grams") == "0.000", paper.get("grams"))
check("paper: pack shows the dash", paper.get("pack") == "—", paper.get("pack"))
check("paper: price basis stays honestly empty", paper.get("price_basis") == "", paper.get("price_basis"))

exe = rows.get(EXE_REF, {})
check("exe: Thai sale label passes through", exe.get("sale_unit") == "ขายเป็นกิโลกรัม / Sell by kg", exe.get("sale_unit"))
check("exe: price basis found inside results", exe.get("price_basis") == "60.000 บาท/กก. ÷ 79.29 ชิ้น/กก.", exe.get("price_basis"))
check("exe: nested thickness unfolds", exe.get("thickness") == "0.06 มม. • ต่อคู่ / Per Pair", exe.get("thickness"))
check("exe: calc price per kg shown", exe.get("calc_price") == "59.468", exe.get("calc_price"))

web = rows.get(WEB_REF, {})
check("web: item and part joined", web.get("item") == "web bag / WB-1", web.get("item"))
check("web: pack weight 4dp", web.get("pack") == "2.0203", web.get("pack"))

for sort in ("product", "size", "oldest"):
    s, _ = call("GET", "/api/history?customer=ZZHIST&sort=" + sort)
    check("sort=" + sort + " answers 200", s == 200)

# --------------------------------------- the slash reference reaches every door
print("The slash reference - every per-row door opens for a paper number")
enc = urllib.parse.quote(PAPER_REF, safe="")
s, d = call("GET", "/api/quotations/" + enc + "/details")
check("details opens through the slash", s == 200 and d.get("title") == "รายละเอียด / Details — " + PAPER_REF, d)
check("details shows the honest dash for item code", "รหัสลูกค้า / Customer Code: -" in d.get("text", ""))

s, f = call("GET", "/api/quotations/" + enc + "/form")
check("edit prefill opens through the slash", s == 200, f)
check("paper form: empty boxes stay empty", f.get("form", {}).get("width") == "", f.get("form", {}).get("width"))
check("paper form: defaults are labeled defaults", f.get("form", {}).get("density") == "0.92")

s, p = call("GET", "/api/quotations/" + enc + "/print")
check("paper row PRINTS from stored figures (no recompute 400)", s == 200, p)
check("paper sheet carries its own ref", PAPER_REF in p.get("html", ""))

s, one = call("GET", "/api/quotations/" + enc)
check("plain GET opens through the slash", s == 200 and one.get("quote_ref") == PAPER_REF)

# -------------------------------------------------- reprint = the SAVED truth
print("Reprint is a snapshot (LAW P5), never a recompute")
s, p = call("GET", "/api/quotations/" + urllib.parse.quote(WEB_REF, safe="") + "/print")
check("web reprint answers", s == 200, p)
check("reprint shows the SAVED kg price", "53.000 บาท" in p.get("html", ""))
check("reprint carries the revised-from row", "แก้ไขจาก / Revised From</th><td>" + PAPER_REF in p.get("html", ""))
check("reprint shows the saved verification", "web verification line" in p.get("html", ""))

s, p = call("GET", "/api/quotations/" + urllib.parse.quote(EXE_REF, safe="") + "/print")
check("exe reprint reads the desktop-shaped record", s == 200 and "exe verification line" in p.get("html", ""), str(p)[:200])

# ------------------------------------------------- planning reads every breed
print("Planning - the loader takes any breed; the comparison refuses honestly")
s, src = call("GET", "/api/planning/source?selected=" + urllib.parse.quote(EXE_REF, safe=""))
check("exe row loads into planning", s == 200 and src.get("width") == "30", src)
s, src = call("GET", "/api/planning/source?selected=" + urllib.parse.quote(PAPER_REF, safe=""))
check("paper row loads without crashing", s == 200, src)
s, cmp_out = call(
    "POST",
    "/api/planning/compare",
    {"quote_ref": PAPER_REF, "quantity": "10", "width": "30", "length": "40", "thickness": "0.06", "gusset": "0"},
)
check(
    "paper row refuses comparison by name",
    s == 400 and cmp_out.get("error") == "ใบราคาไม่มีข้อมูลอ้างอิงครบ / Pricing record lacks reference dimensions",
    cmp_out,
)

# -------------------------------------------------- related sees imported rows
s, rel = call("GET", "/api/related/table?product_reference=PB-77")
check("related finds the paper row by part number", s == 200 and rel.get("count") == 1, rel)
check("related pack cell says Not Set for paper", rel["rows"][0]["pack_kg"] == "ยังไม่ได้กำหนด / Not Set")

# ------------------------------------------------------------------- clean up
print("Clean up - and DELETE through a slash is itself under test")
GONE = {"reason": "test clean-up"}
s, _ = call("DELETE", "/api/quotations/" + enc, GONE)
check("delete opens through the slash", s == 200)
for ref in (EXE_REF, WEB_REF):
    call("DELETE", "/api/quotations/" + urllib.parse.quote(ref, safe=""), GONE)
s, h = call("GET", "/api/history?customer=ZZHIST")
check("nothing test-shaped left behind", s == 200 and h.get("rows") == [], h)

db.close_pool()
print()
if failures:
    print("HONG: " + str(len(failures)) + " kiem tra do - " + ", ".join(failures))
    sys.exit(1)
print("KHOP: ca ba giong dong lich su deu trich xuat va dung duoc qua moi cua - khong dong nao la trang tri.")

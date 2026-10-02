# -*- coding: utf-8 -*-
"""INTEGRATION (HTTP): the CEO's 02-10-2026 handover - MOQ, selling a roll by
the roll, and Delete as a trash with Restore - against the REAL API.

The CEO built all three on dev_mock_api.py + local_history_actions.py; the
figures and sentences checked here are the ones her own tests checked there
(test_moq.py, test_roll_sales.py, test_history_actions.py in the handover).

Needs DATABASE_URL -> a THROWAWAY Postgres (the URL must contain 'smoke')
and the API on BASE (default http://127.0.0.1:8145) started against it with
BOOTSTRAP_EMAIL / BOOTSTRAP_PASSWORD so a local account exists.
"""
import json
import math
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


def enc(ref):
    return urllib.parse.quote(ref, safe="")


def history_row(ref):
    s, h = call("GET", "/api/history?customer=" + enc(CUSTOMER))
    return next((r for r in h.get("rows", []) if r["ref"] == ref), None) if s == 200 else None


s, r = call("POST", "/api/auth/login", {"email": EMAIL, "password": PASSWORD})
TOKEN = r.get("token", "") if isinstance(r, dict) else ""
check("login", s == 200 and TOKEN, r)

CUSTOMER = "ZZ-OCT-FLOW Co.,Ltd"
bag = dict(product_key="flat", width={"value": 4, "unit": "นิ้ว"}, length={"value": 12, "unit": "นิ้ว"},
           thickness={"value": 0.16, "unit": "มม.", "mode": "pair"}, density_g_cm3=0.92,
           material_price_per_kg=65, sale_basis="kg", selling_price_per_kg_override=85,
           pack_quantity=100, sack_quantity=1000, order_quantity=1000)
head = dict(quote_date="2026-10-02", customer=CUSTOMER, customer_code="ZZOCT", item_description="PE BAG 4 x 12")

# --------------------------------------------------------------------- MOQ
print("MOQ")
s, meta = call("GET", "/api/meta")
keys = [c["key"] for c in meta.get("labels", {}).get("history_columns", [])]
check("history has an MOQ column and the six roll columns",
      "moq" in keys and all(k in keys for k in ("roll_kg", "roll_price", "roll_sale_price", "roll_quantity",
                                                  "roll_total_kg", "roll_total_price")), keys)
for quantity, unit in [("-1", "kg"), ("0", "piece"), ("1.5", "piece"), ("1.5", "roll"), ("nan", "kg"),
                       ("1", ""), ("abc", "kg")]:
    s, r = call("POST", "/api/quotations", dict(head, calc=bag, moq_quantity=quantity, moq_unit=unit))
    check(f"MOQ {quantity!r} {unit!r} refused with a reason", s == 400 and "MOQ" in str(r), (s, r))
s, r = call("POST", "/api/print/html", dict(head, calc=bag, moq_quantity="0", moq_unit="kg"))
check("print refuses a bad MOQ too", s == 400 and "MOQ" in str(r), (s, r))

s, r = call("POST", "/api/quotations", dict(head, calc=bag, moq_quantity="1000", moq_unit="piece"))
moq_ref = r.get("quote_ref", "") if isinstance(r, dict) else ""
check("save with MOQ 1000 pieces", s == 200 and moq_ref, (s, r))
row = history_row(moq_ref) or {}
check("history MOQ cell = '1,000 ใบ'", row.get("moq") == "1,000 ใบ", row.get("moq"))
check("a bag row leaves the roll columns blank", row.get("roll_price") == "" and row.get("roll_kg") == "", row)
s, f = call("GET", f"/api/quotations/{enc(moq_ref)}/form")
check("Edit pours the MOQ back", s == 200 and f["form"].get("moq_quantity") == "1000"
      and f["form"].get("moq_unit") == "piece", f.get("form", {}).get("moq_quantity"))
s, d = call("GET", f"/api/quotations/{enc(moq_ref)}/details")
check("details state the MOQ", s == 200 and "MOQ: 1,000 ใบ" in d.get("text", ""), d)
s, p = call("GET", f"/api/quotations/{enc(moq_ref)}/print")
check("reprint carries the MOQ", s == 200 and "1,000 ใบ" in p.get("html", ""), s)
s, r = call("POST", "/api/quotations", dict(head, calc=bag, moq_quantity="25.5", moq_unit="kg"))
check("MOQ in kg may be a fraction", s == 200 and (history_row(r["quote_ref"]) or {}).get("moq") == "25.5 กก.", r)
s, r = call("POST", "/api/quotations", dict(head, calc=bag, moq_quantity="", moq_unit="kg"))
row = history_row(r.get("quote_ref", "")) or {}
check("blank MOQ is 'not stated', the unit alone means nothing", s == 200 and row.get("moq") == "", (s, row.get("moq")))
s, p = call("POST", "/api/print/html", dict(head, calc=bag))
check("a sheet without MOQ prints no MOQ row", s == 200 and "MOQ" not in p.get("html", ""), s)

# ------------------------------------------------------------- sell by roll
print("Sell by roll")
roll = dict(product_key="roll", sale_basis="roll", width={"value": 180, "unit": "ซม."},
            sold_length={"value": 100, "unit": "เมตร"}, thickness={"value": 0.1, "unit": "มม.", "mode": "side"},
            density_g_cm3=0.92, material_price_per_kg=65, order_quantity=10, selling_price_per_kg_override=85,
            selling_price_per_piece_override=999, apply_deduction=True, deduction_percent=10)
s, c = call("POST", "/api/calculate", roll)
v = c.get("results", {}) if isinstance(c, dict) else {}
check("33.12 kg per roll (180 cm x 100 m x 0.1 mm per side)", s == 200 and math.isclose(v.get("roll_kg", 0), 33.12), (s, c))
check("2,815.20 THB per roll at 85 THB/kg", math.isclose(v.get("roll_price", 0), 2815.2), v.get("roll_price"))
check("10 rolls = 331.2 kg, 28,152 THB", math.isclose(v.get("roll_total_kg", 0), 331.2)
      and math.isclose(v.get("roll_total_price", 0), 28152), v)
check("no 10% deduction and the piece box ignored", math.isclose(v.get("production_items_per_kg", 0), v.get("items_per_kg", 1))
      and math.isclose(v.get("roll_sale_price", 0), 2815.2), v)
disp = c.get("display", {}) if isinstance(c, dict) else {}
check("screen boxes say kg per roll and THB per roll", disp.get("grams") == "33.12 กก./ม้วน"
      and disp.get("calculated_piece") == "2,815.20 บาท/ม้วน" and disp.get("roll_total_price") == "28,152.00 บาท", disp)
s, c = call("POST", "/api/calculate", dict(roll, sold_length={"value": 200, "unit": "เมตร"}))
check("twice the length, twice the price (5,630.40)", s == 200 and math.isclose(c["results"]["roll_price"], 5630.4), c)
s, c = call("POST", "/api/calculate", dict(roll, thickness={"value": 0.1, "unit": "มม.", "mode": "pair"}))
check("0.1 per pair weighs half (16.56 kg)", s == 200 and math.isclose(c["results"]["roll_kg"], 16.56), c)
s, c = call("POST", "/api/calculate", dict(roll, selling_price_per_roll_override=3000))
check("actual 3,000 per roll: calculated stays 2,815.20, total 30,000", s == 200
      and math.isclose(c["results"]["roll_price"], 2815.2) and c["results"]["roll_sale_price"] == 3000
      and c["results"]["roll_total_price"] == 30000, c)
for quantity in (0, -1, 1.5):
    s, c = call("POST", "/api/calculate", dict(roll, order_quantity=quantity))
    check(f"{quantity} rolls refused", s == 400 and "ม้วน" in str(c), (s, c))
s, c = call("POST", "/api/calculate", dict(roll, selling_price_per_roll_override=0))
check("actual price per roll 0 refused (blank means calculated)", s == 400, (s, c))
s, c = call("POST", "/api/calculate", dict(roll, selling_price_per_kg_override=0))
check("no price per kg refused", s == 400, (s, c))
s, c = call("POST", "/api/calculate", dict(bag, sale_basis="roll"))
check("a flat bag cannot be sold by the roll", s == 400 and "ม้วน" in str(c), (s, c))

s, r = call("POST", "/api/quotations", dict(head, item_description="PE ROLL 180 cm",
                                            calc=dict(roll, selling_price_per_roll_override=3000),
                                            moq_quantity="2", moq_unit="roll"))
roll_ref = r.get("quote_ref", "") if isinstance(r, dict) else ""
check("save a roll sold by the roll", s == 200 and roll_ref, (s, r))
row = history_row(roll_ref) or {}
check("history: unit 'ม้วน / roll', per-roll figures, per-piece cells empty",
      row.get("sale_unit") == "ม้วน / roll" and row.get("roll_price") == "2,815.20"
      and row.get("roll_sale_price") == "3,000.00" and row.get("roll_quantity") == "10"
      and row.get("roll_total_price") == "30,000.00" and row.get("calc_price") == "—"
      and row.get("price_kg") == "85.000" and row.get("moq") == "2 ม้วน", row)
s, f = call("GET", f"/api/quotations/{enc(roll_ref)}/form")
form = f.get("form", {}) if isinstance(f, dict) else {}
check("Edit pours back sale by roll, 3000 per roll, MOQ in rolls", form.get("sale_basis") == "roll"
      and float(form.get("price_per_roll") or 0) == 3000 and form.get("moq_unit") == "roll"
      and form.get("apply_deduction") is False, form)
s, p = call("GET", f"/api/quotations/{enc(roll_ref)}/print")
html = p.get("html", "") if isinstance(p, dict) else ""
check("reprint: sell by roll, 3,000.00 actual, 30,000.00 total, no pack rows",
      s == 200 and "ขายเป็นม้วน" in html and "3,000.00 บาท" in html and "30,000.00 บาท" in html
      and "บรรจุต่อแพ็ก" not in html, s)
s, d = call("GET", f"/api/quotations/{enc(roll_ref)}/details")
check("details list the roll figures", s == 200 and "2,815.20" in d.get("text", "") and "3,000.00" in d.get("text", ""), d)
s, r = call("POST", "/api/quotations", dict(head, item_description="PE ROLL 180 cm", calc=roll))
row = history_row(r.get("quote_ref", "")) or {}
check("no actual price typed: the cell stays blank (print says calculated used)",
      s == 200 and row.get("roll_sale_price") == "" and row.get("roll_price") == "2,815.20", row)

# --------------------------------------------------------------- the trash
print("Trash")
s, t = call("GET", "/api/history/trash")
check("trash says this server records a reason", s == 200 and t.get("reason_required") is True, (s, t))
s, before = call("GET", f"/api/quotations/{enc(roll_ref)}")
s, r = call("DELETE", f"/api/quotations/{enc(roll_ref)}")
check("delete without a reason is refused", s == 400 and "เหตุผล" in str(r), (s, r))
s, r = call("DELETE", f"/api/quotations/{enc(roll_ref)}", {"reason": "   "})
check("a blank reason is no reason", s == 400, (s, r))
s, r = call("DELETE", f"/api/quotations/{enc(roll_ref)}", {"reason": "x" * 1001, "actor": "Somchai"})
check("a reason over 1,000 characters is refused", s == 400, (s, r))
s, r = call("DELETE", f"/api/quotations/{enc(roll_ref)}", {"reason": "ราคาผิด <ทดสอบ>", "actor": "Somchai"})
check("delete with a reason moves it to the trash", s == 200 and r.get("deleted") == roll_ref, (s, r))
check("gone from history", history_row(roll_ref) is None)
s, _ = call("GET", f"/api/quotations/{enc(roll_ref)}")
check("gone from the record route too", s == 404, s)
s, t = call("GET", "/api/history/trash")
entry = next((e for e in t.get("rows", []) if e["ref"] == roll_ref), {})
check("trash lists it with the reason, the ACCOUNT, the typed name and a time",
      entry.get("reason") == "ราคาผิด <ทดสอบ>" and "Somchai" in entry.get("actor", "")
      and entry.get("actor", "").split(" (")[0] not in ("", "Somchai") and entry.get("time"), entry)
s, r = call("DELETE", f"/api/quotations/{enc(roll_ref)}", {"reason": "again"})
check("deleting it twice says not found", s == 404, (s, r))
s, r = call("POST", f"/api/quotations/{enc(roll_ref)}/restore")
check("restore", s == 200 and r.get("restored") == roll_ref, (s, r))
s, after = call("GET", f"/api/quotations/{enc(roll_ref)}")
check("restored exactly: same id, same figures, same MOQ", s == 200 and after == before,
      {k: (before.get(k), after.get(k)) for k in before if before.get(k) != after.get(k)})
check("back in history", (history_row(roll_ref) or {}).get("roll_sale_price") == "3,000.00")
s, t = call("GET", "/api/history/trash")
check("no longer listed in the trash", all(e["ref"] != roll_ref for e in t.get("rows", [])), t)
s, r = call("POST", f"/api/quotations/{enc(roll_ref)}/restore")
check("restoring what is not in the trash says so", s == 404, (s, r))
s, r = call("POST", "/api/quotations/NO-SUCH-REF/restore")
check("restore of an unknown reference: 404", s == 404, (s, r))

# Clean up through the trash itself, so a re-run starts from the same place.
for ref in [moq_ref, roll_ref]:
    call("DELETE", f"/api/quotations/{enc(ref)}", {"reason": "test clean-up"})

print("\nHONG - %d buoc sai: %s" % (len(bad), bad) if bad else "\nKHOP - MOQ, ban theo cuon va thung rac chay tren may chu that")
sys.exit(1 if bad else 0)

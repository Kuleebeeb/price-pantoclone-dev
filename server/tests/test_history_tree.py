# -*- coding: utf-8 -*-
"""INTEGRATION: the folder tree folds the book the way the request drew it.

Customer > product (same name + same size = ONE folder) > every quote of that
product, newest first. Seeds five rows for two customers into a throwaway
Postgres, then reads the three levels back through real HTTP:

  - the same bag quoted three times over three years is ONE product folder
    holding three quotes, with the latest price and the price span
  - a different size of the same bag is a different folder
  - a filter above the tree reaches every level
  - the leaf rows are the fifteen desktop columns, so the timeline reads like
    the flat table does

Needs DATABASE_URL -> throwaway DB and the API on BASE (default :8145).
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "core"))
sys.path.insert(0, str(HERE / "api"))

if not os.environ.get("DATABASE_URL") or "smoke" not in os.environ["DATABASE_URL"]:
    print("HONG: DATABASE_URL phai tro vao Postgres TAM (co chu 'smoke').")
    sys.exit(1)

import db  # noqa: E402
import store  # noqa: E402
from calculator import PRODUCTS  # noqa: E402

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
        print("  BAD " + name + "  " + str(detail))


CUST_A = "ZZ-TREE ALPHA CO., LTD."
CUST_B = "ZZ-TREE BETA LTD."


def cleanup():
    with store.pool().connection() as conn:
        conn.execute("DELETE FROM quotations WHERE customer LIKE 'ZZ-TREE %%'")


def book_row(ref, date, customer, desc, name, size, price, basis="kg"):
    return {
        "quote_ref": ref, "quote_date": date, "customer": customer, "item_description": desc,
        "product_key": "flat", "product_label": PRODUCTS["flat"], "size_text": size,
        "unit_price": price, "inputs": {"product_name": name, "sale_basis": basis},
        "import_source": "ZZ-TREE.xlsx • test",
    }


cleanup()
S1 = "กว้าง/Width 8 นิ้ว × ยาว/Length 12 นิ้ว"
S2 = "กว้าง/Width 10 นิ้ว × ยาว/Length 14 นิ้ว"
store.import_quotations([
    book_row("ZZT/64-01", "2021-03-01", CUST_A, "PLASTIC BAG PE. 8'' x 12''", "PLASTIC BAG PE", S1, 65.0),
    book_row("ZZT/66-01", "2023-03-01", CUST_A, "PLASTIC BAG PE. 8'' x 12'' (MOQ)", "PLASTIC BAG PE", S1, 71.0),
    book_row("ZZT/69-01", "2026-03-01", CUST_A, "PLASTIC BAG PE 8 x 12", "PLASTIC BAG PE", S1, 78.0),
    book_row("ZZT/69-02", "2026-04-01", CUST_A, "PLASTIC BAG PE 10 x 14", "PLASTIC BAG PE", S2, 80.0),
    book_row("ZZT/69-03", "2026-05-01", CUST_B, "ZIPPER BAG", "ZIPPER BAG", S1, 1.2, basis="piece"),
])

s, r = call("POST", "/api/auth/login", {"email": EMAIL, "password": PASSWORD})
check("login", s == 200 and "token" in r, str(r)[:120])
token = r.get("token")

q = urllib.parse.quote
s, r = call("GET", "/api/history/tree/customers?customer=" + q("ZZ-TREE"))
check("level 1: two customer folders", s == 200 and [g["customer"] for g in r["groups"]] == [CUST_B, CUST_A], str(r)[:200])
alpha = next(g for g in r["groups"] if g["customer"] == CUST_A)
check("level 1: folder counts products (2) and quotes (4)", alpha["products"] == 2 and alpha["quotes"] == 4, alpha)
check("level 1: period spans first to last", alpha["period"] == "2021-03-01 → 2026-03-01" or alpha["period"] == "2021-03-01 → 2026-04-01", alpha["period"])
check("level 1: count text names customers and records", "2 ลูกค้า" in r["count_text"] and "5 รายการ" in r["count_text"], r["count_text"])

s, r = call("GET", "/api/history/tree/products?exact_customer=" + q(CUST_A))
check("level 2: same name + size folded into ONE folder", s == 200 and len(r["groups"]) == 2, str(r)[:300])
g1 = next(g for g in r["groups"] if g["size"] == S1)
check("level 2: folder holds three quotes", g1["quotes"] == 3, g1)
check("level 2: latest price is the newest quote", g1["latest_price"] == "78.000", g1["latest_price"])
check("level 2: price span oldest to newest", g1["price_range"] == "65.000 – 78.000", g1["price_range"])
check("level 2: unit label from the server", g1["sale_unit"].startswith("ขายเป็นกิโลกรัม"), g1["sale_unit"])
check("level 2: newest folder first", r["groups"][0]["size"] == S2, r["groups"][0])

s, r = call("GET", f"/api/history/tree/rows?exact_customer={q(CUST_A)}&product_name={q('PLASTIC BAG PE')}&size_text={q(S1)}")
check("level 3: three timeline rows, newest first", s == 200 and [x["ref"] for x in r["rows"]] == ["ZZT/69-01", "ZZT/66-01", "ZZT/64-01"], str(r)[:200])
check("level 3: fifteen desktop cells per row", len([k for k in r["rows"][0] if not k.startswith("_")]) >= 15, list(r["rows"][0]))
check("level 3: price cell carries the figure", r["rows"][0]["price_kg"] == "78.000", r["rows"][0].get("price_kg"))

s, r = call("GET", "/api/history/tree/customers?customer=" + q("ZZ-TREE") + "&date_from=2026-01-01")
alpha = next(g for g in r["groups"] if g["customer"] == CUST_A)
check("filter reaches the folders: 2026 only -> 2 quotes", alpha["quotes"] == 2, alpha)
s, r = call("GET", "/api/history/tree/products?exact_customer=" + q(CUST_A) + "&date_from=2026-01-01")
g1 = next(g for g in r["groups"] if g["size"] == S1)
check("filter reaches the products: folder shrinks to 1 quote", g1["quotes"] == 1 and g1["price_range"] == "78.000", g1)

cleanup()
check("cleanup", db.get_quotation("ZZT/64-01") is None)
if hasattr(db, "close_pool"):
    db.close_pool()

print()
if failures:
    print(f"KHONG KHOP - {len(failures)} sai: {failures}")
    sys.exit(1)
print("KHOP - cay thu muc gap dung so, dung gia, dung thu tu")

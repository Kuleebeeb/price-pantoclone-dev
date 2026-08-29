# -*- coding: utf-8 -*-
"""INTEGRATION: the enrichment loader writes exactly where it may, nowhere else.

Four promises, each one a way the loader could quietly do harm:
  1. a book row (import_source <> '') gets its specs filled in
  2. a row somebody SAVED (import_source = '') is never rewritten - law P5
  3. a new item is inserted once; a second run adds nothing
  4. the price is left alone unless --prices is asked for

Needs DATABASE_URL pointing at a THROWAWAY Postgres whose schema the API has
already created (start the API against it once).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
for sub in ("core", "api", "deploy"):
    sys.path.insert(0, str(HERE / sub))

if not os.environ.get("DATABASE_URL") or "smoke" not in os.environ["DATABASE_URL"]:
    print("HONG: DATABASE_URL phai tro vao Postgres TAM (co chu 'smoke').")
    sys.exit(1)

import db  # noqa: E402
import store  # noqa: E402
import enrich_history  # noqa: E402
from calculator import PRODUCTS  # noqa: E402

failures: list[str] = []


def check(name, cond, detail=""):
    if cond:
        print("  ok  " + name)
    else:
        failures.append(name)
        print("  BAD " + name + "  " + str(detail))


BOOK_REF = "ZZENR/01-01 · TestBook"
WEB_REF = "QT-ZZENR-0001"
NEW_REF = "ZZENR/02-01 · TestBook"
CUST = "ZZ-ENRICH CO., LTD."


def cleanup():
    with store.pool().connection() as conn:
        conn.execute("DELETE FROM quotations WHERE customer = %s", (CUST,))


cleanup()
baseline = store.quotation_count()
store.import_quotations([
    {"quote_ref": BOOK_REF, "quote_date": "2024-03-23", "customer": CUST,
     "item_description": "ZIPPER BAG 8'' x 12'' x 80 MIC./S", "product_key": "flat",
     "product_label": PRODUCTS["flat"], "unit_price": 1.2, "import_source": "TestBook.xlsx • 67-01"},
    {"quote_ref": WEB_REF, "quote_date": "2024-03-24", "customer": CUST,
     "item_description": "saved by a person", "product_key": "flat",
     "product_label": PRODUCTS["flat"], "unit_price": 9.9, "grams_per_item": 5.0,
     "inputs": {"width": {"value": 1, "unit": "ซม."}}, "import_source": ""},
])

inputs = {"product_key": "flat", "width": {"value": 8, "unit": "นิ้ว"},
          "length": {"value": 12, "unit": "นิ้ว"},
          "thickness": {"value": 80, "unit": "ไมครอน", "mode": "side"},
          "sale_basis": "piece", "product_name": "ZIPPER BAG", "resin": ""}
lines = [
    {"action": "update", "quote_ref": BOOK_REF, "import_source": "TestBook.xlsx • 67-01",
     "product_key": "flat", "size_text": "กว้าง/Width 8 นิ้ว × ยาว/Length 12 นิ้ว",
     "inputs": inputs, "results": {"grams_per_item": 4.558}, "grams_per_item": 4.558,
     "product_reference": "ZZ-PART-1", "unit_price": 1.3, "price_differs": True},
    {"action": "update", "quote_ref": WEB_REF, "import_source": "",
     "product_key": "roll", "inputs": {"hacked": True}, "grams_per_item": 1,
     "product_reference": "NOPE", "unit_price": 0.01, "price_differs": True},
    {"action": "insert", "quote_ref": NEW_REF, "quote_date": "2024-04-01", "customer": CUST,
     "customer_code": "", "item_description": "PLASTIC BAG PE 30 x 40 CM.", "product_key": "flat",
     "product_label": PRODUCTS["flat"], "import_source": "TestBook.xlsx • 67-02",
     "inputs": {"product_key": "flat"}, "results": {}, "grams_per_item": 0,
     "product_reference": "", "unit_price": 65.0},
]
jl = Path(os.environ.get("TEMP", "/tmp")) / "zz-enrich.jsonl"
jl.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in lines) + "\n", encoding="utf-8")

before = store.quotation_count()
enrich_history.main(jl, rewrite_prices=False)
after = store.quotation_count()

book = db.get_quotation(BOOK_REF)
check("1. book row: part code filled", book["product_reference"] == "ZZ-PART-1", book["product_reference"])
check("1. book row: grams written", abs(float(book["grams_per_item"]) - 4.558) < 1e-6, book["grams_per_item"])
check("1. book row: inputs carry name + status", book["inputs_json"].get("product_name") == "ZIPPER BAG",
      book["inputs_json"])
check("1. book row: size text in desktop words", book["size_text"].startswith("กว้าง/Width 8 นิ้ว"), book["size_text"])
check("4. price NOT rewritten without --prices", abs(float(book["unit_price"]) - 1.2) < 1e-6, book["unit_price"])

web = db.get_quotation(WEB_REF)
check("2. saved row untouched: key", web["product_key"] == "flat", web["product_key"])
check("2. saved row untouched: inputs", web["inputs_json"] == {"width": {"value": 1, "unit": "ซม."}}, web["inputs_json"])
check("2. saved row untouched: price", abs(float(web["unit_price"]) - 9.9) < 1e-6, web["unit_price"])

check("3. new item inserted once", after == before + 1 and db.get_quotation(NEW_REF) is not None, (before, after))

enrich_history.main(jl, rewrite_prices=True)
again = store.quotation_count()
check("3. second run adds nothing", again == after, (after, again))
check("4. --prices rewrites the book row's price", abs(float(db.get_quotation(BOOK_REF)["unit_price"]) - 1.3) < 1e-6)
check("2. --prices still never touches the saved row",
      abs(float(db.get_quotation(WEB_REF)["unit_price"]) - 9.9) < 1e-6)

cleanup()
check("cleanup: nothing of ours left", store.quotation_count() == baseline and db.get_quotation(BOOK_REF) is None,
      (baseline, store.quotation_count()))
if hasattr(db, "close_pool"):
    db.close_pool()

print()
if failures:
    print(f"KHONG KHOP - {len(failures)} sai: {failures}")
    sys.exit(1)
print("KHOP - bo lam giau chi ghi dung cho duoc phep, va chi mot lan")

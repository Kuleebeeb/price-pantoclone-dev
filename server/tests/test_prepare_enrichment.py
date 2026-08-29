# -*- coding: utf-8 -*-
"""The join step's two pure decisions: how a new row gets numbered so the
book stays ONE scheme, and when a size text may be written at all."""
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "deploy"))

from prepare_enrichment import aligned, book_and_sheet, derive_ref, size_text_for  # noqa: E402

ok = bad = 0


def check(name, cond, detail=""):
    global ok, bad
    if cond:
        ok += 1
        print("  ok " + name)
    else:
        bad += 1
        print("  BAD " + name + "  " + str(detail))


b, s = book_and_sheet("Z:/H/HONDA LOCK CO\Honda Lock.xlsx#64-01")
check("workbook name survives backslashes", b == "Honda Lock.xlsx" and s == "64-01", (b, s))

check("printed REF cell wins, revision text kept",
      derive_ref({"ref_text": "2564/10 REV.1", "candidate_ref": "2564/10"}, "64-10 REV.1") == "2564/10 REV.1")
check("no REF cell: derived from a numbered sheet name",
      derive_ref({"ref_text": "", "candidate_ref": "63-09"}, "63-09") == "2563/09")
check("no REF and unnumbered sheet: nothing invented",
      derive_ref({"ref_text": "", "candidate_ref": "Sheet1"}, "Sheet1") == "Sheet1")

flat = {"product_key": "flat", "inputs": {"product_key": "flat",
        "width": {"value": 8, "unit": "นิ้ว"}, "length": {"value": 12, "unit": "นิ้ว"}}}
check("flat size text in the desktop's words",
      size_text_for(flat) == "กว้าง/Width 8 นิ้ว × ยาว/Length 12 นิ้ว", size_text_for(flat))

no_unit = {"product_key": "flat", "inputs": {"product_key": "flat",
           "width": {"value": 70, "unit": None}, "length": {"value": 105, "unit": None}}}
check("unit unknown -> no size text rather than a wrong one", size_text_for(no_unit) == "", size_text_for(no_unit))

roll = {"product_key": "roll", "inputs": {"product_key": "roll",
        "width": {"value": 30, "unit": "ซม."}, "length": {"value": 1000, "unit": "เมตร"}}}
check("roll uses its length as roll length",
      size_text_for(roll) == "กว้าง/Width 30 ซม. × ความยาวโรล/Roll Length 1000 เมตร", size_text_for(roll))

check("review row without product key -> no size text",
      size_text_for({"product_key": None, "inputs": {"width": {"value": 1, "unit": "ซม."}}}) == "")

check("same price = aligned", aligned({"unit_price": 1.2}, {"unit_price": "1.200000"}))
check("old CURRENT price explains it = aligned", aligned({"unit_price": 1.3, "previous_price": 1.2}, {"unit_price": "1.2"}))
check("neither price fits = NOT aligned, row held back",
      not aligned({"unit_price": 55.04, "previous_price": 40.4}, {"unit_price": "0.98"}))
check("no price on our side = positional match kept", aligned({"unit_price": None}, {"unit_price": "5"}))

print()
if bad:
    print(f"KHONG KHOP - {bad} sai / {ok} dung")
    sys.exit(1)
print(f"KHOP - {ok} truong hop dung")

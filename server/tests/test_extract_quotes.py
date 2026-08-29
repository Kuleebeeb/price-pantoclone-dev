# -*- coding: utf-8 -*-
"""Regression tests for the quotation-book extractor's parsing brains.

Every case here is a REAL description string met in Z:\\Quotation-... - when a
future tweak breaks one of these, it breaks a shape the books actually contain.
No DB, no network: pure functions only.
"""
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "deploy"))

from extract_quotes import (  # noqa: E402
    Item, classify_product, detect_resin, extract_part_code, extract_product_name,
    normalize_thickness, parse_dimensions,
)

ok = 0
bad = 0


def check(name, cond, detail=""):
    global ok, bad
    if cond:
        ok += 1
        print("  ok " + name)
    else:
        bad += 1
        print("  BAD " + name + "  " + str(detail))


def build(desc, unit="PC.", price=1.0):
    item = Item(description=desc, unit=unit, price=price)
    classify_product(item)
    detect_resin(item)
    extract_product_name(item)
    extract_part_code(item)
    parse_dimensions(item)
    return item


# --- resin detection -------------------------------------------------------
i = build("ZIPPER BAG 8'' x 12'' x 80 MIC./S")
check("zipper: no resin word -> resin empty", i.resin == "", i.resin)
check("zipper: product flat", i.product_key == "flat", i.product_key)
check("zipper: name kept", i.product_name == "ZIPPER BAG", repr(i.product_name))

i = build("Plastic Bag LDPE. 15\" x 20\" x 0.05 MM.")
check("LDPE named", i.resin == "LDPE", i.resin)
check("LDPE density 0.92", i.density == 0.92, i.density)

i = build("PLASTIC HDPE SHEET ROLL 30 CM. x 1,000 M. x 0.04 MM.")
check("HDPE named", i.resin == "HDPE", i.resin)
check("HDPE density 0.95", i.density == 0.95, i.density)
check("sheet roll -> roll", i.product_key == "roll", i.product_key)

i = build("HD ROLL 24\" x 0.03 MM.")
check("bare HD -> HDPE", i.resin == "HDPE", i.resin)
check("width-x-thickness: no length invented", i.length is None, i.length)
check("width-x-thickness: thickness 0.03 mm", i.thickness == 0.03 and i.thickness_unit == "มม.",
      (i.thickness, i.thickness_unit))

i = build("POLY BAG PP. 3'' x 5''", unit="KG.", price=72.0)
check("PP beats PE in POLY BAG PP", i.resin == "PP", i.resin)
check("PP density 0.905", i.density == 0.905, i.density)

i = build("ถุงพีอีติดกาว W: 230 mm. x L: 190 mm. + ฝา 40 mm. x 0.04 mm./S")
check("Thai พีอี -> PE", i.resin == "PE", i.resin)
check("Thai name kept", i.product_name == "ถุงพีอีติดกาว", repr(i.product_name))
check("labeled W/L parsed", i.width == 230.0 and i.length == 190.0, (i.width, i.length))

i = build("PS304 L750xW750xT0.08")
check("PS304 is NOT polystyrene", i.resin == "", i.resin)
check("compact LxWxT parsed mm", i.width == 750.0 and i.width_unit == "มม.", (i.width, i.width_unit))
check("part number becomes the name", i.product_name == "PS304", repr(i.product_name))

i = build("เอกสาร PIR ถุง LDPE 50 CM. x 58 CM.")
check("recycled tag appended", i.resin == "LDPE (PIR)", i.resin)

# --- product name ----------------------------------------------------------
i = build("PLASTIC TUBE LDPE YELLOW (OPEN 2 SIDES) 9 x 16 CM.x 0.04 MM.", unit="KG.", price=95.0)
check("tube name keeps parenthetical", i.product_name == "PLASTIC TUBE LDPE YELLOW (OPEN 2 SIDES)",
      repr(i.product_name))
check("tube -> flat geometry", i.product_key == "flat", i.product_key)

i = build("Ploy Bag (Size : 50 x 90 x 0.06 mm.)")
check("name cut at Size label", i.product_name == "Ploy Bag", repr(i.product_name))

i = build("PLASTIC BAG 6'' x 9'' x 0.05 MM. (MINIMUM ORDER 5,000 PCS.)")
check("MOQ noise not in name", i.product_name == "PLASTIC BAG", repr(i.product_name))

# --- gusset + thickness sanity --------------------------------------------
i = build("LDPE Gusset Bag 65 CM.+(23 CM.) x 95 CM. x 0.04 MM./Side")
check("gusset product", i.product_key == "gusset", i.product_key)
check("gusset size caught", i.gusset == 23.0, i.gusset)
check("side hint caught", i.thickness_mode_hint == "side", i.thickness_mode_hint)

r = normalize_thickness(80.0, "MIC", [])
check("80 MIC stays micron", r == (80.0, "ไมครอน"), r)
reasons = []
r = normalize_thickness(50.0, "MM", reasons)
check("50 'mm' corrected to micron", r == (50.0, "ไมครอน") and reasons, (r, reasons))
r = normalize_thickness(0.05, "", [])
check("bare 0.05 read as mm", r == (0.05, "มม."), r)
r = normalize_thickness(3.0, "", [])
check("ambiguous 3.0 refused", r is None, r)

i = build("ถุงพลาสติก ชนิดไฮเดน 30 CM. x 40 CM.")
check("Thai ไฮเดน -> HDPE", i.resin == "HDPE", i.resin)

i = build("PLASTIC BAG LDPE SIZE 50 x 90 CM. x 0.05 MM.")
check("bare SIZE label not in name", i.product_name == "PLASTIC BAG LDPE", repr(i.product_name))

# --- audit round: the 8-folder adversarial audit found these ---------------
i = build("SSA153D001A PLASTIC SHEET PE 1140 x 1140 mm. x 0.03/S")
check("1140 not truncated to 114", i.width == 1140.0 and i.length == 1140.0, (i.width, i.length))
check("lowercase mm recognized", i.width_unit == "มม." and i.length_unit == "มม.", (i.width_unit, i.length_unit))
check("trailing /S thickness caught", i.thickness == 0.03, i.thickness)
check("/S means per side", i.thickness_mode_hint == "side", i.thickness_mode_hint)

i = build("PLASTIC SHEET PE 500 x 800 MM. x 0.05 MM.")
check("shared trailing unit propagated", i.width_unit == "มม.", i.width_unit)

i = build("ถุงไฮเดน 40 x 40 CM. x 0.035 MM./ด้าน", unit="KG.", price=60.0)
check("Thai /dan means per side", i.thickness_mode_hint == "side", i.thickness_mode_hint)

i = build("ถุงพลาสติก LDPE 30 x 40.1/2 นิ้ว หนา 0.28/ 2 ด้าน")
check("Thai half fraction 40.5", i.length == 40.5, i.length)
check("thickness from Thai label", i.thickness == 0.28, i.thickness)
check("/2 dan means the pair", i.thickness_mode_hint == "pair", i.thickness_mode_hint)

i = build('POLY BAG PE 15"3/4 x 20" x 0.05 MM.')
check("inch fraction 15.75", i.width == 15.75 and i.width_unit == "นิ้ว", (i.width, i.width_unit))

i = build("FS0235 PLASTIC BAG 30 x 45 CM. (40 MC./SIDE)")
check("paren thickness 40 micron", i.thickness == 40.0 and i.thickness_unit == "ไมครอน",
      (i.thickness, i.thickness_unit))

i = build("ถุง LDPE PIR35% 30 x 40 CM.")
check("PIR35% still tagged", i.resin == "LDPE (PIR)", i.resin)

i = build("AIR BUBBLE BAG 20 x 30 CM.")
check("air bubble refused, review", i.status == "review", i.status)

i = build("EPE FOAM SHEET LAMINATE 32.5 x 64 CM x T 1MM.")
check("EPE wins over SHEET", i.status == "review" and "EPE" in i.reasons[0], (i.status, i.reasons))
check("EPE dims still parsed for reviewer", i.width == 32.5, i.width)

i = build("PLASTIC BAG 65 CM.+(23 CM.) x 95 CM. x 0.04 MM./Side")
check("W+(G) x L flips flat to gusset", i.product_key == "gusset", i.product_key)

i = build("PLASTIC BAG 20 cm x 55 cm + 2.5 cm")
check("trailing +flap does NOT flip to gusset", i.product_key == "flat" and i.gusset is None,
      (i.product_key, i.gusset))
check("lowercase cm pair parsed", i.width == 20.0 and i.width_unit == "ซม.", (i.width, i.width_unit))

i = build("PLASTIC BAG PE 30 x 40 CM. x 0.03-0.04 MM.")
check("thickness range noted", i.thickness == 0.03 and any("range" in r for r in i.reasons),
      (i.thickness, i.reasons))

i = build("ACCESSORIES BAG L: 550 x W: 520 x T: 0.06 MM.")
check("L-first labels land correctly", i.length == 550.0 and i.width == 520.0, (i.length, i.width))

# --- customer part codes ----------------------------------------------------
i = build("2P738030-1-TB ACCESSORIES BAG (300 x 950 x T: 0.5)")
check("part code with dashes", i.part_code == "2P738030-1-TB", i.part_code)
check("code removed from name", i.product_name == "ACCESSORIES BAG", repr(i.product_name))

i = build("POLYETHYLENE ACCESSORY BAG RI40021-8L")
check("part code at the end", i.part_code == "RI40021-8L", i.part_code)
check("name survives code removal", i.product_name == "POLYETHYLENE ACCESSORY BAG", repr(i.product_name))

i = build("PS304 L750xW750xT0.08")
check("bare code kept as both code and name", i.part_code == "PS304" and i.product_name == "PS304",
      (i.part_code, i.product_name))

i = build("699-01-00-010 พลาสติกย่น ขนาด 54'' x 60 เมตร")
check("digit-block code caught", i.part_code == "699-01-00-010", i.part_code)

i = build("SSA153D001A PLASTIC SHEET PE 1140 x 1140 mm. x 0.03/S")
check("letters-digits code caught", i.part_code == "SSA153D001A", i.part_code)

i = build("ZIPPER BAG 8'' x 12'' x 80 MIC./S")
check("no code invented from dimensions", i.part_code == "", i.part_code)

i = build("PLASTIC BAG PE. 530 x 600 MM. x T 0.05 MM.", unit="KG.", price=78.0)
check("no code in plain size rows", i.part_code == "", i.part_code)

# --- whole-sheet reading and header residue --------------------------------
import openpyxl
from extract_quotes import read_sheet

def sheet_with(rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    return ws

long_rows = [[None] * 9 for _ in range(7)]
long_rows.append(["TO :", "BIG CUSTOMER", None, None, None, None, "REF NO :", "2565/01", None])
long_rows.append(["ATTEN :", "K.Somchai", None, None, None, None, "DATE :", "12/01/2565", None])
long_rows += [[None] * 9 for _ in range(4)]
long_rows.append(["ITEM", "DESCRIPTION", None, None, "QUANTITY", "UNIT", "CURRENT PRICE", None, "NEW PRICE"])
long_rows.append([None, None, None, None, None, None, "(THB)", None, "(THB)"])
for i in range(1, 121):
    long_rows.append([i, None, f"PB{i:03d} L{100+i}xW{50+i}xT0.04", None, 1, "PC.", 0.5, None, 0.6])
long_rows.append([None, "หมายเหตุ :", None, "1. note", None, None, None, None, None])

sh = read_sheet(sheet_with(long_rows), Path("x/honda.xlsx"), "65-01")
check("all 120 items read, not 29", len(sh.items) == 120, len(sh.items))
check("(THB) residue is not an item", sh.items[0].description.startswith("PB001"), sh.items[0].description)
check("item 10 is really item 10", sh.items[9].description.startswith("PB010"), sh.items[9].description)
check("NEW PRICE taken, CURRENT kept as previous", sh.items[0].price == 0.6 and sh.items[0].previous_price == 0.5,
      (sh.items[0].price, sh.items[0].previous_price))
check("ref and date read from header", sh.ref == "2565/01" and sh.date_iso == "2022-01-12", (sh.ref, sh.date_iso))

rev_rows = [[None] * 9 for _ in range(7)]
rev_rows.append(["TO :", "HONDA LOGISTICS", None, None, None, None, "REF NO :", "2564/10 REV.1", None])
rev_rows.append(["ATTEN :", "K.A", None, None, None, None, "DATE :", "1/10/2564", None])
rev_rows += [[None] * 9 for _ in range(4)]
rev_rows.append(["ITEM", "DESCRIPTION", None, None, "QUANTITY", "UNIT", "PRICE (BAHT)", None, None])
rev_rows.append([1, None, "PLASTIC BAG PE 8'' x 12''", None, 1, "KG.", 65, None, None])
sh = read_sheet(sheet_with(rev_rows), Path("x/honda logistics.xlsx"), "64-10 REV.1")
check("ref number isolated", sh.ref == "2564/10", sh.ref)
check("whole REF cell kept for numbering", sh.ref_text == "2564/10 REV.1", sh.ref_text)

i = build("PLASTIC BAG 105CM x 1100W x 0.05 MM.")
check("number+unit tokens are not codes", i.part_code == "", i.part_code)
i = build("03TENMA PLASTIC BAG 30 x 40 CM.")
check("digits+long letters is still a code", i.part_code == "03TENMA", i.part_code)

import datetime as _dt
dt_rows = [[None] * 9 for _ in range(5)]
dt_rows.append([None, None, None, None, "DATE : ", _dt.datetime(2021, 12, 18, 0, 0), None, None, None])
dt_rows.append(["TO :", "HONDA LOCK", None, None, None, None, "REF NO :", "2564/01", None])
dt_rows += [[None] * 9 for _ in range(6)]
dt_rows.append(["ITEM", "DESCRIPTION", None, None, "QUANTITY", "UNIT", "PRICE (BAHT)", None, None])
dt_rows.append([1, None, "PLASTIC BAG PE. 17'' x 28''", None, 1, "KG.", 65, None, None])
sh = read_sheet(sheet_with(dt_rows), Path("x/honda lock.xlsx"), "64-01")
check("Excel-typed date cell is read", sh.date_iso == "2021-12-18", sh.date_iso)

# --- trading stays out of the calculator -----------------------------------
i = build("PLASTIC PALLET 100 x 120 CM.")
check("pallet -> trading, no calc", i.status == "trading", i.status)

print()
if bad:
    print(f"KHONG KHOP - {bad} truong hop sai / {ok} dung")
    sys.exit(1)
print(f"KHOP - {ok} truong hop dung")

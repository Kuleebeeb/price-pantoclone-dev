# -*- coding: utf-8 -*-
"""The business logic behind each UX action, checked against literal strings.

Every sentence the screen prints is composed on the server (api/main.py), so a
"pretty but hollow" frontend is impossible to hide from these checks: if a
button's behaviour were only painted on, the endpoint behind it would answer
wrongly here, in Thai, character for character.

Same house style as test_parity.py: a plain script, no framework, run with
    .venv/Scripts/python.exe tests/test_screen_logic.py
The database is STUBBED (every db call the endpoints make is replaced with a
plain function) - this file checks arithmetic and wording, never storage.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "core"))
sys.path.insert(0, str(HERE / "api"))

from fastapi import HTTPException  # noqa: E402

import main  # noqa: E402
from main import (  # noqa: E402
    CalcRequest,
    Measure,
    PlanningCompareRequest,
    PrintRequest,
    Thickness,
    WorkOrderRequest,
    as_float_thai,
    build_print_html,
    run_calculation,
)

failures: list[str] = []


def check(name: str, got, want) -> None:
    if got == want:
        print("  ok  " + name)
    else:
        failures.append(name)
        print("  BAD " + name)
        print("       muon: " + repr(want))
        print("       nhan: " + repr(got))


def check_in(name: str, needle, hay) -> None:
    if needle in hay:
        print("  ok  " + name)
    else:
        failures.append(name)
        print("  BAD " + name)
        print("       khong thay: " + repr(needle))


def refusal(name: str, fn, want: str) -> None:
    try:
        fn()
    except (ValueError, HTTPException) as exc:
        got = exc.detail if isinstance(exc, HTTPException) else str(exc)
        check(name, got, want)
        return
    failures.append(name)
    print("  BAD " + name + "  (khong tu choi gi ca)")


# --------------------------------------------------------------- as_float_thai
print("as_float_thai - bon loi tu choi cua desktop, nguyen van")
check("blank is nought", as_float_thai("", "X"), 0.0)
check("thousands comma read", as_float_thai("1,000", "X"), 1000.0)
refusal("text refused by name", lambda: as_float_thai("abc", "จำนวนใบ"), "จำนวนใบต้องเป็นตัวเลข")
refusal("negative refused", lambda: as_float_thai("-1", "ความกว้าง"), "ความกว้างต้องไม่ติดลบ")
refusal(
    "zero refused when it must be positive",
    lambda: as_float_thai("0", "ความยาว", allow_zero=False),
    "ความยาวต้องมากกว่า 0",
)

# ------------------------------------------------- the calculate button, by kg
print("Calculate, selling by kg - the bag on every screenshot: 45 x 60 x 0.08")


def flat_bag(**over) -> CalcRequest:
    base = dict(
        product_key="flat",
        width=Measure(value=45, unit="ซม."),
        length=Measure(value=60, unit="ซม."),
        thickness=Thickness(value=0.08, unit="มม.", mode="pair"),
        bottom_allowance=Measure(value=1, unit="ซม."),
        length_reference="ปากถึงแนวซีล / Opening to Seal",
        density_g_cm3=0.92,
        material_price_per_kg=65,
        deduction_percent=10,
        apply_deduction=True,
        sale_basis="kg",
        selling_price_per_kg_override=53,
        pack_quantity=100,
        order_quantity=1000,
    )
    base.update(over)
    return CalcRequest(**base)


out = run_calculation(flat_bag())
d = out["display"]
check("grams, three decimals with the unit", d["grams"], "20.203 กรัม")
check(
    "primary line names both counts",
    d["primary_line"],
    "ขายเป็นกก. / Sell by kg • จำนวนมาตรฐาน 49.50 ชิ้น/กก. • จำนวนหลังหัก 10% = 44.55 ชิ้น/กก.",
)
check("derivation hides when selling by kg", d["derivation"], "")
check(
    "live caption follows the percentage",
    d["deduction_caption"],
    "จำนวนชิ้นต่อกก.หลังหัก 10% / Items per kg after 10% deduction",
)
check("pack under 25 kg gets the tick", d["pack_warning"], "√ น้ำหนักบรรจุไม่เกิน 25 กก. / Packaging ≤ 25 kg")
check_in("verification line shows the weight sum", "= 20.203 g", out["human_summary"])
check_in("verification uses the desktop separator", "หลังหัก 10% / adjusted = 44.55/kg", out["human_summary"])

print("Calculate, selling by piece - four lines and a derivation")
piece = run_calculation(flat_bag(sale_basis="piece"))
check("primary is four lines", piece["display"]["primary_line"].count("\n"), 3)
check_in("primary names the weight", "น้ำหนักต่อชิ้น / Weight per item: 20.203 กรัม / g", piece["display"]["primary_line"])
check_in("derivation shows the division", "53.000 บาท/กก. ÷ จำนวนหลังหัก 10% (44.55 ชิ้น/กก.)", piece["display"]["derivation"])
check_in("derivation says pack is not used", "ไม่ใช้จำนวนแพ็กในการคำนวณ / pack quantity not used", piece["display"]["derivation"])

print("The deduction switch and the 25 kg warning")
off = run_calculation(flat_bag(apply_deduction=False))
check("caption when switched off", off["display"]["deduction_caption"], "จำนวนชิ้นต่อกก. (ไม่หักเผื่อ) / Items per kg (no deduction)")
check("effect tile says OFF", off["display"]["deduction_effect"], "ปิด / OFF (ใช้จำนวนปกติ / normal)")
heavy = run_calculation(flat_bag(sack_quantity=3000))
check("sack over 25 kg gets the bang", heavy["display"]["pack_warning"], "! น้ำหนักบรรจุเกิน 25 กก. / Packaging over 25 kg")
bare = run_calculation(flat_bag(pack_quantity=0))
check("no packaging typed, no verdict", bare["display"]["pack_warning"], "ยังไม่ได้กำหนดจำนวนบรรจุ / Packaging Not Set")
half = run_calculation(flat_bag(deduction_percent=7.5))
check("caption keeps 7.5 as 7.5", half["display"]["deduction_caption"], "จำนวนชิ้นต่อกก.หลังหัก 7.5% / Items per kg after 7.5% deduction")

# ------------------------------------------------------ the history table cells
print("History cells - one row, fifteen truths")
check("no thickness reads N/A", main._thickness_cell({}), "ไม่ใช้ / N/A")
check("pair thickness cell", main._thickness_cell({"value": 0.08, "unit": "มม.", "mode": "pair"}), "0.08 มม. • ต่อคู่ / Per Pair")
check("side thickness cell", main._thickness_cell({"value": 0.05, "unit": "มม.", "mode": "side"}), "0.05 มม. • ต่อด้าน / Per Side")
check("web 'kg' wears the Thai label", main._sale_label("kg"), "ขายเป็นกิโลกรัม / Sell by kg")
check("web 'piece' wears the Thai label", main._sale_label("piece"), "ขายเป็นชิ้น / Sell by piece")
check(
    "a desktop-synced label passes through untouched",
    main._sale_label("ขายเป็นกิโลกรัม / Sell by kg"),
    "ขายเป็นกิโลกรัม / Sell by kg",
)

kg_row = {"sale_basis": "kg", "calc_price_kg": "52.47", "selling_price_per_kg": "53", "unit_price": 1.25}
check("kg row: calc, kg price, piece dash", main._calc_price_cells(kg_row), ("52.470", "53.000", "—"))
piece_row = {
    "sale_basis": "piece",
    "calc_price_kg": None,
    "calc_price_piece": "1.19",
    "production_items_per_kg": "44.55",
    "unit_price": 1.25,
}
check("piece row: piece figures, kg dash", main._calc_price_cells(piece_row), ("1.190", "—", "1.250"))
# A row read out of the old books: kg basis, a unit price, and no results
# block at all. Before 28-08-2026 this printed 0.000 in the kg column.
book_kg_row = {"sale_basis": "kg", "unit_price": 78.0, "selling_price_per_kg": None,
               "calc_price_kg": None, "calc_price_piece": None}
check("book kg row: unit price shows as price/kg", main._calc_price_cells(book_kg_row), ("—", "78.000", "—"))
check(
    "item and part join with a slash",
    main._item_cell({"item_description": "eye bag", "product_reference": "EYE-01"}),
    "eye bag / EYE-01",
)
check("a lone item stands alone", main._item_cell({"item_description": "eye bag", "product_reference": ""}), "eye bag")

# ---------------------------------------------------- planning: load + compare
print("Planning - the source picker and the weight comparison")

FAKE_QUOTE = {
    "quote_ref": "QT-20260827-0009",
    "quote_date": "2026-08-27",
    "customer": "ZZ-TEST Co., Ltd.",
    "customer_code": "ZT-9",
    "item_description": "test bag",
    "product_reference": "T-9",
    "product_label": "ถุงพลาสติกเปิดปากตรง (Plastic Bag)",
    "product_key": "flat",
    "size_text": "กว้าง/Width 45 ซม. × ยาว/Length 60 ซม.",
    "grams_per_item": 20.2032,
    "product_image_path": "",
    "revised_from_ref": "",
    "length_reference": "ปากถึงแนวซีล / Opening to Seal",
    "inputs_json": {
        "sale_basis": "kg",
        "thickness": {"value": 0.08, "unit": "มม.", "mode": "pair"},
        "bottom_allowance": {"value": 1, "unit": "ซม."},
        "deduction_percent": 10,
        "apply_deduction": True,
        "pack_quantity": 100,
        "sack_quantity": 0,
        "order_quantity": 1000,
        "price_basis": "ราคาขายที่กรอก 53.000 บาท/กก. / Entered final price per kg",
        "normalized": {"width_cm": 45.0, "length_cm": 60.0, "gusset_cm": 0.0},
    },
    "results_json": {
        "material_length_cm": 61.0,
        "items_per_kg": 49.497,
        "production_items_per_kg": 44.5473,
        "selling_price_per_kg": 53.0,
        "calculated_price_per_piece_from_kg": 1.1898,
        "unit_price": 1.1898,
        "total_price": 1189.744,
        "required_kg": 22.448,
        "pack_weight_kg": 2.0203,
        "sack_weight_kg": 0.0,
        "control_status": "ยังไม่กำหนด / Not Set",
    },
    "formulas_json": {"weight": "width_cm * material_length_cm", "price": "grams / 1000"},
}

main.db.get_quotation = lambda ref: FAKE_QUOTE if ref == "QT-20260827-0009" else None
main.db.find_quotations = lambda q, limit=12: []

src = main.api_planning_source(selected="QT-20260827-0009 | ZT-9 | ZZ-TEST Co., Ltd. | test bag")
check("picker takes the ref before the first pipe", src["quote_ref"], "QT-20260827-0009")
check("length prefills from the MATERIAL length", src["length"], "61")
check("package carries its unit", src["package"], "100 ชิ้น/แพ็ก")
check(
    "summary strings the identity with bullets",
    src["summary"],
    "QT-20260827-0009 • ZT-9 • ZZ-TEST Co., Ltd. • test bag • กว้าง/Width 45 ซม. × ยาว/Length 60 ซม.",
)
refusal(
    "an unknown line is refused with the line itself",
    lambda: main.api_planning_source(selected="no-such-thing"),
    "ไม่พบใบคำนวณราคาที่ตรงกับ / No saved pricing record matches:\nno-such-thing",
)

same = main.api_planning_compare(
    PlanningCompareRequest(quote_ref="QT-20260827-0009", quantity="1000", width="45", length="61", thickness="0.08", gusset="0")
)
check_in("same sizes differ by +0.000", "ต่าง +0.000 กก.", same["line"])
check_in("comparison opens with the count", "1,000 ใบ / pcs • อ้างอิง 20.203 กก. (20.203 g/ใบ)", same["line"])
refusal(
    "blank quantity refused by name",
    lambda: main.api_planning_compare(
        PlanningCompareRequest(quote_ref="QT-20260827-0009", quantity="", width="45", length="61", thickness="0.08", gusset="")
    ),
    "จำนวนใบต้องมากกว่า 0",
)
NO_DIMS = dict(FAKE_QUOTE, inputs_json=dict(FAKE_QUOTE["inputs_json"], normalized={}), results_json={})
main.db.get_quotation = lambda ref: NO_DIMS if ref == "bare" else FAKE_QUOTE
refusal(
    "a record without reference dimensions cannot compare",
    lambda: main.api_planning_compare(
        PlanningCompareRequest(quote_ref="bare", quantity="10", width="45", length="61", thickness="0.08", gusset="0")
    ),
    "ใบราคาไม่มีข้อมูลอ้างอิงครบ / Pricing record lacks reference dimensions",
)
main.db.get_quotation = lambda ref: FAKE_QUOTE if ref == "QT-20260827-0009" else None

# ------------------------------------------------------------ details + form
print("Details window and the Edit prefill")
details = main.api_details("QT-20260827-0009")
check("details window is titled with the ref", details["title"], "รายละเอียด / Details — QT-20260827-0009")
check_in("kg branch prints the kg price line", "ราคาขายจริงต่อกิโลกรัม / Final Selling Price per kg: 53.000 บาท", details["text"])
check_in("deduction line says ON with the figure", "การหักเผื่อ / Deduction: เปิด / ON (10%)", details["text"])
check_in("pack line pairs count and weight", "แพ็ก / Pack: 100 ชิ้น / pieces • 2.0203 กก. / kg", details["text"])
check_in("sack line says Not Set", "กระสอบ / Sack: ยังไม่ได้กำหนด / Not Set", details["text"])

DESKTOP_ROW = dict(
    FAKE_QUOTE,
    inputs_json={
        # The exe's own shape: sizes nested under `dimensions`, the sale basis
        # as its Thai label. The web must read this book too.
        "dimensions": {
            "width": {"value": 45, "unit": "ซม."},
            "length": {"value": 60, "unit": "ซม."},
            "height": {"value": 0, "unit": "ซม."},
            "gusset": {"value": 0, "unit": "ซม."},
            "sold_length": {"value": 0, "unit": "เมตร"},
        },
        "bottom_allowance": {"value": 1, "unit": "ซม."},
        "thickness": {"value": 0.08, "unit": "มม.", "mode": "pair"},
        "sale_basis": "ขายเป็นกิโลกรัม / Sell by kg",
        "density_g_cm3": 0.92,
        "material_price_per_kg": 65,
        "deduction_percent": 10,
        "apply_deduction": True,
        "selling_price_per_kg_override": 53,
        "order_quantity": 1000,
    },
)
main.db.get_quotation = lambda ref: DESKTOP_ROW
form = main.api_quotation_form("QT-20260827-0009")["form"]
check("desktop-shaped width unfolds", (form["width"], form["width_unit"]), ("45", "ซม."))
check("Thai sale basis maps to kg", form["sale_basis"], "kg")
check("pair mode survives the trip", (form["thickness"], form["thickness_mode"]), ("0.08", "pair"))
check("untyped boxes come back empty, not 0", form["pack_quantity"], "")
check_in("the header says Editing with the ref", "กำลังแก้ไข / Editing: QT-20260827-0009", main.api_quotation_form("QT-20260827-0009")["ref_text"])
main.db.get_quotation = lambda ref: FAKE_QUOTE if ref == "QT-20260827-0009" else None

# --------------------------------------------------- work order + print sheet
print("Shop-floor sheet and the A4 print")
wo = main.api_work_order_html(
    WorkOrderRequest(department="blown", source="x", width="45", notes="<b>escape me</b>")
)["html"]
check_in("blown department is named in full", "แผนกเป่า / Blown-film Department", wo)
check_in("an empty box prints an em dash", "<td>—</td>", wo)
check_in("typed HTML cannot run on the sheet", "&lt;b&gt;escape me&lt;/b&gt;", wo)

sheet = build_print_html(
    PrintRequest(calc=flat_bag(), quote_date="2026-08-27", customer="ZZ-TEST", customer_code="ZT-9"),
    run_calculation(flat_bag()),
)
check_in("unsaved sheet says so in the ref row", "ยังไม่บันทึก / Unsaved", sheet)
check_in("kg sheet prints the kg price row", "ราคาขายจริงต่อกิโลกรัม / Final selling price per kg</th><td>53.000 บาท", sheet)
check_in("the sheet prints itself after 350ms", "setTimeout(function(){ window.print(); }, 350)", sheet)

piece_sheet = build_print_html(
    PrintRequest(calc=flat_bag(sale_basis="piece"), quote_date="2026-08-27", customer="Z", customer_code="1"),
    run_calculation(flat_bag(sale_basis="piece")),
)
check_in("piece sheet prints the basis row", "ราคาฐานต่อกิโลกรัม / Price basis per kg", piece_sheet)
check_in("piece sheet prints the calculated piece", "ราคาต่อชิ้นที่คำนวณได้ / Calculated price per piece", piece_sheet)

cover = CalcRequest(
    product_key="cover",
    width=Measure(value=100, unit="ซม."),
    length=Measure(value=200, unit="ซม."),
    height=Measure(value=150, unit="ซม."),
    sale_basis="kg",
)
cover_sheet = build_print_html(
    PrintRequest(calc=cover, quote_date="2026-08-27", customer="Z", customer_code="1"),
    run_calculation(cover),
)
check_in("a cover has no thickness row to lie about", "ความหนา / Thickness</th><td>ไม่ใช้ / Not applicable", cover_sheet)

print()
if failures:
    print("HONG: " + str(len(failures)) + " kiem tra do - " + ", ".join(failures))
    sys.exit(1)
print("KHOP: moi cau chu va con so cua tung thao tac deu la cua may chu, khong co gi dan cung.")

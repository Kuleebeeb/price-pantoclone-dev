"""Every word the CEO's screen prints, lifted verbatim from app.py.

WHY THIS FILE EXISTS. He asked for his own program, not a translation of it -
"CEO nói nó dễ hơn". A screen that says "Width" where his says
"ความกว้าง * / Width" is a different screen, however correct the arithmetic
behind it. So the words travel with the calculation, out of the same service,
and the React panel holds no Thai text of its own.

WHY NOT PUT THEM THROUGH PacOs's _() . Because _() TRANSLATES, and these must
not be translated. They are not this application's copy; they are the labels of
a program somebody else wrote and uses every day, bilingual on purpose - Thai
for the shop floor, English underneath for anyone who needs it. Switching PacOs
to Vietnamese must leave them exactly as they are.

WHERE THEY CAME FROM. Z:\\1\\app.py, APP_VERSION "1.7.1 (Phase 1) - Planning
screen", read on 27-08-2026 evening (the file is edited daily; before trusting
this copy, compare Z:\\1\\app.py's mtime and version string, and re-lift what
changed). The full widget-by-widget catalogue that produced this file lives in
D:\\ThaiPlasticPricing\\ui-spec\\01..05-*.md with app.py line numbers as
evidence. Anything not in app.py is not on his screen either.
"""

from __future__ import annotations

from typing import Any

# branding.py: APP_NAME / APP_SUBTITLE. The version is NOT part of the title
# (branding.py:8-11); it belongs on the sign-in screen and the Server window.
APP_TITLE = "PantongOne"
APP_SUBTITLE = "โปรแกรมคำนวณราคาพลาสติก / Plastic pricing"
# app.py:386-390 - the header's second line.
HEADER_SUBTITLE = APP_SUBTITLE + " • ระยะที่ 1 / Phase 1"
# gate.py:150 prints "v" + version.split(" ")[0]; app.py:51 holds the version.
VERSION_LABEL = "v1.7.1"

TABS = {
    "pricing": "คำนวณราคา / Pricing",
    "planning": "ข้อมูลวางแผนการผลิต / Production Planning",
    "drawing": "แบบขออนุมัติ / Drawing for Approval",
    "history": "ประวัติ / Quote History",
}

BUTTONS = {
    "new": "รายการใหม่ / New",
    "restore": "เปิดร่างล่าสุด / Restore Latest Draft",
    "calculate": "คำนวณราคา / Calculate Price",
    "save": "เก็บบันทึก / Save",
    "print": "พิมพ์สรุป / Print Summary",
    "variables": "ตัวแปรสูตร / Formula Variables",
    "sync": "ซิงค์ขึ้นเซิร์ฟเวอร์ / Sync",
    "server": "เซิร์ฟเวอร์ / Server",
    "reset_formula": "คืนค่าเริ่มต้น / Reset Formula",
    "search": "ค้นหา / Search",
    "clear_filters": "ล้างตัวกรอง (ไม่ลบรายการ) / Clear Filters (does not delete)",
    "view_companies": "ดูบริษัท / View Companies",
    "delete": "ลบ / Delete",
    "load": "เปิด / Load",
    # app.py:717-729 - the general card's own two buttons.
    "use_existing": "เลือกข้อมูลเดิม / Use Existing Record",
    "more_details": "รายละเอียดเพิ่ม / More Details",
    "hide_details": "ซ่อนรายละเอียด / Hide Details",
    "attach": "แนบไฟล์ / Attach…",
    # app.py:907-911 - opens the quality card AND jumps to the planning tab.
    "qc_toggle": "ข้อมูล QC สำหรับการผลิต / Production QC Details (คลิกเพื่อเปิด/ปิด / Show/Hide)",
}

# app.py:1421-1427. Between the steps: two spaces, », two spaces.
STEPS = "1. กรอกสเปก / Enter Specs  »  2. คำนวณ / Calculate  »  3. กรอกราคาขาย / Final Price  »  4. เก็บบันทึก / Save"

FIELDS = {
    "customer_code": "รหัสลูกค้า * / Customer Code",
    "customer": "ชื่อลูกค้า/บริษัท * / Customer/Company",
    "date": "วันที่ * / Date",
    "product_type": "ประเภทสินค้า * / Product Type",
    "item_description": "รายการสินค้าของลูกค้า / Customer Item Name",
    "product_reference": "รหัสสินค้าอ้างอิง / Customer Item Code",
    "width": "ความกว้าง * / Width",
    "length": "ความยาว * / Length",
    "gusset": "พับข้าง * / Gusset",
    "height": "ความสูง * / Height",
    "sold_length": "ความยาวม้วน * / Roll Length",
    "thickness": "ความหนา * / Thickness",
    "thickness_mode": "ต่อด้าน/ต่อคู่ / Per Side/Pair (Pair = รวมสองด้าน / combined)",
    "bottom_allowance": "ค่าบวกก้นถุง / Bottom Allowance",
    "length_reference": "จุดอ้างอิงความยาว / Length Reference",
    "sale_basis": "รูปแบบการขาย / Sale Basis",
    "density": "ความหนาแน่น / Density (g/cm³)",
    "material_price": "ราคาวัตถุดิบ / Material (บาท/kg)",
    "markup": "บวกเพิ่มอัตโนมัติ / Auto Markup (%)",
    "deduction": "ค่าหักจำนวนต่อกก. / Items-per-kg Deduction",
    "apply_deduction": "ใช้ค่าหัก / Apply",
    "order_qty": "จำนวนสั่งผลิต / Order Quantity • ค่าเริ่มต้น / Default 1,000",
    "deduction_full": "หักเผื่อผลิต / Deduction (%) • ค่าเริ่มต้น / Default 10",
    "control_min": "น้ำหนักต่ำสุด / Min Control (g)",
    "control_max": "น้ำหนักสูงสุด / Max Control (g)",
    "pack_qty": "ชิ้นต่อแพ็กเล็ก / Pieces per Small Pack (กรอกเพื่อคำนวณน้ำหนัก / Needed for Weight)",
    "sack_qty": "ชิ้นต่อกระสอบ / Pieces per Sack (กรอกเพื่อคำนวณน้ำหนัก / Needed for Weight)",
    "roof_gsm": "น้ำหนักหลังคา / Roof GSM",
    "mesh_gsm": "น้ำหนักตาข่าย / Mesh GSM",
    "roof_area": "พื้นที่หลังคา / Roof Area",
    "mesh_area": "พื้นที่ตาข่าย / Mesh Area",
    "weight_formula": "สูตรน้ำหนักต่อชิ้น / Item Weight Formula (Editable)",
    "price_formula": "สูตรราคาต่อชิ้น / Unit Price Formula (Editable)",
    "tol_width": "ค่าคลาดเคลื่อนความกว้าง / Width Tolerance ±",
    "tol_length": "ค่าคลาดเคลื่อนความยาว / Length Tolerance ±",
    "tol_thickness": "ค่าคลาดเคลื่อนความหนา / Thickness Tolerance ±",
    # The FULL general card (behind "More Details") words several of the same
    # boxes differently from the compact card - app.py:730-768.
    "customer_full": "ชื่อลูกค้า/บริษัท * / Customer/Company Name",
    "date_full": "วันที่ * / Date (YYYY-MM-DD)",
    "product_type_full": "ประเภทสินค้า / Product Type *",
    "item_full": "รายการสินค้า / Item Description",
    "part_full": "รหัสสินค้า / Part Number",
    "image": "รูปสินค้า/ไฟล์อ้างอิง / Product Image/File (Optional)",
    "percent": "%",
}

SECTIONS = {
    "quotation": "ข้อมูลเสนอราคาและสเปกหลัก / Quotation & Main Specifications",
    "general": "ข้อมูลลูกค้าและใบเสนอราคา / Customer & Quotation",
    "production": "คำนวณสำหรับสั่งผลิตและบรรจุ / Production & Packaging",
    "quality": "เงื่อนไขคุณภาพสำหรับการผลิต / Production Quality Conditions",
    "planning": "รายละเอียดสำหรับวางแผนผลิต / Production Planning Details",
    "planning_tab": "ข้อมูลผลิต / Production Data",
    "source": "ต้นทางจากใบคำนวณราคาที่บันทึกแล้ว / Source from Saved Pricing",
    "work_orders": "ใบรายการหน้างาน / Shop-floor Work Orders",
    "pricing": "คำนวณราคาลูกค้า / Customer Pricing",
    "history": "ประวัติ / Quote History",
    "deduction_box": "การหักเผื่อสำหรับจำนวนต่อกิโล / Deduction for Items per kg",
    "apply_deduction_above": "ใช้เปอร์เซ็นต์หักด้านบน / Apply deduction above",
}

# app.py:358-374 - {name}.Section.TLabel backgrounds, white bold text.
SECTION_COLORS = {
    "product": "#185a8d",
    "spec": "#0f766e",
    "quality": "#694a85",
    "calculation": "#2f6f4e",
    "pricing": "#1f6f5f",
    "production": "#9a5b13",
    "history": "#5b4b8a",
}

CHOICES = {
    "thickness_mode": [
        {"value": "side", "label": "ต่อด้าน / Per Side"},
        {"value": "pair", "label": "ต่อคู่ / Per Pair"},
    ],
    "sale_basis": [
        {"value": "kg", "label": "ขายเป็นกิโลกรัม / Sell by kg"},
        {"value": "piece", "label": "ขายเป็นชิ้น / Sell by piece"},
    ],
    # app.py:2488-2494 - the desktop's five sort orders, not a price sort.
    "sort": [
        {"value": "newest", "label": "วันที่ล่าสุด / Newest"},
        {"value": "oldest", "label": "วันที่เก่าสุด / Oldest"},
        {"value": "customer", "label": "ลูกค้า / Customer"},
        {"value": "product", "label": "ประเภทสินค้า / Product"},
        {"value": "size", "label": "ขนาด / Size"},
    ],
}

# The three coloured boxes (app.py:1509-1603). The kg box RE-WORDS ITSELF with
# the sale basis (app.py:2748-2777), and when selling by kg it is the only box
# drawn - the other two hide.
PRICE_BOXES = {
    "calculated": "ราคาต่อชิ้นที่คำนวณได้ (อ่านอย่างเดียว)\nCalculated price per piece (Read-only)",
    "final_piece": "ราคาขายต่อชิ้น (กรอก/แก้ไขได้)\nFinal selling price per piece (Editable)",
    "kg_when_selling_by_kg": "ราคาขายต่อกิโลกรัม (กรอก/แก้ไขได้)\nFinal selling price per kg (Editable)",
    "kg_when_selling_by_piece": "ราคาฐานต่อกิโลกรัม (กรอกได้)\nPrice basis per kg (Editable)",
}

# The hint beside the sale-basis box before anything is calculated
# (app.py:2774-2781). After a calculation the server sends display.primary_line.
PRIMARY_HINTS = {
    "kg": "ขายเป็นกก. / Sell by kg: จำนวนมาตรฐาน = 1,000 ÷ กรัมต่อชิ้น / Standard items/kg = 1,000 ÷ grams/item",
    "piece": "ขายเป็นชิ้น / Sell by piece: ราคาต่อชิ้น = ราคาฐาน/กก. ÷ จำนวนหลังหัก/กก. / Price per piece = price basis/kg ÷ adjusted items/kg",
}

# Notes that are ALWAYS on screen, never a tooltip. LAW P9: the people who need
# them use a touch screen in the workshop, where hovering does not exist.
NOTES = {
    "markup": "บวกเพิ่ม (%) = ((ราคาฐานต่อกก. ÷ ราคาวัตถุดิบต่อกก.) − 1) × 100 / Auto-calculated; no manual entry",
    "thickness_mode": "ค่าเริ่มต้น: ต่อคู่ (ความหนารวมสองด้าน) / Default: Per Pair (combined two-side thickness)",
    # app.py:2683-2709 - one note, three wordings, following the product.
    "allowance": (
        "ถุงพลาสติกเปิดปากตรง (Plastic Bag) / ถุงพับข้าง (Gusset Bag) • "
        "ปากถึงแนวซีล / Opening to Seal: เริ่มต้น +1 ซม. / default +1 cm • "
        "ปากถึงก้นถุง / Opening to Bottom: +0 ไม่มีค่าเผื่อแฝง / no hidden allowance"
    ),
    "allowance_roll": "ไม่มีค่าเผื่อตะเข็บเพิ่มเติม / No additional seam allowance",
    "allowance_cover": (
        "ถุงคลุมสินค้า / Product Cover only: หลังคา / Roof = (กว้าง/Width + 1 ซม.) × (ยาว/Length + 1 ซม.) • "
        "ตาข่าย / Mesh = ((กว้าง/Width + ยาว/Length) × 2 + 4 ซม.) × (สูง/Height + 1 ซม.)"
    ),
    "tolerance": "วัดความหนาต่อแผ่น / Thickness tolerance is measured per sheet (even when main thickness is per pair)",
    "deduction": "ทั้งสองหน่วยขายเปิดค่าหัก 10% เป็นค่าเริ่มต้นและแก้ไข/ปิดได้ / Both modes default to 10%; editable or switchable off",
    # app.py:589-609 - the caption over the adjusted-items tile follows the
    # percentage as it is typed; {n} is filled by the screen.
    "deduction_caption": "จำนวนชิ้นต่อกก.หลังหัก {n}% / Items per kg after {n}% deduction",
    "deduction_caption_off": "จำนวนชิ้นต่อกก. (ไม่หักเผื่อ) / Items per kg (no deduction)",
    "related_idle": "กรอกรหัสสินค้า หรือรายการพร้อมขนาด แล้วกดคำนวณเพื่อตรวจประวัติ / Enter Part No. or Item + Size, then Calculate",
    "related_none": "ยังไม่เคยเสนอราคาสินค้านี้ให้บริษัทอื่น / No other company was quoted this item",
    "verification_idle": "ลำดับตรวจสอบ / Verification: กรอกข้อมูลแล้วกดคำนวณเพื่อแสดง น้ำหนัก » จำนวน/กก. » ราคา/ชิ้น",
    "derivation_idle": "ราคาต่อใบที่คำนวณได้ / Calculated Price/Piece: —  (ราคาฐาน/กก. ÷ จำนวนหลังหัก/กก.)",
    "ready": "พร้อมคำนวณ—หากข้อมูลไม่ครบจะแจ้งตรงนี้ / Ready; missing fields will be shown here",
    "calculated_ok": "คำนวณสำเร็จ—กรอกราคาขายในช่องด้านบน หรือใช้ผลจากสูตร แล้วกดเก็บบันทึก / Calculated; enter a selling price or keep formula result, then Save",
    "check_input": "กรุณาตรวจข้อมูล / Check input: ",
    "formula_help": "ใช้ได้เฉพาะตัวแปรเหล่านี้ กับ + − × ÷ และฟังก์ชัน abs, min, max, round, ceil, floor, sqrt",
    "not_saved": "ยังไม่บันทึก / Not saved",
    # app.py:260 - the header's top-right state, before the first save.
    "unsaved": "ยังไม่บันทึก / Unsaved",
    # app.py:2962-2965 - the two-line formula summary under the action bar.
    "weight_formula_prefix": "สูตรน้ำหนัก / Weight formula: ",
    "price_formula_prefix": "สูตรคำนวณราคา / Price formula: ",
    # app.py:3307-3315 - after a save.
    "quote_ref_prefix": "เลขอ้างอิง / Quote Ref: ",
    "saved_status_prefix": "เก็บบันทึกแล้ว / Saved: ",
    "saved_title": "บันทึกแล้ว / Saved",
    "saved_body": "บันทึกใบเสนอราคาเรียบร้อย / Quotation saved",
    # app.py:3236-3244 - the three header refusals.
    "need_customer": "กรุณากรอกชื่อลูกค้า/บริษัท / Please enter customer/company name",
    "need_customer_code": "กรุณากรอกรหัสลูกค้า / Please enter customer code",
    "bad_date": "วันที่ต้องอยู่ในรูป ปปปป-ดด-วว เช่น 2026-08-27",
    # app.py:3604-3665 - the draft, word for word.
    "draft_none_title": "ไม่พบร่าง / Draft Not Found",
    "draft_none_body": "ยังไม่มีร่างล่าสุดให้เปิด / No latest draft is available.",
    "draft_confirm_title": "เปิดร่างล่าสุด / Restore Latest Draft",
    "draft_confirm_body": "ข้อมูลที่กำลังกรอกในฟอร์มนี้จะถูกแทนด้วยร่างล่าสุด\nReplace the current form with the latest draft?",
    "draft_ref": "ร่างล่าสุด—ยังไม่บันทึก / Latest Draft—Unsaved",
    "draft_restored": "เปิดร่างล่าสุดแล้ว—ตรวจข้อมูลและกดคำนวณก่อนบันทึก / Latest draft restored; review and Calculate before Save",
    # app.py:3544-3557 - printing before the form is complete.
    "print_incomplete": "พิมพ์ไม่ได้: กรุณากรอกสเปกและคำนวณให้ครบ / Print requires complete specs and a successful calculation",
    "print_draft_saved": "บันทึกร่างแล้ว แต่ยังพิมพ์ไม่ได้จนกว่าข้อมูลจะครบ / Draft saved; complete the required fields before printing",
}

# The production result tiles, in the order the desktop lays them out
# (app.py:1809-1871) - twelve of them, reflowing to the width available.
# `key` is the field of the display block the service already formats.
# The adjusted_items tile has a LIVE label: notes.deduction_caption.
RESULTS = [
    {"key": "grams", "label": "กรัมต่อชิ้น / Grams per Item"},
    {"key": "items_per_kg", "label": "จำนวนปกติต่อกก. / Normal Items per kg"},
    {"key": "deduction_effect", "label": "การหักเผื่อ / Deduction Effect"},
    {"key": "adjusted_items", "label": "จำนวนชิ้นต่อกก.หลังหัก 10% / Items per kg after 10% deduction", "live_label": "deduction_caption"},
    {"key": "small_pack_qty", "label": "ชิ้นต่อแพ็กเล็ก / Pieces per Small Pack"},
    {"key": "pack_weight", "label": "น้ำหนักแพ็กเล็ก / Small Pack Weight"},
    {"key": "sack_qty", "label": "ชิ้นต่อกระสอบ / Pieces per Sack"},
    {"key": "sack_weight", "label": "น้ำหนักกระสอบ / Sack Weight"},
    {"key": "pack_warning", "label": "คำเตือน 25 กก. / 25 kg Warning"},
    {"key": "control_range", "label": "ช่วง/สถานะควบคุม / Control Range & Status"},
    {"key": "required_kg", "label": "วัตถุดิบ / Required Material"},
    {"key": "total_price", "label": "ราคารวม / Total Price"},
]

# The planning tab's Source card and the shop-floor work orders
# (app.py:1122-1415), lifted whole on 27-08-2026 evening.
PLANNING = {
    "find": "ค้นหาใบราคา: เลขที่ REF · ชื่อลูกค้า · รหัสสินค้า / Find a pricing record: REF, customer or part number",
    "load": "รับข้อมูลใบราคา / Load Pricing Data",
    "summary_idle": "เลือกใบคำนวณราคาที่บันทึกแล้วเพื่อเริ่มวางแผน / Select a saved pricing record to begin",
    "fields": {
        "production_width": "ความกว้างสำหรับผลิต (แก้ได้) / Production Width (cm)",
        "production_length": "ความยาวสำหรับผลิต (แก้ได้) / Production Length (cm)",
        "production_thickness": "ความหนาสำหรับผลิต (แก้ได้) / Production Thickness",
        "production_gusset": "พับข้างสำหรับผลิต / Production Gusset (cm)",
        "packaging": "แพ็กเกจ / Packaging",
        "fixed_qty": "จำนวนใบคงเดิม / Fixed Quantity",
        "production_notes": "รายละเอียดการผลิต / Production Notes",
    },
    "compare": "เปรียบเทียบน้ำหนัก / Compare Weight",
    "compare_idle": "น้ำหนักอ้างอิง » น้ำหนักใหม่ / Reference » New Weight: —",
    "next_note": "ขั้นต่อไป / Next: ข้อมูลชุดนี้เตรียมไว้ต่อยอดเป็นใบสั่งงานแผนกเป่าและแผนกตัดถุง / This planning data is structured for future blown-film and bag-cutting work orders.",
    "messages": {
        "select_first": "กรุณาเลือกใบคำนวณราคาที่บันทึกแล้ว / Please select a saved pricing record",
        "not_found": "ไม่พบใบคำนวณราคาที่ตรงกับ / No saved pricing record matches:",
        "missing_source": "กรุณารับข้อมูลจากใบราคาก่อน / Load a pricing record first",
        "cannot_compare": "ใบราคาไม่มีข้อมูลอ้างอิงครบ / Pricing record lacks reference dimensions",
        "loaded": "รับข้อมูลใบราคา {ref} เข้าหน้าวางแผนแล้ว / Pricing data loaded into Planning",
        "missing_source_work_order": "กรุณาเลือกและรับข้อมูลจากใบคำนวณราคาก่อน / Load a saved pricing record first",
        "prepared": "เตรียมใบรายการ {dept} แล้ว / Work order prepared",
    },
}

WORK_ORDERS = {
    "tabs": {
        "blown": "ใบรายการแผนกเป่า / Blown-film Department",
        "cutting": "ใบรายการแผนกตัดถุง / Bag-cutting Department",
    },
    "note": "รับลูกค้า สินค้า ไซซ์ และค่าผลิตจากใบราคาต้นทาง โดยแก้เฉพาะค่าหน้างานใน Planning / Copies the saved pricing identity; planning edits do not overwrite the quotation.",
    "copy": {
        "blown": "คัดลอกข้อมูลไปใบแผนกเป่า / Copy to Blown-film Department",
        "cutting": "คัดลอกข้อมูลไปใบแผนกตัดถุง / Copy to Bag-cutting Department",
    },
    "print": {
        "blown": "พิมพ์สรุปใบแผนกเป่า / Print Blown-film Department",
        "cutting": "พิมพ์สรุปใบแผนกตัดถุง / Print Bag-cutting Department",
    },
    "names": {
        "blown": "แผนกเป่า / Blown-film",
        "cutting": "แผนกตัดถุง / Bag-cutting",
    },
}

# app.py:2526-2579 - the fifteen columns, in order, with the desktop's widths.
# Every column is LEFT-aligned there, including the figures.
HISTORY_COLUMNS = [
    {"key": "ref", "label": "เลขอ้างอิง / Ref", "width": 145},
    {"key": "date", "label": "วันที่ / Date", "width": 95},
    {"key": "customer_code", "label": "รหัสลูกค้า / Code", "width": 100},
    {"key": "customer", "label": "ชื่อลูกค้า/บริษัท / Customer/Company", "width": 150},
    {"key": "sale_unit", "label": "หน่วยขาย / Selling Unit", "width": 145},
    {"key": "item", "label": "รายการ/รหัส / Item/Part", "width": 180},
    {"key": "product", "label": "ประเภท / Product", "width": 220},
    {"key": "size", "label": "ขนาด / Size", "width": 230},
    {"key": "thickness", "label": "ความหนา / Thickness", "width": 155},
    {"key": "grams", "label": "กรัม/ชิ้น / g/Item", "width": 85},
    {"key": "price_basis", "label": "ฐาน/สูตรคำนวณ / Price Basis/Formula", "width": 300},
    {"key": "calc_price", "label": "ผลราคาที่คำนวณ / Calculated Result", "width": 125},
    {"key": "price_kg", "label": "ราคา/กก. / Price/kg", "width": 105},
    {"key": "price", "label": "ราคาขายจริง/ชิ้น / Final Price/Piece", "width": 125},
    {"key": "pack", "label": "น้ำหนักต่อแพ็ก (กก.) / Pack Weight (kg)", "width": 85},
]

# The history tab beyond the table: filter captions, the five buttons, and
# every dialog sentence - app.py:2425-2630, 4048-4296.
HISTORY = {
    "section": "ค้นหาและจัดการประวัติใบเสนอราคา / Search & Manage Quotation History",
    "buttons": {
        "details": "รายละเอียด / Details",
        "edit": "แก้ไข / Edit",
        "print_selected": "พิมพ์รายการที่เลือก / Print Selected",
        "delete_selected": "ลบรายการที่เลือก / Delete Selected",
        "related": "บริษัทที่เคยเสนอ / Related Companies",
    },
    "edit_note": "แก้ไข / Edit: โหลดรายการเดิมเพื่อแก้ไข คำนวณใหม่ และเก็บเป็นฉบับใหม่ที่เชื่อมต้นฉบับ—รายการเดิมจะไม่ถูกลบหรือเขียนทับ / Loads a linked revision; the original is preserved.",
    "select_first": "กรุณาเลือกใบเสนอราคา / Please select a quotation",
    "delete_confirm": "ต้องการลบใบเสนอราคา {ref} ถาวรหรือไม่?\nDelete this quotation permanently? This cannot be undone.",
    "deleted_status": "ลบแล้ว / Deleted: {ref}",
    "deleted_body": "ลบใบเสนอราคาแล้ว / Quotation deleted: {ref}",
    "delete_missing": "ไม่พบรายการที่เลือก อาจถูกลบไปแล้ว / The selected record may already have been deleted.",
    "details_title": "รายละเอียด / Details — {ref}",
    "related_title": "บริษัทที่เคยได้รับใบเสนอราคา / Related Companies",
    "related_info": "ข้อมูลประกอบการตัดสินใจ ไม่ขัดขวางการบันทึก / Informational only; saving remains available",
    "related_formula": "น้ำหนักต่อแพ็ก (กก.) = กรัมต่อชิ้น × ชิ้นในแพ็ก ÷ 1,000 / Pack Weight (kg) = grams per item × pieces per pack ÷ 1,000",
    "related_none": "ยังไม่พบใบเสนอราคาเดิม / No matching quotation found",
    "edit_ref": "กำลังแก้ไข / Editing: {ref} (เก็บเป็นฉบับใหม่ / Save as revision)",
    "edit_status": "แก้ไขแล้วคำนวณใหม่ จากนั้นกดเก็บบันทึก / Edit, recalculate, then save — {ref}",
    "revised_from": "แก้ไขจาก / Revised from: {ref}",
    "new_status": "รายการใหม่ล้างข้อมูลเดิมแล้ว—ค่าที่เหลือเป็นค่าเริ่มต้นที่ระบุไว้ / New record cleared; remaining values are labeled defaults",
    # The folder view. Not in the desktop (its history is one flat table); asked
    # for on 28-08-2026 with a screenshot: "group by customer first, then click
    # to see the customer's old prices - like folders on a computer".
    "view_table": "ตาราง / Table",
    "view_tree": "ตามลูกค้า / By customer",
    "tree_hint": "ลูกค้า ▸ สินค้า (ชื่อและขนาดเดียวกันรวมเป็นหนึ่ง) ▸ ราคาทุกครั้งที่เคยเสนอ / Customer ▸ product (same name + size folded together) ▸ every price ever quoted",
    "tree_col_customer": "ลูกค้า / Customer",
    "tree_col_code": "รหัส / Code",
    "tree_col_products": "สินค้า / Products",
    "tree_col_quotes": "ใบเสนอราคา / Quotes",
    "tree_col_period": "ช่วงเวลา / Period",
    "tree_col_product": "สินค้า / Product",
    "tree_col_size": "ขนาด / Size",
    "tree_col_unit": "หน่วยขาย / Unit",
    "tree_col_latest": "ราคาล่าสุด / Latest price",
    "tree_col_range": "ช่วงราคา / Price range",
    "tree_empty": "ไม่พบรายการ / No records",
    "tree_loading": "กำลังโหลด… / Loading…",
}

# The Related Companies window's thirteen columns (app.py:3153-3183).
RELATED_COLUMNS = [
    {"key": "ref", "label": "เลขอ้างอิง / Quote Ref", "width": 155},
    {"key": "date", "label": "วันที่ / Date", "width": 105},
    {"key": "customer_code", "label": "รหัสลูกค้า / Code", "width": 120},
    {"key": "customer", "label": "บริษัท / Company", "width": 180},
    {"key": "sale_unit", "label": "หน่วยขาย / Selling Unit", "width": 150},
    {"key": "item", "label": "รายการ/รหัส / Item/Part", "width": 220},
    {"key": "size", "label": "ขนาด / Size", "width": 240},
    {"key": "grams", "label": "กรัม/ชิ้น / g/Item", "width": 110},
    {"key": "price_basis", "label": "ฐาน/สูตรคำนวณ / Price Basis/Formula", "width": 300},
    {"key": "calc_price", "label": "ผลราคาที่คำนวณ / Calculated Result", "width": 150},
    {"key": "price_piece", "label": "ราคาขายจริง/ชิ้น / Final Price/Piece", "width": 155},
    {"key": "price_kg", "label": "ราคา/กก. / Price/kg", "width": 120},
    {"key": "pack_kg", "label": "น้ำหนักต่อแพ็ก (กก.) / Pack Weight (kg)", "width": 165},
]

# THE APPROVAL DRAWING TAB - app.py _build_drawing (1876-2135), v1.7.1: four
# cards (document, dimensions & tolerances, features, the saved register), a
# four-button action row, and a status line of its own. The customer signs
# what comes out of it, so the wording is not this application's to reword.
DRAWING = {
    "tab": "แบบขออนุมัติ / Drawing for Approval",
    "status_idle": "กรอกข้อมูลแล้วกดดูตัวอย่าง เลขเอกสารจะออกให้ตอนกดบันทึกเท่านั้น / Fill in the form and preview; the document number is issued only on save",
    "buttons": {
        "copy": "ดึงข้อมูลจากหน้าคำนวณราคา / Copy from Pricing",
        "preview": "ดูตัวอย่าง & พิมพ์ / Preview & Print",
        "save": "บันทึกแบบ (ออกเลขเอกสาร) / Save Drawing",
        "new": "แบบใหม่ / New Drawing",
        "search": "ค้นหา / Search",
        "open": "เปิดแบบที่เลือก / Open Selected",
    },
    "sections": {
        "document": "ข้อมูลเอกสาร / Drawing Document",
        "dimensions": "ขนาดและค่าคลาดเคลื่อน / Dimensions and Tolerances",
        "features": "ลักษณะพิเศษและหมายเหตุ / Features and Notes",
        "register": "ทะเบียนแบบที่บันทึกไว้ / Saved Drawing Register",
    },
    "fields": {
        "doc_no": "เลขเอกสาร / Document No.",
        "date": "วันที่ / Date",
        "revision": "ครั้งที่แก้ / Revision",
        "customer_code": "รหัสลูกค้า / Customer Code",
        "customer": "ชื่อลูกค้า / Customer *",
        "title": "ชื่อแบบ / Drawing Title *",
        "part_no": "รหัสสินค้า / Part No.",
        "material": "วัสดุ / Material",
        "color": "สี / Color",
        "printing": "งานพิมพ์ / Printing",
        "product_type": "ประเภทสินค้า / Product Type",
        "length_reference": "จุดอ้างอิงความยาว / Length Reference *",
        "display_unit": "หน่วยที่พิมพ์บนแบบ / Unit on Drawing",
        "thickness_side": "ความหนาต่อด้าน / Thickness per Side",
        "width": "ความกว้าง *\nWidth",
        "length": "ความยาว *\nLength",
        "height": "ความสูง\nHeight",
        "gusset": "ขนาดพับข้าง\nGusset",
        "tol_lo": "ค่าคลาดเคลื่อนต่ำสุด (มม.) / Tolerance Lower (mm)",
        "tol_hi": "ค่าคลาดเคลื่อนสูงสุด (มม.) / Tolerance Upper (mm)",
        "tol_thickness": "ค่าคลาดเคลื่อนความหนา ± (มม.) / Thickness Tolerance (mm)",
        "holes_count": "จำนวนรูเจาะ / Number of Holes",
        "holes_dia": "ขนาดรูเจาะ Ø (มม.) / Hole Diameter",
        "label_w": "ลาเบลกว้าง (มม.) / Label Width",
        "label_h": "ลาเบลสูง (มม.) / Label Height",
        "extra_notes": "ลักษณะพิเศษที่ลูกค้าอนุมัติ บรรทัดละหนึ่งข้อ / Approved special characteristics, one per line",
    },
    "not_issued": "— ยังไม่ออกเลข / not issued —",
    "notes": {
        "revision": "แบบที่ส่งลูกค้าแล้วห้ามแก้ทับ ให้เพิ่มครั้งที่แก้ (Rev.B) แล้วบันทึก เลขเอกสารเดิมจะถูกคงไว้ / A drawing already sent must not be overwritten: raise the revision and save; the document number stays the same",
        "thickness": "ความหนาบนแบบพิมพ์เป็นมิลลิเมตรเสมอ แม้เลือกหน่วยเป็นนิ้ว เพราะหน้างานวัดด้วยไมโครมิเตอร์หน่วยมิลลิเมตร / Thickness is always printed in mm even when the unit is inch",
        "standard": "ข้อความมาตรฐาน (รูเจาะ ลาเบล จุดอ้างอิง ความหนา ค่าคลาดเคลื่อน วัสดุ) โปรแกรมเขียนให้เองจากค่าด้านบน ไม่ต้องพิมพ์ซ้ำ / Standard notes are generated from the values above",
    },
    "register_columns": [
        {"key": "doc_no", "label": "เลขเอกสาร / Doc No.", "width": 190},
        {"key": "date", "label": "วันที่ / Date", "width": 90},
        {"key": "rev", "label": "แก้ครั้งที่ / Rev", "width": 90},
        {"key": "customer", "label": "ลูกค้า / Customer", "width": 190},
        {"key": "title", "label": "ชื่อแบบ / Title", "width": 190},
        {"key": "size", "label": "ขนาด / Size (mm)", "width": 190},
    ],
    "statuses": {
        "copied": "คัดลอกข้อมูลจากหน้าคำนวณราคาแล้ว ตรวจค่าคลาดเคลื่อนก่อนส่งลูกค้า / Copied from the pricing tab; check the tolerances before sending",
        "previewed": "เปิดแบบในเบราว์เซอร์แล้ว กดปุ่มพิมพ์แล้วเลือก A4 แนวนอน / Drawing opened in the browser; print as A4 landscape",
        "saved": "บันทึกแล้ว เลขเอกสาร {doc} / Saved as {doc}",
        "reset": "เริ่มแบบใหม่ เลขเอกสารจะออกให้ตอนกดบันทึก / New drawing; the number is issued on save",
        "select_row": "เลือกแถวในทะเบียนก่อน / Select a row in the register first",
        "opened": "เปิดแบบ {doc} แล้ว ถ้าจะแก้ให้เพิ่มครั้งที่แก้ก่อนบันทึก / Opened {doc}; raise the revision before saving changes",
        "cannot_build": "สร้างแบบไม่ได้ / Cannot build drawing: ",
        "cannot_save": "บันทึกไม่ได้ / Cannot save: ",
    },
    "errors": {
        "need_customer": "ต้องระบุชื่อลูกค้า / Customer is required",
        "need_title": "ต้องระบุชื่อแบบ / Drawing title is required",
    },
}

# THE FORMULA WINDOW. The desktop opens it from the toolbar; both formulas are
# editable there, and the variable list is what may appear in them.
FORMULAS = {
    "title": "ตัวแปรสูตร / Formula Variables",
    "weight": "สูตรน้ำหนักต่อชิ้น / Item Weight Formula (Editable)",
    "price": "สูตรราคาต่อชิ้น / Unit Price Formula (Editable)",
    "reset": "คืนค่าเริ่มต้น / Reset Formula",
    "close": "ปิด / Close",
    "variables": "ตัวแปรที่ใช้ได้ / Variables you may use",
}

# WHICH BOXES EACH PRODUCT DRAWS on the compact form (app.py:1095-1120,
# mirrored by _on_product_changed 2657-2718).
#
# Deliberately only about what is DRAWN. The arithmetic still refuses on the
# server when a required figure is missing (LAW K1), so if this list ever
# drifts the failure is a visible message from the server, never a wrong
# number.
#
# COVER HIDES THE THICKNESS - and the mode box and the allowance with it. The
# cover formula weighs roof and mesh by GSM; a thickness box left on screen
# would be a question the calculation never reads.
FIELDS_BY_PRODUCT = {
    "flat": ["width", "length", "thickness"],
    "opaque": ["width", "length", "thickness"],
    "gusset": ["width", "length", "gusset", "thickness"],
    "roll": ["width", "sold_length", "thickness"],
    "cover": ["width", "length", "height"],
}

# The bottom allowance is a bag question: a sheet and a roll have no seal.
# (The desktop's length-reference combobox lives on the legacy dimensions card,
# which v1.7.1 never draws - the reference stays at its default.)
ASKS_LENGTH_REFERENCE = ["flat", "gusset"]

# app.py:2449-2496 - the filter captions, in the desktop's left-to-right order.
HISTORY_FILTERS = {
    "customer": "ลูกค้า/รหัส / Customer/Code",
    "date_from": "วันที่เริ่ม / From",
    "date_to": "วันที่สิ้นสุด / To",
    "size": "ขนาด / Size",
    "item": "รหัส/รายการ / Part/Item",
    "product_key": "ประเภท / Product Type",
    "sort": "เรียงตาม / Sort",
    "all_types": "ทุกประเภท / All Types",
    "empty": "ไม่พบข้อมูล / No records",
    "count": "รายการ / records",
}


# The button that sends ticked prices to PacOs, and every sentence around it.
# Bee, 28-08-2026: the refusal for a wrong customer is shown in Thai AND
# English - so is everything else here, the way this whole screen speaks.
BRIDGE = {
    "check_col": "เลือก / Pick",
    "button": "สร้างใบเสนอราคาใน PacOs / Create quotation in PacOs",
    "button_count": "สร้างใบเสนอราคาใน PacOs ({n}) / Create quotation in PacOs ({n})",
    "select_first": "กรุณาติ๊กเลือกรายการที่จะส่งไป PacOs ก่อน / Tick the rows to send to PacOs first",
    "none": "กรุณาติ๊กเลือกรายการที่จะส่งไป PacOs ก่อน / Tick the rows to send to PacOs first",
    "mixed_customers": "รายการที่เลือกเป็นของลูกค้าคนละราย ใบเสนอราคาหนึ่งใบมีลูกค้าได้รายเดียว กรุณาเลือกเฉพาะรายการของลูกค้ารายเดียว / The rows you ticked belong to different customers. A quotation is for one customer - tick rows of one customer only",
    "no_customer_code": "รายการ {ref} ยังไม่ผูกกับลูกค้าใน PacOs กรุณาเลือกลูกค้าจากรายการที่ซิงค์จาก PacOs แล้วบันทึกใหม่ / {ref} is not linked to a PacOs customer yet - choose the customer from the list synced from PacOs and save it again",
    "too_many": "เลือกได้ไม่เกิน 50 รายการต่อครั้ง / Up to 50 rows at a time",
    "missing": "ไม่พบใบเสนอราคา {ref} / Quotation not found: {ref}",
    "needs_pacos_login": "ต้องเข้าสู่ระบบด้วยบัญชี PacOs จึงจะส่งราคาไป PacOs ได้ / Sign in with your PacOs account to send prices to PacOs",
    "off": "เซิร์ฟเวอร์นี้ยังไม่ได้เชื่อมกับ PacOs / PacOs is not connected on this server",
    "sending": "กำลังส่งไป PacOs… / Sending to PacOs…",
    "sent": "ส่งไป PacOs แล้ว {n} รายการ กำลังเปิด PacOs… / Sent {n} rows to PacOs, opening PacOs…",
}


def screen_labels() -> dict[str, Any]:
    return {
        "app_title": APP_TITLE,
        "app_subtitle": APP_SUBTITLE,
        "header_subtitle": HEADER_SUBTITLE,
        "tabs": TABS,
        "buttons": BUTTONS,
        "steps": STEPS,
        "fields": FIELDS,
        "sections": SECTIONS,
        "section_colors": SECTION_COLORS,
        "choices": CHOICES,
        "price_boxes": PRICE_BOXES,
        "primary_hints": PRIMARY_HINTS,
        "notes": NOTES,
        "results": RESULTS,
        "planning": PLANNING,
        "work_orders": WORK_ORDERS,
        "history": HISTORY,
        "history_columns": HISTORY_COLUMNS,
        "related_columns": RELATED_COLUMNS,
        "history_filters": HISTORY_FILTERS,
        "bridge": BRIDGE,
        "drawing": DRAWING,
        "formulas": FORMULAS,
        "fields_by_product": FIELDS_BY_PRODUCT,
        "asks_length_reference": ASKS_LENGTH_REFERENCE,
    }

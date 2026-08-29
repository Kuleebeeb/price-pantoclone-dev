# 02 — Tab "ข้อมูลวางแผนการผลิต / Production Planning" + Action Bar

> Nguồn: `Z:\1\app.py` (4336 dòng). Mọi nhãn ghi NGUYÊN VĂN (Thái/Anh).
> Chuỗi version thật trong code: `APP_VERSION = "1.7.1 (Phase 1) — Planning screen"` (dòng 51) — KHÁC với "1.5.1" trong đề bài; clone theo chuỗi nào thì phải chốt lại với CEO.

---

## 0. Hằng màu gốc (app.py dòng 88-93)

| Hằng | Hex | Dùng cho |
|---|---|---|
| `BG` | `#f4f6f8` | nền cửa sổ, nền `TFrame`, nền `TLabel` thường |
| `NAVY` | `#16324f` | chữ tiêu đề, Subhead, KeyResult, tab chưa chọn |
| `BLUE` | `#1f6aa5` | nút Accent, tab đang chọn, selectbackground của dropdown gợi ý |
| `GREEN` | `#167d5a` | chữ `Result.TLabel` (kết quả xanh) |
| `RED` | `#b42318` | `Danger.TLabel`, `Danger.TButton`, `Critical.TLabel` |
| `MUTED` | `#5f6b76` | `Muted.TLabel`, ghi chú phụ |

Font mặc định toàn app: `("Leelawadee UI", 10)` qua `option_add("*Font", ...)` (dòng 278-279). Theme ttk: `clam` (dòng 277).

## 0b. Style ttk dùng trong phần này (dòng 280-374)

| Style | Thuộc tính | Dòng |
|---|---|---|
| `TFrame` | bg `#f4f6f8` (BG) | 280 |
| `Card.TFrame` | bg `white`, relief solid, borderwidth 1 | 281 |
| `Field.TFrame` | bg `white`, relief flat, borderwidth 0 | 282 |
| `ResultCard.TFrame` | bg `#f5f9fc`, relief solid, borderwidth 1 | 283 |
| `TLabel` | bg BG, fg `#1d2939` | 284 |
| `Card.TLabel` | bg `white` (fg kế thừa `#1d2939`) | 285 |
| `Glyph.TButton` | font `("Segoe UI", 9)` — riêng cho nút ký hiệu `▼` vì Leelawadee UI không có glyph mũi tên | 298-303 |
| `Subhead.TLabel` | font `("Leelawadee UI", 12, "bold")`, fg NAVY | 305 |
| `Result.TLabel` | font `("Leelawadee UI", 12, "bold")`, fg GREEN `#167d5a` | 306 |
| `KeyResult.TLabel` | bg `#f5f9fc`, font `("Leelawadee UI", 13, "bold")`, fg NAVY | 307-312 |
| `ResultName.TLabel` | bg `#f5f9fc`, fg `#344054` | 313 |
| `Danger.TLabel` | font `("Leelawadee UI", 11, "bold")`, fg RED | 314 |
| `Warning.TLabel` | font `("Leelawadee UI", 10, "bold")`, fg `#9a6700`, bg `white` | 315-320 |
| `Muted.TLabel` | fg MUTED `#5f6b76` | 334 |
| `Accent.TButton` | font `("Leelawadee UI", 10, "bold")`, padding `(12, 7)`, bg BLUE, fg white; map: active `#174f7a`, pressed `#123e60`, fg disabled `#d0d5dd` | 335-341 |
| `TNotebook.Tab` | padding `(16, 9)`, font `("Leelawadee UI", 10, "bold")`, bg `#dbe7f2`, fg NAVY; selected: bg BLUE fg white; active: bg `#b9d3e8` fg NAVY | 346-357 |

**Màu section (thanh tiêu đề card)** — `{name}.Section.TLabel`: bg theo bảng dưới, fg `white`, font `("Leelawadee UI", 11, "bold")`, padding `(10, 7)` (dòng 358-374):

| Section | Hex |
|---|---|
| Product | `#185a8d` |
| Spec | `#0f766e` |
| Quality | `#694a85` |
| Calculation | `#2f6f4e` |
| Pricing | `#1f6f5f` |
| Production | `#9a5b13` |
| History | `#5b4b8a` |

**Khung card chung** `_card()` (dòng 546-555): `ttk.Frame` style `Card.TFrame`, padding 12, grid `sticky="ew"`, padx 8, pady 5; hàng 0 là label tiêu đề style `{section}.Section.TLabel`, sticky ew, pady (0, 8).

**Ô nhập có nhãn** `_labeled_entry()` (dòng 672-699): khung `Field.TFrame` grid padx 8 pady 5 sticky ew; nhãn `Card.TLabel` hàng 0 (wraplength tự bám bề rộng qua `follow_width(caption, slack=8)`); `ttk.Entry` width mặc định 12 ở hàng 1, pady (3, 0). Nếu có `lookup` thì entry là `SuggestEntry` (autocomplete).

**Dropdown gợi ý `SuggestEntry`** (widgets.py 95-132): popup không viền (`overrideredirect`), `tk.Listbox` font `("Segoe UI", 9)`, bg `#ffffff`, fg `#16324f`, selectbackground `#1f6aa5`, selectforeground `#ffffff`, rộng ≥ max(ô nhập, 260px), tự chọn sẵn dòng đầu.

---

## 1. Cấu trúc tab (dòng 468-516)

`main_tabs` (ttk.Notebook, pack padx 18, pady (0, 18)), thứ tự tab:

1. `คำนวณราคา / Pricing` (dòng 505) — chứa action bar (mục 5) + form compact (mục 2)
2. `ข้อมูลวางแผนการผลิต / Production Planning` (dòng 508-511) — `planning_frame` padding 8, bên trong 1 `ScrollFrame` duy nhất (`planning_body`)
3. `แบบขออนุมัติ / Drawing for Approval` (dòng 512-515)
4. `ประวัติ / Quote History` (dòng 516)

Thứ tự card TRONG `planning_body` (theo grid row của card):

| row | Card (tiêu đề verbatim) | Section màu | Dòng build |
|---|---|---|---|
| 0 | `ต้นทางจากใบคำนวณราคาที่บันทึกแล้ว / Source from Saved Pricing` | Production `#9a5b13` | 1122-1128 |
| 1 | `เงื่อนไขคุณภาพสำหรับการผลิต / Production Quality Conditions` — **ẨN mặc định** (`quality.grid_remove()` dòng 962), bật/tắt bằng nút toggle bên tab Pricing (dòng 907-911) | Quality `#694a85` | 913-962 |
| 2 | `รายละเอียดสำหรับวางแผนผลิต / Production Planning Details` | Calculation `#2f6f4e` | 972-984 |
| 3 | `ใบรายการหน้างาน / Shop-floor Work Orders` | Production `#9a5b13` | 1325-1331 |

---

## 2. `_build_compact_pricing_form` (dòng 995-1093)

**LƯU Ý VỊ TRÍ**: card này nằm ở tab **`คำนวณราคา / Pricing`** (`parent` = `calc_content`, gọi ở dòng 986), KHÔNG nằm trong tab Planning. Card row 0.

- Card: `ข้อมูลเสนอราคาและสเปกหลัก / Quotation & Main Specifications`, section `Product` `#185a8d` — nhưng **thanh tiêu đề bị GỠ** (`grid_remove()` dòng 1006, lý do: đỡ tốn chiều cao). Padding card ghi đè = 6 (dòng 1005). 6 cột weight đều nhau (dòng 1007-1008).

Widget theo thứ tự (grid row, col):

| # | Widget | Nhãn verbatim | row, col | Ghi chú |
|---|---|---|---|---|
| 1 | `_labeled_entry` | `รหัสลูกค้า * / Customer Code` | 1, 0 | dòng 1009 |
| 2 | `_labeled_entry` (SuggestEntry) | `ชื่อลูกค้า/บริษัท * / Customer/Company` | 1, 1 (colspan 2) | lookup khách hàng; pick tự điền mã KH (dòng 1010-1019, 571-583) |
| 3 | `_labeled_entry` | `วันที่ * / Date` | 1, 3 | dòng 1020 |
| 4 | Combobox readonly | `ประเภทสินค้า * / Product Type` | 1, 4 (colspan 2) | values = PRODUCTS (calculator.py 11-17): `ถุงพลาสติกเปิดปากตรง (Plastic Bag)` · `แผ่นพลาสติก (Plastic Sheet)` · `ถุงพับข้าง (Gusset Bag)` · `ม้วนพลาสติก (Plastic Roll)` · `ถุงคลุมสินค้า (Product Cover)`; đổi → `_on_product_changed` (dòng 1021-1031) |
| 5-9 | 5 khung spec (Entry width 10 + Combobox đơn vị width 7) | `ความกว้าง * / Width` · `ความยาว * / Length` · `พับข้าง * / Gusset` · `ความสูง * / Height` · `ความยาวม้วน * / Roll Length` | row 2, col theo loại SP | dòng 1033-1052; đơn vị = DIMENSION_FACTORS_TO_CM: `นิ้ว` `ซม.` `มม.` `เมตร` (calculator.py 24-29) |
| 10 | Khung độ dày (Entry width 10 + Combobox width 7) | `ความหนา * / Thickness` | row 2, col 2 hoặc 3 | đơn vị = THICKNESS_FACTORS_TO_MM: `มม.` `ซม.` `นิ้ว` `ไมครอน` (calculator.py 31-36); dòng 1054-1064 |
| 11 | Combobox readonly | `ต่อด้าน/ต่อคู่ / Per Side/Pair (Pair = รวมสองด้าน / combined)` | row 3, col 0 | values: `ต่อด้าน / Per Side` · `ต่อคู่ / Per Pair` (dòng 1065-1079) |
| 12 | Entry width 8 | `ค่าบวกก้นถุง / Bottom Allowance` | row 3, col 1 | chỉ hiện với flat/gusset (dòng 1081-1083) |
| 13 | `_labeled_entry` | `รายการสินค้าของลูกค้า / Customer Item Name` | 3, 2 (colspan 2) | dòng 1084-1087 |
| 14 | `_labeled_entry` | `รหัสสินค้าอ้างอิง / Customer Item Code` | 3, 4 (colspan 2) | dòng 1088-1091 |

### `_update_compact_spec_fields` (dòng 1095-1120) — field hiện theo loại SP

| product key | Ô hiện ở row 2 (col 0→) | Thickness col | Bottom Allowance |
|---|---|---|---|
| `flat` | width, length | 2 | có (row 3 col 1) |
| `gusset` | width, length, gusset | 3 | có |
| `roll` | width, sold_length | 2 | không |
| `opaque` | width, length | 2 | không |
| `cover` | width, length, height | **ẨN cả thickness + mode + bottom** | không |

---

## 3. `_build_planning_source` (dòng 1122-1211) — card `ต้นทางจากใบคำนวณราคาที่บันทึกแล้ว / Source from Saved Pricing`

Card row 0 của planning_body, section **Production `#9a5b13`**, 4 cột weight 1.

| # | Widget | Verbatim | Layout | Dòng |
|---|---|---|---|---|
| 1 | Label `Card.TLabel` | `ค้นหาใบราคา: เลขที่ REF · ชื่อลูกค้า · รหัสสินค้า / Find a pricing record: REF, customer or part number` | picker frame row 1 col 0-2 (padx 8 pady 4); label ở row 0 trong picker | 1136-1140 |
| 2 | `SuggestEntry` width 48 | (ô tìm) | picker row 1 col 0, sticky ew | 1141-1148 |
| 3 | Button `▼` width 3, style `Glyph.TButton` (font Segoe UI 9) | `▼` | picker row 1 col 1, padx (5, 0) | 1153-1159. Bấm mở list gợi ý (mở với các báo giá mới nhất khi chưa gõ gì) |
| 4 | Button style `Accent.TButton` (BLUE, chữ trắng) | `รับข้อมูลใบราคา / Load Pricing Data` | card row 1 col 3, padx 8, pady (22, 4) | 1160-1165 |
| 5 | Label `Card.TLabel`, wraplength 1100 | Giá trị mặc định: `เลือกใบคำนวณราคาที่บันทึกแล้วเพื่อเริ่มวางแผน / Select a saved pricing record to begin` | row 2, col 0-3, padx 8, pady (2, 6) | 1166-1175 |
| 6 | `_labeled_entry` | `ความกว้างสำหรับผลิต (แก้ได้) / Production Width (cm)` | row 3 col 0 | 1184 |
| 7 | `_labeled_entry` | `ความยาวสำหรับผลิต (แก้ได้) / Production Length (cm)` | row 3 col 1 | 1185 |
| 8 | `_labeled_entry` | `ความหนาสำหรับผลิต (แก้ได้) / Production Thickness` | row 3 col 2 | 1186 |
| 9 | `_labeled_entry` | `พับข้างสำหรับผลิต / Production Gusset (cm)` | row 3 col 3 | 1187 |
| 10 | `_labeled_entry` | `แพ็กเกจ / Packaging` | row 4 col 0 | 1188 |
| 11 | `_labeled_entry` | `จำนวนใบคงเดิม / Fixed Quantity` | row 4 col 1 | 1189 |
| 12 | `_labeled_entry` | `รายละเอียดการผลิต / Production Notes` | row 4 col 2 | 1190 |
| 13 | Button `Accent.TButton` | `เปรียบเทียบน้ำหนัก / Compare Weight` | row 4 col 3, padx 8 pady 5 | 1191-1196 |
| 14 | Label style `Result.TLabel` (xanh GREEN, bold 12) | Mặc định: `น้ำหนักอ้างอิง » น้ำหนักใหม่ / Reference » New Weight: —` | row 5, col 0-3, padx 8 pady 4 | 1197-1200 |
| 15 | Label style `Muted.TLabel` (xám `#5f6b76`), wraplength 1100 | `ขั้นต่อไป / Next: ข้อมูลชุดนี้เตรียมไว้ต่อยอดเป็นใบสั่งงานแผนกเป่าและแผนกตัดถุง / This planning data is structured for future blown-film and bag-cutting work orders.` | row 6, col 0-3, padx 8 pady (4, 0) | 1201-1210 |

### Format dòng gợi ý (dòng 1213-1218)
`{quote_ref} | {customer_code} | {customer} | {item_description hoặc product_label}` — nối bằng ` | `. Lookup query DB mỗi keystroke (`db.find_quotations`, dòng 1220-1232).

### Load Pricing Data (dòng 1237-1287)
- Chưa chọn gì → warning: tiêu đề `เลือกใบราคา / Select Pricing`, nội dung `กรุณาเลือกใบคำนวณราคาที่บันทึกแล้ว / Please select a saved pricing record` (1240-1245).
- Nhận 3 kiểu input: pick từ list / gõ REF trần / paste nguyên dòng (tách trước ` | `) (1246-1254).
- Không tìm thấy → warning `ไม่พบใบราคา / Not Found`: `ไม่พบใบคำนวณราคาที่ตรงกับ / No saved pricing record matches:\n{selected}` (1255-1261).
- Điền: width = `width_cm` format `:g`; length = `material_length_cm` (fallback `length_cm`) `:g`; thickness = giá trị thô; gusset `:g`; package = `{n:g} ชิ้น/แพ็ก` nếu có; quantity `:g` (1266-1279).
- Reset dòng so sánh về `น้ำหนักอ้างอิง » น้ำหนักใหม่ / Reference » New Weight: —` (1280).
- Summary set: `{quote_ref} • {customer_code} • {customer} • {item_description|product_label} • {size_text}` (nối bằng ` • `, 1281-1284).
- Status bar: `รับข้อมูลใบราคา {quote_ref} เข้าหน้าวางแผนแล้ว / Pricing data loaded into Planning` (1285-1287).

### Compare Weight (dòng 1289-1323)
- Chưa load nguồn → warning `ยังไม่มีต้นทาง / Missing Source`: `กรุณารับข้อมูลจากใบราคาก่อน / Load a pricing record first` (1292).
- Input sai → error `ตรวจข้อมูล / Check Input` + message từ `as_float` (`{label}ต้องเป็นตัวเลข`...) (1300-1302).
- Thiếu số liệu gốc → error `เทียบไม่ได้ / Cannot Compare`: `ใบราคาไม่มีข้อมูลอ้างอิงครบ / Pricing record lacks reference dimensions` (1310-1312).
- Công thức: `ratio = ((new_width+new_gusset)/(ref_width+ref_gusset)) × (new_length/ref_length) × (new_thickness/ref_thickness)` (1313-1315).
- Kết quả VERBATIM (1 dòng, dòng 1320-1323):
  `{quantity:,.0f} ใบ / pcs • อ้างอิง {ref_kg:,.3f} กก. ({ref_grams:,.3f} g/ใบ) » ใหม่ {new_kg:,.3f} กก. ({new_grams:,.3f} g/ใบ) • ต่าง {new_kg-ref_kg:+,.3f} กก.`
  (kg: 3 thập phân; hiệu số có dấu `+`/`−`; pcs: 0 thập phân, có phân cách nghìn).

---

## 4. `_build_work_order_scaffold` (dòng 1325-1361) — card `ใบรายการหน้างาน / Shop-floor Work Orders`

Card row 3 planning_body, section **Production `#9a5b13`**. Bên trong 1 `ttk.Notebook` với 2 tab (frame padding 10):

| Department key | Tab verbatim |
|---|---|
| `blown` | `ใบรายการแผนกเป่า / Blown-film Department` |
| `cutting` | `ใบรายการแผนกตัดถุง / Bag-cutting Department` |

Trong mỗi tab (dòng 1338-1360):
1. Label (font mặc định, wraplength 1050): `รับลูกค้า สินค้า ไซซ์ และค่าผลิตจากใบราคาต้นทาง โดยแก้เฉพาะค่าหน้างานใน Planning / Copies the saved pricing identity; planning edits do not overwrite the quotation.` — row 0.
2. Button thường (không style): `คัดลอกข้อมูลไปใบแผนกเป่า / Copy to Blown-film Department` (tab blown) / `คัดลอกข้อมูลไปใบแผนกตัดถุง / Copy to Bag-cutting Department` (tab cutting) — row 1 col 0.
3. Button `Accent.TButton`: `พิมพ์สรุปใบแผนกเป่า / Print Blown-film Department` / `พิมพ์สรุปใบแผนกตัดถุง / Print Bag-cutting Department` — row 1 col 1, pady (7, 0).

### `copy_to_work_order` (1363-1382)
- Chưa có nguồn → warning `ยังไม่มีต้นทาง / Missing Source`: `กรุณาเลือกและรับข้อมูลจากใบคำนวณราคาก่อน / Load a saved pricing record first`.
- Payload: source, width, length, thickness, gusset, package, notes.
- Status: `เตรียมใบรายการ {แผนกเป่า / Blown-film | แผนกตัดถุง / Bag-cutting} แล้ว / Work order prepared`.

### `print_work_order` (1384-1415) — HTML in ra
- File: `{app_data}/print_previews/work_order_{department}_{YYYYMMDD_HHMMSS}.html`, mở bằng `os.startfile`.
- Cấu trúc: `<h1>` = `แผนกเป่า / Blown-film Department` hoặc `แผนกตัดถุง / Bag-cutting Department`; 1 `<table>` gồm 7 hàng `<tr><th>tên</th><td>giá trị hoặc —</td></tr>`:
  1. `ต้นทางใบราคา / Pricing Source`
  2. `ความกว้างผลิต / Production Width`
  3. `ความยาวผลิต / Production Length`
  4. `ความหนาผลิต / Production Thickness`
  5. `พับข้าง / Gusset`
  6. `แพ็กเกจ / Packaging`
  7. `รายละเอียด / Notes`
- CSS inline: `body{font-family:Arial,sans-serif;margin:28px}`, table full-width border-collapse, `th,td{border:1px solid #999;padding:9px;text-align:left}`, `th{width:34%;background:#eef4f8}`, `@media print{button{display:none}}`.
- Cuối trang: `<button onclick='window.print()'>พิมพ์ / Print</button>`.

---

## 5. `_build_action_bar` (dòng 1417-1641)

Vị trí: `pack(fill="x", side="bottom")` trong tab **`คำนวณราคา / Pricing`** (`calc_frame`, gọi dòng 471) — luôn ghim đáy tab, không cuộn. Khung style `Card.TFrame` (trắng, viền), padding `(10, 7)`.

### Row 0 — Thanh step (dòng 1421-1427)
Label style `Pricing.Section.TLabel` → **bg `#1f6f5f`, chữ trắng, bold 11, padding (10, 7)**, colspan 7, pady (0, 7). Text VERBATIM (một chuỗi tĩnh, không đổi màu theo trạng thái):
`1. กรอกสเปก / Enter Specs  »  2. คำนวณ / Calculate  »  3. กรอกราคาขาย / Final Price  »  4. เก็บบันทึก / Save`
(giữa các step là 2 space + `»` + 2 space).

### Row 1 (dòng 1450-1465)
- Combobox readonly width 28, col 0: values `ขายเป็นกิโลกรัม / Sell by kg` · `ขายเป็นชิ้น / Sell by piece` (mặc định kg).
- Label `Result.TLabel` (GREEN bold 12), col 1-6: biến `quick_primary_result_var`.
  - Mặc định/kg: `ขายเป็นกก. / Sell by kg: จำนวนมาตรฐาน = 1,000 ÷ กรัมต่อชิ้น / Standard items/kg = 1,000 ÷ grams/item`
  - Chuyển sang piece (2779-2781): `ขายเป็นชิ้น / Sell by piece: ราคาต่อชิ้น = ราคาฐาน/กก. ÷ จำนวนหลังหัก/กก. / Price per piece = price basis/kg ÷ adjusted items/kg`
  - Sau khi tính (kg, 2813-2815): `ขายเป็นกก. / Sell by kg • จำนวนมาตรฐาน {:,.2f} ชิ้น/กก. • จำนวนหลังหัก {:g}% = {:,.2f} ชิ้น/กก.`
  - Sau khi tính (piece, 2819-2826): 4 dòng `ขายเป็นชิ้น / Sell by piece` / `น้ำหนักต่อชิ้น / Weight per item: {:,.3f} กรัม / g` / `จำนวนมาตรฐานต่อกก. / Standard items per kg: {:,.2f} (จำนวนหลังหัก {:g}% / Adjusted: {:,.2f})` / `ราคาคำนวณต่อชิ้น / Calculated price per piece: {:,.3f} บาท / THB`

### Row 2 — pricing_factors (Card.TFrame, 4 cột; dòng 1466-1508)
| col | Widget | Verbatim | Ghi chú |
|---|---|---|---|
| 0 | `_labeled_entry` width 12 | `ความหนาแน่น / Density (g/cm³)` | default "0.92" (DEFAULTS dòng 67-73) |
| 1 | `_labeled_entry` width 12 | `ราคาวัตถุดิบ / Material (บาท/kg)` | default "65" |
| 2 | `_labeled_entry` width 12, **state readonly** | `บวกเพิ่มอัตโนมัติ / Auto Markup (%)` | tự tính = `((basis/material)−1)×100`, format `:.2f`, sai input thì rỗng (2784-2794) |
| 3 | Khung: Label `ค่าหักจำนวนต่อกก. / Items-per-kg Deduction` + Checkbutton `ใช้ค่าหัก / Apply` (mặc định BẬT) + Label `%` + Entry width 7 | | default "10" (1495-1508) |

Row 1 của pricing_factors (dòng 1606-1612): Label `Muted.TLabel`: `บวกเพิ่ม (%) = ((ราคาฐานต่อกก. ÷ ราคาวัตถุดิบต่อกก.) − 1) × 100 / Auto-calculated; no manual entry`

### Row 3 — price_fields: 3 hộp giá (tk.Frame màu tùy chỉnh; dòng 1509-1603)

| Hộp | bg | viền (highlight) | Nhãn verbatim (2 dòng) | Nhãn: màu chữ / font | Ô nhập |
|---|---|---|---|---|---|
| 1. calculated_box (col 0) | `#eaf3fb` | `#7aa7c7`, dày 2 | `ราคาต่อชิ้นที่คำนวณได้ (อ่านอย่างเดียว)`⏎`Calculated price per piece (Read-only)` | NAVY / Leelawadee UI 10 bold | tk.Entry readonly, readonlybackground `#f4f8fb`, relief solid bw 1, width 22; giá trị mặc định `—`, sau tính: `{:,.3f} บาท/ชิ้น` (3014-3016) |
| 2. final_piece_box (col 1) | `#fff4c2` | `#b7791f`, dày 3 | `ราคาขายต่อชิ้น (กรอก/แก้ไขได้)`⏎`Final selling price per piece (Editable)` | `#7a4300` / Leelawadee UI 11 bold | tk.Entry width 18, bg `#fffbed`, disabledbackground `#eeeeee`, relief solid bw 2, font Leelawadee UI 12 bold |
| 3. kg_box (col 2) | `#eaf7ee` | `#4b8f63`, dày 2 | `ราคาฐานต่อกิโลกรัม (กรอกได้)`⏎`Price basis per kg (Editable)` | `#245c38` / Leelawadee UI 10 bold | tk.Entry width 18, bg `#f4fcf6`, relief solid bw 1, font Leelawadee UI 11 bold |

Padding hộp: box 1 & 3 padx 9 pady 7; box 2 padx 9 pady 6.

**Trạng thái theo Sale Basis** (`_on_sale_basis_changed`, dòng 2741-2782):
- `ขายเป็นกิโลกรัม / Sell by kg` (mặc định): ẨN hộp 1 + hộp 2 + label dẫn giải; hộp 3 giãn full (col 0, colspan 3, padx 0) và nhãn ĐỔI thành `ราคาขายต่อกิโลกรัม (กรอก/แก้ไขได้)`⏎`Final selling price per kg (Editable)`; ô piece bị `disabled` (nền `#eeeeee`). Checkbox `ใช้ค่าหัก / Apply` bị reset về BẬT.
- `ขายเป็นชิ้น / Sell by piece`: hiện đủ 3 hộp; hộp 3 nhãn về `ราคาฐานต่อกิโลกรัม (กรอกได้)`⏎`Price basis per kg (Editable)`; ô piece `normal`.

### Row 4-6 — 3 label kết quả/dẫn giải
| row | Style | Giá trị mặc định verbatim | Dòng |
|---|---|---|---|
| 4 | `Result.TLabel` (GREEN) | `ราคาต่อใบที่คำนวณได้ / Calculated Price/Piece: —  (ราคาฐาน/กก. ÷ จำนวนหลังหัก/กก.)` — ẨN khi bán theo kg; sau tính: `สูตรคำนวณ / Derivation`⏎`{basis:,.3f} บาท/กก. ÷ จำนวนหลังหัก {:g}% ({:,.2f} ชิ้น/กก.) = {:,.3f} บาท/ชิ้น`⏎`ไม่ใช้จำนวนแพ็กในการคำนวณ / pack quantity not used` (3017-3023) | 1613-1622 |
| 5 | `Result.TLabel` (GREEN) | `ลำดับตรวจสอบ / Verification: กรอกข้อมูลแล้วกดคำนวณเพื่อแสดง น้ำหนัก » จำนวน/กก. » ราคา/ชิ้น` | 1623-1632 |
| 6 | `Muted.TLabel` | (rỗng — tóm tắt công thức máy) | 1633-1640 |

**Status của action** (`action_status_var`): hiển thị ở label style `Warning.TLabel` (fg `#9a6700` bold, nền trắng) TRÊN vùng nút chính đầu trang (dòng 453-459); mặc định: `พร้อมคำนวณ—หากข้อมูลไม่ครบจะแจ้งตรงนี้ / Ready; missing fields will be shown here` (261-263). Sau tính OK: `คำนวณสำเร็จ—กรอกราคาขายในช่องด้านบน หรือใช้ผลจากสูตร แล้วกดเก็บบันทึก / Calculated; enter a selling price or keep formula result, then Save` (3077-3079). Lỗi: `กรุณาตรวจข้อมูล / Check input: {exc}` (3083).

---

## 6. Card `รายละเอียดสำหรับวางแผนผลิต / Production Planning Details` (dòng 972-984)

Section **Calculation `#2f6f4e`**, row 2 planning_body. Bên trong: Notebook `calc_panels`, panel padding 14.

⚠️ **Chỉ 1 tab được add**: `ข้อมูลผลิต / Production Data` (production_panel, dòng 982). `pricing_panel` được BUILD (dòng 983) nhưng **KHÔNG add vào notebook → không hiển thị** ở v1.7.1 (spec ở mục 8 để tham khảo, đừng render trên web trừ khi CEO yêu cầu).

## 7. `_build_production_panel` (dòng 1717-1872) — tab `ข้อมูลผลิต / Production Data`

Header: Label style `Production.Section.TLabel` (**bg `#9a5b13`**, chữ trắng bold 11): `คำนวณสำหรับสั่งผลิตและบรรจุ / Production & Packaging` — row 0, colspan 4 (1726-1730).

Row 1 — 4 `_labeled_entry`:
| col | Verbatim | Default |
|---|---|---|
| 0 | `หักเผื่อผลิต / Deduction (%) • ค่าเริ่มต้น / Default 10` (phần `• ค่าเริ่มต้น / Default 10` sinh từ `default_note`, dòng 76-85) | 10 |
| 1 | `จำนวนสั่งผลิต / Order Quantity • ค่าเริ่มต้น / Default 1,000` | 1000 |
| 2 | `น้ำหนักต่ำสุด / Min Control (g)` | 0 |
| 3 | `น้ำหนักสูงสุด / Max Control (g)` | 0 |

Row 2 — card con packaging (`Card.TFrame` padding 10, dòng 1736-1775):
- col 0: `ชิ้นต่อแพ็กเล็ก / Pieces per Small Pack (กรอกเพื่อคำนวณน้ำหนัก / Needed for Weight)`
- col 1: `ชิ้นต่อกระสอบ / Pieces per Sack (กรอกเพื่อคำนวณน้ำหนัก / Needed for Weight)`
- col 2-3 (khung deduction_box): Label `การหักเผื่อสำหรับจำนวนต่อกิโล / Deduction for Items per kg`; Checkbutton `ใช้เปอร์เซ็นต์หักด้านบน / Apply deduction above` (cùng biến với checkbox action bar); Label fg MUTED: `ทั้งสองหน่วยขายเปิดค่าหัก 10% เป็นค่าเริ่มต้นและแก้ไข/ปิดได้ / Both modes default to 10%; editable or switchable off`

Row 3 — cover_material_frame (chỉ hiện khi SP = `ถุงคลุมสินค้า (Product Cover)`; dòng 1777-1796):
- `น้ำหนักหลังคา / Roof GSM` (default 120) · `น้ำหนักตาข่าย / Mesh GSM` (default 80)
- Ô đọc: `พื้นที่หลังคา / Roof Area` + `พื้นที่ตาข่าย / Mesh Area` (Result.TLabel, format `{:,.3f} ตร.ซม. ({:,.3f} ตร.ม.)`, dòng 3069-3074)

Row 4-6: Label `Subhead.TLabel` `สูตรน้ำหนักต่อชิ้น / Item Weight Formula (Editable)`; tk.Text height 2, font `("Consolas", 10)`, relief solid bw 1; Button `คืนค่าเริ่มต้น / Reset Formula` (row 6 col 3, sticky e) (1798-1807).

### Bảng ô kết quả production (dòng 1809-1871) — thực tế 12 ô (đề bài ghi 16: SAI so với code)

Khung `Card.TFrame` padding 10; mỗi ô = `ResultCard.TFrame` (bg `#f5f9fc`, viền solid 1) padding 8; tên ô style `ResultName.TLabel` (fg `#344054`, bg `#f5f9fc`, wraplength 250); giá trị style `KeyResult.TLabel` (NAVY, Leelawadee UI 13 bold, bg `#f5f9fc`), pady (3, 0). **Grid tự reflow**: số cột = `floor(width / 240)` (MIN_RESULT_CARD = 240, dòng 611, 656-670), padx/pady 5, sticky nsew — KHÔNG cố định 4 cột.

| # | Tên ô verbatim | Giá trị (format, dòng set) |
|---|---|---|
| 1 | `กรัมต่อชิ้น / Grams per Item` | `{:,.3f} กรัม` (2998) |
| 2 | `จำนวนปกติต่อกก. / Normal Items per kg` | `{:,.2f} ชิ้น` (3009) |
| 3 | `การหักเผื่อ / Deduction Effect` | `เปิด / ON −{:g}%` hoặc `ปิด / OFF (ใช้จำนวนปกติ / normal)` (3055-3059) |
| 4 | (động) `จำนวนชิ้นต่อกก.หลังหัก {n}% / Items per kg after {n}% deduction` — khi tắt hộp hếck: `จำนวนชิ้นต่อกก. (ไม่หักเผื่อ) / Items per kg (no deduction)` (589-609) | `{:,.2f} ชิ้น` (3051) |
| 5 | `ชิ้นต่อแพ็กเล็ก / Pieces per Small Pack` | `{:,.0f} ชิ้น` hoặc `ยังไม่ได้กำหนด / Not Set` (3031-3033) |
| 6 | `น้ำหนักแพ็กเล็ก / Small Pack Weight` | `{:,.4f} กก.` hoặc `ยังไม่ได้กำหนด / Not Set` (3025-3027) |
| 7 | `ชิ้นต่อกระสอบ / Pieces per Sack` | `{:,.0f} ชิ้น` hoặc `ยังไม่ได้กำหนด / Not Set` (3034-3036) |
| 8 | `น้ำหนักกระสอบ / Sack Weight` | `{:,.4f} กก.` hoặc `ยังไม่ได้กำหนด / Not Set` (3028-3030) |
| 9 | `คำเตือน 25 กก. / 25 kg Warning` | `ยังไม่ได้กำหนดจำนวนบรรจุ / Packaging Not Set` \| `! น้ำหนักบรรจุเกิน 25 กก. / Packaging over 25 kg` \| `√ น้ำหนักบรรจุไม่เกิน 25 กก. / Packaging ≤ 25 kg` (3045-3050) |
| 10 | `ช่วง/สถานะควบคุม / Control Range & Status` | `{min:g}–{max:g} กรัม • {status}` hoặc `ไม่กำหนดช่วง / No range • {status}` (3064-3068) |
| 11 | `วัตถุดิบ / Required Material` | `{:,.3f} กก.` (3060) |
| 12 | `ราคารวม / Total Price` | `{:,.3f} บาท` (3062) |

(`pack_count_result` `{:,.3f} แพ็ก` và `control_status_result` được set ở 3061/3063 nhưng KHÔNG có ô hiển thị trong panel này.)
Giá trị khởi tạo mọi ô: `—`.

## 8. `_build_pricing_panel` (dòng 1643-1715) — ĐANG ẨN (không add vào notebook)

Header `Pricing.Section.TLabel` (bg `#1f6f5f`): `คำนวณราคาลูกค้า / Customer Pricing`. Row 1: `ความหนาแน่น / Density (g/cm³) • ค่าเริ่มต้น / Default 0.92` · `ราคาวัตถุดิบ / Material (บาท/kg) • ค่าเริ่มต้น / Default 65` · `บวกเพิ่ม / Markup (%) • ค่าเริ่มต้น / Default 20` · Combobox `รูปแบบการขาย / Sale Basis` (cùng 2 giá trị). Row 2-4: `สูตรราคาต่อชิ้น / Unit Price Formula (Editable)` + tk.Text (Consolas 10) + Button `คืนค่าเริ่มต้น / Reset Formula`. Row 5 — 5 ô kết quả (`Card.TFrame`, nhãn `Card.TLabel` wraplength 190, giá trị `Result.TLabel` nền white) + 1 ô cảnh báo `Danger.TLabel` (RED, nền white):
1. `ความยาววัสดุ / Material Length` — `{:,.3f} {unit}` kèm ` ({:,.3f} ซม.)` nếu unit ≠ `ซม.` (2999-3008)
2. `จำนวนต่อกก. / Items per kg` — `{:,.2f} ชิ้น`
3. `ราคาขายจริง/ชิ้น / Final Price per Piece` — `{:,.3f} บาท` (ẩn khi bán kg, 2766-2772)
4. `ราคาขายจริง/กก. / Final Price per kg` — `{:,.3f} บาท` (ẩn khi bán piece)
5. `น้ำหนักแพ็ก / Pack Weight` — `{:,.4f} กก.` / `ยังไม่ได้กำหนด / Not Set`
6. (col 5) cảnh báo 25 กก. — cùng chuỗi mục 7 #9.

# 05 — Kết quả tính, Lưu, In, Nháp, Đăng nhập, Widgets, Server

> Catalog UI app desktop tkinter **PantongOne** để web React clone 100%.
> Nguồn: `Z:\1\app.py`, `Z:\1\gate.py`, `Z:\1\widgets.py`, `Z:\1\server_ui.py`, `Z:\1\config.py`, `Z:\1\branding.py`.
> Mọi chuỗi nhãn ghi **NGUYÊN VĂN** (Thái / Anh song ngữ, giữ cả dấu `•`, `!`, `√`, `×`, `—`).
> Số dòng = bằng chứng trong file nguồn.

---

## 0. Hằng số màu + tên app (app.py 46-93, config.py, branding.py)

| Hằng | Giá trị | Bằng chứng |
|---|---|---|
| `BG` | `#f4f6f8` | app.py:88 (gate.py:35 giống hệt) |
| `NAVY` | `#16324f` | app.py:89, gate.py:36 |
| `BLUE` | `#1f6aa5` | app.py:90, gate.py:37 |
| `GREEN` | `#167d5a` | app.py:91 |
| `RED` | `#b42318` | app.py:92, gate.py:38 |
| `MUTED` | `#5f6b76` | app.py:93, gate.py:39 |
| `AMBER` (chỉ gate.py) | `#8a5a00` | gate.py:40 (server_ui.py:301 dùng literal cùng màu) |
| `APP_TITLE` | `"PantongOne"` (= `branding.APP_NAME`) | app.py:46, branding.py:24 |
| `APP_SUBTITLE` | `"โปรแกรมคำนวณราคาพลาสติก / Plastic pricing"` | app.py:47, branding.py:28 |
| `APP_VERSION` | `"1.7.1 (Phase 1) — Planning screen"` ⚠️ KHÔNG phải 1.5.1 như đề bài | app.py:51 |
| `DEFAULT_SERVER_URL` | `"https://download.pantongone.com"` | config.py:32 |
| `HISTORY_PAGE` | `500` dòng/lần cho bảng lịch sử | app.py:55 |

`DEFAULTS` (app.py:67-73): `density_g_cm3="0.92"` · `material_price_per_kg="65"` · `markup_percent=""` · `deduction_percent="10"` · `order_quantity="1000"`.
Ghi chú default sinh tự động (app.py:76-85): `" • ค่าเริ่มต้น / Default " + <giá trị>` (vd: ` • ค่าเริ่มต้น / Default 10`).

---

## 1. Kết quả tính + Lưu

### 1.1 `_update_primary_selling_result` (app.py:2811-2826)

Ô kết quả chính `quick_primary_result_var`, 2 nhánh theo `sale_basis`:

**Nhánh bán theo kg** — `sale_basis` bắt đầu bằng `"ขายเป็นกิโลกรัม"` (app.py:2812-2815), 1 dòng:
```
ขายเป็นกก. / Sell by kg • จำนวนมาตรฐาน {items_per_kg:,.2f} ชิ้น/กก. • จำนวนหลังหัก {deduction_percent:g}% = {production_items_per_kg:,.2f} ชิ้น/กก.
```

**Nhánh bán theo chiếc** (app.py:2816-2826), 4 dòng (`\n`):
```
ขายเป็นชิ้น / Sell by piece
น้ำหนักต่อชิ้น / Weight per item: {grams_per_item:,.3f} กรัม / g
จำนวนมาตรฐานต่อกก. / Standard items per kg: {items_per_kg:,.2f} (จำนวนหลังหัก {deduction_percent:g}% / Adjusted: {production_items_per_kg:,.2f})
ราคาคำนวณต่อชิ้น / Calculated price per piece: {calculated_price_per_piece_from_kg:,.3f} บาท / THB
```
Trong đó `basis_text` (app.py:2817-2818): nếu `selling_price_per_kg_override > 0` → `{basis:,.3f}`, ngược lại → `"ผลสูตร / formula result"` (biến này được tạo nhưng nhánh piece hiện tại không chèn vào chuỗi).

### 1.2 `_human_calculation_summary` (app.py:2916-2954) — "Lời giải kiểm chứng"

Đổ vào `human_formula_summary_var` (gọi ở app.py:2995). Theo `product_key`:

- `gusset` → `area_text = "({width_cm:g} + {gusset_cm:g}) × {material_length_cm:g}"` (2922-2923)
- `flat` | `opaque` → `"{width_cm:g} × {material_length_cm:g}"` (2924-2925)
- `roll` → `"{width_cm:g} × {sold_length_m:g} m"` (2926-2927)
- **Loại khác** (2928-2933) → trả về 1 dòng ngắn:
```
น้ำหนัก / Weight = {grams_per_item:,.3f} g  »  จำนวน / Items = {items_per_kg:,.2f}/kg  »  ราคา / Price = {calculated_price_per_piece_from_kg:,.3f} THB/item
```
(chú ý 2 dấu cách quanh `»`)

`thickness_text` theo mode (2934-2941):
- mode `"pair"` → `({thickness_mm:g}/10) × {density:g} [Per Pair: ใช้ความหนารวมโดยตรง, ไม่คูณ 2 / no extra ×2]`
- ngược lại → `2 × ({thickness_mm:g}/10) × {density:g} [Per Side: คูณสองด้าน / ×2 sides]`

`deduction` = `deduction_percent` nếu `apply_deduction`, ngược lại `0` (2942).
`price_step` (2944-2948): nếu `selling_price_per_kg_override > 0` → `"{price_basis:g} ÷ {production_items_per_kg:,.2f} = "`, ngược lại → `"ผลสูตรต้นทุน / cost formula = "`.

Chuỗi trả về 3 dòng (2949-2954):
```
ตรวจสูตรน้ำหนัก / Weight: {area_text} × {thickness_text} = {grams_per_item:,.3f} g
จำนวน / Items: 1,000 ÷ {grams_per_item:,.3f} = {items_per_kg:,.2f}/kg; หลังหัก {deduction:g}% / adjusted = {production_items_per_kg:,.2f}/kg
ราคาต่อชิ้น / Price per item: {price_step}{calculated_price_per_piece_from_kg:,.3f} THB
```

### 1.3 `calculate_now` (app.py:2956-3086) — mọi ô kết quả

Tóm tắt công thức đang dùng, `main_formula_summary_var` (2962-2965), 2 dòng:
```
สูตรน้ำหนัก / Weight formula: {weight_formula}
สูตรคำนวณราคา / Price formula: {price_formula}
```
Sau khi tính xong, lưu công thức vào settings DB (2996-2997). Các ô kết quả:

| Biến | Định dạng nguyên văn | Dòng |
|---|---|---|
| `grams_result` | `{grams_per_item:,.3f} กรัม` | 2998 |
| `material_length_result` | `{shown_length:,.3f} {length_unit}` + nếu unit ≠ `ซม.` thêm ` ({material_length_cm:,.3f} ซม.)` | 2999-3008 |
| `items_per_kg_result` | `{items_per_kg:,.2f} ชิ้น` | 3009 |
| `quick_normal_items_var` | `จำนวนมาตรฐานต่อกก. / Standard items per kg: {items_per_kg:,.2f}` | 3010-3012 |
| `unit_price_result` | `{unit_price:,.3f} บาท` | 3013 |
| `calculated_piece_display_var` | `{calculated_price_per_piece_from_kg:,.3f} บาท/ชิ้น` | 3014-3016 |
| `quick_calculated_piece_var` | 3 dòng: `สูตรคำนวณ / Derivation` ⏎ `{selling_price_per_kg_override:,.3f} บาท/กก. ÷ จำนวนหลังหัก {deduction_percent:g}% ({production_items_per_kg:,.2f} ชิ้น/กก.) = {calculated_price_per_piece_from_kg:,.3f} บาท/ชิ้น` ⏎ `ไม่ใช้จำนวนแพ็กในการคำนวณ / pack quantity not used` | 3017-3023 |
| `selling_price_per_kg_result` | `{selling_price_per_kg:,.3f} บาท` | 3024 |
| `pack_weight_result` | `{pack_weight_kg:,.4f} กก.` nếu pack_quantity>0, ngược lại `ยังไม่ได้กำหนด / Not Set` | 3025-3027 |
| `sack_weight_result` | `{sack_weight_kg:,.4f} กก.` / `ยังไม่ได้กำหนด / Not Set` | 3028-3030 |
| `small_pack_qty_result` | `{pack_quantity:,.0f} ชิ้น` / `ยังไม่ได้กำหนด / Not Set` | 3031-3033 |
| `sack_qty_result` | `{sack_quantity:,.0f} ชิ้น` / `ยังไม่ได้กำหนด / Not Set` | 3034-3036 |
| `pack_warning_result` | 3 trạng thái: chưa đặt → `ยังไม่ได้กำหนดจำนวนบรรจุ / Packaging Not Set`; max>25kg → `! น้ำหนักบรรจุเกิน 25 กก. / Packaging over 25 kg`; ok → `√ น้ำหนักบรรจุไม่เกิน 25 กก. / Packaging ≤ 25 kg` | 3045-3050 |
| `adjusted_items_result` | `{production_items_per_kg:,.2f} ชิ้น` | 3051 |
| `quick_adjusted_items_var` | `จำนวนหลังหัก {deduction_percent:g}% / Items per kg after deduction: {production_items_per_kg:,.2f}` | 3052-3054 |
| `deduction_effect_result` | ON → `เปิด / ON −{deduction_percent:g}%` (dấu trừ Unicode −); OFF → `ปิด / OFF (ใช้จำนวนปกติ / normal)` | 3055-3059 |
| `required_kg_result` | `{required_kg:,.3f} กก.` | 3060 |
| `pack_count_result` | `{pack_count:,.3f} แพ็ก` | 3061 |
| `total_price_result` | `{total_price:,.3f} บาท` | 3062 |
| `control_status_result` | `{control_status}` (chuỗi từ calculator) | 3063 |
| `control_range_result` | có range → `{control_min_g:g}–{control_max_g:g} กรัม • {control_status}` (en-dash –); không → `ไม่กำหนดช่วง / No range • {control_status}` | 3064-3068 |
| `roof_area_result` | `{roof_area_cm2:,.3f} ตร.ซม. ({cm2/10000:,.3f} ตร.ม.)` | 3069-3071 |
| `mesh_area_result` | `{mesh_area_cm2:,.3f} ตร.ซม. ({cm2/10000:,.3f} ตร.ม.)` | 3072-3074 |

Status thành công (`action_status_var`, 3077-3079):
```
คำนวณสำเร็จ—กรอกราคาขายในช่องด้านบน หรือใช้ผลจากสูตร แล้วกดเก็บบันทึก / Calculated; enter a selling price or keep formula result, then Save
```
Lỗi (3081-3086): status = `กรุณาตรวจข้อมูล / Check input: {exc}`; messagebox lỗi tiêu đề `ตรวจข้อมูล / Check Input`, thân = message exception. Các message validate từ `_collect_inputs`/`as_float`: `{label}ต้องเป็นตัวเลข` (app.py:104,114), `{label}ต้องมากกว่า 0` / `{label}ต้องไม่ติดลบ` (116), `น้ำหนักควบคุมต่ำสุดต้องไม่มากกว่าค่าสูงสุด` (2913).

### 1.4 Alert báo giá liên quan `_update_related_quote_alert` (app.py:3088-3127) — chỉ câu chữ

3 trạng thái của `related_alert_var`:

1. **Trùng chính xác** (Part No. + Size, 3104-3113):
   `! พบรายการซ้ำ: รหัสสินค้าและขนาดเดียวกัน / DUPLICATE Part No. + Size — {n} ใบ / quotes — {preview}`
   - `preview` = tối đa 3 tên công ty nối `", "`; quá 3 thêm ` และอีก {còn lại} บริษัท` (3106-3108)
   - Label style `Critical.TLabel`; nút style `Danger.TButton`, state `normal` (3112-3113)
2. **Có lịch sử khớp** (3114-3123):
   `• พบประวัติตรงกัน / Matching history: {n} ใบเสนอราคา / quotes — {preview}`
   - preview cùng quy tắc; label `Warning.TLabel`, nút `TButton` state `normal`
3. **Không khớp** (3124-3127):
   `ยังไม่พบรายการตรงกัน / No matching Part No. or Item + Size found`
   - label `Warning.TLabel`, nút disabled

### 1.5 `save_quotation` (app.py:3246-3322)

- Validate header trước (`_validate_header` 3236-3244): thiếu tên KH → `กรุณากรอกชื่อลูกค้า/บริษัท / Please enter customer/company name`; thiếu mã KH → `กรุณากรอกรหัสลูกค้า / Please enter customer code`; sai ngày (định dạng `%Y-%m-%d`) → `วันที่ต้องอยู่ในรูป ปปปป-ดด-วว เช่น 2026-08-27`.
- Gọi `calculate_now()`; nếu None thì dừng im lặng (3249-3251).
- Payload lưu DB (3254-3305): header (quote_date, customer, customer_code, item_description, product_reference, product_image_path, `revised_from_ref` = `editing_source_ref`), product_key/label, `size_text`, `length_reference`, `inputs` đầy đủ, `formulas: {weight, price}`, `results` gồm: grams_per_item, items_per_kg, production_items_per_kg, unit_price, selling_price_per_kg, calculated_price_per_piece_from_kg, `calculated_price_per_kg` = piece × production_items_per_kg (3276-3279), final_selling_price_per_piece (= unit_price), final_selling_price_per_kg, `price_basis_summary`, pack/sack weight, total_price, required_kg, pack_count, control_status, roof/mesh area, material_length_cm, `verification_summary` = kết quả `_human_calculation_summary` (3296).
- Sau lưu: `current_quote_ref` = `เลขอ้างอิง / Quote Ref: {ref}` (3307); refresh lịch sử; messagebox tiêu đề `บันทึกแล้ว / Saved`, thân:
  ```
  บันทึกใบเสนอราคาเรียบร้อย / Quotation saved
  เลขอ้างอิง / Quote Ref: {ref}
  ```
  nếu là revision thêm dòng `แก้ไขจาก / Revised from: {editing_source_ref}` (3309-3314).
- Status: `เก็บบันทึกแล้ว / Saved: {ref}` (3315). Refresh gợi ý khách hàng (3317), reset `editing_source_ref` (3318).
- Lỗi ValueError → messagebox `ตรวจข้อมูล / Check Input`. Lỗi khác → tiêu đề `บันทึกไม่สำเร็จ / Save Failed`, thân `ไม่สามารถบันทึกข้อมูลได้ / Unable to save: {exc}` (3319-3322).

### 1.6 Popup lịch sử liên quan `show_related_quotes` (app.py:3129-3234) — tham khảo thêm

- Không có dòng nào → messagebox `ประวัติสินค้า / Product History` / `ยังไม่พบใบเสนอราคาเดิม / No matching quotation found` (3132-3136).
- Cửa sổ Toplevel `1080x480`, tiêu đề mặc định `บริษัทที่เคยได้รับใบเสนอราคา / Related Companies` (3139-3140).
- 2 dòng chú thích trên bảng: `ข้อมูลประกอบการตัดสินใจ ไม่ขัดขวางการบันทึก / Informational only; saving remains available` (style Warning, 3143) và `น้ำหนักต่อแพ็ก (กก.) = กรัมต่อชิ้น × ชิ้นในแพ็ก ÷ 1,000 / Pack Weight (kg) = grams per item × pieces per pack ÷ 1,000` (style Muted, 3148).
- Treeview 13 cột (nhãn, độ rộng px — app.py:3169-3183): `เลขอ้างอิง / Quote Ref` 155 · `วันที่ / Date` 105 · `รหัสลูกค้า / Code` 120 · `บริษัท / Company` 180 · `หน่วยขาย / Selling Unit` 150 · `รายการ/รหัส / Item/Part` 220 · `ขนาด / Size` 240 · `กรัม/ชิ้น / g/Item` 110 · `ฐาน/สูตรคำนวณ / Price Basis/Formula` 300 · `ผลราคาที่คำนวณ / Calculated Result` 150 · `ราคาขายจริง/ชิ้น / Final Price/Piece` 155 · `ราคา/กก. / Price/kg` 120 · `น้ำหนักต่อแพ็ก (กก.) / Pack Weight (kg)` 165. Ô không áp dụng hiển thị `—`; pack chưa đặt hiển thị `ยังไม่ได้กำหนด / Not Set` (3222-3228).

---

## 2. In tờ tóm tắt

### 2.1 `_current_print_payload` (app.py:3324-3368)

Snapshot in KHÔNG lưu lịch sử. `quote_ref` hiển thị: nếu đang sửa từ bản cũ → `ฉบับใหม่จาก {ref} / New revision from {ref}`, ngược lại → `ยังไม่บันทึก / Unsaved` (3331-3335). `customer` rỗng → `—` (3337). Results cùng bộ khóa như save (3346-3367) gồm cả `price_basis_summary` và `verification_summary`.

### 2.2 `_build_print_html` (app.py:3371-3517) — cấu trúc HTML in ĐẦY ĐỦ

Trang A4 song ngữ tự chứa, `<html lang="th">`, `<title>` = quote_ref (3486-3487). Giá trị rỗng/None hiển thị `—` (hàm `e`, 3381-3382).

**CSS (3489-3503) — nguyên văn giá trị:**
- `@page { size: A4; margin: 14mm; }`
- `body`: màu chữ `#172b3a`, font `14px/1.45 "Leelawadee UI", "Tahoma", sans-serif`, nền `#eef3f7`
- `.sheet`: `210mm × min-height 276mm`, margin `12px auto`, padding `14mm`, nền trắng, `box-shadow: 0 2px 14px #8aa0b333`
- `h1`: màu `#16324f` (NAVY), `font-size 24px`, margin 0
- `.subtitle`: màu `#516273`, margin `4px 0 18px`
- `h2`: chữ trắng trên nền `#1f6aa5` (BLUE), `font-size 16px`, padding `7px 10px`, margin `18px 0 7px`
- `table`: `width 100%`, `border-collapse: collapse`
- `th, td`: viền `1px solid #9fb1c1`, padding `7px 9px`, text-align left, vertical-align top
- `th`: rộng `44%`, nền `#f1f6fa`, `font-weight 700`
- `.price th, .price td`: viền đậm hơn `#6f91ac`
- `.note`: margin-top 12px, padding 9px, viền `1px solid #c7d3dd`, nền `#f8fafc`, chữ `#445667`
- `.actions`: sticky top 0, padding 10px, căn giữa, nền `#16324f` (NAVY)
- `button`: padding `9px 22px`, không viền, `border-radius 5px`, nền `#167d5a` (GREEN), chữ trắng, `font-weight 700`, cursor pointer
- `@media print`: body nền trắng; `.sheet` bỏ khung/bóng; `.no-print { display:none !important }`

**Hành vi:** `<body onload="setTimeout(function(){ window.print(); }, 350)">` — tự mở hộp thoại in sau 350ms (3505). Thanh nút sticky `.actions no-print` chứa 1 nút `พิมพ์ / Print` gọi `window.print()` (3506).

**Bố cục các section (3507-3516), thứ tự:**
1. `<h1>สรุปการคำนวณและใบเสนอราคา / Calculation & Quotation Summary</h1>`
2. `<p class="subtitle">จัดทำเมื่อ / Generated: {YYYY-MM-DD HH:MM}</p>` (timestamp 3484)
3. `<h2>ข้อมูลลูกค้าและสินค้า / Customer & Product</h2>` + bảng `identity_rows`
4. `<h2>ผลคำนวณและราคา / Calculation & Pricing</h2>` + bảng `class="price"` `result_rows`
5. `<p class="note">น้ำหนักต่อแพ็ก (กก.) = กรัมต่อชิ้น × ชิ้นในแพ็ก ÷ 1,000 / Pack Weight (kg) = grams per item × pieces per pack ÷ 1,000</p>`
6. `<h2>สูตรที่บันทึก / Saved Formulas</h2>` + bảng 2 hàng: `สูตรน้ำหนัก / Weight Formula` và `สูตรราคา / Price Formula` (3516)

Mỗi hàng bảng = `<tr><th>{nhãn}</th><td>{giá trị}</td></tr>` (3479-3482).

**Bảng 1 — identity_rows (3387-3414), thứ tự nhãn nguyên văn:**
1. `เลขอ้างอิง / Quote Ref`
2. `วันที่ / Date`
3. `รหัสลูกค้า / Customer Code`
4. `ชื่อลูกค้า/บริษัท / Customer/Company`
5. `รายการสินค้า / Item`
6. `รหัสสินค้า / Part Number`
7. `ประเภทสินค้า / Product Type`
8. `ขนาด / Size`
9. `ความหนา / Thickness` — giá trị: `{value} {unit} • ` + (`ต่อคู่ / Per Pair` nếu mode pair, ngược lại `ต่อด้าน / Per Side`); riêng sản phẩm `cover` → `ไม่ใช้ / Not applicable` (3396-3409)
10. `หน่วยขาย / Selling Unit` = sale_basis
11. (chỉ khi là revision) `แก้ไขจาก / Revised From` (3412-3414)

**Bảng 2 — result_rows (3416-3477), thứ tự:**
1. `น้ำหนักต่อชิ้น / Grams per item` → `{:,.3f} กรัม / g`
2. `จำนวนมาตรฐานต่อกก. / Standard items per kg` → `{:,.2f}`
3. `จำนวนหลังหัก {deduction:g}% / Adjusted items per kg` → `{:,.2f}` + ` (เปิด / ON)` hoặc ` (ปิด / OFF)` (3419-3423)
4. `ฐาน/สูตรคำนวณราคา / Price Basis or Formula` = `price_basis_summary` hoặc fallback công thức giá (3425-3426)
5. (nếu có) `ลำดับตรวจสอบสูตร / Human-readable Verification` = verification_summary (3427-3430)
6. **Nếu bán theo kg** (3431-3437): `ราคาขายจริงต่อกิโลกรัม / Final selling price per kg` → `{:,.3f} บาท`
7. **Nếu bán theo chiếc** (3438-3458), 3 hàng: `ราคาฐานต่อกิโลกรัม / Price basis per kg` → `{:,.3f} บาท` · `ราคาต่อชิ้นที่คำนวณได้ / Calculated price per piece` → `{:,.3f} บาท` · `ราคาขายจริงต่อชิ้น / Final selling price per piece` → `{:,.3f} บาท`
8. `บรรจุต่อแพ็ก / Pieces per pack` → `{pack_qty:,.0f} ชิ้น • {pack_weight:,.4f} กก.` hoặc `ยังไม่ได้กำหนด / Not Set` (3460-3477)
9. `บรรจุต่อกระสอบ / Pieces per sack` → cùng định dạng với sack

### 2.3 `_open_print_preview` (app.py:3519-3536)

Ghi file HTML vào `{app_data}/print_previews/{safe_ref}-{YYYYMMDD-HHMMSS-ffffff}.html` (safe_ref: ký tự alnum/`-_`, còn lại thay `-`, cắt 60 ký tự, fallback `quotation`); mở bằng `os.startfile`, fallback `webbrowser.open`. Status:
```
เปิดตัวอย่างพิมพ์ในเบราว์เซอร์แล้ว—โปรแกรมยังเปิดอยู่ด้านหลัง / Print preview opened in the browser; this app remains open behind it
```

### 2.4 `print_current_summary` (app.py:3538-3565)

Thứ tự: **lưu nháp trước** (`_save_form_draft`) → validate header → tính. Nếu payload None → status `พิมพ์ไม่ได้: กรุณากรอกสเปกและคำนวณให้ครบ / Print requires complete specs and a successful calculation` (3544-3547). ValueError → messagebox tiêu đề `ข้อมูลยังไม่ครบ / Incomplete Data`, thân `กรุณากรอกข้อมูลและคำนวณก่อนพิมพ์ / Complete the form and calculate before printing:\n{exc}` + status `บันทึกร่างแล้ว แต่ยังพิมพ์ไม่ได้จนกว่าข้อมูลจะครบ / Draft saved; complete the required fields before printing` (3549-3557). OSError → messagebox `เปิดหน้าพิมพ์ไม่สำเร็จ / Print Preview Failed` / `ไม่สามารถเปิดหน้าตัวอย่างพิมพ์ได้ / Unable to open print preview: {exc}` (3559-3565).

### 2.5 `print_selected_quote` (app.py:3669-3681)

In lại bản đã lưu chọn từ lịch sử; không chọn gì → return im lặng. OSError → cùng messagebox `เปิดหน้าพิมพ์ไม่สำเร็จ / Print Preview Failed` như trên (3675-3681).

---

## 3. Nháp (Draft)

### 3.1 `_save_form_draft` (app.py:3567-3598)

Ghi `{app_data}/drafts/latest_pricing_draft.json` (1 file duy nhất, ghi đè). JSON pretty (indent 2, giữ Unicode). Trường: `saved_at` (ISO giây), customer_code, customer, quote_date, product_label, item_description, product_reference, `dimensions` (mỗi field `{value, unit}`), `thickness` `{value, unit, mode}`, sale_basis, density, material_price, deduction_percent, apply_deduction (bool), selling_price_piece, selling_price_kg. **Không** lưu công thức, không lưu pack/sack.

### 3.2 `restore_latest_draft` (app.py:3600-3667)

- Không có file → messagebox warning `ไม่พบร่าง / Draft Not Found` / `ยังไม่มีร่างล่าสุดให้เปิด / No latest draft is available.` (3604-3608).
- Có file → hỏi Yes/No: tiêu đề `เปิดร่างล่าสุด / Restore Latest Draft`, thân 2 dòng:
  ```
  ข้อมูลที่กำลังกรอกในฟอร์มนี้จะถูกแทนด้วยร่างล่าสุด
  Replace the current form with the latest draft?
  ```
  (3610-3615). Từ chối → không làm gì.
- Đọc lỗi → messagebox `เปิดร่างไม่สำเร็จ / Restore Failed` / `ไม่สามารถอ่านร่างล่าสุดได้ / Unable to read the latest draft: {exc}` (3621-3626).
- Khôi phục: mọi trường về form; product_label không hợp lệ → fallback loại `flat` (3631-3632); thickness unit mặc định `มม.` (3643); mode label → `ต่อคู่ / Per Pair` hoặc `ต่อด้าน / Per Side` (3645-3647); sale_basis mặc định `ขายเป็นกิโลกรัม / Sell by kg` (3649).
- Sau khôi phục: `editing_source_ref = ""`; `current_quote_ref` = `ร่างล่าสุด—ยังไม่บันทึก / Latest Draft—Unsaved` (3658); `last_result = None`; status:
  ```
  เปิดร่างล่าสุดแล้ว—ตรวจข้อมูลและกดคำนวณก่อนบันทึก / Latest draft restored; review and Calculate before Save
  ```
  (3663-3665); tự chuyển về tab tính giá (`main_tabs.select(calc_frame)`, 3666).

---

## 4. Màn đăng nhập — gate.py (TOÀN BỘ)

**Nguyên tắc:** chạy TRƯỚC khi build cửa sổ chính; đóng cửa sổ = thoát chương trình, không có "tiếp tục không đăng nhập" (docstring 1-21, `WM_DELETE_WINDOW` → close_program, dòng 239).

**Cửa sổ (102-106):** tiêu đề `เข้าสู่ระบบ / Sign in — PantongOne` (`"เข้าสู่ระบบ / Sign in — " + app_title`), nền `BG #f4f6f8`, không resize, có icon app. Căn giữa ngang màn hình, dọc ở 1/3 trên (255-258); topmost 200ms đầu rồi thả (260-261).

**Styles ttk theme clam (113-119):**
| Style | Màu chữ | Font |
|---|---|---|
| `Gate.TLabel` | NAVY `#16324f` | Segoe UI 10 |
| `GateTitle.TLabel` | NAVY | Segoe UI 15 **bold** |
| `GateMuted.TLabel` | MUTED `#5f6b76` | Segoe UI 9 |
| `GateError.TLabel` | RED `#b42318` | Segoe UI 9 |
| `GateWork.TLabel` | BLUE `#1f6aa5` | Segoe UI 9 |
| `GateWarn.TLabel` | AMBER `#8a5a00` | Segoe UI 9 |

Tất cả nền `BG`. Frame ngoài padding **26** (121).

**Header (125-152):** logo PNG 256px subsample 4 → **64px**, bên trái, padx phải 14 (129-139). Bên phải 3 dòng:
1. Tiêu đề = `PantongOne` (GateTitle)
2. Phụ đề = `โปรแกรมคำนวณราคาพลาสติก / Plastic pricing` (GateMuted)
3. Dòng phiên bản+server (GateMuted): `"v" + version.split(" ")[0] + "  •  " + server_host` → hiện tại: `v1.7.1  •  download.pantongone.com` (chú ý 2 dấu cách quanh `•`, dòng 150)

**Form (154-167):**
- Nhãn `อีเมล / Email` + Entry width 34, font Segoe UI 10, tự điền email đăng nhập lần trước (`credentials.last_email`)
- Nhãn `รหัสผ่าน / Password` + Entry `show="•"` (che bằng bullet), width 34, pady trên 8
- Nhãn cột trái, ô cột phải padx trái 12

**Dòng thông báo (169-171):** label `GateError.TLabel`, `wraplength=380`, justify left, pady trên 10. Đổi style động: đang xử lý → `GateWork.TLabel` (xanh BLUE) text `กำลังตรวจสอบ… / checking…` (210-213, 228); lỗi → `GateError.TLabel` đỏ + focus lại ô mật khẩu (215-218).

**Câu lỗi verbatim:**
- Thiếu email/mật khẩu: `กรอกอีเมลและรหัสผ่าน / enter the email and the password` (224)
- Server từ chối / offline từ chối: message từ `ServerError` hoặc `credentials.verify_offline` (`decide` 59-89 — lưu ý: server trả lời "từ chối" thì KHÔNG fallback offline)

**Cảnh báo offline (LAW P9 — luôn hiện, không tooltip; 176-190):** chỉ hiện khi số ngày còn lại ≤ 3, style `GateWarn.TLabel` (amber), wraplength 380:
```
เครื่องนี้ออฟไลน์มา {days} วัน เหลืออีก {left} วันต้องต่อเน็ต / offline {days} days - connect within {left}
```

**Hàng nút (192-208):** trái = label GateMuted `ยังไม่มีบัญชี ติดต่อผู้ดูแล / No account? ask your administrator`; phải = 2 nút: `ออก / Exit` rồi `เข้าสู่ระบบ / Sign in` (Sign in ngoài cùng phải). Enter = Sign in (238). Khi bấm: nút disabled trong lúc kiểm tra (227), thất bại thì enable lại (231).

**Focus ban đầu (252):** có email cũ → focus ô mật khẩu; chưa có → focus ô email.
**Update (241-250):** 500ms sau khi mở, tự kiểm tra bản mới và mời cập nhật (trước khi nhập mật khẩu).
**Session offline:** nhãn người dùng có hậu tố ` (ออฟไลน์ / offline)` (52-56).

Timeout đăng nhập `SIGN_IN_TIMEOUT = 12` giây (config.py:48).

---

## 5. Custom widgets — widgets.py

### 5.1 `SuggestEntry` (32-367) — ô nhập có dropdown gợi ý

**Hình thức trực quan:**
- Là `ttk.Entry` thường; danh sách gợi ý là **cửa sổ nổi không viền tiêu đề** (`overrideredirect`, topmost) ngay **dưới mép dưới** ô nhập, thẳng mép trái (x = rootx của ô, y = rooty + height; 128-131).
- Rộng = max(độ rộng ô, **260px**) (130). Cao = đúng số dòng, tối đa **12 dòng** (`MAX_SUGGESTIONS=12`, dòng 29, 123).
- Popup bọc trong frame style `Field.TFrame` padding **1** → tạo viền mảnh 1px quanh list (101).
- Listbox: nền `#ffffff`, chữ `#16324f` (NAVY), dòng được chọn nền `#1f6aa5` (BLUE) chữ `#ffffff`, font Segoe UI 9, không viền focus (103-113). Mở list là dòng đầu được chọn sẵn (125-126).
- **KHÔNG có 2 cột riêng** — mỗi dòng là 1 chuỗi `shown` (tên hiển thị); `payload` (mã khách) đi kèm ngầm, khi chọn sẽ gọi `on_pick(payload)` để điền ô mã khách bên cạnh (36-38, 341-359). Web nên vẽ 1 cột text.

**Hành vi:**
- Chỉ mở khi NGƯỜI GÕ (phím in được, Backspace, Delete, hoặc Paste) — chương trình tự điền form thì KHÔNG bật list (232-272). Ô rỗng khi gõ → đóng list (260-264).
- Phím: **Down** mở list (kể cả ô rỗng = duyệt toàn bộ) / di xuống; **Up** di lên; **Enter** chọn dòng (nếu list đóng thì Enter đi tiếp cho màn hình, vd Search); **Escape** đóng, GIỮ nguyên chữ đã gõ; không cướp Tab (285-318, docstring 19-21).
- Click chuột vào dòng = chọn (115). Chọn xong: điền text, con trỏ về cuối, đóng list, gọi on_pick (341-359).
- Lookup lỗi → đóng list im lặng, không bao giờ chặn việc gõ (265-271).
- Watchdog 120ms: list tự đóng khi ô bị che/cuộn/kéo cửa sổ/mất focus (155-205). FocusOut trễ 120ms để không nuốt cú click vào dòng (320-339).
- Có method `open_list()` cho nút mũi tên cạnh ô (217-228).

**`customer_matches` (369-393):** lọc gợi ý — dữ liệu đã xếp theo tần suất; tên **bắt đầu bằng** chuỗi gõ xếp trước, sau đó mới đến chứa trong tên hoặc trong mã; rỗng → trả cả danh sách (giới hạn 12).

### 5.2 `FlowFrame` (396-480)

Container xếp con **trái → phải, tự xuống hàng** khi hẹp (toolbar 9 nút không bị tràn mất nút). Khoảng cách mặc định `gap=6px` ngang, 4px dọc dưới mỗi hàng, con căn trái (`sticky="w"`) (411, 470-477). Chỉ re-layout khi số cột vừa thay đổi (chống giật khi kéo cửa sổ). **Web tương đương: `display:flex; flex-wrap:wrap; gap:4px 6px; align-items:start`.**

### 5.3 `follow_width` (483-510)

Giữ `wraplength` của label = độ rộng thật của container trừ `slack=24px`, sàn `floor=120px`; chỉ cập nhật khi lệch > 8px. **Web tương đương: text tự wrap theo container, `min-width:120px`** — không cần code gì thêm ngoài không đặt width cứng.

---

## 6. Cửa sổ Server — server_ui.py (tóm nhanh)

Màn này có thể không cần trên web, nhưng **`status_var` hiện trên toolbar chính** thì cần:

### 6.1 `status_var` toolbar (59, 64-79) — QUAN TRỌNG
```
{who} • ค้างในเครื่อง / waiting here: {total}
```
- `who` = tên/email người đăng nhập (kèm ` (ออฟไลน์ / offline)` nếu offline), hoặc `ยังไม่เข้าสู่ระบบ / not signed in` (78)
- `total` = số quotations + drawings chưa sync. LAW P9: luôn hiện, không tooltip.

### 6.2 Sync (116-152)
- Sau sync, status dòng chính (`action_status_var`) = `sync.describe(...)` (file sync.py, ngoài phạm vi). Lỗi → messagebox warning tiêu đề `ซิงค์ / Sync` (152).
- Có bản mới → `มีเวอร์ชันใหม่ v{newest} / A newer version is available — {base_url}/download` (+ `  ({why})` nếu có lý do; 87-92).
- Token hết hạn (401) giữa phiên → mở dialog đăng nhập lại rồi sync tiếp (128-131).

### 6.3 Dialog đăng nhập giữa phiên (156-222)
Toplevel `เข้าสู่ระบบ / Sign in`, không resize, padding 16. Hàng 1: nhãn `เซิร์ฟเวอร์ / Server` + host màu `#1f6aa5`. Hàng 2-3: `อีเมล / Email`, `รหัสผ่าน / Password` (show `•`, width 34). Dòng lỗi đỏ `#b42318` wraplength 320. Nút phải-dưới: `ยกเลิก / Cancel` · `เข้าสู่ระบบ / Sign in`. Enter = đăng nhập. Không có fallback offline.

### 6.4 Đăng xuất (226-253)
Hỏi askyesno tiêu đề `ออกจากระบบ / Sign out`, dòng đầu `ออกจากระบบและปิดโปรแกรม / Sign out and close the program?`; nếu còn việc chưa sync thêm 4 dòng (243-246):
```
ยังมีงานค้างในเครื่องนี้ {total} รายการ ที่ยังไม่ได้ส่งขึ้นเซิร์ฟเวอร์
{total} item(s) here have not been sent to the server yet.
งานไม่หาย แต่จะต้องเข้าสู่ระบบใหม่จึงจะส่งได้
Nothing is lost - but it will take another sign-in to send them.
```
Đồng ý → quên tài khoản, đóng app (đăng xuất = thoát chương trình).

### 6.5 Cửa sổ Settings `เซิร์ฟเวอร์ / Server` (257-331)
Chỉ HIỂN THỊ, không sửa được:
- `ที่อยู่เซิร์ฟเวอร์ / Server address` + URL màu `#1f6aa5`; chú thích muted `#5f6b76`: `ที่อยู่มากับตัวโปรแกรม แก้ในหน้านี้ไม่ได้ / the address ships with the build and cannot be changed here`
- `เวอร์ชัน / Version` + `v{app_version}` màu `#16324f`
- `เข้าสู่ระบบเป็น / Signed in as` + tên màu `#16324f`
- Nếu offline, dòng amber `#8a5a00`: `โหมดออฟไลน์ ส่งขึ้นเซิร์ฟเวอร์ไม่ได้จนกว่าจะเข้าสู่ระบบออนไลน์ (เหลือ {n} วัน) / offline - signing in online is needed before anything can be sent`
- Kết quả Test: `√ ต่อได้ / reachable — {version}` hoặc `× {lỗi}` (315-317)
- 4 nút: `ตรวจอัปเดต / Check for update` · `ทดสอบ / Test` · `ออกจากระบบ / Sign out` · `ปิด / Close`

---

## 7. Ghi chú cho bản web

1. ⚠️ **Phiên bản thực tế trong code là `1.7.1 (Phase 1) — Planning screen`** (app.py:51), không phải 1.5.1 như brief — cần xác nhận bản nào là chuẩn để clone.
2. Ký tự đặc biệt phải giữ đúng: `•` (cả trong ô mật khẩu), `—`, `–` (range), `−` (dấu trừ Unicode ở deduction ON), `»`, `√`, `×`, `!`, `…`, và 2 dấu cách quanh `•` ở dòng version gate.
3. Định dạng số: nghìn có phẩy; gram/giá `.3f`, items/kg `.2f`, pack weight `.4f`, số lượng `.0f`, `%g` cho phần trăm và kích thước.
4. Font hệ: UI dùng Segoe UI (9/10/15bold); trang in dùng `"Leelawadee UI", "Tahoma", sans-serif` 14px/1.45.
5. Trang in tự gọi `window.print()` sau 350ms khi mở — web nên giữ hành vi này.

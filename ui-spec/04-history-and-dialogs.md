# 04 — Tab "ประวัติ / Quote History" + các cửa sổ dialog

> Nguồn: `Z:\1\app.py` (PantongOne, `APP_VERSION = "1.7.1 (Phase 1) — Planning screen"` — dòng 51).
> Mọi chuỗi trong file này là NGUYÊN VĂN từ mã nguồn. Số dòng ghi kèm làm bằng chứng.

---

## 0. Bảng màu gốc (app.py:88-93)

| Tên | Hex |
|---|---|
| `BG` | `#f4f6f8` |
| `NAVY` | `#16324f` |
| `BLUE` | `#1f6aa5` |
| `GREEN` | `#167d5a` |
| `RED` | `#b42318` |
| `MUTED` | `#5f6b76` |

Style liên quan tab này (app.py:281-374):

- `Card.TFrame`: nền `white`, viền solid 1px (281). `Field.TFrame`: nền `white`, không viền (282). `Card.TLabel`: nền `white` (285).
- `Warning.TLabel`: chữ `#9a6700` đậm ("Leelawadee UI" 10 bold), nền `white` (315-320).
- `Critical.TLabel`: chữ `white` đậm, **nền `RED` `#b42318`**, padding (8, 6) (321-327).
- `Danger.TButton`: nền `RED`, chữ trắng, "Leelawadee UI" 10 bold; hover `#8f1d14`, pressed `#73180f` (328-333).
- `Muted.TLabel`: chữ `MUTED` `#5f6b76` (334).
- `Accent.TButton`: nền `BLUE`, chữ trắng, "Leelawadee UI" 10 bold, padding (12, 7); hover `#174f7a`, pressed `#123e60`, disabled chữ `#d0d5dd` (335-341).
- `Treeview` chung: `rowheight=30`; heading "Leelawadee UI" 10 bold (342-343).
- **`History.Treeview`: `rowheight=31`, viền solid 1px** (344).
- `Vertical.TScrollbar`: width 22, arrowsize 18 (345).
- `History.Section.TLabel`: nền **`#5b4b8a`** (tím), chữ trắng "Leelawadee UI" 11 bold, padding (10, 7) (358-374).
- `Product.Section.TLabel`: nền **`#185a8d`**, cùng font/padding (359, 367-374).

Tên tab trên Notebook: `ประวัติ / Quote History` (app.py:516).

`HISTORY_PAGE = 500` — số dòng tối đa mỗi lần đổ bảng (app.py:55).

---

## 1. Khối bộ lọc — `_build_history` (app.py:2425-2506)

Khung `Card.TFrame` padding 12, pack fill-x, pady (0, 10) (2426-2427).

Tiêu đề khối (2437-2441), style `History.Section.TLabel`:

```
ค้นหาและจัดการประวัติใบเสนอราคา / Search & Manage Quotation History
```

Các ô lọc nằm trong `FlowFrame` (tự xuống dòng khi hẹp — 2449-2452). **Thứ tự trái → phải:**

| # | Nhãn (verbatim) | Widget | Ghi chú |
|---|---|---|---|
| 1 | `ลูกค้า/รหัส / Customer/Code` | `SuggestEntry` (ô nhập có gợi ý khách hàng) | Chọn 1 gợi ý → gọi `refresh_history()` ngay (2460-2468) |
| 2 | `วันที่เริ่ม / From` | `ttk.Entry` | |
| 3 | `วันที่สิ้นสุด / To` | `ttk.Entry` | |
| 4 | `ขนาด / Size` | `ttk.Entry` | |
| 5 | `รหัส/รายการ / Part/Item` | `ttk.Entry` | |
| 6 | `ประเภท / Product Type` | `ttk.Combobox` readonly (2473-2481) | Giá trị mặc định `ทุกประเภท / All Types` |
| 7 | `เรียงตาม / Sort` | `ttk.Combobox` readonly (2482-2496) | Mặc định `วันที่ล่าสุด / Newest` |

Nhãn đặt TRÊN ô nhập (pack anchor-w), ô nhập pady (3, 0) (2457-2471).

**Hành vi lọc: KHÔNG lọc khi gõ.** Lọc chạy khi: (a) nhấn **Enter** trong bất kỳ ô Entry nào (2472), (b) bấm nút `ค้นหา / Search`, (c) chọn gợi ý khách hàng trong ô 1 (2467). Combobox không tự trigger — phải bấm Search/Enter.

Giá trị combobox **ประเภท / Product Type** (2479, danh sách `PRODUCTS` calculator.py:11-17):

```
ทุกประเภท / All Types
ถุงพลาสติกเปิดปากตรง (Plastic Bag)
แผ่นพลาสติก (Plastic Sheet)
ถุงพับข้าง (Gusset Bag)
ม้วนพลาสติก (Plastic Roll)
ถุงคลุมสินค้า (Product Cover)
```

Giá trị combobox **เรียงตาม / Sort** (2488-2494), map sang sort_key (3962-3968):

```
วันที่ล่าสุด / Newest      → date_desc (mặc định)
วันที่เก่าสุด / Oldest     → date_asc
ลูกค้า / Customer          → customer
ประเภทสินค้า / Product     → product
ขนาด / Size               → size
```

Hàng nút dưới bộ lọc (2497-2506), pady (10, 0):

- `ค้นหา / Search` → `refresh_history` (2497)
- `ล้างตัวกรอง (ไม่ลบรายการ) / Clear Filters (does not delete)` → `clear_history_filters` (2500-2503)

`clear_history_filters` (4048-4056): đặt lại 5 ô text = rỗng, product = `ทุกประเภท / All Types`, sort = `วันที่ล่าสุด / Newest`, rồi gọi `refresh_history()`.

`_search_product_key` (3954-3959): tra ngược nhãn combobox → key sản phẩm; không khớp (tức "ทุกประเภท") trả `""`.

---

## 2. Bảng kết quả (app.py:2508-2592, 3979-4034)

- Khung chứa cố định `width=900, height=420`, `grid_propagate(False)` — bảng KHÔNG được nong rộng cửa sổ (2520-2525).
- `ttk.Treeview` style `History.Treeview` (rowheight 31, viền solid 1px), `show="headings"` (2543-2545).
- Có cả scrollbar dọc + ngang (2583-2588). Mọi cột `anchor="w"` (căn TRÁI), `minwidth=70` (2582).
- Double-click 1 dòng → `view_selected_quote` (2591). Đổi selection → `_on_history_selection_changed` (2592).
- `iid` của mỗi dòng = `quote_ref` (4008).

**15 cột theo đúng thứ tự** (2526-2579), heading verbatim + width:

| # | id | Heading (verbatim) | Width | Định dạng giá trị (refresh_history 3980-4034) |
|---|---|---|---|---|
| 1 | `ref` | `เลขอ้างอิง / Ref` | 145 | `quote_ref` nguyên văn |
| 2 | `date` | `วันที่ / Date` | 95 | `quote_date` nguyên văn (ISO `YYYY-MM-DD`) |
| 3 | `customer_code` | `รหัสลูกค้า / Code` | 100 | nguyên văn |
| 4 | `customer` | `ชื่อลูกค้า/บริษัท / Customer/Company` | 150 | nguyên văn |
| 5 | `sale_unit` | `หน่วยขาย / Selling Unit` | 145 | `sale_basis` từ inputs; mặc định `ขายเป็นกิโลกรัม / Sell by kg` (3984) |
| 6 | `item` | `รายการ/รหัส / Item/Part` | 180 | `item_description` + `" / "` + `product_reference` (bỏ phần rỗng) (4015-4019) |
| 7 | `product` | `ประเภท / Product` | 220 | `product_label` |
| 8 | `size` | `ขนาด / Size` | 230 | `size_text` |
| 9 | `thickness` | `ความหนา / Thickness` | 155 | `"{value} {unit} • ต่อคู่ / Per Pair"` hoặc `"... • ต่อด้าน / Per Side"`; không có thickness → `ไม่ใช้ / N/A` (3996-4004) |
| 10 | `grams` | `กรัม/ชิ้น / g/Item` | 85 | `{:,.3f}` (3 số lẻ, có dấu phẩy nghìn) (4023) |
| 11 | `price_basis` | `ฐาน/สูตรคำนวณ / Price Basis/Formula` | 300 | `price_basis_summary` (3990-3992) |
| 12 | `calc_price` | `ผลราคาที่คำนวณ / Calculated Result` | 125 | bán theo kg → `calculated_price_per_kg` `{:,.3f}`; bán theo chiếc → `calculated_piece` `{:,.3f}` (4025-4027) |
| 13 | `price_kg` | `ราคา/กก. / Price/kg` | 105 | bán theo kg → `price_per_kg` `{:,.3f}`; ngược lại → `—` (4028-4030) |
| 14 | `price` | `ราคาขายจริง/ชิ้น / Final Price/Piece` | 125 | bán theo kg → `—`; ngược lại → `unit_price` `{:,.3f}` (4031) |
| 15 | `pack` | `น้ำหนักต่อแพ็ก (กก.) / Pack Weight (kg)` | 85 | `pack_quantity > 0` → `pack_weight_kg` `{:,.4f}` (4 số lẻ); không → `—` (4032) |

Cờ "bán theo kg": `sale_basis.startswith("ขายเป็นกิโลกรัม")` (3985).

---

## 3. Dòng đếm / status (app.py:2619, 4039-4046)

Biến `history_count_var`, hiện style `Muted.TLabel`, nằm **bên PHẢI** hàng nút (2619-2620). Giá trị khởi tạo: `0 รายการ / records` (2619).

- Khi số dòng < 500: `f"{len(rows):,} รายการ / records"` — ví dụ `123 รายการ / records` (4046).
- Khi đầy trang (>= `HISTORY_PAGE` 500) (4039-4044):

```
แสดง {len(rows):,} จากทั้งหมด {total:,} รายการ — ใช้ตัวกรองเพื่อค้นหา / showing {len(rows):,} of {total:,} — narrow with the filters above
```

(số có dấu phẩy nghìn; `total` = `db.count_quotations()`).

---

## 4. Hàng nút dưới bảng (app.py:2593-2618) + trạng thái enable

Frame padding (0, 10, 0, 0), pack fill-x. **Thứ tự trái → phải:**

| Nhãn (verbatim) | Lệnh | Enabled khi |
|---|---|---|
| `รายละเอียด / Details` | `view_selected_quote` | luôn enabled (2595) |
| `แก้ไข / Edit` | `load_selected_quote` | khởi tạo `disabled`; bật khi có dòng được chọn (2596-2599) |
| `พิมพ์รายการที่เลือก / Print Selected` | `print_selected_quote` | khởi tạo `disabled`; bật khi có selection (2600-2606) |
| `ลบรายการที่เลือก / Delete Selected` | `delete_selected_quote` | khởi tạo `disabled`; bật khi có selection (2607-2613) |
| `บริษัทที่เคยเสนอ / Related Companies` | `show_related_for_selected_quote` | luôn enabled (2614-2618) |

`_on_history_selection_changed` (4065-4069): có selection → `normal`, không → `disabled` cho đúng 3 nút Edit / Print Selected / Delete Selected.

Dòng chú thích dưới cùng của tab (2621-2630), style `Muted.TLabel`, `wraplength=1250`:

```
แก้ไข / Edit: โหลดรายการเดิมเพื่อแก้ไข คำนวณใหม่ และเก็บเป็นฉบับใหม่ที่เชื่อมต้นฉบับ—รายการเดิมจะไม่ถูกลบหรือเขียนทับ / Loads a linked revision; the original is preserved.
```

### `_selected_quote` (4058-4063)

Không chọn dòng nào → messagebox warning, title `เลือกรายการ / Select`, nội dung `กรุณาเลือกใบเสนอราคา / Please select a quotation`.

### `delete_selected_quote` (4071-4099)

1. Hộp xác nhận yes/no — title `ยืนยันการลบ / Confirm Delete`, nội dung (2 dòng):

```
ต้องการลบใบเสนอราคา {quote_ref} ถาวรหรือไม่?
Delete this quotation permanently? This cannot be undone.
```

2. Xóa thành công → refresh bảng, status: `ลบแล้ว / Deleted: {quote_ref}` (4086); messagebox info title `ลบแล้ว / Deleted`, nội dung `ลบใบเสนอราคาแล้ว / Quotation deleted: {quote_ref}` (4087-4091).
3. Không tìm thấy → messagebox warning title `ไม่พบรายการ / Record Not Found`, nội dung `ไม่พบรายการที่เลือก อาจถูกลบไปแล้ว / The selected record may already have been deleted.` (4095-4099).

---

## 5. Cửa sổ xem chi tiết — `view_selected_quote` (app.py:4101-4169)

Toplevel, title: `รายละเอียด / Details — {quote_ref}` (4164), kích thước `760x650` (4165). Nội dung là `tk.Text` wrap word, padx/pady 18, chỉ đọc (`state="disabled"`) (4166-4169).

**Nội dung, ĐÚNG thứ tự từng dòng** (4113-4156; `{}` là chỗ điền dữ liệu; trường rỗng thay bằng `-`):

```
เลขอ้างอิง / Quote Ref: {quote_ref}
วันที่ / Date: {quote_date}
ชื่อลูกค้า/บริษัท / Customer/Company: {customer}
รหัสลูกค้า / Customer Code: {customer_code|-}
รายการ / Item: {item_description|-}
รหัสสินค้า / Part Number: {product_reference|-}
แก้ไขจาก / Revised from: {revised_from_ref|-}
รูป/ไฟล์ / Image/File: {product_image_path|-}
ประเภท / Product Type: {product_label}
ขนาด / Size: {size_text}
ความหนา / Thickness: {value} {unit} • ต่อคู่ / Per Pair   (hoặc • ต่อด้าน / Per Side)
จุดอ้างอิง / Length Reference: {length_reference|-}
ค่าบวกก้นถุง / Bottom Allowance: {value:g} {unit}          (unit mặc định ซม.)
                                                            (dòng trống)
ผลคำนวณ / Results
  หน่วยขาย / Selling Unit: {sale_basis}                     (mặc định ขายเป็นกิโลกรัม / Sell by kg)
  ความยาววัสดุ / Material Length: {material_length_cm:,.3f} ซม.
  จำนวนมาตรฐานต่อกก. / Standard Items per kg: {items_per_kg:,.2f}
  การหักเผื่อ / Deduction: เปิด / ON ({deduction_percent:g}%)   (hoặc ปิด / OFF)
  จำนวนชิ้นต่อกก.หลังหัก {deduction_percent:g}% / Items per kg after deduction: {production_items_per_kg:,.2f}
  ฐาน/สูตรที่ใช้คำนวณ / Price Basis/Formula: {price_basis_summary}
```

Tiếp theo, RẼ NHÁNH theo đơn vị bán (4135-4142):

- Bán theo kg (sale_basis bắt đầu `ขายเป็นกิโลกรัม`) — 1 dòng:

```
  ราคาขายจริงต่อกิโลกรัม / Final Selling Price per kg: {selling_price_per_kg:,.3f} บาท
```

- Bán theo chiếc — 2 dòng:

```
  ราคาต่อชิ้นที่คำนวณได้ / Calculated Price per Piece: {calculated_piece:,.3f} บาท
  ราคาขายจริงต่อชิ้น / Final Selling Price per Piece: {unit_price:,.3f} บาท
```

Rồi tiếp (4143-4155):

```
  ราคารวม / Total Price: {total_price:,.3f} บาท
  แพ็ก / Pack: {pack_quantity:,.0f} ชิ้น / pieces • {pack_weight_kg:,.4f} กก. / kg      (nếu pack_quantity>0, không thì:  แพ็ก / Pack: ยังไม่ได้กำหนด / Not Set)
  กระสอบ / Sack: {sack_quantity:,.0f} ชิ้น / pieces • {sack_weight_kg:,.4f} กก. / kg    (nếu sack_quantity>0, không thì:  กระสอบ / Sack: ยังไม่ได้กำหนด / Not Set)
  วัตถุดิบ / Required Material: {required_kg:,.3f} กก. / kg
  สถานะควบคุม / Control Status: {control_status}
                                                            (dòng trống)
สูตรที่บันทึก / Saved Formulas
  น้ำหนัก / Weight = {formulas.weight}
  ราคา / Price = {formulas.price}
```

Riêng sản phẩm `cover` thêm cuối (4157-4162):

```
                                                            (dòng trống)
พื้นที่หลังคา / Roof Area: {roof_area_cm2:,.3f} ตร.ซม.
พื้นที่ตาข่าย / Mesh Area: {mesh_area_cm2:,.3f} ตร.ซม.
```

---

## 6. Cảnh báo trùng + cửa sổ Related — `_update_related_quote_alert` (3088-3127), `show_related_quotes` (3129-3234)

### 6a. Dòng cảnh báo trên màn tính giá (3104-3127)

3 trạng thái (preview = tối đa 3 tên công ty, nhiều hơn nối thêm ` และอีก {n} บริษัท`):

1. **Trùng CHÍNH XÁC Part No. + Size** — label style `Critical.TLabel` (chữ trắng nền đỏ), nút style `Danger.TButton` enabled:

```
! พบรายการซ้ำ: รหัสสินค้าและขนาดเดียวกัน / DUPLICATE Part No. + Size — {n} ใบ / quotes — {preview}
```

2. **Chỉ khớp lịch sử** — label `Warning.TLabel`, nút `TButton` enabled:

```
• พบประวัติตรงกัน / Matching history: {n} ใบเสนอราคา / quotes — {preview}
```

3. **Không khớp** — label `Warning.TLabel`, nút disabled:

```
ยังไม่พบรายการตรงกัน / No matching Part No. or Item + Size found
```

### 6b. Cửa sổ danh sách Related (3129-3234)

- Không có rows → messagebox info title `ประวัติสินค้า / Product History`, nội dung `ยังไม่พบใบเสนอราคาเดิม / No matching quotation found` (3131-3137).
- Toplevel `1080x480` (3140). Title mặc định: `บริษัทที่เคยได้รับใบเสนอราคา / Related Companies` (3139); khi mở từ tab history (`show_related_for_selected_quote` 4171-4183) title là:

```
บริษัทที่เคยได้รับใบเสนอราคา / Related Companies — {product_reference | item_description | size_text}
```

- 2 dòng chữ đầu cửa sổ:
  - `Warning.TLabel` (3141-3145): `ข้อมูลประกอบการตัดสินใจ ไม่ขัดขวางการบันทึก / Informational only; saving remains available`
  - `Muted.TLabel` (3146-3150): `น้ำหนักต่อแพ็ก (กก.) = กรัมต่อชิ้น × ชิ้นในแพ็ก ÷ 1,000 / Pack Weight (kg) = grams per item × pieces per pack ÷ 1,000`
- Treeview style `History.Treeview`, chỉ scrollbar DỌC (3231-3234), mọi cột căn trái. **13 cột** (3153-3183):

| id | Heading (verbatim) | Width |
|---|---|---|
| `ref` | `เลขอ้างอิง / Quote Ref` | 155 |
| `date` | `วันที่ / Date` | 105 |
| `customer_code` | `รหัสลูกค้า / Code` | 120 |
| `customer` | `บริษัท / Company` | 180 |
| `sale_unit` | `หน่วยขาย / Selling Unit` | 150 |
| `item` | `รายการ/รหัส / Item/Part` | 220 |
| `size` | `ขนาด / Size` | 240 |
| `grams` | `กรัม/ชิ้น / g/Item` | 110 |
| `price_basis` | `ฐาน/สูตรคำนวณ / Price Basis/Formula` | 300 |
| `calc_price` | `ผลราคาที่คำนวณ / Calculated Result` | 150 |
| `price_piece` | `ราคาขายจริงต่อชิ้น / Final Price/Piece`* | 155 |
| `price_kg` | `ราคา/กก. / Price/kg` | 120 |
| `pack_kg` | `น้ำหนักต่อแพ็ก (กก.) / Pack Weight (kg)` | 165 |

*Heading verbatim dòng 3180: `ราคาขายจริง/ชิ้น / Final Price/Piece`.

Định dạng ô như bảng history (grams `{:,.3f}`, giá `{:,.3f}`, pack `{:,.4f}`); khác một chỗ: pack chưa đặt hiện `ยังไม่ได้กำหนด / Not Set` thay vì `—` (3226-3228). Cột giá theo đơn vị bán dùng `—` cho bên không áp dụng (3219-3225).

---

## 7. Record picker — `show_existing_record_picker` (3813-3939), `reuse_quote_reference` (3941-3952)

Toplevel title `เลือกข้อมูลเดิม / Use Existing Record` (3815), `1120x620`, minsize `900x520`, `transient` theo cửa sổ chính (3816-3818).

**Cấu trúc trên → dưới:**

1. Label style `Product.Section.TLabel` (nền `#185a8d` chữ trắng), wraplength 1000 (3820-3826):

```
ค้นหาและโหลดเป็นงานแก้ไขใหม่—ประวัติเดิมไม่ถูกเขียนทับ / Search and load into a new editable calculation; history is preserved
```

2. Hàng tìm kiếm: nhãn 2 dòng (3831-3835):

```
ชื่อลูกค้า / รหัสลูกค้า / ชื่อสินค้า / รหัสสินค้า
Customer Name / Code / Item / Product Code
```

   + `ttk.Entry` (focus sẵn khi mở, Enter = tìm — 3936, 3939) + nút `ค้นหา / Search` (3922).

3. Treeview style `History.Treeview`, scrollbar dọc + ngang, cột căn trái `minwidth=80` (3855-3877). **9 cột** (3844-3868):

| id | Heading (verbatim) | Width |
|---|---|---|
| `ref` | `เลขอ้างอิง / Ref` | 150 |
| `date` | `วันที่ / Date` | 95 |
| `customer_code` | `รหัสลูกค้า / Customer Code` | 130 |
| `customer` | `ลูกค้า / Customer` | 170 |
| `item` | `รายการสินค้า / Item` | 180 |
| `product_ref` | `รหัสสินค้า / Product Code` | 145 |
| `product` | `ประเภท / Product` | 200 |
| `size` | `ขนาด / Size` | 230 |
| `thickness` | `ความหนา / Thickness` | 135 |

   Cột thickness: `"{value} {unit} • ต่อคู่ / Per Pair"` hoặc `"... • ต่อด้าน / Per Side"` (3886-3890). Danh sách nạp ngay khi mở (3938). Double-click dòng = dùng luôn (3937).

4. Footer (3925-3934): trái = label đếm `Muted.TLabel`: `พบ {n:,} รายการ / {n:,} records` (3907). Phải, thứ tự pack: `ยกเลิก / Cancel` (ngoài cùng phải, 3928) rồi `ใช้ข้อมูลที่เลือกเป็นงานใหม่ / Use Selected as New` style `Accent.TButton` (3929-3934).

`use_selected` (3909-3920): chưa chọn dòng → warning title `เลือกรายการ / Select Record`, nội dung `กรุณาเลือกรายการเดิมที่ต้องการใช้ / Please select a past record`; có chọn → đóng cửa sổ, gọi `reuse_quote_reference(quote_ref)`.

`reuse_quote_reference` (3941-3952): clear filters → chọn dòng trong bảng history → `load_selected_quote()` → đặt lại ngày = hôm nay → ref hiển thị: `ใช้ข้อมูลเดิมเป็นงานใหม่ / New from: {quote_ref}`; status: `โหลดข้อมูลเดิมแล้ว—แก้ความหนา/ราคา คำนวณ และบันทึกเป็นฉบับใหม่ / Loaded; edit, calculate, and save as a new revision — {quote_ref}`. Không tìm thấy ref → lỗi `ไม่พบเลขอ้างอิง / Quote reference not found: {quote_ref}` (3945).

---

## 8. Formula help — `show_formula_help` (3795-3811)

Toplevel title `ตัวแปรสูตร / Formula Variables` (3806), `650x600`, `tk.Text` font `("Consolas", 10)` wrap word, padx/pady 16, chỉ đọc (3808-3811).

Nội dung verbatim (3796-3804; danh sách biến từ `FORMULA_VARIABLES` calculator.py:48-71, dạng `{name}  =  {description}` — 2 space quanh dấu `=`):

```
ตัวแปรที่ใช้ได้ในสูตร / Formula Variables

width_cm  =  ความกว้าง / Width (cm)
length_cm  =  ความยาวตามสเปก / Specification Length (cm)
material_length_cm  =  ความยาววัสดุคำนวณ / Material Length (cm)
bottom_allowance_cm  =  ค่าบวกก้นถุง / Bottom Allowance (cm)
height_cm  =  ความสูง / Height (cm)
gusset_cm  =  ขนาดพับข้าง / Gusset (cm)
sold_length_m  =  ความยาวโรล / Roll Length (m)
thickness_input_mm  =  ความหนาที่กรอก / Input Thickness (mm)
thickness_side_mm  =  ความหนาต่อด้าน / Per-side Thickness (mm)
thickness_pair_mm  =  ความหนาต่อคู่ / Pair Thickness (mm)
density_g_cm3  =  ความหนาแน่น / Density (g/cm³)
roof_area_cm2  =  พื้นที่หลังคา / Roof Area (cm²)
mesh_area_cm2  =  พื้นที่ตาข่าย / Mesh Area (cm²)
roof_area_m2  =  พื้นที่หลังคา / Roof Area (m²)
mesh_area_m2  =  พื้นที่ตาข่าย / Mesh Area (m²)
roof_gsm  =  น้ำหนักวัสดุหลังคา / Roof GSM
mesh_gsm  =  น้ำหนักตาข่าย / Mesh GSM
grams_per_item  =  น้ำหนักต่อชิ้น / Weight per Item (g)
material_price_per_kg  =  ราคาวัตถุดิบ / Material Price per kg
markup_percent  =  เปอร์เซ็นต์บวกเพิ่ม / Markup (%)
pack_quantity  =  จำนวนต่อแพ็ก / Pieces per Pack
deduction_percent  =  เปอร์เซ็นต์หักเผื่อผลิต / Production Deduction (%)

เครื่องหมาย / Operators: +  -  *  /  %  **  ( )
ฟังก์ชัน / Functions: abs, min, max, round, ceil, floor, sqrt

หมายเหตุ / Note: สูตรไม่สามารถเรียกไฟล์ อินเทอร์เน็ต หรือคำสั่งระบบ / formulas cannot access files, internet, or system commands
```

---

## 9. `_validate_header` (3236-3244)

Lỗi ném ra (hiển thị verbatim):

- Thiếu tên khách: `กรุณากรอกชื่อลูกค้า/บริษัท / Please enter customer/company name`
- Thiếu mã khách: `กรุณากรอกรหัสลูกค้า / Please enter customer code`
- Ngày sai định dạng `%Y-%m-%d`: `วันที่ต้องอยู่ในรูป ปปปป-ดด-วว เช่น 2026-08-27`

---

## 10. `new_record` (3683-3793) — nút tạo mới reset gì

KHÔNG có hộp xác nhận — reset ngay lập tức.

**Xóa trắng:** customer, customer_code, description, product_reference, product_image, `editing_source_ref` (3686-3691); mọi ô kích thước (3695-3696); thickness (3701); markup (3716); giá bán chiếc/kg override (3720-3721); pack_qty, sack_qty (3722-3723); `related_quotes_cache` (3756); `pack_warning_result` (3788).

**Đặt về mặc định** (nguồn `DEFAULTS` app.py:67-73):

- Ngày = hôm nay ISO (3692); loại SP = `ถุงพลาสติกเปิดปากตรง (Plastic Bag)` (`PRODUCTS["flat"]`, 3693).
- Đơn vị kích thước: `ซม.` (riêng sold_length: `เมตร`) (3697); length ref = `ปากถึงแนวซีล / Opening to Seal`; bottom allowance = `1` `ซม.` (3698-3700).
- Thickness unit `มม.`, mode `pair` nhãn `ต่อคู่ / Per Pair` (3702-3704); tolerance các trường = `0` `มม.` (3706-3710); ẩn card quality (3711-3712).
- density = `0.92` · material_price = `65` · deduction = `10` (bật) · order_qty = `1000` (3714-3724); control min/max = `0` (3725-3726); roof_gsm = `120`, mesh_gsm = `80` (3727-3728).
- Formula: weight = `DEFAULT_WEIGHT_FORMULAS["flat"]`, price = `DEFAULT_PRICE_FORMULA` (3729-3730).
- Đơn vị bán = `ขายเป็นกิโลกรัม / Sell by kg` (3717); bố cục giá quay về chế độ kg, nhãn: `ราคาขายต่อกิโลกรัม (กรอก/แก้ไขได้)` xuống dòng `Final selling price per kg (Editable)` (3743-3753).
- Các dòng quick result (3732-3742):
  - `จำนวนปกติ / Normal: —`
  - `จำนวนชิ้นต่อกก.หลังหัก / Items per kg after deduction: —`
  - `ขายเป็นกก. / Sell by kg: จำนวนมาตรฐาน = 1,000 ÷ กรัมต่อชิ้น / Standard items/kg = 1,000 ÷ grams/item`
  - `ราคาต่อใบที่คำนวณได้ / Calculated Price/Piece: —  (ราคาฐาน/กก. ÷ จำนวนหลังหัก/กก.)`
  - `calculated_piece_display_var` = `—`
- Ref hiện tại = `ยังไม่บันทึก / Unsaved` (3754); mọi biến kết quả (18 biến, 3767-3787) = `—`.
- Cảnh báo related reset (3757-3762): text `กรอกรหัสสินค้า หรือรายการพร้อมขนาด แล้วกดคำนวณเพื่อตรวจประวัติ / Enter Part No. or Item + Size, then Calculate`, nút disabled, style về `Warning.TLabel` / `TButton`.
- Thu gọn "More Details": nút về nhãn `รายละเอียดเพิ่ม / More Details` (3763-3766).
- Status (3789-3791):

```
รายการใหม่ล้างข้อมูลเดิมแล้ว—ค่าที่เหลือเป็นค่าเริ่มต้นที่ระบุไว้ / New record cleared; remaining values are labeled defaults
```

- Chuyển về tab tính giá, focus ô width (3792-3793).

---

## 11. `load_selected_quote` (4185-4296) — nút Edit làm gì

Nạp toàn bộ inputs của quote vào form (product, customer, ngày, kích thước, thickness, length ref + map nhãn cũ `วัดจากปากถึงแนวซีล`/`วัดจากปากถึงก้นถุง` sang nhãn mới (4208-4215), bottom allowance (thiếu → 1 nếu ref = Opening to Seal, 0 nếu không — 4220-4223), tolerance, 11 biến số (4232-4247), sale basis, overrides), đổi bố cục khối giá theo đơn vị bán (4260-4285; nhãn chế độ chiếc: `ราคาฐานต่อกิโลกรัม (กรอกได้)` xuống dòng `Price basis per kg (Editable)`), nạp 2 formula, rồi:

- `editing_source_ref` = quote_ref (4288).
- Ref hiển thị: `กำลังแก้ไข / Editing: {quote_ref} (เก็บเป็นฉบับใหม่ / Save as revision)` (4289-4291).
- Status: `แก้ไขแล้วคำนวณใหม่ จากนั้นกดเก็บบันทึก / Edit, recalculate, then save — {quote_ref}` (4292-4294).
- Chuyển sang tab tính giá và **tự chạy `calculate_now()`** (4295-4296).

# 01 — Form nhập liệu tab "คำนวณราคา / Pricing"

> Nguồn: `Z:\1\app.py` (PantongOne, APP_VERSION dòng 51: `"1.7.1 (Phase 1) — Planning screen"`).
> Phạm vi: `_build_calculator` (701-995), hành vi form (2633-2811), `_collect_inputs` (2839-2916),
> class `DimensionField` (120-171), `default_note` (76-85), hằng số đầu file (1-120), style (275-374).
> Mọi chuỗi nhãn giữ NGUYÊN VĂN — kể cả dấu cách, `/`, ngoặc, `*`, `\n` (xuống dòng trong nhãn).

---

## 0. Hằng số màu + font + style dùng chung

### 0.1 Màu (app.py:88-93)

| Hằng | Hex |
|---|---|
| `BG` | `#f4f6f8` |
| `NAVY` | `#16324f` |
| `BLUE` | `#1f6aa5` |
| `GREEN` | `#167d5a` |
| `RED` | `#b42318` |
| `MUTED` | `#5f6b76` |

### 0.2 Font toàn app (app.py:278-279)

- `("Leelawadee UI", 10)` đặt qua `option_add("*Font", ...)` — mọi widget mặc định dùng font này.

### 0.3 Style ttk form dùng (app.py:280-374)

| Style | Giá trị | Dòng |
|---|---|---|
| `TFrame` | background `BG` (#f4f6f8) | 280 |
| `Card.TFrame` | background `white`, relief `solid`, borderwidth `1` | 281 |
| `Field.TFrame` | background `white`, relief `flat`, borderwidth `0` | 282 |
| `TLabel` | background `BG`, foreground `#1d2939` | 284 |
| `Card.TLabel` | background `white` (foreground kế thừa `#1d2939`) | 285 |
| `ProductChoice.TRadiobutton` | bg `white`, fg `NAVY` #16324f, font `("Leelawadee UI", 10, "bold")`, padding `(6, 5)`; map: bg `active` `#e9f3fb`, `selected` `#dceefa`; fg `selected` `NAVY` | 286-297 |
| `Warning.TLabel` | font `("Leelawadee UI", 10, "bold")`, fg `#9a6700`, bg `white` | 315-320 |
| `Muted.TLabel` | fg `MUTED` #5f6b76 | 334 |
| `Accent.TButton` | font `("Leelawadee UI", 10, "bold")`, padding `(12, 7)`, bg `BLUE` #1f6aa5, fg `white`; map: bg `active` `#174f7a`, `pressed` `#123e60`; fg `disabled` `#d0d5dd`, `!disabled` `white` | 335-341 |
| `TNotebook.Tab` | padding `(16, 9)`, font `("Leelawadee UI", 10, "bold")`, bg `#dbe7f2`, fg `NAVY`; map: bg `selected` `BLUE`, `active` `#b9d3e8`; fg `selected` `white`, `active` `NAVY` | 346-357 |
| `{name}.Section.TLabel` (tiêu đề card) | bg = màu section (bảng dưới), fg `white`, font `("Leelawadee UI", 11, "bold")`, padding `(10, 7)` | 358-374 |

### 0.4 Màu section của tiêu đề card (app.py:358-366)

| Section | Hex |
|---|---|
| `Product` | `#185a8d` |
| `Spec` | `#0f766e` |
| `Quality` | `#694a85` |
| `Calculation` | `#2f6f4e` |
| `Pricing` | `#1f6f5f` |
| `Production` | `#9a5b13` |
| `History` | `#5b4b8a` |

### 0.5 Helper `_card` (app.py:546-555)

- Frame ngoài: `Card.TFrame` (nền trắng, viền solid 1px), `padding=12`, grid `sticky="ew"`, `padx=8`, `pady=5`.
- Tiêu đề: `ttk.Label` style `{section}.Section.TLabel` ở row 0, `sticky="ew"`, `pady=(0, 8)` — thanh màu chạy hết chiều ngang card, chữ trắng.

### 0.6 Helper `_labeled_entry` (app.py:672-699)

- Hộp `Field.TFrame` grid `padx=8, pady=5, sticky="ew"`, cột 0 weight 1.
- Nhãn `Card.TLabel`, `justify="left"`, row 0 `sticky="w"`; wraplength tự bám theo bề rộng thực (`follow_width(caption, slack=8)`, dòng 691).
- Entry width mặc định `12`, row 1, `sticky="ew"`, `pady=(3, 0)`. Nếu có `lookup` thì là `SuggestEntry` (autocomplete khách hàng).

---

## 1. Class `DimensionField` (app.py:120-171) — ô kích thước + đơn vị

| Thuộc tính | Giá trị | Dòng |
|---|---|---|
| Frame | `Field.TFrame`, grid `padx=8, pady=6, sticky="ew"`, cột 0 weight 1 | 133-135 |
| Nhãn | `Card.TLabel`, `wraplength=250`, `justify="left"`, row 0, colspan 2, `sticky="w"` | 136-140 |
| Entry giá trị | `ttk.Entry` width `18`, row 1 col 0, `sticky="ew"`, `pady=(3, 0)` | 143-144 |
| Combobox đơn vị | width `7`, `state="readonly"`, row 1 col 1, `padx=(5, 0)`, `pady=(3, 0)` | 148-151 |
| Values đơn vị | keys của `DIMENSION_FACTORS_TO_CM`: `นิ้ว` · `ซม.` · `มม.` · `เมตร`; nếu `include_meter=False` (mặc định) thì **bỏ** `เมตร` | 145-147 |
| Mặc định | `default_value=""`, `default_unit="ซม."` | 128-129 |
| `set_raw` | format lại giá trị dạng `{:g}` (bỏ số 0 thừa) | 161 |
| `show()`/`hide()` | `frame.grid()` / `frame.grid_remove()` | 166-171 |

Hệ số quy đổi (calculator.py:24-36) — cần cho clone logic:

- `DIMENSION_FACTORS_TO_CM`: `นิ้ว`=2.54 · `ซม.`=1.0 · `มม.`=0.1 · `เมตร`=100.0
- `THICKNESS_FACTORS_TO_MM`: `มม.`=1.0 · `ซม.`=10.0 · `นิ้ว`=25.4 · `ไมครอน`=0.001

---

## 2. `default_note` (app.py:76-85)

- Trả chuỗi ghim sau nhãn: `" • ค่าเริ่มต้น / Default "` + giá trị format `{float(value):,g}` (ví dụ key `deduction_percent` → ` • ค่าเริ่มต้น / Default 10`).
- Key không có trong `DEFAULTS` hoặc value rỗng (`markup_percent`) → trả chuỗi rỗng, KHÔNG hiện note.
- Note được build từ giá trị thật trong `DEFAULTS`, không bao giờ gõ tay cạnh nhãn (comment dòng 57-66).

---

## 3. Kiến trúc tab Pricing — CÁI GÌ THẬT SỰ HIỆN (quan trọng cho clone)

`_build_calculator(parent)` (701-995) build theo thứ tự:

1. Card **"ข้อมูลลูกค้าและใบเสนอราคา / Customer & Quotation"** (`general_card`, section `Product` #185a8d) — dòng 704.
2. Card **"เลือกสินค้าและกรอกขนาด / Select Product & Enter Dimensions"** (`dimensions_card`, section `Spec` #0f766e) — dòng 791.
3. Card **"เงื่อนไขคุณภาพสำหรับการผลิต / Production Quality Conditions"** (`quality_card`, section `Quality` #694a85) — nằm trên `self.planning_body` (tab Vẽ kế hoạch sản xuất, KHÔNG phải tab Pricing) — dòng 913-918, ẩn lúc build (`quality.grid_remove()`, 962).
4. Card **"รายละเอียดสำหรับวางแผนผลิต / Production Planning Details"** (section `Calculation` #2f6f4e) trên `planning_body`, chứa `ttk.Notebook` (`calc_panels`); `production_panel` add với tab text **"ข้อมูลผลิต / Production Data"** (982); `pricing_panel` padding 14 (980) được add trong `_build_pricing_panel` (ngoài phạm vi file spec này).
5. `_build_compact_pricing_form(parent)` (986 → 995-1093): card **"ข้อมูลเสนอราคาและสเปกหลัก / Quotation & Main Specifications"** — bản compact DÙNG CHUNG các `tk.StringVar` với 2 card trên.

**⚠️ Trạng thái mặc định (dòng 987-988):** `general_card.grid_remove()` và `dimensions_card.grid_remove()` — cả hai card đầy đủ bị ẨN ngay khi build. Cái người dùng thấy trên tab Pricing là **card compact** (mục 5). `general_card` chỉ hiện lại khi bấm "รายละเอียดเพิ่ม / More Details" (xem §7.2). `dimensions_card` không bao giờ hiện lại — nó là bản legacy giữ StringVar. Web clone phải tái hiện đúng: compact hiện mặc định, general hiện theo toggle, dimensions ẩn vĩnh viễn (nhưng logic show/hide field của nó vẫn chạy song song với compact — xem §7.3).

Khởi tạo cuối `_build_calculator` (990-992): gọi lần lượt `_on_product_changed()` → `_on_thickness_mode_changed()` → `_on_sale_basis_changed()`.

---

## 4. Card 1 — "ข้อมูลลูกค้าและใบเสนอราคา / Customer & Quotation" (704-789)

Section `Product`, tiêu đề nền `#185a8d` chữ trắng. Card 2 cột, cả 2 weight 1 (706-707). **Ẩn mặc định** (987), hiện khi toggle More Details (2644).

Widget theo thứ tự xuất hiện:

| # | Widget | Nhãn VERBATIM | Vị trí | Style/chi tiết | Dòng |
|---|---|---|---|---|---|
| 1 | Frame `general_actions` | — | row 0, col 1, `sticky="e"`, `pady=(0, 8)` | `Field.TFrame` | 715-716 |
| 1a | Button | `เลือกข้อมูลเดิม / Use Existing Record` | pack left trong frame trên | `Accent.TButton` (xanh #1f6aa5, chữ trắng bold 10, padding 12,7); lệnh `show_existing_record_picker` | 717-723 |
| 1b | Button | `รายละเอียดเพิ่ม / More Details` | pack left, `padx=(6, 0)` | TButton thường; lệnh `toggle_quote_details`; nhãn đổi thành `ซ่อนรายละเอียด / Hide Details` khi đang mở (2649-2655) | 724-729 |
| 2 | SuggestEntry (autocomplete) | `ชื่อลูกค้า/บริษัท * / Customer/Company Name` | row 1, col 0 | qua `_labeled_entry` + lookup khách hàng; chọn gợi ý thì auto điền mã khách (`_on_customer_picked`, 574-583: chỉ điền khi code không rỗng) | 730-738 |
| 3 | Entry | `รหัสลูกค้า * / Customer Code` | row 1, col 1 | `customer_code_var` | 739 |
| 4 | Entry | `วันที่ * / Date (YYYY-MM-DD)` | row 2, col 0 | mặc định `date.today().isoformat()` (710) | 740 |
| 5 | Combobox | nhãn trên: `ประเภทสินค้า / Product Type *` | row 2, col 1 (`padx=8, pady=5`) | `state="readonly"`, width `28`, values = `PRODUCTS.values()`, mặc định `ถุงพลาสติกเปิดปากตรง (Plastic Bag)` (714); bind `<<ComboboxSelected>>` → `_on_product_changed` | 741-752 |
| 6 | Entry (optional) | `รายการสินค้า / Item Description` | row 3, col 0 | `description_var`; thuộc `optional_quote_widgets` — chỉ hiện khi More Details mở | 753, 755 |
| 7 | Entry (optional) | `รหัสสินค้า / Part Number` | row 3, col 1 | `product_reference_var`; optional | 754-755 |
| 8 | Hộp file (optional) | nhãn: `รูปสินค้า/ไฟล์อ้างอิง / Product Image/File (Optional)` | row 4, col 0-1 (colspan 2, `padx=8, pady=5`) | Entry `state="readonly"` (`product_image_var`) + Button `แนบไฟล์ / Attach…` (lệnh `choose_product_image`, `padx=(5, 0)`) | 756-768 |
| 9 | Hộp cảnh báo lịch sử (optional) | Label mặc định: `กรอกรหัสสินค้า หรือรายการพร้อมขนาด แล้วกดคำนวณเพื่อตรวจประวัติ / Enter Part No. or Item + Size, then Calculate` | row 5, col 0-1, `padx=8, pady=(8, 2)` | Label style `Warning.TLabel` (bold, fg #9a6700, bg trắng); Button `ดูบริษัท / View Companies` bên phải (`padx=(8, 0)`), `state="disabled"` ban đầu, lệnh `show_related_quotes` | 769-786 |

`quote_details_visible = False` ban đầu; mọi widget optional bị `grid_remove()` (787-789).

---

## 5. Card 2 — "เลือกสินค้าและกรอกขนาด / Select Product & Enter Dimensions" (791-911)

Section `Spec`, tiêu đề nền `#0f766e`. 4 cột weight 1 (793-794). **Ẩn vĩnh viễn** (988) — vẫn spec đầy đủ vì hành vi show/hide của nó là nguồn sự thật của `_on_product_changed`.

| # | Widget | Nhãn VERBATIM | Vị trí | Chi tiết | Dòng |
|---|---|---|---|---|---|
| 1 | Frame chọn loại SP (ẨN — grid_remove 823) | Nhãn tiêu đề: `รายการประเภทสินค้า * / Product Type Options` — `Card.TLabel`, font `("Leelawadee UI", 11, "bold")` | row 0, colspan 4, `padx=8, pady=(0, 8)` | 5 Radiobutton style `ProductChoice.TRadiobutton`, mỗi cột uniform `product`, `padx=3`; text = nhãn PRODUCTS với `" ("` đầu tiên thay bằng xuống dòng + `(` (dòng 809). Giữ để tương thích, hàng bị ẩn | 795-823 |
| 2 | `DimensionField` width | `ความกว้าง *\nWidth` | row 1, col 0 | đơn vị mặc định `ซม.`, không có `เมตร` | 825 |
| 3 | `DimensionField` length | `ความยาวตามสเปก *\nSpecification Length` | row 1, col 1 | như trên | 826 |
| 4 | `DimensionField` height | `ความสูง *\nHeight` | row 1, col 2 | như trên | 827 |
| 5 | `DimensionField` gusset | `ขนาดพับข้าง *\nGusset` | row 1, col 3 | như trên | 828 |
| 6 | `DimensionField` sold_length | `ความยาวม้วน *\nRoll Length` | row 1, col 1 (đè chỗ length khi hiện) | `default_unit="เมตร"`, `include_meter=True` → có đủ 4 đơn vị | 829-831 |
| 7 | `DimensionField` bottom_allowance | `ค่าบวกก้นถุง\nBottom Allowance` | row 2, col 2 | `default_value="1"`, `default_unit="ซม."` | 833-840 |
| 8 | Hộp độ dày (`thickness_box`) | nhãn: `ความหนา *\nThickness` | row 2, col 0, `padx=8, pady=6` | Entry width `14` (`thickness_var`, mặc định rỗng) + Combobox readonly width `9`, values = keys `THICKNESS_FACTORS_TO_MM` (`มม.` · `ซม.` · `นิ้ว` · `ไมครอน`), mặc định `มม.` (842) | 841-859 |
| 9 | Hộp chế độ dày (`thickness_mode_box`) | tiêu đề: `ความหนา: ต่อด้าน / ต่อคู่ *\nThickness: Per Side / Per Pair` (`Card.TLabel`, wraplength 250) | row 1, col 3, `padx=8, pady=6` | Combobox readonly values `["ต่อด้าน / Per Side", "ต่อคู่ / Per Pair"]`, mặc định `ต่อคู่ / Per Pair` (844); bind → `_on_thickness_mode_changed` | 861-879 |
| 9a | Note dưới combobox trên | `ค่าเริ่มต้น: ต่อคู่ (ความหนารวมสองด้าน) / Default: Per Pair (combined two-side thickness)` | pack dưới, `pady=(2, 0)` | style `Muted.TLabel` (fg #5f6b76) — LUÔN hiện cùng hộp | 880-884 |
| 10 | Hộp mốc đo chiều dài (`length_ref_box`) | nhãn: `จุดอ้างอิงความยาว\nLength Reference` | row 2, col 3, `padx=8, pady=6` | Combobox readonly, values = `LENGTH_REFERENCES.values()`: `ปากถึงแนวซีล / Opening to Seal` · `ปากถึงก้นถุง / Opening to Bottom`; mặc định `ปากถึงแนวซีล / Opening to Seal` (886); bind → `_on_length_reference_changed` | 886-897 |
| 11 | Label ghi chú allowance (`allowance_note`) | mặc định: `ถุงพลาสติกเปิดปากตรง (Plastic Bag) / ถุงพับข้าง (Gusset Bag) • ปากถึงแนวซีล / Opening to Seal: เริ่มต้น +1 ซม. / default +1 cm • ปากถึงก้นถุง / Opening to Bottom: +0 ไม่มีค่าเผื่อแฝง / no hidden allowance` | row 3, colspan 4, `padx=8, pady=(2, 0)`, `sticky="w"` | `Card.TLabel`, `foreground=MUTED` #5f6b76, `wraplength=1100`, `justify="left"`; text đổi theo loại SP (§7.3) | 898-906 |
| 12 | Button QC | `ข้อมูล QC สำหรับการผลิต / Production QC Details (คลิกเพื่อเปิด/ปิด / Show/Hide)` | row 4, colspan 4, `padx=8, pady=(5, 0)`, `sticky="w"` | TButton thường; lệnh `toggle_quality_details` | 907-911 |

---

## 6. Card Quality — "เงื่อนไขคุณภาพสำหรับการผลิต / Production Quality Conditions" (913-962)

Section `Quality`, tiêu đề nền `#694a85`. Parent = `planning_body` (tab kế hoạch SX). 4 cột weight 1. **Ẩn mặc định** (962); bật/tắt bằng nút QC ở §5#12 — khi bật, app tự nhảy sang tab planning (2732).

| # | Widget | Nhãn VERBATIM | Vị trí | Chi tiết | Dòng |
|---|---|---|---|---|---|
| 1 | `DimensionField` tolerance width | `ค่าคลาดเคลื่อนความกว้าง / Width Tolerance ±` | row 1, col 0 | `default_value="0"`, `default_unit="มม."` | 924-926 |
| 2 | `DimensionField` tolerance length | `ค่าคลาดเคลื่อนความยาว / Length Tolerance ±` | row 1, col 1 | `default_value="0"`, `default_unit="มม."` | 927-929 |
| 3 | Hộp tolerance dày | nhãn: `ค่าคลาดเคลื่อนความหนา / Thickness Tolerance ±` (`Card.TLabel`, wraplength 260, justify left) | row 1, col 2, `padx=8, pady=6` | Entry width `14` (`thickness_tolerance_var` mặc định `"0"`) + Combobox readonly width `9` values `THICKNESS_FACTORS_TO_MM`, mặc định `มม.` (931-932) | 931-953 |
| 4 | Label ghi chú | `วัดความหนาต่อแผ่น / Thickness tolerance is measured per sheet (even when main thickness is per pair)` | row 1, col 3, `padx=8, pady=6`, `sticky="w"` | `Card.TLabel`, fg `MUTED`, wraplength 280, justify left — LUÔN hiện | 954-961 |

---

## 7. Hành vi điều kiện

### 7.1 `product_key` (2633-2638)

Map nhãn đang chọn (`product_label_var`) ngược về key qua dict `PRODUCTS`; không khớp → fallback `"flat"`.

`PRODUCTS` (calculator.py:11-17) — values VERBATIM:

| key | nhãn |
|---|---|
| `flat` | `ถุงพลาสติกเปิดปากตรง (Plastic Bag)` |
| `opaque` | `แผ่นพลาสติก (Plastic Sheet)` |
| `gusset` | `ถุงพับข้าง (Gusset Bag)` |
| `roll` | `ม้วนพลาสติก (Plastic Roll)` |
| `cover` | `ถุงคลุมสินค้า (Product Cover)` |

### 7.2 `toggle_quote_details` (2640-2655)

- Đảo `quote_details_visible`.
- Mở: `general_card.grid(row=1, column=0, sticky="ew", padx=8, pady=3)` + grid() mọi widget optional (Item Description, Part Number, hộp file, hộp cảnh báo lịch sử). Nút đổi text → `ซ่อนรายละเอียด / Hide Details`.
- Đóng: `general_card.grid_remove()` + ẩn optional. Nút → `รายละเอียดเพิ่ม / More Details`.

### 7.3 `_on_product_changed` (2657-2718) — BẢNG 5 loại sản phẩm × ô hiện/ẩn

Ô kích thước hiện (set `visible`, 2660-2666) và vị trí grid compact (2669-2677, grid lại `padx=6, pady=3` trong dimensions_card; đồng thời `_update_compact_spec_fields` 2659 làm y hệt trên card compact ở row 2):

| Loại SP | width | length | gusset | height | sold_length | thickness | thickness mode | bottom allowance | length reference | cover material |
|---|---|---|---|---|---|---|---|---|---|---|
| `flat` ถุงพลาสติกเปิดปากตรง | ✓ col 0 | ✓ col 1 | ✗ | ✗ | ✗ | ✓ row 1 col 2 | ✓ row 1 col 3 | ✓ row 2 col 0 | ✓ row 2 col 1 | ✗ |
| `gusset` ถุงพับข้าง | ✓ col 0 | ✓ col 1 | ✓ col 2 | ✗ | ✗ | ✓ row 1 col 3 | ✓ **row 2 col 2** | ✓ row 2 col 0 | ✓ row 2 col 1 | ✗ |
| `roll` ม้วนพลาสติก | ✓ col 0 | ✗ | ✗ | ✗ | ✓ col 1 | ✓ row 1 col 2 | ✓ row 1 col 3 | ✗ | ✗ | ✗ |
| `opaque` แผ่นพลาสติก | ✓ col 0 | ✓ col 1 | ✗ | ✗ | ✗ | ✓ row 1 col 2 | ✓ row 1 col 3 | ✗ | ✗ | ✗ |
| `cover` ถุงคลุมสินค้า | ✓ col 0 | ✓ col 1 | ✗ | ✓ col 2 | ✗ | ✗ ẩn | ✗ ẩn | ✗ ẩn | ✗ ẩn | ✓ hiện (`cover_material_frame.grid()`, 2686 — frame thuộc production panel) |

(Bảng vị trí: cột thickness theo dict dòng 2688 `{"flat": 2, "gusset": 3, "roll": 2, "opaque": 2}`; mode box: gusset → row 2 col 2, còn lại row 1 col 3, dòng 2690-2696. Trên card compact, `_update_compact_spec_fields` 1095-1120: thickness col = 2 nếu <3 ô kích thước, ngược lại 3; mode luôn row 3 col 0; bottom allowance row 3 col 1 chỉ với flat/gusset.)

Text `allowance_note` đổi theo loại (VERBATIM):

- `flat` / `gusset` (2703-2705): `ถุงพลาสติกเปิดปากตรง (Plastic Bag) / ถุงพับข้าง (Gusset Bag) • ปากถึงแนวซีล / Opening to Seal: เริ่มต้น +1 ซม. / default +1 cm • ปากถึงก้นถุง / Opening to Bottom: +0 ไม่มีค่าเผื่อแฝง / no hidden allowance`
- `roll` / `opaque` (2709): `ไม่มีค่าเผื่อตะเข็บเพิ่มเติม / No additional seam allowance`
- `cover` (2683-2685): `ถุงคลุมสินค้า / Product Cover only: หลังคา / Roof = (กว้าง/Width + 1 ซม.) × (ยาว/Length + 1 ซม.) • ตาข่าย / Mesh = ((กว้าง/Width + ยาว/Length) × 2 + 4 ซม.) × (สูง/Height + 1 ซม.)`

Cuối hàm (2710-2718): nạp công thức trọng lượng theo loại từ DB setting `weight_formula.{key}` (fallback `DEFAULT_WEIGHT_FORMULAS[key]`, calculator.py:38-44) và công thức giá setting `price_formula` (fallback `DEFAULT_PRICE_FORMULA`, calculator.py:46) vào 2 ô Text; set summary: `"สูตรน้ำหนัก / Weight formula: " + saved + "\nสูตรคำนวณราคา / Price formula: " + price_saved`; xóa `last_result`.

### 7.4 `_on_length_reference_changed` (2720-2726)

- Chọn `ปากถึงแนวซีล / Opening to Seal` → ô Bottom Allowance auto set `1`; chọn `ปากถึงก้นถุง / Opening to Bottom` → set `0`. Đơn vị luôn reset về `ซม.`. Xóa `last_result`.

### 7.5 `toggle_quality_details` (2728-2734)

- Đảo `quality_visible`. Bật: `quality_card.grid()` **và** `main_tabs.select(planning_frame)` (nhảy sang tab planning). Tắt: `grid_remove()`.

### 7.6 `_on_thickness_mode_changed` (2736-2739)

- Nhãn chọn == `ต่อคู่ / Per Pair` → `thickness_mode_var = "pair"`, ngược lại `"side"`. Xóa `last_result`.

### 7.7 `_on_sale_basis_changed` (2741-2782)

`sale_basis_var` values (app.py:1453, 1664): `["ขายเป็นกิโลกรัม / Sell by kg", "ขายเป็นชิ้น / Sell by piece"]`, mặc định `ขายเป็นกิโลกรัม / Sell by kg` (1429). Điều kiện: chuỗi bắt đầu bằng `ขายเป็นกิโลกรัม` → bán theo kg.

Mỗi lần đổi: `apply_deduction_var` luôn set `True` (2744).

Khi **bán theo kg** (2748-2755, 2767-2769, 2774-2777):
- Ô giá/chiếc nhanh (`quick_piece_entry`) → `state="disabled"`; ô giá/kg → `normal`.
- Ẩn `calculated_price_box`, `final_piece_box`, `quick_calculated_piece_label`; `kg_price_box` giãn ra `column=0, columnspan=3, padx=0`.
- Nhãn ô kg: `ราคาขายต่อกิโลกรัม (กรอก/แก้ไขได้)\nFinal selling price per kg (Editable)`
- Panel pricing: ẩn `unit_price_box`, hiện `price_per_kg_box`.
- Hint: `ขายเป็นกก. / Sell by kg: จำนวนมาตรฐาน = 1,000 ÷ กรัมต่อชิ้น / Standard items/kg = 1,000 ÷ grams/item`

Khi **bán theo chiếc** (2756-2765, 2770-2772, 2778-2781):
- `quick_piece_entry` → `normal`.
- Hiện lại `calculated_price_box` (row 0 col 0, `padx=(0, 6)`), `final_piece_box` (row 0 col 1, `padx=6`), `quick_calculated_piece_label` (row 4, colspan 7, `padx=2, pady=(6, 0)`); `kg_price_box` về `column=2, columnspan=1, padx=(6, 0)`.
- Nhãn ô kg: `ราคาฐานต่อกิโลกรัม (กรอกได้)\nPrice basis per kg (Editable)`
- Panel pricing: hiện `unit_price_box`, ẩn `price_per_kg_box`.
- Hint: `ขายเป็นชิ้น / Sell by piece: ราคาต่อชิ้น = ราคาฐาน/กก. ÷ จำนวนหลังหัก/กก. / Price per piece = price basis/kg ÷ adjusted items/kg`

Xóa `last_result` (2782).

### 7.8 `_auto_update_markup` (2784-2795)

- markup% = `((giá bán cơ sở/kg ÷ giá vật liệu/kg) - 1) × 100`, format `%.2f`.
- Vật liệu ≤ 0, basis < 0, hoặc parse lỗi → ô markup set rỗng `""`. Xóa `last_result`.

### 7.9 `_price_basis_summary` (2797-2809) — chuỗi audit lưu kèm bản ghi

1. Bán theo kg và có giá nhập > 0: `ราคาขายที่กรอก {basis:,.3f} บาท/กก. / Entered final price per kg`
2. Có basis > 0 và adjusted > 0: `{basis:,.3f} บาท/กก. ÷ {adjusted:,.2f} ชิ้น/กก.`
3. Còn lại: `สูตรราคา / Price formula: {price_formula}`

### 7.10 Caption hệ số hụt (`_refresh_deduction_caption`, 589-609 — liên quan trực tiếp form)

- Không áp dụng hụt: `จำนวนชิ้นต่อกก. (ไม่หักเผื่อ) / Items per kg (no deduction)`
- Có áp dụng: `จำนวนชิ้นต่อกก.หลังหัก {n}% / Items per kg after {n}% deduction` — `n` lấy từ ô hoặc fallback `DEFAULTS["deduction_percent"]`, format `{:g}`.

---

## 8. `_collect_inputs` (2839-2914) — ô nào map về trường nào

| Trường payload | Nguồn widget/var | Nhãn dùng trong thông báo lỗi (verbatim) | Dòng |
|---|---|---|---|
| `dimensions.{width,length,height,gusset,sold_length}` | các `DimensionField` (`{"value", "unit"}` thô) | nhãn field | 2840 |
| `normalized.width_cm` / `length_cm` / `height_cm` / `gusset_cm` | `get_cm()` từng field | — | 2852-2855 |
| `normalized.sold_length_m` | `sold_length.get_cm() / 100` | — | 2856 |
| `normalized.thickness_input_mm` | `thickness_var` + `thickness_unit_var` qua `thickness_to_mm` | `ความหนา` | 2857-2859 |
| `normalized.bottom_allowance_cm` | bottom_allowance quy về cm; **chỉ flat/gusset**, loại khác = `0.0` | — | 2841-2846, 2860 |
| `thickness` | `{value, unit, mode}` — mode = `pair`/`side` | `ความหนา` | 2866-2870 |
| `length_reference` | `length_ref_var`; **chỉ flat/gusset**, loại khác = `""` | — | 2871-2873 |
| `bottom_allowance` | raw; loại khác flat/gusset = `{"value": 0.0, "unit": "ซม."}` | — | 2874-2876 |
| `quality_tolerances.width` / `.length` | 2 `DimensionField` tolerance | nhãn field | 2847, 2878-2879 |
| `quality_tolerances.thickness_per_sheet` | `thickness_tolerance_var` + unit | `ค่าคลาดเคลื่อนความหนา` | 2848-2850, 2880-2883 |
| `quality_tolerances.normalized.{width_cm,length_cm,thickness_per_sheet_mm}` | quy đổi cm/mm | — | 2884-2890 |
| `density_g_cm3` | `density_var` (allow_zero=False) | `ความหนาแน่น` | 2892 |
| `material_price_per_kg` | `material_price_var` | `ราคาวัตถุดิบ` | 2893 |
| `markup_percent` | `markup_var` | `เปอร์เซ็นต์บวกเพิ่ม` | 2894 |
| `deduction_percent` | `deduction_var` | `เปอร์เซ็นต์หัก` | 2895 |
| `apply_deduction` | `apply_deduction_var` (bool) | — | 2896 |
| `sale_basis` | `sale_basis_var` (chuỗi nguyên văn) | — | 2897 |
| `selling_price_per_piece_override` | `selling_price_piece_input_var` | `ราคาขายต่อชิ้น` | 2898-2900 |
| `selling_price_per_kg_override` | `selling_price_kg_input_var` | `ราคาขายต่อกิโลกรัม` | 2901-2903 |
| `pack_quantity` | `pack_qty_var` | `จำนวนต่อแพ็ก` | 2904 |
| `sack_quantity` | `sack_qty_var` | `จำนวนต่อกระสอบ` | 2905 |
| `order_quantity` | `order_qty_var` | `จำนวนสั่งผลิต` | 2906 |
| `control_min_g` | `control_min_var` | `น้ำหนักควบคุมต่ำสุด` | 2907 |
| `control_max_g` | `control_max_var` | `น้ำหนักควบคุมสูงสุด` | 2908 |
| `roof_gsm` | `roof_gsm_var` | `น้ำหนักวัสดุหลังคา` | 2909 |
| `mesh_gsm` | `mesh_gsm_var` | `น้ำหนักตาข่าย` | 2910 |

Validation trong hàm:
- `require_positive_dimensions(product_key, normalized)` sau khi quy đổi (2862).
- `control_min_g > control_max_g` (khi max > 0) → lỗi `น้ำหนักควบคุมต่ำสุดต้องไม่มากกว่าค่าสูงสุด` (2912-2913).
- Parse số (`as_float`, 107-117): rỗng → 0.0; không phải số → `{label}ต้องเป็นตัวเลข`; âm → `{label}ต้องไม่ติดลบ`; cần >0 → `{label}ต้องมากกว่า 0`. Dấu phẩy nghìn `,` được strip trước khi parse (108).

---

## 9. DEFAULTS mà form dùng (app.py:67-73)

| Key | Giá trị mặc định | Note hiển thị (qua `default_note`) |
|---|---|---|
| `density_g_cm3` | `"0.92"` | ` • ค่าเริ่มต้น / Default 0.92` |
| `material_price_per_kg` | `"65"` | ` • ค่าเริ่มต้น / Default 65` |
| `markup_percent` | `""` (rỗng) | không hiện note (default_note trả `""`, dòng 79-80) |
| `deduction_percent` | `"10"` | ` • ค่าเริ่มต้น / Default 10` — cũng là fallback của caption hệ số hụt (600) |
| `order_quantity` | `"1000"` | ` • ค่าเริ่มต้น / Default 1,000` |

Mặc định khác của form (không nằm trong dict `DEFAULTS`):
- Ngày = hôm nay ISO (710) · Loại SP = `ถุงพลาสติกเปิดปากตรง (Plastic Bag)` (714) · Đơn vị kích thước = `ซม.` (129) · Roll Length đơn vị = `เมตร` (830) · Bottom Allowance = `1` `ซม.` (838-839) · Độ dày = rỗng, đơn vị `มม.` (841-842) · Chế độ dày = `ต่อคู่ / Per Pair` (843-844) · Mốc đo = `ปากถึงแนวซีล / Opening to Seal` (886) · Tolerance = `0` `มม.` (925-932) · Sale basis = `ขายเป็นกิโลกรัม / Sell by kg` (1429).

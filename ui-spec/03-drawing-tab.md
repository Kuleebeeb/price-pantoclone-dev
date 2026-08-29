# 03 — Tab "แบบขออนุมัติ / Drawing for Approval"

> Nguồn: `Z:\1\app.py` (bản đang đọc ghi `APP_VERSION = "1.7.1 (Phase 1) — Planning screen"`, dòng 51 —
> LƯU Ý: đề bài nói v1.5.1, file thật là 1.7.1). Tab dựng bởi `_build_drawing` (dòng 1876–2135).
> Mọi chuỗi nhãn dưới đây là NGUYÊN VĂN từ code.

---

## 0. Hằng màu + style dùng chung (app.py 88–93, 275–374)

| Hằng | Hex | Dòng |
|---|---|---|
| `BG` | `#f4f6f8` | 88 |
| `NAVY` | `#16324f` | 89 |
| `BLUE` | `#1f6aa5` | 90 |
| `GREEN` | `#167d5a` | 91 |
| `RED` | `#b42318` | 92 |
| `MUTED` | `#5f6b76` | 93 |

Font toàn app: `("Leelawadee UI", 10)` qua `option_add("*Font", font)` (dòng 278–279). Theme ttk: `clam` (277).

Style dùng trong tab này:

| Style | Thuộc tính | Dòng |
|---|---|---|
| `TFrame` | background `#f4f6f8` (BG) | 280 |
| `Card.TFrame` | background `white`, relief `solid`, borderwidth 1 | 281 |
| `Field.TFrame` | background `white`, relief `flat`, borderwidth 0 | 282 |
| `TLabel` | background BG, foreground `#1d2939` | 284 |
| `Card.TLabel` | background `white` (chữ mặc định `#1d2939`, Leelawadee UI 10) | 285 |
| `ResultName.TLabel` | background `#f5f9fc`, foreground `#344054` | 313 |
| `Warning.TLabel` | Leelawadee UI 10 **bold**, foreground `#9a6700`, background `white` | 315–320 |
| `Accent.TButton` | Leelawadee UI 10 **bold**, padding (12,7), background BLUE `#1f6aa5`, chữ trắng; active `#174f7a`, pressed `#123e60`, disabled chữ `#d0d5dd` | 335–341 |
| `Treeview` | rowheight 30 | 342 |
| `Treeview.Heading` | Leelawadee UI 10 **bold** | 343 |
| `History.Treeview` | rowheight 31, relief `solid`, borderwidth 1 | 344 |
| `<Section>.Section.TLabel` | background = màu section, chữ trắng, Leelawadee UI 11 **bold**, padding (10,7) | 358–374 |

Màu section (dải tiêu đề card, dòng 358–366): `Product` `#185a8d` · `Spec` `#0f766e` · `Quality` `#694a85` · `Production` `#9a5b13` (tab này dùng 4 màu đó).

Helper `_card(parent, title, row, section_style)` (546–555): khung ngoài `Card.TFrame` padding 12, grid `row=row, column=0, sticky="ew", padx=8, pady=5`; dòng tiêu đề là Label `f"{section}.Section.TLabel"` grid row 0 sticky ew, pady (0,8).

Helper `_labeled_entry(parent, label, var, row, col, width=12)` (672–699): khung `Field.TFrame` grid `padx=8, pady=5, sticky="ew"`; caption `Card.TLabel` row 0 sticky w (wraplength bám bề rộng qua `follow_width(caption, slack=8)`); Entry row 1 sticky ew, pady (3,0). Có `lookup` thì Entry là `SuggestEntry` (autocomplete).

`DimensionField` (120–170): khung `Field.TFrame` grid `padx=8, pady=6, sticky="ew"`; nhãn `Card.TLabel` wraplength 250 justify left (row 0, colspan 2); Entry width 18 (row 1 col 0) + Combobox đơn vị width 7 readonly (row 1 col 1, padx (5,0)). Đơn vị = keys của `DIMENSION_FACTORS_TO_CM` bỏ `"เมตร"`: **`นิ้ว` · `ซม.` · `มม.`** — mặc định `"ซม."`. Ẩn/hiện bằng `grid_remove()`/`grid()` (166–170).

---

## 1. Khung tab

- Tab thêm vào notebook với text NGUYÊN VĂN: **"แบบขออนุมัติ / Drawing for Approval"** (512–515). Tab thứ 3 (sau "คำนวณราคา / Pricing" và "ข้อมูลวางแผนการผลิต / Production Planning", trước "ประวัติ / Quote History").
- `drawing_frame` padding 8, chứa `ScrollFrame` (canvas nền BG + scrollbar dọc `Vertical.TScrollbar` width 22, arrowsize 18; cuộn chuột 3 unit/nấc, yscrollincrement 24) (498–504, 173–194, 345).
- Body: `columnconfigure(0, weight=1)` (1877).
- Style tab notebook: `TNotebook.Tab` padding (16,9), Leelawadee UI 10 bold, nền `#dbe7f2` chữ NAVY; selected nền BLUE chữ trắng; active nền `#b9d3e8` chữ NAVY (346–357).

---

## 2. Hàng nút hành động (row 0) — dòng 1907–1938

Frame `ttk.Frame(padding=(8,4))` grid row 0 sticky ew; 4 cột weight=1. Mỗi nút `padx=4, sticky="ew"`.

| # | Widget | Nhãn NGUYÊN VĂN | Style | Grid | Lệnh | Dòng |
|---|---|---|---|---|---|---|
| 1 | ttk.Button | `ดึงข้อมูลจากหน้าคำนวณราคา / Copy from Pricing` | mặc định | r0 c0 | `drawing_load_from_pricing` | 1911–1915 |
| 2 | ttk.Button | `ดูตัวอย่าง & พิมพ์ / Preview & Print` | **Accent.TButton** (nền BLUE chữ trắng bold) | r0 c1 | `drawing_preview` | 1916–1921 |
| 3 | ttk.Button | `บันทึกแบบ (ออกเลขเอกสาร) / Save Drawing` | mặc định | r0 c2 | `drawing_save` | 1922–1926 |
| 4 | ttk.Button | `แบบใหม่ / New Drawing` | mặc định | r0 c3 | `drawing_reset` | 1927–1931 |
| 5 | ttk.Label (status) | bind `drawing_status_var` | **Warning.TLabel** (bold, `#9a6700` trên trắng), wraplength 1100, justify left | r1 c0 colspan 4, sticky ew, pady (6,0) | — | 1932–1938 |

Giá trị khởi tạo `drawing_status_var` NGUYÊN VĂN (1879–1882):
`กรอกข้อมูลแล้วกดดูตัวอย่าง เลขเอกสารจะออกให้ตอนกดบันทึกเท่านั้น / Fill in the form and preview; the document number is issued only on save`

---

## 3. Card 1 — "ข้อมูลเอกสาร / Drawing Document" (row 1, section **Product** `#185a8d`) — dòng 1940–1979

4 cột weight=1. Bố cục grid trong card (row 0 là dải tiêu đề):

| Widget | Nhãn NGUYÊN VĂN | Loại | Mặc định / var | Grid | Dòng |
|---|---|---|---|---|---|
| Ô hiển thị số | `เลขเอกสาร / Document No.` (Card.TLabel) + Label bind `drawing_doc_no_var` style **ResultName.TLabel** (nền `#f5f9fc` chữ `#344054`) | Frame `Field.TFrame` chứa 2 Label | `— ยังไม่ออกเลข / not issued —` (1883) | r1 c0, padx 8 pady 5 | 1945–1952 |
| Entry | `วันที่ / Date` | `_labeled_entry` | `date.today().isoformat()` (ISO yyyy-mm-dd) (1884) | r1 c1 | 1953 |
| Entry | `ครั้งที่แก้ / Revision` | `_labeled_entry` | `A` (1885) | r1 c2 | 1954 |
| Entry | `รหัสลูกค้า / Customer Code` | `_labeled_entry` | rỗng | r1 c3 | 1955 |
| Entry autocomplete | `ชื่อลูกค้า / Customer *` | `_labeled_entry` + `lookup=self._customer_lookup`, `on_pick=self._on_drawing_customer_picked` (SuggestEntry — gõ ra gợi ý khách; chọn khách CÓ mã thì tự điền `drawing_customer_code_var`, mã rỗng thì KHÔNG ghi đè — 585–587) | rỗng | r2 c0 | 1956–1964 |
| Entry | `ชื่อแบบ / Drawing Title *` | `_labeled_entry` | rỗng | r2 c1 | 1965 |
| Entry | `รหัสสินค้า / Part No.` | `_labeled_entry` | `-` (1889) | r2 c2 | 1966 |
| Entry | `วัสดุ / Material` | `_labeled_entry` | `POLYETHYLENE` (1890) | r2 c3 | 1967 |
| Entry | `สี / Color` | `_labeled_entry` | `-` (1891) | r3 c0 | 1968 |
| Entry | `งานพิมพ์ / Printing` | `_labeled_entry` | `-` (1892) | r3 c1 | 1969 |
| Label ghi chú | NGUYÊN VĂN: `แบบที่ส่งลูกค้าแล้วห้ามแก้ทับ ให้เพิ่มครั้งที่แก้ (Rev.B) แล้วบันทึก เลขเอกสารเดิมจะถูกคงไว้ / A drawing already sent must not be overwritten: raise the revision and save; the document number stays the same` | Card.TLabel, foreground MUTED `#5f6b76`, wraplength 1100, justify left | — | r4 c0 colspan 4, padx 8, pady (4,0), sticky w | 1970–1979 |

---

## 4. Card 2 — "ขนาดและค่าคลาดเคลื่อน / Dimensions and Tolerances" (row 2, section **Spec** `#0f766e`) — dòng 1981–2077

4 cột weight=1.

**Hàng 1 (4 ô Field.TFrame, padx 8 pady 5):**

| Widget | Nhãn NGUYÊN VĂN | Loại + giá trị | Grid | Dòng |
|---|---|---|---|---|
| Combobox readonly | `ประเภทสินค้า / Product Type` | values = `PRODUCTS.values()` (calculator.py 11–17): `ถุงพลาสติกเปิดปากตรง (Plastic Bag)` · `แผ่นพลาสติก (Plastic Sheet)` · `ถุงพับข้าง (Gusset Bag)` · `ม้วนพลาสติก (Plastic Roll)` · `ถุงคลุมสินค้า (Product Cover)` — mặc định flat. Đổi lựa chọn → `_drawing_sync_fields()` | r1 c0 | 1986–2001 |
| Combobox readonly | `จุดอ้างอิงความยาว / Length Reference *` | values = `LENGTH_REFERENCES.values()` (calculator.py 19–22): `ปากถึงแนวซีล / Opening to Seal` · `ปากถึงก้นถุง / Opening to Bottom` — mặc định opening_to_seal | r1 c1 | 2002–2016 |
| Combobox readonly | `หน่วยที่พิมพ์บนแบบ / Unit on Drawing` | values `["mm", "inch"]` — mặc định `mm` | r1 c2 | 2017–2028 |
| Entry width 12 + Combobox width 9 readonly | `ความหนาต่อด้าน / Thickness per Side` (wraplength 250) | Entry rỗng; đơn vị = keys `THICKNESS_FACTORS_TO_MM` (calculator.py 31–36): `มม.` · `ซม.` · `นิ้ว` · `ไมครอน` — mặc định `มม.` | r1 c3 (combobox padx (5,0)) | 2029–2048 |

**Hàng 2 — 4 DimensionField (2050–2055):** nhãn 2 dòng (có `\n`):

| key | Nhãn NGUYÊN VĂN | Grid |
|---|---|---|
| width | `ความกว้าง *\nWidth` | r2 c0 |
| length | `ความยาว *\nLength` | r2 c1 |
| height | `ความสูง\nHeight` | r2 c2 |
| gusset | `ขนาดพับข้าง\nGusset` | r2 c3 |

Mỗi ô: Entry width 18 + Combobox đơn vị (`นิ้ว`/`ซม.`/`มม.`, mặc định `ซม.`).

**Hàng 3 — 3 `_labeled_entry` (2056–2067):**

| Nhãn NGUYÊN VĂN | Mặc định | Grid |
|---|---|---|
| `ค่าคลาดเคลื่อนต่ำสุด (มม.) / Tolerance Lower (mm)` | `-10` (1898) | r3 c0 |
| `ค่าคลาดเคลื่อนสูงสุด (มม.) / Tolerance Upper (mm)` | `10` (1899) | r3 c1 |
| `ค่าคลาดเคลื่อนความหนา ± (มม.) / Thickness Tolerance (mm)` | `0.005` (1900) | r3 c2 |

**Hàng 4 — Label ghi chú** (Card.TLabel, MUTED, wraplength 1100, justify left, r4 colspan 4, padx 8 pady (4,0)) NGUYÊN VĂN (2068–2077):
`ความหนาบนแบบพิมพ์เป็นมิลลิเมตรเสมอ แม้เลือกหน่วยเป็นนิ้ว เพราะหน้างานวัดด้วยไมโครมิเตอร์หน่วยมิลลิเมตร / Thickness is always printed in mm even when the unit is inch`

---

## 5. Card 3 — "ลักษณะพิเศษและหมายเหตุ / Features and Notes" (row 3, section **Quality** `#694a85`) — dòng 2079–2102

4 cột weight=1.

| Widget | Nhãn NGUYÊN VĂN | Mặc định | Grid | Dòng |
|---|---|---|---|---|
| `_labeled_entry` | `จำนวนรูเจาะ / Number of Holes` | `0` (1901) | r1 c0 | 2082 |
| `_labeled_entry` | `ขนาดรูเจาะ Ø (มม.) / Hole Diameter` | `20-25` (1902) | r1 c1 | 2083 |
| `_labeled_entry` | `ลาเบลกว้าง (มม.) / Label Width` | `0` (1903) | r1 c2 | 2084 |
| `_labeled_entry` | `ลาเบลสูง (มม.) / Label Height` | `0` (1904) | r1 c3 | 2085 |
| Label | `หมายเหตุเพิ่มเติม บรรทัดละหนึ่งข้อ / Extra notes, one per line` (Card.TLabel) | — | r2 colspan 4, padx 8, pady (6,2), sticky w | 2086–2090 |
| `tk.Text` | (không nhãn riêng — textarea ghi chú) | height 3, wrap `word`, rỗng | r3 colspan 4, padx 8, sticky ew | 2091–2092 |
| Label ghi chú | NGUYÊN VĂN: `ข้อความมาตรฐาน (รูเจาะ ลาเบล จุดอ้างอิง ความหนา ค่าคลาดเคลื่อน วัสดุ) โปรแกรมเขียนให้เองจากค่าด้านบน ไม่ต้องพิมพ์ซ้ำ / Standard notes are generated from the values above` (Card.TLabel, MUTED, wraplength 1100, justify left) | — | r4 colspan 4, padx 8, pady (4,0), sticky w | 2093–2102 |

---

## 6. Card 4 — "ทะเบียนแบบที่บันทึกไว้ / Saved Drawing Register" (row 4, section **Production** `#9a5b13`) — dòng 2104–2132

| Widget | Nhãn NGUYÊN VĂN | Grid | Dòng |
|---|---|---|---|
| Entry tìm kiếm | (không nhãn, bind `drawing_search_var`, không placeholder) | search_row r0 c0 sticky ew (search_row: r1 c0 sticky ew, padx 8, pady (0,6)) | 2106–2109 |
| ttk.Button | `ค้นหา / Search` → `drawing_refresh_register` | r0 c1, padx (6,0) | 2110–2112 |
| ttk.Button | `เปิดแบบที่เลือก / Open Selected` → `drawing_load_selected` | r0 c2, padx (6,0) | 2113–2115 |
| ttk.Treeview | style `History.Treeview`, `show="headings"`, height 6; double-click = mở dòng đang chọn | r2 c0 sticky ew, padx 8 | 2125–2132 |

Cột Treeview (2116–2130) — heading NGUYÊN VĂN, anchor `w`; width 90 cho `date`/`rev`, còn lại 190:

| id | Heading NGUYÊN VĂN |
|---|---|
| doc_no | `เลขเอกสาร / Doc No.` |
| date | `วันที่ / Date` |
| rev | `แก้ครั้งที่ / Rev` |
| customer | `ลูกค้า / Customer` |
| title | `ชื่อแบบ / Title` |
| size | `ขนาด / Size (mm)` |

Giá trị cột `size`: `f"{width_mm:g} x {length_mm:g}"`, có thickness thì nối thêm ` x {thickness_mm:g}"` (2363–2365). iid của dòng = `doc_no` (2369).

Cuối `_build_drawing` gọi ngay `_drawing_sync_fields()` + `drawing_refresh_register()` (2134–2135).

---

## 7. Hành vi

### 7.1 Đổi loại sản phẩm — `_drawing_sync_fields` (2144–2160)

Ô kích thước hiện theo loại (còn lại `grid_remove`):

| product_key | Ô hiện |
|---|---|
| flat | width, length |
| gusset | width, length, gusset |
| opaque | width, length |
| roll | width, length |
| cover | width, length, height |

Combobox `จุดอ้างอิงความยาว / Length Reference *`: state `readonly` khi loại ∈ {flat, gusset}, ngược lại **`disabled`** (2159–2160). `_drawing_product_key` map ngược nhãn → key, fallback `"flat"` (2137–2142).

### 7.2 Nút "ดึงข้อมูลจากหน้าคำนวณราคา / Copy from Pricing" — `drawing_load_from_pricing` (2230–2267)

Chép từ tab Pricing: tên khách, mã khách, mô tả sản phẩm → `ชื่อแบบ`, mã sản phẩm → `รหัสสินค้า` (rỗng thành `-`), loại sản phẩm, ngày, length reference; 4 kích thước (giữ nguyên value+unit); độ dày — nếu Pricing đang ở chế độ `pair` (đo cả 2 mặt) thì **chia 2** để thành per-side (2250–2251), kèm đơn vị; tolerance width của Pricing (quy về mm) → điền `-span`/`+span` vào Lower/Upper; thickness tolerance quy về mm. Xong đặt status NGUYÊN VĂN:
`คัดลอกข้อมูลจากหน้าคำนวณราคาแล้ว ตรวจค่าคลาดเคลื่อนก่อนส่งลูกค้า / Copied from the pricing tab; check the tolerances before sending`

### 7.3 Validate chung — `_drawing_collect` (2162–2228)

- Thiếu tên khách → lỗi NGUYÊN VĂN `ต้องระบุชื่อลูกค้า / Customer is required`; thiếu tên bản vẽ → `ต้องระบุชื่อแบบ / Drawing title is required` (2166–2168).
- Kích thước quy hết về **mm** (`to_cm(...)*10`); độ dày quy về mm bằng `thickness_to_mm`.
- doc_no chưa bắt đầu bằng `DFA-` thì spec dùng `— DRAFT —` (2200).
- Fallback khi bỏ trống: revision→`A`, part_no→`-`, material→`POLYETHYLENE`, color→`-`, printing→`-` (2205–2210).
- Lỗi hiện ở status (`สร้างแบบไม่ได้ / Cannot build drawing: {exc}` khi preview, `บันทึกไม่ได้ / Cannot save: {exc}` khi save) VÀ messagebox lỗi có title NGUYÊN VĂN `แบบขออนุมัติ / Drawing for Approval` (2274–2275, 2299–2300, 2336–2337).

### 7.4 Nút Preview — `drawing_preview` (2269–2293)

Gọi `render_html(spec)` (drawing.py) → ghi file HTML vào `<application_data_dir>/drawing_previews/{doc_no-đã-lọc-ký-tự}-{YYYYmmdd-HHMMSS}.html` → mở bằng `os.startfile` (fallback `webbrowser.open`). Status NGUYÊN VĂN:
`เปิดแบบในเบราว์เซอร์แล้ว กดปุ่มพิมพ์แล้วเลือก A4 แนวนอน / Drawing opened in the browser; print as A4 landscape`

### 7.5 Nút Save — `drawing_save` (2295–2344)

Payload gửi `db.save_drawing`: `doc_no` (rỗng nếu chưa có `DFA-` — DB sẽ cấp số), `drawing_date`, `revision`, `customer`, `customer_code`, `title`, `part_no`, `product_key`, `length_datum`, `display_unit`, `width_mm`, `length_mm`, `height_mm`, `gusset_mm`, `thickness_mm`, và object `spec` {material, color, printing, tol_dim_lo, tol_dim_hi, tol_thickness, holes_count, holes_dia, label_w, label_h, extra_notes}. Thành công: điền số vào ô Document No., refresh register, status NGUYÊN VĂN:
`บันทึกแล้ว เลขเอกสาร {doc_no} / Saved as {doc_no}`

### 7.6 Nút New — `drawing_reset` (2346–2357)

Chỉ reset: doc_no → `— ยังไม่ออกเลข / not issued —`, revision → `A`, date → hôm nay, 4 ô kích thước → rỗng, độ dày → rỗng, textarea ghi chú → rỗng. (KHÔNG xoá khách/tên/vật liệu/màu...). Status NGUYÊN VĂN:
`เริ่มแบบใหม่ เลขเอกสารจะออกให้ตอนกดบันทึก / New drawing; the number is issued on save`

### 7.7 Register — `drawing_refresh_register` (2359–2378) + `drawing_load_selected` (2380–2423)

- Refresh: xoá hết dòng, đổ lại từ `db.search_drawings(text tìm kiếm)`.
- Open Selected: chưa chọn dòng → status NGUYÊN VĂN `เลือกแถวในทะเบียนก่อน / Select a row in the register first`. Chọn rồi: nạp toàn bộ record vào form (kích thước set lại với đơn vị `มม.`; defaults khi thiếu: material `POLYETHYLENE`, color `-`, printing `-`, tol -10/10/0.005, holes 0, label 0). Status NGUYÊN VĂN:
`เปิดแบบ {doc_no} แล้ว ถ้าจะแก้ให้เพิ่มครั้งที่แก้ก่อนบันทึก / Opened {doc_no}; raise the revision before saving changes`
- Double-click dòng = Open Selected (2132).

### 7.8 `choose_product_image` (4298–4308)

(Nút này thuộc tab Pricing, không thuộc tab Drawing — liệt kê vì đề bài yêu cầu.) `filedialog.askopenfilename` với title NGUYÊN VĂN `แนบรูปหรือไฟล์อ้างอิง / Attach Product Image or Reference File`; filetypes NGUYÊN VĂN: `("รูปภาพและ PDF", "*.png *.jpg *.jpeg *.bmp *.gif *.pdf")` và `("ไฟล์ทั้งหมด", "*.*")`. Chọn xong set `product_image_var` = đường dẫn.

---

## 8. DrawingSpec (drawing.py 40–100) — trường + nhãn, để web gửi đúng object

`PRODUCT_TO_SHAPE` (40–46): flat→`flat_bag` · gusset→`gusset_bag` · opaque→`plastic_sheet` · roll→`plastic_roll` · cover→`product_cover`.
`LENGTH_DATUM_TEXT` (48–51): opening_to_seal→`OPENING TO SEAL` · opening_to_bottom→`OPENING TO BOTTOM` (fallback `LENGTH` qua `length_label()`, 99–100).

`@dataclass DrawingSpec` (69–97), thứ tự trường và mặc định:

| Trường | Kiểu | Mặc định |
|---|---|---|
| doc_no | str | (bắt buộc) |
| customer | str | (bắt buộc) |
| title | str | (bắt buộc) |
| shape | str | (bắt buộc — key bảng SHAPES) |
| revision | str | `"A"` |
| date | str | `""` |
| part_no | str | `"-"` |
| customer_code | str | `""` |
| material | str | `"POLYETHYLENE"` |
| color | str | `"-"` |
| printing | str | `"-"` |
| width_mm / length_mm / height_mm / gusset_mm / thickness_mm | float | `0.0` (luôn mm — hàng comment 82: đơn vị người dùng chọn chỉ là hiển thị) |
| tol_dim_lo | float | `-10.0` |
| tol_dim_hi | float | `10.0` |
| tol_thickness | float | `0.005` |
| length_datum | str | `""` (`opening_to_seal` \| `opening_to_bottom`) |
| display_unit | str | `"mm"` (`mm` \| `inch`) |
| holes_count | int | `0` |
| holes_dia | str | `""` |
| label_w / label_h | float | `0.0` |
| extra_notes | list[str] | `[]` |

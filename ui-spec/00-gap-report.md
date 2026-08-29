# GAP REPORT — price.pantongone.com so với app desktop PantongOne v1.7.1

> Ngày đo: 27-08-2026 ~20:00. Nguồn sự thật: `Z:\1\app.py` v1.7.1 "(Phase 1) — Planning screen"
> (sửa 18:12 hôm nay — MỚI HƠN file exe v1.5.1 Bee tải lúc 17:31; clone theo nguồn, không theo exe).
> Chi tiết từng widget/màu/chữ nằm ở `01→05-*.md` cùng thư mục — file này CHỈ liệt kê khoảng thiếu,
> không chép lại spec (một sự thật một nơi).
>
> ⚠️ CEO đang sửa app liên tục trong ngày. Trước mỗi đợt clone mới: kiểm lại mtime `Z:\1\app.py`
> và `APP_VERSION` (app.py:51), lệch thì chạy lại catalog.

## Trạng thái web hiện tại (đã đọc toàn bộ mã)

`D:\ThaiPlasticPricing\pantongone-frontend` (React 19 + Vite, bundle local = bundle prod
`index-CApQo_fY.js`) + `server/` (FastAPI, `screen.py` giữ mọi nhãn chữ — frontend không có
tiếng Thái riêng). Web có 4 tab nhưng đều là bản RÚT GỌN của snapshot **sáng** 27-08;
desktop đã đi tiếp cả ngày.

## A. Khung chính (app shell)

| # | Desktop v1.7.1 | Web hiện tại | Spec |
|---|---|---|---|
| A1 | Header: **"PantongOne"** (branding.APP_NAME) + góc phải `ยังไม่บันทึก / Unsaved` (chữ BLUE, đổi thành số REF sau khi lưu) | Tiêu đề cũ "โปรแกรมคำนวณราคาพลาสติก / Plastic Pricing", không có quote-ref góc phải | 05 |
| A2 | Subtitle: `โปรแกรมคำนวณราคาพลาสติก / Plastic pricing • ระยะที่ 1 / Phase 1` | `ระยะที่ 1 • ราคาและประวัติ / Phase 1 • Pricing & Quote History` (cũ) | 05 |
| A3 | Toolbar 8 nút: New · Restore Latest Draft · Calculate (Accent) · Save (Accent) · Print Summary · Formula Variables · **ซิงค์ขึ้นเซิร์ฟเวอร์ / Sync** · **เซิร์ฟเวอร์ / Server** | 6 nút; nút Calculate chỉ chuyển tab, không tính | 01·05 |
| A4 | 2 dòng status: Warning `#9a6700` bold (`พร้อมคำนวณ—หากข้อมูลไม่ครบจะแจ้งตรงนี้ / Ready; missing fields will be shown here`) + dòng server Muted (`{who} • ค้างในเครื่อง / waiting here: {n}`) | 1 dòng, chữ khác, màu GREEN | 05 |
| A5 | Tab: nền `#dbe7f2`, selected BLUE trắng, hover `#b9d3e8`, padding 16×9 | nền `#e9eef3`, thiếu màu hover | 01 |
| A6 | Restore Latest Draft **luôn hiện** | chỉ hiện khi có draft (fix cố ý 27-08 — cần chốt giữ hay bỏ) | 05 |

Ghi chú A3: Sync/Server là khái niệm của bản desktop (làm việc offline rồi đẩy lên). Web
chính LÀ server — hai nút này vô nghĩa trên web. Cần Bee/CEO chốt: bỏ hẳn, hay vẽ nút mờ
để hai màn giống nhau từng nút.

## B. Tab คำนวณราคา / Pricing

| # | Desktop | Web | Spec |
|---|---|---|---|
| B1 | Card compact `ข้อมูลเสนอราคาและสเปกหลัก` + nút **`รายละเอียดเพิ่ม / More Details`** mở card đầy đủ 9 cụm ô (dùng chung biến) | Chỉ có card compact, không có More Details | 01 |
| B2 | Loại **cover**: ẨN thickness + mode + length-ref + bottom-allowance, HIỆN các ô vật liệu cover (roof/mesh GSM, area) | Vẫn vẽ thickness cho cover; roof_gsm=120, mesh_gsm=80 bị ghi cứng, không có ô nhập | 01 |
| B3 | Đổi mốc đo (ถึงซีล/ถึงก้น) → bottom allowance tự nhảy 1 ↔ 0 cm; 3 biến thể câu `allowance_note` theo loại | Không auto, 1 câu note tĩnh | 01 |
| B4 | Sale basis đổi → disable ô giá/chiếc, đổi nhãn + hint 2 ô giá, deduction luôn bật, caption động `จำนวนชิ้นต่อกก.หลังหัก {X}%` | Chỉ đổi nhãn 1 ô; caption tĩnh | 01·02 |
| B5 | 3 hộp giá 3 MÀU: xanh dương `#eaf3fb`/viền `#7aa7c7` · vàng `#fff4c2`/viền `#b7791f` dày 3px · xanh lá `#eaf7ee`/viền `#4b8f63`, ẩn/hiện theo sale basis | Cả 3 hộp kiểu xanh lá/xám, luôn hiện | 02 |
| B6 | Step bar nền `#1f6f5f` | web dùng `#17715c` — SAI MÀU | 02 |
| B7 | Băng section 7 màu: Product `#185a8d` · Spec `#0f766e` · Quality `#694a85` · Calculation `#2f6f4e` · Pricing `#1f6f5f` · Production `#9a5b13` · History `#5b4b8a` | chỉ 2 màu, đều sai số (`#167d5a`, `#8a5518`) | 01 |
| B8 | Cảnh báo trùng lịch sử 3 trạng thái, trùng Part No+Size → băng **Critical** chữ trắng nền đỏ + nút `ดูบริษัท / View Companies` | Không có gì | 04·05 |
| B9 | Nút chọn ảnh sản phẩm (`choose_product_image`) | Không có (cần chỗ lưu — quyết định MinIO còn treo) | 03 |
| B10 | Auto Markup readonly format `.2f` | có, format chưa kiểm | 02 |

## C. Tab ข้อมูลวางแผนการผลิต / Production Planning — **màn CEO vừa làm hôm nay, thiếu nhiều nhất**

| # | Desktop | Web | Spec |
|---|---|---|---|
| C1 | Card `ต้นทางจากใบคำนวณราคาที่บันทึกแล้ว` (Source `#9a5b13`): SuggestEntry width 48 + nút `▼` + nút Accent `รับข้อมูลใบราคา / Load Pricing Data`; gợi ý dạng `REF \| code \| customer \| item`; dòng so trọng lượng format `,.3f` kèm dấu `+` | **Không có** | 02 |
| C2 | Card Quality (ẩn mặc định) — dung sai ±W/L/T | **Không có** ô dung sai nào trên web | 01·02 |
| C3 | Card Planning Details (Calculation `#2f6f4e`) chứa **Notebook** con; bảng kết quả **12 ô** ResultCard `#f5f9fc`, giá trị NAVY 13 bold, reflow min-240px, format từng ô (กรัม 3 lẻ · ชิ้น 2 · กก. 4 · tiền 3) | Grid phẳng 6 ô nhập + **16** tile (danh sách cũ trong screen.py), format mặc định | 02 |
| C4 | Card Work Orders: 2 tab con **แผนกเป่า** / **แผนกตัดถุง**, mỗi tab nút Copy + nút Print (Accent); HTML in: h1 + bảng 7 hàng, th nền `#eef4f8` width 34%, viền `#999`, tự `window.print()` | **Không có** | 02 |

## D. Tab แบบขออนุมัติ / Drawing for Approval

| # | Desktop | Web | Spec |
|---|---|---|---|
| D1 | Hàng 4 nút đầu tab + dòng status Warning riêng | 2 nút cuối form | 03 |
| D2 | Card `Dimensions and Tolerances` (Spec `#0f766e`) — kích thước hiện theo loại + dung sai mặc định −10/10/0.005 | **Không có** — web lấy thẳng size từ form Pricing, không cho sửa/dung sai | 03 |
| D3 | Nút `ดึงข้อมูลจากหน้าคำนวณราคา / Copy from Pricing` — chép TƯỜNG MINH, chế độ pair thì **chia đôi độ dày** | Tự đọc form ngầm, không chia pair | 03 |
| D4 | **Save** cấp số `DFA-…` lúc lưu + card `Saved Drawing Register` 6 cột, double-click mở lại + nút Reset (giữ thông tin khách) | Không có save/register/reset (server ĐÃ có bảng drawings — migration 0002) | 03 |
| D5 | Preview ghi HTML ra file mở browser; in chỉ tờ vẽ | Preview SVG inline ✓ nhưng Print = in cả trang web | 03 |

## E. Tab ประวัติ / Quote History

| # | Desktop | Web | Spec |
|---|---|---|---|
| E1 | 7 ô lọc (customer SuggestEntry · code · item · **type combobox** · size · **from/to date** · sort); lọc khi **Enter/nút Search**, không lọc khi gõ; nút `ล้างตัวกรอง (ไม่ลบรายการ) / Clear Filters (does not delete)` | 4 ô lọc live-debounce; thiếu type/code/ngày; không có nút Search/Clear | 04 |
| E2 | Bảng **15 cột** căn TRÁI, số `{:,.3f}` (pack `{:,.4f}`), trang 500 dòng, rowheight 31 | 9 cột, numeric căn phải, trang 200 | 04 |
| E3 | Dòng đếm: `{n:,} รายการ / records` và `แสดง … จากทั้งหมด … / showing X of Y` | câu tự chế khác | 04 |
| E4 | **5 nút dưới bảng** (Edit / Print Selected / Delete Selected… chỉ bật khi chọn dòng) + chọn dòng | Không có khái niệm chọn dòng, không nút nào | 04 |
| E5 | Cửa sổ **xem chi tiết** 760×650 (~30 dòng, rẽ nhánh kg/chiếc, cover thêm 2 dòng diện tích) | Không có | 04 |
| E6 | Cửa sổ **Related** 1080×480, 13 cột (ô pack chưa đặt hiện `ยังไม่ได้กำหนด / Not Set`) | Không có | 04 |
| E7 | **Record picker** 1120×620, 9 cột, nút `ใช้ข้อมูลที่เลือกเป็นงานใหม่ / Use Selected as New` → nạp lại form | Không có — web KHÔNG có đường nào mở lại tờ cũ vào form | 04 |
| E8 | Xoá có câu xác nhận verbatim + 3 messagebox | API xoá có, UI không có | 04 |

## F. In tóm tắt / Print Summary

| # | Desktop | Web | Spec |
|---|---|---|---|
| F1 | `_build_print_html`: trang in 4 section, CSS đủ mã màu (body `#172b3a`/`#eef3f7`, h2 trắng/`#1f6aa5`, nút `#167d5a`, viền bảng `#9fb1c1`/`#6f91ac`, th 44% `#f1f6fa`), 11 nhãn identity + 9 nhóm dòng kết quả, tự `window.print()` sau 350ms | `window.print()` in nguyên màn hình | 05 |

## G. Đăng nhập + Formula + Nháp

| # | Desktop | Web | Spec |
|---|---|---|---|
| G1 | Gate: dòng `v1.7.1  •  download.pantongone.com`, cảnh báo offline ≤3 ngày, font **Segoe UI** 9/10/15bold, nút `ออก / Exit` | Gần khớp; version_label cũ, không cảnh báo offline (N/A?), font Leelawadee | 05 |
| G2 | Formula help 650×600, **Consolas 10**, 22 biến + dòng operators/functions | Có dialog, cần đối chiếu 22 biến + monospace | 04 |
| G3 | Nháp: câu hỏi xác nhận + 3 messagebox verbatim, restore về tab Pricing, fallback flat | localStorage im lặng, không câu chữ | 05 |

## Việc hạ tầng đi kèm (không phải UI nhưng chặn đường)

1. **`screen.py` phải làm mới toàn bộ theo v1.7.1** — mọi nhãn mới (planning source, work
   order, 15 cột history, 5 nút, dialog, print) phải vào đây trước, frontend chỉ đọc.
   Đây là bước 1 của mọi bước.
2. Backend cần thêm: endpoint planning-source lookup/load; drawing save/register/load
   (bảng đã có từ 0002); print payload đầy đủ như `_current_print_payload`; related theo
   Part No+Size khớp logic desktop; history đủ 15 cột + lọc type/date + trang 500.
3. `D:\ThaiPlasticPricing` **chưa nằm trong git** (vi phạm H6) — rủi ro lớn nhất repo này,
   ghi từ frontend-report 27-08, vẫn chưa xử.
4. Kiểm tra bằng mắt: chạy desktop từ nguồn không cần gate
   (`PlasticPricingApp(db_path=temp)` — server/session mặc định None) để chụp màn từng tab,
   so với web qua Playwright (Bee đã cho phép MCP 27-08).

## Thứ tự clone đề xuất

1. `screen.py` mới + shell (A1–A6, B5–B7 màu) — mọi thứ khác đứng trên nó
2. Tab Pricing đầy đủ (B1–B4, B8, B10)
3. Tab Planning (C1–C4) — màn CEO vừa dựng, thiếu nặng nhất
4. History (E1–E8) — nhiều đường dùng hằng ngày (mở lại tờ cũ)
5. Print Summary (F1) + Drawing (D1–D5)
6. Gate/Formula/Nháp (G1–G3) — phần lệch nhỏ
7. Mỗi bước: build + test + Playwright chụp web ↔ chụp desktop, sửa đến khớp

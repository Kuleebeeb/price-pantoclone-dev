# Frontend Audit & Fix — PantongOne web

Ngày: 2026-08-27 · Stack phát hiện: **React 19 + TypeScript + Vite 7**
(không Tailwind · không Next.js · không React Router · không thư viện i18n)

Khác lần audit trước (bản desktop Tkinter, 10/10 mảng đều không áp dụng): lần này
**6/10 mảng áp dụng được**, vì đây là ứng dụng web thật.

Audit chạy trên bản **đang chạy thật** tại `https://price.pantongone.com`, mở bằng
trình duyệt thật — không chỉ đọc mã nguồn. Bốn lỗi dưới đây **chỉ nhìn thấy khi
mở màn hình lên**, không có lỗi nào trong số đó làm test đỏ hay build gãy.

---

## Chỉ số

| Mảng | Vấn đề tìm thấy | Đã fix | Còn lại |
|---|---|---|---|
| React (state, effect, render) | 2 | 2 | 0 |
| Async / dữ liệu | 0 | — | 0 |
| Accessibility | 2 | 2 | 0 |
| Chữ hiển thị sai / vô nghĩa | 4 | 4 | 0 |
| Bố cục (CSS) | 1 | 1 | 0 |
| TypeScript | 0 | — | 0 |
| Testing | 1 | 1 | 0 |
| **Tổng** | **10** | **10** | **0** |

Test: **21 xanh** · `tsc --noEmit` sạch · `oxlint` sạch · console trình duyệt **0 lỗi, 0 cảnh báo**.

---

## Đã fix (chi tiết)

| # | Mảng | Nơi | Trước → Sau |
|---|---|---|---|
| 1 | React | `Desk.tsx` effect `[meta]` | Khi nhãn từ máy chủ về, nó **thay cả biểu mẫu** bằng `blank(meta)`. Mạng chậm, hoặc mở lại bản nháp có ô "จุดอ้างอิงความยาว" rỗng → **xoá sạch những gì đã gõ, không báo gì**. Nay chỉ điền đúng một ô còn thiếu |
| 2 | React | `Desk.tsx` effect `[form]` | Bản nháp được ghi vô điều kiện, nên trên máy chưa dùng bao giờ nút **"เปิดร่างล่าสุด / Restore Latest Draft" tự hiện sau 0,8 giây** — mời mở lại một biểu mẫu rỗng. Nay chỉ ghi khi đã có tên khách hoặc kích thước |
| 3 | A11y | `Desk.tsx` ô tên khách | Danh sách gợi ý nằm **bên trong `<label>`**, mà `<label>` biến mọi cú bấm bên trong thành cú bấm vào ô nhập. Nay là `<div>` + `aria-label` |
| 4 | A11y | `styles/tokens.css` | Không có viền focus ngoài màn đăng nhập — người dùng Tab đi hết 30 ô mà không thấy mình đang ở đâu. Thêm `:focus-visible` toàn cục |
| 5 | Chữ | `History.tsx` | Dòng đếm ghi `200 รายการ / records — ชื่อ/รหัสลูกค้า / Customer` — hai nhãn dính vào nhau, vô nghĩa, và tệ hơn là **nói với người dùng rằng họ đã xem hết** trong khi sổ có 17.391 dòng |
| 6 | Chữ | `Login.tsx` | Trên ô mật khẩu in `src-2026-08-27T07:42 (formulas == exe v1.2.3)` — đó là chuỗi build dành cho log. Nay là `version_label` do máy chủ trả về, một dòng đọc được |
| 7 | Chữ | `Login.tsx` | Thứ tự tiêu đề khác bản desktop (phụ đề nằm **sau** dòng phiên bản). Nay đúng thứ tự .exe |
| 8 | Chữ | `Drawing.tsx` | Nút in bản vẽ mang nhãn **"พิมพ์สรุป / Print Summary"** — tên của nút khác. Thêm `drawing.buttons.print` ở máy chủ |
| 9 | Chữ | `Desk.tsx` | Một chuỗi tiếng Thái **viết cứng trong frontend** (nút mở bản nháp) — phá đúng luật mà chính tệp này đặt ra. Chuyển sang `screen.py` |
| 10 | CSS | `Desk.css` `.desk-band` | Mọi dải màu bị kéo lên 14px, nên **dải nâu thứ hai leo lên đè ghi chú** của ô ngay trên nó — dòng "ความหนาบนแบบพิมพ์เป็นมิลลิเมตรเสมอ" bị che mất một nửa. Nay chỉ dải đầu tiên được kéo lên |
| 11 | UX | `Formulas.tsx` | Ô công thức trọng lượng **trống trơn**: trống nghĩa là "dùng mặc định của loại sản phẩm", nhưng người mở cửa sổ ra là để **đọc** công thức. Nay công thức thật hiện dạng placeholder — đọc được mà vẫn bám theo loại sản phẩm |

**Test thêm:** `Suggest.test.ts` (8 ca cho thứ tự gợi ý), nâng 13 → 21.

---

## Hai lỗi backend bắt được trong lúc audit

Không thuộc frontend nhưng cùng đợt, và cả hai đều **im lặng**:

- **Mount trang web đặt giữa `main.py`** nuốt mọi route khai báo sau nó.
  `/api/health`, `/api/meta`, `/api/calculate`, toàn bộ `/api/quotations` trả 404
  trong khi `/api/version` vẫn sống — nên nhìn từ ngoài tưởng máy chủ vẫn ổn.
  Mount phải là **dòng cuối cùng của tệp**.
- **Frontend gọi `/auth/login`** trong khi router có tiền tố `/api`. Trả về **405
  Method Not Allowed**, không phải 404 — vì mount `"/"` nhận đường đó nhưng chỉ
  cho GET. Một mã lỗi chỉ đúng nửa sự thật là mã lỗi dẫn đi sai hướng.

---

## Đã bỏ qua (không thuộc stack)

- **Tailwind** — SKIPPED: CSS thuần + custom properties (`styles/tokens.css`),
  theo `tech-stack.md` §2.
- **Next.js** — SKIPPED: không có `next.config`, không có `app/`.
- **React Router** — SKIPPED: một màn hình đổi nội dung, chọn bằng `useState`.
  Không có URL nào người dùng gõ hay bookmark.
- **i18n** — SKIPPED, và **cố ý**: không có thư viện locale. Mọi chữ song ngữ
  Thái/Anh do `/api/meta` trả về, lấy nguyên văn từ `app.py` của bản .exe. Dịch
  chúng là làm sai — đó là nhãn của một chương trình người ta đang dùng hằng ngày.

---

## Cần review tay (không tự fix)

- **Ô ngày hiển thị theo locale trình duyệt** (`08/27/2026` trên máy này) trong khi
  bản desktop luôn in `2026-08-27`. Đây là `<input type="date">` gốc của trình duyệt:
  đổi sang ô chữ sẽ khớp bản desktop nhưng mất bộ chọn ngày trên điện thoại. Chưa đổi.
- **Dữ liệu có tên khách trùng lặp.** Danh sách gợi ý làm lộ ra ngay: *Honda Logistics
  Asia* tồn tại dưới **4 cách viết** (`Co.,Ltd.` · `CO.,Ltd.` · `Co., Ltd.` · `CO.,LTD.`).
  Ô gợi ý ngăn được từ nay trở đi, nhưng 17.391 dòng cũ thì cần một đợt gộp — và
  đó là quyết định nghiệp vụ, không phải việc của frontend.
- **Chưa có test render cho `Desk` và `History`.** Phần thuần (dựng request, lọc gợi ý)
  đã có test; phần vẽ ra màn hình thì chưa.
- **Kho mã `D:\ThaiPlasticPricing` vẫn chưa nằm trong git.** Deploy đang là `scp`.
  Đây là rủi ro lớn nhất còn lại của cả dự án, và nó không phải lỗi frontend.

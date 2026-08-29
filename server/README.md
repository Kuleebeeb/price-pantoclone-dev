# pacos-pricing

Bản web của **ThaiPlasticPricing** — phần mềm tính giá sản phẩm nhựa mà CEO đã dựng
bằng ChatGPT (bản gốc: `Z:\1`, desktop Tkinter, `.exe` v1.2.3).

Cùng công thức, cùng màn hình, khác chỗ chạy: mở bằng trình duyệt, dữ liệu nằm trong
Postgres trên máy chủ thay vì file SQLite trên một máy lẻ.

---

## Điều quan trọng nhất: công thức KHÔNG được chép lại

`core/calculator.py` và `core/formula_engine.py` là **bản sao từng byte** của bản desktop.

```
45f93633702898dfec83f0dc709445bc  calculator.py       (giống hệt bản gốc)
d0164747503a870a4b756b40625be481  formula_engine.py   (giống hệt bản gốc)
```

**Không sửa hai file này.** Muốn đổi công thức thì đổi ở bản gốc rồi chép sang, và
chạy lại `tests/test_parity.py`.

Lý do: nhà máy đã trả giá một lần cho chuyện chép công thức. SRS §1.1 ghi mỗi nhân
viên dùng một hệ số riêng (1.620 / 1.800) và giá vốn lệch **11%** cho cùng một sản
phẩm. Chép công thức sang ngôn ngữ khác là mở lại đúng cái cửa đó. Ở đây chỉ có
**một** bản công thức, và cả web lẫn `.exe` đều gọi chính nó.

`api/main.py` chỉ làm ba việc: quy đổi đơn vị ở biên, gọi `calculate()`, và định dạng
chữ hiển thị. Nếu số web lệch số `.exe`, lỗi nằm ở `api/main.py` — không bao giờ ở công thức.

### Test đối chiếu

```bash
.venv/Scripts/python.exe tests/test_parity.py
```

12 ca (cả 5 loại sản phẩm, đủ đơn vị nút/micron/mét, bán theo kg và theo chiếc,
bật/tắt hệ số hao hụt), mỗi ca so **15 trường**. Đỏ một số là dừng deploy.

---

## Chạy trên máy lập trình

```bash
py -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
cp .env.example .env          # rồi điền DATABASE_URL
.venv/Scripts/python.exe -m uvicorn main:app --app-dir api --port 8100
```

Mở `http://127.0.0.1:8100`.

Chạy bằng Docker (giống hệt máy chủ):

```bash
docker compose build
docker compose up -d
curl http://127.0.0.1:8101/api/health
```

---

## Ba màn hình

| Tab | Làm gì |
|---|---|
| **คำนวณราคา / Pricing** | Nhập khách + quy cách + giá, bấm Calculate, nhập giá bán, bấm Save |
| **ข้อมูลวางแผนการผลิต / Production Planning** | Số lượng đặt, đóng gói, dung sai, công thức sửa được, bảng 16 ô kết quả |
| **ประวัติ / Quote History** | Lọc theo khách/hàng/loại/ngày/kích thước, mở lại, xoá |

Năm loại sản phẩm giữ nguyên bản gốc: túi thẳng · tấm nhựa · túi hông · màng cuộn ·
túi cover. Ô nhập tự đổi theo loại đúng như bản desktop.

---

## API

| Method | Đường dẫn | Làm gì |
|---|---|---|
| GET | `/api/health` | Ping **thật** Postgres, 503 kèm lý do nếu hỏng |
| GET | `/api/meta` | Danh sách loại SP, đơn vị, công thức mặc định, biến dùng được |
| POST | `/api/calculate` | Tính, không lưu |
| POST | `/api/quotations` | Tính lại phía máy chủ rồi lưu, trả số REF |
| GET | `/api/quotations` | Tìm kiếm, lọc, sắp xếp |
| GET | `/api/quotations/related` | Khách nào khác từng được chào cùng mã hàng |
| GET | `/api/quotations/{ref}` | Một tờ đầy đủ, kèm snapshot |
| DELETE | `/api/quotations/{ref}` | Xoá |

Tài liệu tự sinh: `/api/docs`.

**Máy chủ luôn tính lại khi lưu.** Không nhận số giá do trình duyệt gửi lên — sửa
JSON trong DevTools không đổi được giá đã lưu (luật K1).

---

## Dữ liệu

Postgres, database riêng tên `pricing`, **cùng máy chủ Postgres với PacOs nhưng khác
database**. Một migration sai ở đây không chạm được vào 70 báo giá của PacOs.

Mỗi tờ lưu ba khối JSON — `inputs_json`, `formulas_json`, `results_json` — nên mở lại
một báo giá ba năm sau vẫn giải thích được vì sao lúc đó giá là như vậy.

### Số REF: đã sửa một lỗi của bản gốc

Bản desktop cấp số bằng `SELECT MAX(quote_ref)+1` ([database.py:147](../../../Z:/1/database.py)).
Hai người bấm Lưu cùng lúc đọc ra cùng một số lớn nhất và ghi cùng một số.

Ở đây số được cấp bằng **một câu** `INSERT ... ON CONFLICT DO UPDATE ... RETURNING`
trên bảng `quotation_counters`. Postgres khoá dòng đó lại, nên không thể trùng.

Đã kiểm: **30 lần lưu đồng thời, 0 số trùng, 0 lỗi**, số chạy liền mạch 0001→0030.

Định dạng số **giữ nguyên** `QT-YYYYMMDD-NNNN` để CEO không thấy khác.

> Còn một điểm khác PacOs: PacOs đếm số theo **từng khách, reset mỗi năm** (luật P10).
> Bản này đếm theo **ngày**, đúng như bản desktop. Chưa đổi vì đây là bản clone —
> đổi cách đánh số là đổi thứ CEO nhìn thấy, phải hỏi trước.

---

## Deploy

**Không cần tên miền con, không cần certbot, không cần đụng DNS.** Nó nằm trong
`pantongone.com` như một đường dẫn nội bộ `/pricing-api/`, do nginx của container `web`
chuyển tiếp (`pacos-fontend/nginx.conf`). Hệ quả: **đã có sẵn đăng nhập của PacOs** — màn hình
gác bằng quyền `specs.calc`, không có cửa thứ hai vào dữ liệu giá vốn.

Thứ tự trên máy chủ:

```bash
cd /srv/pacos/pacos-pricing && docker compose up -d --build   # service Python
cd /srv/pacos/pacos-infra   && docker compose up -d --build web   # nginx + bundle
```

`deploy/deploy.sh` làm 6 bước và **dừng nếu bước nào hỏng**:

1. `pg_dump` database `pricing` — trước khi làm bất cứ gì
2. `git pull --ff-only`
3. `docker compose build`
4. **chạy test đối chiếu** — lệch một số là dừng, không deploy
5. `docker compose up -d`
6. poll `/api/health` tối đa 60 giây, hỏng thì in log và trả mã lỗi

Nó **không** tự dựng lại container `web`. Đổi giao diện thì phải chạy lệnh thứ hai ở trên.

## Chỗ chưa làm

Bản này là **Phase 1 web**, bám đúng phạm vi bản desktop. Chưa có:

- **Trang tự phục vụ ở `web/` không có đăng nhập.** Nó là bản chạy độc lập để thử nhanh
  (cổng 8101). Đường dùng thật là qua PacOs (`/pricing-api/` + màn Price estimates), ở đó
  phiên đăng nhập và quyền `specs.calc` đã gác sẵn. **Đừng mở cổng 8101 ra internet.**
- Đính kèm ảnh/bản vẽ (bản desktop chọn file trên máy; trên web cần chỗ lưu như MinIO)
- Xuất PDF/Excel — hiện dùng lệnh In của trình duyệt
- Tab "ต้นทางจากใบคำนวณราคาที่บันทึกแล้ว" (nạp lại từ tờ đã lưu để so trọng lượng)
- Phiếu công việc cho phân xưởng (`copy_to_work_order` / `print_work_order`)
- Lưu nháp tự động (`restore_latest_draft`)

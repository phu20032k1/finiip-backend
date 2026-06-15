# IIP/Finiip - Hướng dẫn nhập dữ liệu thật Giai đoạn 1

Mục tiêu: cho Finiip chạy được bằng dữ liệu thật trước khi làm frontend riêng.

## 1. Bộ file mẫu đã thêm

Có 2 dạng mẫu trong thư mục `templates/`:

- `templates/iip_stage1_input_templates.xlsx`: một workbook tổng hợp nhiều sheet để xem nhanh.
- `templates/iip_stage1_inputs/*.xlsx`: các file Excel riêng, dùng để import trực tiếp vào API.

Các file import trực tiếp:

| File | API import | Người nhập chính |
|---|---|---|
| `01_dealers.xlsx` | `POST /iip/import/dealers` | Kinh doanh / kế toán công nợ |
| `02_sales_staff.xlsx` | `POST /iip/import/sales-staff` | Quản lý kinh doanh / nhân sự |
| `03_price_floors.xlsx` | `POST /iip/import/price-floors` | Chủ tịch / giám đốc kinh doanh |
| `04_credit_limits.xlsx` | `POST /iip/import/credit-limits` | Chủ tịch / kế toán công nợ |
| `05_orders.xlsx` | `POST /iip/import/orders` | Kinh doanh / kế toán bán hàng |
| `06_debts.xlsx` | `POST /iip/import/debts` | Kế toán công nợ |
| `07_payments.xlsx` | `POST /iip/import/payments` | Kế toán ngân hàng |
| `08_invoices.xlsx` | `POST /iip/import/invoices` | Kế toán thuế |
| `09_vas_targets.xlsx` | `POST /iip/import/vas-targets` | Chủ tịch / quản lý kinh doanh |

> Lưu ý: giữ nguyên dòng header đầu tiên trong Excel. Dữ liệu thật bắt đầu từ dòng 2.

## 2. Thứ tự nhập dữ liệu khuyến nghị

```text
sales-staff
→ dealers
→ price-floors
→ credit-limits
→ orders
→ debts
→ payments
→ invoices
→ vas-targets
```

Sau khi nhập xong, kiểm tra:

```text
GET /iip/status
GET /iip/chairman/morning-report
GET /iip/risk/overdue-debts
GET /iip/risk/credit-limit-violations
GET /iip/risk/low-price-sales
GET /iip/reconcile/4-way
GET /iip/vas/progress
```

## 3. Cách test nhanh không cần frontend

Chạy backend:

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Mở Swagger:

```text
http://127.0.0.1:8000/docs
```

Hoặc chạy test tự động:

```bash
python scripts/test_iip_real_input_api.py
```

Script này sẽ import các file Excel mẫu trong `templates/iip_stage1_inputs/`, sau đó gọi báo cáo sáng và đối soát 4 chiều.

## 4. Luồng thực tế khi có frontend riêng

```text
Kế toán / kinh doanh nhập dữ liệu trên frontend
        ↓
Frontend gọi API POST /iip/...
        ↓
Backend lưu database
        ↓
Backend tự tính cảnh báo
        ↓
Chủ tịch xem dashboard/báo cáo sáng
```

Frontend không cần xử lý nghiệp vụ phức tạp. Logic nghiệp vụ nằm ở backend.

## 5. Tối thiểu cần nhập mỗi ngày

Hằng ngày nên nhập 4 nhóm trước:

1. Đơn hàng phát sinh: `orders`
2. Công nợ: `debts`
3. Tiền về/sao kê: `payments`
4. Hóa đơn đầu ra: `invoices`

Các nhóm như đại lý, nhân viên, giá sàn, hạn mức tín dụng chỉ cần cập nhật khi có thay đổi.

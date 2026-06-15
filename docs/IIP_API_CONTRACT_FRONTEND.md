# IIP API Contract cho Frontend riêng

Mục tiêu: frontend làm riêng, không chứa logic nghiệp vụ. Frontend chỉ gọi API backend `/iip/*`.

## 1. Chạy backend

```bash
cd copy
pip install -r requirements.txt
uvicorn main:app --reload
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

Seed dữ liệu mẫu:

```bash
python scripts/seed_iip_sample_data.py
```

Test API lõi:

```bash
python scripts/test_iip_backend.py
```

---

## 2. Base URL

Dev local:

```text
http://127.0.0.1:8000
```

Tất cả API IIP có prefix:

```text
/iip
```

---

## 3. Màn Dashboard Chủ tịch

### GET `/iip/chairman/morning-report`

Dùng cho màn hình báo cáo sáng.

Frontend hiển thị:

- Hôm nay cần thu
- Nợ quá hạn
- Đại lý vượt hạn mức
- Nhân viên bán dưới giá sàn
- Rủi ro VAS
- Dự báo dòng tiền

Ví dụ gọi:

```bash
curl http://127.0.0.1:8000/iip/chairman/morning-report
```

---

## 4. Màn Công nợ & Đại lý

### GET `/iip/risk/overdue-debts`

Danh sách công nợ quá hạn.

```bash
curl http://127.0.0.1:8000/iip/risk/overdue-debts
```

### GET `/iip/risk/credit-limit-violations`

Danh sách đại lý vượt hạn mức.

```bash
curl http://127.0.0.1:8000/iip/risk/credit-limit-violations
```

### GET `/iip/dealers/{dealer_code}/wallet`

Ví công nợ từng đại lý.

```bash
curl http://127.0.0.1:8000/iip/dealers/DL_SON_LA/wallet
```

---

## 5. Màn Cảnh báo rủi ro

### GET `/iip/risk/low-price-sales`

Danh sách đơn hàng bán dưới giá sàn.

```bash
curl http://127.0.0.1:8000/iip/risk/low-price-sales
```

### POST `/iip/orders/{order_code}/check-before-approve`

Kiểm tra đơn trước khi duyệt.

```bash
curl -X POST http://127.0.0.1:8000/iip/orders/ORD001/check-before-approve
```

### POST `/iip/orders/{order_code}/approve`

Duyệt đơn nếu không vi phạm.

```bash
curl -X POST http://127.0.0.1:8000/iip/orders/ORD001/approve
```

---

## 6. Màn Đối soát 4 chiều

### GET `/iip/reconcile/4-way`

Đối soát:

```text
Đơn hàng / xuất kho / hóa đơn / công nợ / tiền về
```

```bash
curl http://127.0.0.1:8000/iip/reconcile/4-way
```

Frontend nên hiển thị các trạng thái:

- OK
- Thiếu hóa đơn
- Thiếu thanh toán
- Thiếu xuất kho
- Lệch công nợ

---

## 7. Màn VAS

### GET `/iip/vas/progress`

Theo dõi sản lượng VAS và rủi ro hụt thưởng.

```bash
curl http://127.0.0.1:8000/iip/vas/progress
```

### POST `/iip/vas-targets`

Tạo/chỉnh mục tiêu VAS.

```json
{
  "year": 2026,
  "target_ton": 50000,
  "bonus_amount": 1800000000,
  "milestones": [
    {"ton": 40000, "bonus": 1000000000},
    {"ton": 50000, "bonus": 1800000000}
  ]
}
```

---

## 8. API nhập liệu thủ công

Frontend form nhập liệu gọi các API này:

```text
POST /iip/dealers
POST /iip/sales-staff
POST /iip/products
POST /iip/price-floors
POST /iip/credit-limits
POST /iip/debts
POST /iip/orders
POST /iip/payments
POST /iip/invoices
POST /iip/warehouse-slips
POST /iip/deliveries
```

API xem danh sách:

```text
GET /iip/dealers
GET /iip/sales-staff
GET /iip/products
GET /iip/price-floors
GET /iip/credit-limits
GET /iip/debts
GET /iip/orders
GET /iip/payments
GET /iip/invoices
GET /iip/warehouse-slips
GET /iip/deliveries
GET /iip/vas-targets
```

---

## 9. Import file Excel/CSV

Xem template:

```bash
curl http://127.0.0.1:8000/iip/import/templates
```

Import:

```text
POST /iip/import/{data_type}
```

Ví dụ:

```bash
curl -X POST -F "file=@dealers.csv" http://127.0.0.1:8000/iip/import/dealers
```

`data_type` hỗ trợ:

```text
dealers
sales-staff
products
price-floors
credit-limits
debts
payments
invoices
warehouse-slips
deliveries
vas-targets
```

---

## 10. Nguyên tắc frontend

Frontend không tự tính công nợ, không tự tính rủi ro, không tự tính VAS.

Frontend chỉ:

1. Gọi API
2. Hiển thị dữ liệu
3. Gửi form nhập liệu
4. Hiển thị cảnh báo từ backend

Logic nghiệp vụ nằm ở backend để sau này mobile app, web app, chatbot, AI agent đều dùng chung được.

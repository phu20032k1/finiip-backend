# IIP Backend-first – lộ trình 5 bước

Mục tiêu: làm backend trước, frontend tách riêng và chỉ gọi API sau.

## Bước 1 – Kích hoạt backend IIP

File `iip_steel_platform.py` đã được đưa ra thư mục gốc, ngang hàng với `main.py`.

Chạy backend:

```bash
cd copy
pip install -r requirements.txt
uvicorn main:app --reload
```

Kiểm tra Swagger:

```text
http://127.0.0.1:8000/docs
```

API kiểm tra nhanh:

```bash
curl http://127.0.0.1:8000/iip/status
```

## Bước 2 – Nạp dữ liệu nền

Giai đoạn 1 cần 8 nhóm dữ liệu:

1. Đại lý cấp 2
2. Công nợ hiện tại
3. Nhân viên kinh doanh
4. Bảng giá sàn
5. Hạn mức tín dụng
6. Đơn hàng phát sinh hằng ngày
7. Thanh toán / sao kê ngân hàng
8. Hóa đơn đầu ra

Xem template import:

```bash
curl http://127.0.0.1:8000/iip/import/templates
```

Nạp dữ liệu demo để test:

```bash
curl -X POST http://127.0.0.1:8000/iip/demo/seed
```

## Bước 3 – Làm lõi công nợ, hạn mức, giá sàn

Các API cần frontend gọi đầu tiên:

```text
GET  /iip/chairman/morning-report
GET  /iip/risk/overdue-debts
GET  /iip/risk/credit-limit-violations
GET  /iip/risk/low-price-sales
GET  /iip/dealers/{dealer_code}/wallet
POST /iip/orders/{order_code}/check-before-approve
POST /iip/orders/{order_code}/approve
```

Mục tiêu bước này: Chủ tịch nhìn thấy ngay nợ quá hạn, đại lý vượt hạn mức, nhân viên bán dưới giá sàn.

## Bước 4 – Làm đối soát 4 chiều và VAS

API đối soát:

```text
GET /iip/reconcile/4-way
```

Logic đối soát:

```text
Đơn hàng / hàng xuất kho / hóa đơn / công nợ / tiền về
```

API VAS:

```text
GET  /iip/vas/progress
POST /iip/vas-targets
```

Mục tiêu bước này: cảnh báo thiếu hóa đơn, tiền chưa về, rủi ro hụt thưởng VAS.

## Bước 5 – Frontend làm riêng, chỉ gọi API

Frontend không chứa logic nghiệp vụ. Frontend chỉ hiển thị dữ liệu từ backend.

4 màn hình frontend nên làm đầu tiên:

1. Dashboard Chủ tịch: gọi `/iip/chairman/morning-report`
2. Công nợ & đại lý: gọi `/iip/risk/overdue-debts`, `/iip/dealers/{dealer_code}/wallet`
3. Cảnh báo rủi ro: gọi `/iip/risk/credit-limit-violations`, `/iip/risk/low-price-sales`
4. Đối soát 4 chiều + VAS: gọi `/iip/reconcile/4-way`, `/iip/vas/progress`

## Test nhanh toàn bộ backend

```bash
python scripts/test_iip_backend.py
```

Kết quả đúng là các API đều trả về HTTP 200.

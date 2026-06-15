# Finiip + IIP Steel Platform Backend V2

Bản V2 nâng cấp tiếp backend IIP Steel Giai đoạn 1 để dễ demo và tiến gần triển khai thật hơn.

## 1. Chạy backend

```bash
cd copy
pip install -r requirements.txt
uvicorn main:app --reload
```

Mở Swagger:

```text
http://127.0.0.1:8000/docs
```

## 2. Seed dữ liệu demo V2

```bash
curl -X POST http://127.0.0.1:8000/iip/demo/seed-v2
```

Sau khi seed, có thể dùng API key demo:

```text
demo-chairman-key
```

Header demo:

```text
X-IIP-API-Key: demo-chairman-key
```

## 3. API mới quan trọng trong V2

### Kiểm tra trạng thái V2

```http
GET /iip/v2/status
GET /iip/roadmap/completion-score
```

### Tải Excel template cho 8 dữ liệu đầu vào

```http
GET /iip/import/template/dealers
GET /iip/import/template/debts
GET /iip/import/template/sales-staff
GET /iip/import/template/price-floors
GET /iip/import/template/credit-limits
GET /iip/import/template/orders
GET /iip/import/template/payments
GET /iip/import/template/invoices
```

### AI hỏi dữ liệu thật bằng tiếng Việt

```http
POST /iip/ai/ask
```

Ví dụ body:

```json
{
  "question": "VAS có nguy cơ hụt thưởng không?",
  "role": "chairman"
}
```

Có thể hỏi:

- Hôm nay công nợ thế nào?
- Ai vượt hạn mức?
- Đơn nào bán dưới giá sàn?
- VAS có hụt thưởng không?
- Đối soát 4 chiều thế nào?
- Đại lý nào có nguy cơ mất khách?

### Tin nhắn báo cáo sáng cho Chủ tịch

```http
GET /iip/reports/chairman-message
POST /iip/reports/notification-draft
POST /iip/reports/schedules
GET /iip/reports/schedules
```

### Phân quyền demo

```http
POST /iip/users
GET /iip/users
GET /iip/auth/me
```

Các role demo:

```text
admin, chairman, accounting, sales, warehouse, driver, dealer
```

### Duyệt ngoại lệ vượt hạn mức / giá thấp

```http
POST /iip/orders/{order_code}/override-credit-limit
GET /iip/approval-exceptions
```

### Rủi ro mất đại lý cấp 2

```http
GET /iip/dealers/churn-risk
```

### Geofence vận chuyển

```http
POST /iip/geofence/rules
GET /iip/deliveries/{delivery_code}/geofence-check?lat=21.3256&lng=103.9188
```

### Task mobile theo vai trò

```http
GET /iip/mobile/tasks/chairman
GET /iip/mobile/tasks/accounting
GET /iip/mobile/tasks/warehouse
GET /iip/mobile/tasks/driver
GET /iip/mobile/tasks/sales
GET /iip/mobile/tasks/dealer
```

### Xuất CSV dữ liệu

```http
GET /iip/export/dealers.csv
GET /iip/export/orders.csv
GET /iip/export/debts.csv
```

## 4. Mức hoàn thiện sau V2

Backend Giai đoạn 1 hiện đạt khoảng 78-80% theo kế hoạch IIP nếu xét logic backend.

Điểm đã bổ sung trong V2:

- RBAC user/api-key model
- Excel template tải trực tiếp
- AI Ask router hỏi dữ liệu thật
- Approval workflow cho đơn rủi ro
- Dealer churn risk
- Geofence check
- Report schedule và notification draft
- CSV export
- Roadmap completion score

## 5. Việc tiếp theo nên làm

Sau V2, nên làm tiếp:

1. Frontend Dashboard Chủ tịch.
2. Frontend import Excel cho kế toán.
3. Giao diện đơn hàng / duyệt ngoại lệ.
4. Portal đại lý cấp 2.
5. Mobile giao hàng / quét QR thật.
6. PostgreSQL + Alembic + Docker production.

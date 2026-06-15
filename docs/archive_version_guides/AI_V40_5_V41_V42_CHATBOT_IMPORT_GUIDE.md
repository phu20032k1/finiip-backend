# Finiip V40.5–V42: Import dữ liệu, learning memory và chatbot kế toán

## Mục tiêu

Bản này nâng V25–V40 thành một MVP có dữ liệu đầu vào tốt hơn và chatbot dùng được:

- V40.5: Import dữ liệu kế toán từ JSON bulk, CSV, XLSX và tạo dữ liệu mẫu.
- V40.5 Learning Memory: hệ thống ghi nhớ ví dụ từ approve/reject/post để học dần.
- V41: Chatbot hỏi báo cáo, tính VAT, lợi nhuận, dashboard, xuất Excel.
- V42: Chatbot hành động có xác nhận, ví dụ backup, duyệt draft an toàn, ghi sổ draft đã duyệt.

## Chạy app

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Mở Swagger:

```text
http://127.0.0.1:8000/docs
```

Mở chatbot UI:

```text
http://127.0.0.1:8000/v41/chatbot-ui
```

## Test nhanh bằng dữ liệu mẫu

Gọi endpoint này để có dữ liệu mẫu và tự post vào sổ:

```text
POST /import/v40-5/sample-data?auto_post=true
```

Sau đó hỏi chatbot:

```text
POST /ai/v41/chat
{
  "message": "Làm cho tôi báo cáo tổng hợp tháng này"
}
```

Hoặc:

```text
POST /ai/v41/chat
{
  "message": "Tính VAT tháng này"
}
```

## Import nhiều giao dịch bằng JSON

```text
POST /import/v40-5/transactions/bulk
```

Body mẫu:

```json
{
  "source": "manual_bulk",
  "auto_create_drafts": true,
  "auto_approve_safe": false,
  "items": [
    {
      "date": "2026-05-01",
      "description": "Bán hàng cho khách A chuyển khoản",
      "amount": 52000000,
      "transaction_type": "income",
      "vat_rate": 0.1,
      "payment_method": "bank"
    },
    {
      "date": "2026-05-03",
      "description": "Thanh toán quảng cáo Facebook tháng 5",
      "amount": 6500000,
      "transaction_type": "expense",
      "vat_rate": 0.1,
      "payment_method": "bank"
    }
  ]
}
```

## Import CSV/XLSX

```text
POST /import/v40-5/transactions/file
```

File nên có các cột sau, tiếng Việt hoặc tiếng Anh đều được:

```text
date / ngày
description / mô tả / nội dung
amount / số tiền
vat_rate / vat / thuế
payment_method / thanh toán
category / danh mục
```

## Learning memory

Xem dữ liệu hệ thống đã học:

```text
GET /ai/learning/v40-5/memory
```

Hệ thống sẽ ghi học từ:

- approve journal draft
- reject journal draft
- post journal draft
- sample data auto post
- V42 approve/post action

## Chatbot V41

Endpoint:

```text
POST /ai/v41/chat
```

Ví dụ câu hỏi:

```text
Tính VAT tháng này
Tháng này lãi hay lỗ?
Làm báo cáo tổng hợp tháng này
Xuất Excel cho tôi
Tạo dữ liệu mẫu để test
```

V41 chỉ đọc dữ liệu, tính toán, tổng hợp và hướng dẫn. Nó không tự ghi sổ.

## Chatbot hành động V42

Endpoint lập kế hoạch hành động:

```text
POST /ai/v42/chat-action
```

Ví dụ:

```json
{
  "message": "Sao lưu dữ liệu giúp tôi"
}
```

Hoặc:

```json
{
  "message": "Ghi sổ các bút toán đã duyệt"
}
```

Nếu hành động có thể thay đổi dữ liệu, hệ thống trả về `confirmation_id`.

Xác nhận:

```text
POST /ai/v42/confirm-action
```

```json
{
  "confirmation_id": "CONFIRM-00001",
  "confirm": true
}
```

## API mới chính

```text
POST /import/v40-5/sample-data?auto_post=true
POST /import/v40-5/transactions/bulk
POST /import/v40-5/transactions/file
GET  /import/v40-5/status
GET  /ai/learning/v40-5/memory
GET  /v41/chatbot-ui
POST /ai/v41/chat
POST /ai/v42/chat-action
POST /ai/v42/confirm-action
```

## Test tự động

```bash
PYTHONPATH=. pytest -q
```

Kỳ vọng ở bản này:

```text
40 passed
```

# Finiip V42-V47 Working Chatbot Upgrade

Bản này nâng chatbot từ mức hỏi đáp sang mức có thể làm việc theo luồng kế toán an toàn.

## Đã thêm

1. `POST /ai/v42/transaction-proposal`  
   Nhận câu tự nhiên, trả về proposal có cấu trúc: mô tả, số tiền, danh mục, TK Nợ/Có, risk note.

2. `POST /ai/v42/confirm-journal`  
   Người dùng xác nhận proposal và hệ thống lưu thành journal draft. Có thể chọn `post_immediately=true` để ghi sổ ngay sau xác nhận.

3. `POST /ai/v47/feedback` và `GET /ai/v47/feedback/list`  
   Lưu feedback/sửa lỗi của người dùng để sau này cải thiện rule hoặc train model.

4. `GET /v43/working-chatbot-ui`  
   Giao diện demo: chat → tạo proposal → sửa → xác nhận lưu draft.

## Cách chạy

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Mở UI:

```text
http://localhost:8000/v43/working-chatbot-ui
```

## Test API nhanh

```bash
curl -X POST http://localhost:8000/ai/v42/transaction-proposal \
  -H "Content-Type: application/json" \
  -d '{"message":"Thanh toán tiền điện 2 triệu bằng chuyển khoản"}'
```

```bash
curl -X POST http://localhost:8000/ai/v42/confirm-journal \
  -H "Content-Type: application/json" \
  -d '{
    "description":"Thanh toán tiền điện 2 triệu bằng chuyển khoản",
    "amount":2000000,
    "category":"Chi phí điện nước",
    "debit_account":"642",
    "credit_account":"112",
    "payment_method":"bank",
    "vat_rate":0.1,
    "risk_note":"Cần có hóa đơn/chứng từ hợp lệ",
    "post_immediately":false
  }'
```

## Nguyên tắc an toàn

- AI chỉ gợi ý và lưu nháp.
- Kế toán/người dùng xác nhận trước khi ghi sổ.
- Mọi xác nhận và feedback được lưu lại để audit và cải thiện hệ thống.
- Báo cáo VAT/lợi nhuận chỉ lấy từ dữ liệu đã ghi sổ, không để AI tự bịa số liệu.

## Lộ trình tiếp theo

- V48: nâng OCR hóa đơn scan ảnh thật.
- V49: thêm bảng review feedback và thống kê rule sai nhiều nhất.
- V50: tự đề xuất rule mới từ feedback đã tích lũy.

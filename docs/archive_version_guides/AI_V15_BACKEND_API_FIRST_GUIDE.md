# Finiip V15 - Backend API-first Pack

Bản này dành cho trường hợp bạn đã có frontend sẵn và chỉ cần backend/API để nối vào.

## Điểm mới

- Version API nâng lên `15.0.0`.
- Thêm nhóm endpoint `/api/v1/*` ổn định hơn cho frontend.
- Thêm health-check, meta, route list, bootstrap data.
- Thêm preview giao dịch cho màn hình nhập liệu frontend.
- Thêm preview hóa đơn không ghi database mặc định.
- Thêm bulk re-analyze nhiều giao dịch.
- Thêm wrapper train AI dễ gọi từ frontend.
- Thêm API key bảo vệ backend khi deploy thật.

## Chạy backend

```bash
cd copy
pip install -r requirements.txt
python scripts/seed_and_train_ai.py
uvicorn main:app --reload
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

OpenAPI JSON cho frontend generate client:

```text
http://127.0.0.1:8000/openapi.json
```

## Endpoint frontend nên gọi đầu tiên

```bash
curl http://127.0.0.1:8000/api/v1/health
curl http://127.0.0.1:8000/api/v1/meta
curl http://127.0.0.1:8000/api/v1/frontend/bootstrap
```

## Preview giao dịch trước khi tạo

```bash
curl -X POST http://127.0.0.1:8000/api/v1/ai/transaction-preview \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Thanh toán tiền điện EVN tháng 5",
    "amount": 2200000,
    "min_confidence": 0.55
  }'
```

Frontend nhận được:

- `ai_result`: kết quả AI phân loại.
- `journal_lines`: dòng Nợ/Có gợi ý.
- `journal_balance`: kiểm tra Nợ = Có.
- `frontend_decision.can_auto_create`: có thể tự tạo hay cần user review.
- `frontend_decision.next_api_to_create`: API tạo giao dịch thật.
- `frontend_decision.next_api_to_correct`: API feedback nếu AI sai.

## Tạo giao dịch thật sau khi user xác nhận

```bash
curl -X POST http://127.0.0.1:8000/ai/create-transaction \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Thanh toán tiền điện EVN tháng 5",
    "amount": 2200000,
    "auto_create_journal": true
  }'
```

## Preview hóa đơn cho frontend

```bash
curl -X POST http://127.0.0.1:8000/api/v1/ocr/invoice-preview \
  -H "Content-Type: application/json" \
  -d '{
    "raw_text": "HÓA ĐƠN GTGT\nSố hóa đơn: HD009\nNgày 20/05/2026\nĐơn vị bán hàng: Công ty Điện lực EVN\nCộng tiền hàng: 2.000.000\nThuế suất GTGT: 10%\nTiền thuế GTGT: 200.000\nTổng cộng thanh toán: 2.200.000",
    "create_drafts": false
  }'
```

Nếu `create_drafts=false`, backend chỉ preview, không ghi DB. Khi user xác nhận, frontend có thể gọi endpoint cũ:

```text
POST /ocr/invoice/text
```

## Train AI từ frontend

```bash
curl -X POST http://127.0.0.1:8000/api/v1/frontend/train-ai \
  -H "Content-Type: application/json" \
  -d '{"min_examples": 1, "include_corrections": true}'
```

## Bulk re-analyze nhiều giao dịch

```bash
curl -X POST http://127.0.0.1:8000/api/v1/bulk/transactions/reanalyze \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_ids": [1,2,3],
    "update_transactions": false,
    "min_confidence": 0.55
  }'
```

Nếu `update_transactions=true`, backend sẽ cập nhật các giao dịch có confidence đủ ngưỡng.

## Bảo vệ backend khi deploy thật

Tạo biến môi trường:

```bash
export FINIIP_API_KEY="your-secret-key"
```

Sau đó frontend phải gửi header:

```text
X-API-Key: your-secret-key
```

Ở local dev nếu không set `FINIIP_API_KEY`, backend không yêu cầu API key.

## Test

```bash
pytest
```

Kết quả bản V15:

```text
20 passed
```

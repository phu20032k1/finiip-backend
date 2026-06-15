# Finiip V18-V22 - Self-made AI Accounting Workflow

Bản này nâng Finiip từ V17 Autopilot lên workflow AI kế toán tự làm hoàn chỉnh hơn, không dùng OpenAI, không Ollama, không LLM ngoài.

## V18 - Feedback Learning

Mục tiêu: AI học từ sửa lỗi của kế toán.

API chính:

```bash
POST /ai/v18/feedback-learning
```

Payload mẫu:

```json
{
  "description": "Thanh toán quảng cáo Facebook tháng 5",
  "amount": 3000000,
  "ai_category": "Chưa phân loại",
  "ai_type": "expense",
  "ai_debit_account_code": "642",
  "ai_credit_account_code": "112",
  "ai_confidence": 0.42,
  "correct_category": "Marketing",
  "correct_type": "expense",
  "correct_debit_account_code": "641",
  "correct_credit_account_code": "112",
  "train_after": true
}
```

Kết quả: lưu vào `ai_corrections`, có thể train model ngay.

## V19 - AI Review Queue

Mục tiêu: giao dịch AI chưa chắc chắn được đưa vào hàng chờ kế toán duyệt.

API:

```bash
POST /ai/v19/review-queue/from-analyze
GET  /ai/v19/review-queue
POST /ai/v19/review-queue/{id}/decision
```

Decision có 3 hành động:

- `approve`: chấp nhận kết quả AI
- `correct`: sửa kết quả AI và lưu feedback
- `reject`: từ chối kết quả AI

Payload sửa:

```json
{
  "action": "correct",
  "correct_category": "Tài sản cố định",
  "correct_type": "expense",
  "correct_debit_account_code": "211",
  "correct_credit_account_code": "112",
  "train_after_correction": true
}
```

## V20 - Retrain model từ feedback

Mục tiêu: train lại model Naive Bayes tự viết từ toàn bộ correction/feedback.

```bash
POST /ai/v20/retrain-from-feedback
```

Payload:

```json
{
  "min_examples": 1,
  "evaluate_after": true,
  "test_ratio": 0.2
}
```

## V21 - OCR hóa đơn tốt hơn

Mục tiêu: đọc hóa đơn, trích xuất số hóa đơn/ngày/nhà cung cấp/VAT/tổng tiền, rồi tự đưa vào review queue.

```bash
POST /ocr/v21/invoice-improved/text
```

Payload:

```json
{
  "raw_text": "HÓA ĐƠN GIÁ TRỊ GIA TĂNG...",
  "auto_push_review_queue": true
}
```

## V22 - Tự sinh bút toán kép

Mục tiêu: sinh bút toán Nợ/Có cân bằng, hỗ trợ VAT đầu vào/đầu ra.

```bash
POST /ai/v22/double-entry/generate
```

Payload mẫu chi phí có VAT:

```json
{
  "description": "Thanh toán quảng cáo Facebook có VAT",
  "amount": 3300000,
  "mode": "expense",
  "vat_rate": 10,
  "auto_create_journal": false
}
```

Payload mẫu mua tài sản:

```json
{
  "description": "Mua laptop văn phòng có VAT",
  "amount": 22000000,
  "mode": "asset",
  "vat_rate": 10,
  "auto_create_journal": false
}
```

Payload mẫu bán hàng:

```json
{
  "description": "Bán hàng cho khách có VAT",
  "amount": 11000000,
  "mode": "sales",
  "vat_rate": 10,
  "auto_create_journal": false
}
```

Mặc định nên để `auto_create_journal=false` để preview trước. Khi frontend đã có màn hình duyệt, có thể bật `auto_create_journal=true` nhưng vẫn để `status=draft`.

## Kiểm tra trạng thái nâng cấp

```bash
GET /ai/v18-v22/upgrade-status
```

## Test

Đã thêm test:

```bash
pytest -q tests/test_v18_v22_workflow.py
```

Đã chạy toàn bộ test project:

```text
29 passed
```

## Mức AI hiện tại

Sau V18-V22, Finiip đạt khoảng:

```text
Cấp 4 nhẹ / Cấp 5 prototype
```

Lý do: đã có rule engine, ML tự train, feedback loop, review queue, OCR parser, retrain workflow và sinh bút toán kép. Tuy nhiên vẫn chưa phải Cấp 6 ChatGPT kế toán vì chưa có LLM/RAG/agent đọc toàn bộ database để suy luận tự do.

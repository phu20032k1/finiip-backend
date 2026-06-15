# Finiip V11 - AI Feedback & Evaluation

Bản V11 nâng Finiip từ AI học mẫu sang AI có vòng lặp học thật:

```text
AI phân tích giao dịch
→ người dùng sửa nếu AI sai
→ hệ thống lưu feedback thành training example
→ train lại model
→ evaluate độ chính xác
→ xem nhóm nào AI còn yếu
```

## API mới

### 1. Lưu feedback khi AI đoán sai

```bash
curl -X POST http://127.0.0.1:8000/ai/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Thanh toán chi phí chạy LinkedIn Ads tháng 5",
    "amount": 4600000,
    "ai_category": "Chưa phân loại",
    "ai_type": "unknown",
    "ai_debit_account_code": null,
    "ai_credit_account_code": null,
    "ai_confidence": 0.2,
    "correct_category": "Chi phí marketing",
    "correct_type": "expense",
    "correct_debit_account_code": "641",
    "correct_credit_account_code": "112",
    "note": "Người dùng sửa kết quả AI",
    "train_after": true
  }'
```

Nếu `train_after=true`, hệ thống sẽ lưu feedback rồi train lại model ngay.

### 2. Xem dataset AI đã học

```bash
curl http://127.0.0.1:8000/ai/training-examples
```

Có thể lọc theo category:

```bash
curl "http://127.0.0.1:8000/ai/training-examples?category=Chi%20phí%20marketing"
```

### 3. Thêm ví dụ học mới

```bash
curl -X POST http://127.0.0.1:8000/ai/training-examples \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Chi phí quảng cáo Google Ads",
    "amount": 3000000,
    "user_category": "Chi phí marketing",
    "user_type": "expense",
    "user_debit_account_code": "641",
    "user_credit_account_code": "112"
  }'
```

### 4. Sửa một ví dụ học

```bash
curl -X PUT http://127.0.0.1:8000/ai/training-examples/1 \
  -H "Content-Type: application/json" \
  -d '{
    "user_category": "Chi phí marketing",
    "user_debit_account_code": "641",
    "user_credit_account_code": "112",
    "note": "Đã sửa nhãn"
  }'
```

### 5. Xóa ví dụ học rác

```bash
curl -X DELETE http://127.0.0.1:8000/ai/training-examples/1
```

### 6. Train lại model

```bash
curl -X POST http://127.0.0.1:8000/ai/ml/train \
  -H "Content-Type: application/json" \
  -d '{"min_examples": 10, "include_corrections": true}'
```

### 7. Đánh giá độ chính xác AI

```bash
curl "http://127.0.0.1:8000/ai/ml/evaluate?min_examples=10&test_ratio=0.2"
```

Kết quả sẽ có:

```json
{
  "accuracy_percent": 82.5,
  "test_samples": 40,
  "correct": 33,
  "wrong": 7,
  "weak_categories": []
}
```

## Quy trình dùng đúng

```text
1. POST /setup/default-accounts
2. POST /ai/ml/seed-and-train
3. POST /ai/analyze
4. Nếu AI sai → POST /ai/feedback
5. POST /ai/ml/evaluate
6. Sửa/xóa dữ liệu sai trong /ai/training-examples
7. POST /ai/ml/train
```

## Trạng thái cấp độ

Sau V11, Finiip đang ở:

```text
Cấp 3 ML nhẹ + Feedback Loop + Evaluation System
```

Đây là nền để sau này làm frontend quản lý AI và OCR hóa đơn.

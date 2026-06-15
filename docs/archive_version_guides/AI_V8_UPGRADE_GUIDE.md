# Finiip Backend V8 - AI Knowledge Upgrade

Bản này nâng AI backend theo hướng chưa cần frontend nhưng AI thông minh hơn.

## API mới

### 1. Phân tích sâu
`POST /ai/v8/analyze-deep`

```json
{
  "description": "Chạy quảng cáo Facebook Ads có VAT 10% thanh toán chuyển khoản",
  "amount": 11000000
}
```

Trả về:
- category
- confidence
- confidence_status
- needs_review
- explanation
- journal_entry
- tax_risk

### 2. Chỉ lấy bút toán AI
`POST /ai/v8/journal-entry`

### 3. Kiểm tra rủi ro thuế
`POST /ai/v8/risk-check`

### 4. Kiểm tra độ chính xác AI
`POST /ai/v8/accuracy-test`

Không truyền body thì dùng bộ test mẫu. Có thể truyền bộ test riêng:

```json
{
  "cases": [
    {
      "description": "Thanh toán tiền điện EVN bằng chuyển khoản",
      "amount": 2500000,
      "expected_category": "Chi phí điện nước",
      "expected_debit": "642",
      "expected_credit": "112"
    }
  ]
}
```

### 5. Xem kho kiến thức
`GET /ai/v8/knowledge-store`

### 6. Xem lộ trình backend tiếp theo
`GET /ai/v8/roadmap`

## Cách test nhanh

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Mở:

```text
http://127.0.0.1:8000/docs
```

Test theo thứ tự:
1. `GET /setup/default-accounts`
2. `POST /ai/v8/analyze-deep`
3. `POST /ai/v8/accuracy-test`
4. `POST /ai/teach` để dạy thêm ví dụ
5. Chạy lại `POST /ai/v8/analyze-deep`

## Backend hiện tại đang ở đâu?

Hiện backend đạt mức:

```text
Cấp 3+ gần Cấp 5
Rule-based AI + học ví dụ + explanation + confidence gate + rủi ro thuế + gợi ý bút toán
```

Chưa phải ChatGPT kế toán thật sự, vì chưa có LLM/RAG/vector database. Nhưng đã là nền backend tốt để sau này gắn chatbot.

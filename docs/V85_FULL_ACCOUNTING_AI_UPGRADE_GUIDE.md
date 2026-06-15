# V85 - Full Accounting AI Upgrade Guide

## Những gì đã thêm

V85 bổ sung một core AI kế toán mới, không phá các version cũ:

- `services/accounting_ai_full.py`: core AI kế toán đầy đủ.
- `accounting_rules.json`: đã merge thêm bộ rule nghiệp vụ V85.
- `knowledge_base/accounting_full_playbook_v85.md`: playbook nghiệp vụ cho RAG/local knowledge.
- `data/accounting_training_examples_full_v85.json`: 155 ví dụ training seed.
- `tests/test_v85_accounting_ai_full.py`: test riêng cho V85.
- `main.py`: thêm endpoint backend mới.

## Endpoint mới

### 1. Xem năng lực AI kế toán

```bash
curl http://localhost:8000/ai/accounting/full-capabilities
```

### 2. Xem rule catalog

```bash
curl http://localhost:8000/ai/accounting/rules
```

### 3. Phân tích giao dịch và gợi ý bút toán

```bash
curl -X POST http://localhost:8000/ai/accounting/analyze-transaction \
  -H "Content-Type: application/json" \
  -d '{
    "description": "mua hàng hóa nhập kho chuyển khoản VAT 10%",
    "amount": 11000000,
    "vat_rate": 0.10,
    "amount_includes_vat": true,
    "has_invoice": true
  }'
```

Kết quả gồm:

- `matched_rule`: rule nghiệp vụ đã match.
- `journal_lines`: bút toán Nợ/Có nháp.
- `journal_check`: kiểm tra cân Nợ/Có.
- `risk_review`: cảnh báo/chặn/review.
- `missing_questions`: thông tin cần hỏi thêm.
- `required_documents`: chứng từ cần có.
- `decision`: `auto_draft_allowed`, `review_required`, hoặc `blocked`.

### 4. Chỉ lấy bút toán gợi ý

```bash
curl -X POST http://localhost:8000/ai/accounting/suggest-entry \
  -H "Content-Type: application/json" \
  -d '{"description":"bán hàng thu tiền qua ngân hàng VAT 10%","amount":22000000,"vat_rate":0.10}'
```

### 5. Hỏi AI kế toán kiểu chatbot

```bash
curl -X POST http://localhost:8000/ai/accounting/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"mua tài sản cố định có VAT hạch toán thế nào?","limit":5}'
```

Endpoint này kết hợp:

- solver tính toán/định khoản,
- tìm trong `knowledge_base`,
- trả nguồn nội bộ tham khảo,
- cảnh báo đây là kết quả nháp cần kế toán xác nhận.

### 6. Tính công thức kế toán

```bash
curl -X POST http://localhost:8000/ai/accounting/solve \
  -H "Content-Type: application/json" \
  -d '{"formula":"vat","amount":11000000,"rate":0.10,"amount_includes_vat":true}'
```

Công thức hỗ trợ:

- `vat`
- `depreciation`
- `prepaid`
- `weighted_average`
- `fifo`
- `profit`
- `cit`
- `payroll`

### 7. Kiểm tra bút toán cân chưa

```bash
curl -X POST http://localhost:8000/ai/accounting/check-journal \
  -H "Content-Type: application/json" \
  -d '{
    "lines": [
      {"side":"debit","account_code":"642","amount":1000000},
      {"side":"credit","account_code":"112","amount":1000000}
    ]
  }'
```

### 8. Endpoint frontend-friendly

```bash
curl -X POST http://localhost:8000/api/v1/ai/accounting-preview \
  -H "Content-Type: application/json" \
  -d '{"description":"chi tiền mặt tiếp khách 25 triệu","amount":25000000,"has_invoice":false}'
```

## Chạy test

```bash
python -m pytest -q tests/test_v85_accounting_ai_full.py
```

## Lưu ý quan trọng

V85 đã nâng code và rule mạnh hơn, nhưng để dùng thực chiến vẫn cần bạn bổ sung thủ công:

1. Thông tư/quy định mới nhất.
2. Chính sách nội bộ của doanh nghiệp.
3. Dữ liệu thật: hóa đơn, sao kê, công nợ, bảng lương.
4. Mapping tài khoản theo công ty.
5. Người kế toán duyệt cuối trước khi ghi sổ/quyết toán.

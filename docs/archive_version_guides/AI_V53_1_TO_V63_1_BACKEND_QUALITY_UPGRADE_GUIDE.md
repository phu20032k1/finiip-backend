# AI kế toán V53.1–V63.1 Backend Quality Upgrade

Bản này không thêm frontend. Các API cũ vẫn giữ nguyên để frontend riêng có thể gọi tiếp, nhưng response đã được làm giàu để dễ render bảng, checklist, cảnh báo, workflow và export Excel.

## Mục tiêu nâng cấp

- V53.1: Kiểm tra chứng từ theo checklist riêng cho từng loại tài liệu.
- V54.1: Đề xuất bút toán có nhiều phương án, kiểm tra Tổng Nợ = Tổng Có và validate tài khoản.
- V58.1: RAG trả JSON có nguồn, confidence, missing_info và cơ chế “chưa đủ căn cứ”.
- V62.1: Workflow chứng từ rõ trạng thái, có allowed_next_actions cho frontend.
- V63.1: Báo cáo ưu tiên journal entries đã posted.
- V57.1: Export Excel cho chứng từ, journal entries và báo cáo.

## API mới

```text
GET  /ai/v53-v63/quality-upgrade-status
POST /ai/v58/rag-answer
GET  /documents/{document_id}/workflow
GET  /ai/v57/journal-entries/export-excel
GET  /ai/v57/reports/trial-balance/export-excel
GET  /ai/v57/reports/general-ledger/export-excel
```

## API cũ được làm giàu response

```text
POST /ai/v53/document-review/text
POST /ai/v53/document-review/upload-file
POST /ai/v54/journal-suggestion
POST /ai/v56/tax-risk-checklist
GET  /reports/trial-balance
GET  /reports/general-ledger
```

## V53.1 - Document review checklist

Response của `/ai/v53/document-review/text` có thêm:

```json
{
  "review": {
    "document_checklist": {
      "overall_status": "need_review",
      "quality_score": 71.4,
      "items": [
        {"code": "invoice_number", "label": "Có số hóa đơn/ký hiệu hóa đơn", "status": "missing"},
        {"code": "invoice_date", "label": "Có ngày hóa đơn/ngày phát sinh", "status": "pass"}
      ]
    },
    "overall_status": "need_review",
    "quality_score": 71.4,
    "confidence": "medium",
    "risk_level": "medium",
    "missing_info": []
  }
}
```

Frontend có thể render `document_checklist.items` thành bảng checklist.

## V54.1 - Journal suggestion có validation

Response của `/ai/v54/journal-suggestion` có thêm:

```json
{
  "journal_suggestion": {
    "options": [
      {
        "name": "Phương án CCDC/chi phí trả trước",
        "confidence": "high",
        "journal_lines": [],
        "balance_check": {"debit": 22000000, "credit": 22000000, "difference": 0},
        "is_balanced": true,
        "account_validation_errors": [],
        "explanation": "...",
        "assumptions": [],
        "missing_info": []
      }
    ],
    "primary_option": {},
    "warnings": [],
    "missing_info": []
  }
}
```

Frontend nên hiển thị `options` để người dùng chọn phương án, rồi mới tạo journal entry chính thức.

## V58.1 - RAG answer an toàn hơn

Gọi:

```http
POST /ai/v58/rag-answer
```

Body:

```json
{
  "query": "Chi phí quảng cáo Facebook cần chứng từ gì?",
  "category": "thue_tndn",
  "limit": 5
}
```

Nếu chưa đủ nguồn, backend trả:

```json
{
  "data": {
    "conclusion": "Chưa đủ căn cứ trong kho tài liệu đã upload để trả lời chắc chắn.",
    "confidence": "low",
    "sources": [],
    "missing_info": ["Thiếu nguồn văn bản trong knowledge base"]
  }
}
```

## V62.1 - Workflow status cho frontend

Gọi:

```http
GET /documents/{document_id}/workflow
```

Response có:

```json
{
  "data": {
    "document_id": "DOC-00001",
    "status": "pending_approval",
    "allowed_next_actions": ["approve", "reject"],
    "workflow": {}
  }
}
```

## V57.1 - Export Excel

```text
GET /ai/v57/journal-entries/export-excel?company_id=COMP-00001&status=posted
GET /ai/v57/reports/trial-balance/export-excel?company_id=COMP-00001
GET /ai/v57/reports/general-ledger/export-excel?company_id=COMP-00001&account=112
```

## Cách chạy

```bash
python -m pip install -r requirements.txt
uvicorn main:app --reload
```

Mở Swagger:

```text
http://127.0.0.1:8000/docs
```

Kiểm tra bản nâng cấp:

```text
http://127.0.0.1:8000/ai/v53-v63/quality-upgrade-status
```

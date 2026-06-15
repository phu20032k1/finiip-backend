# AI kế toán V53–V58 Backend-only Guide

Bản này không thêm frontend. Frontend riêng có thể gọi các API JSON/download Excel dưới đây.

## Chạy backend

```bash
cd copy
python -m pip install -r requirements.txt
uvicorn main:app --reload
```

Mở Swagger:

```text
http://127.0.0.1:8000/docs
```

Kiểm tra trạng thái nâng cấp:

```text
GET /ai/v53-v58/upgrade-status
```

---

## V53 — AI kiểm tra chứng từ

### Upload file chứng từ

```text
POST /ai/v53/document-review/upload-file
```

Form-data:

```text
file: PDF/DOCX/XLSX/TXT/CSV/JSON
source: upload
categories/tags: purchase_invoice, thue_gtgt... nếu muốn
save_document: true
save_review: true
```

API trả về:

```json
{
  "review_id": "REV...",
  "document": {},
  "review": {
    "classification": {},
    "detected_fields": {},
    "missing_info": [],
    "review_summary": "..."
  },
  "journal_suggestion": {},
  "tax_risk": {}
}
```

### Review từ text

```text
POST /ai/v53/document-review/text
```

Body mẫu:

```json
{
  "title": "Hoa don mua laptop",
  "content": "Hóa đơn VAT mua laptop 18.000.000 đồng, thanh toán chuyển khoản",
  "source": "manual",
  "tags": ["purchase_invoice"],
  "save_document": true,
  "save_review": true
}
```

### Danh sách review

```text
GET /ai/v53/document-reviews
```

---

## V54 — AI đề xuất bút toán

```text
POST /ai/v54/journal-suggestion
```

Có thể gọi bằng `review_id`:

```json
{
  "review_id": "REV000001"
}
```

Hoặc gọi trực tiếp:

```json
{
  "description": "Mua laptop dùng cho văn phòng",
  "content": "Hóa đơn VAT 18.000.000, thanh toán chuyển khoản",
  "total_amount": 18000000,
  "payment_method": "chuyển khoản",
  "document_type": "purchase_invoice"
}
```

API trả về `suggested_lines` dạng JSON:

```json
[
  {
    "debit_account": "242",
    "credit_account": "112",
    "amount": 16363636.36,
    "description": "Ghi nhận giá trị chưa VAT/chi phí/tài sản theo chứng từ"
  },
  {
    "debit_account": "1331",
    "credit_account": "112",
    "amount": 1636363.64,
    "description": "Thuế GTGT đầu vào được khấu trừ nếu đủ điều kiện"
  }
]
```

---

## V55 — Tự phân loại tài liệu kế toán

```text
POST /ai/v55/classify-document
```

Body:

```json
{
  "title": "Sao kê ngân hàng tháng 5",
  "content": "Sao kê ngân hàng, giao dịch chuyển khoản...",
  "tags": []
}
```

Loại tài liệu đang hỗ trợ:

```text
purchase_invoice      Hóa đơn đầu vào
sale_invoice          Hóa đơn đầu ra
contract              Hợp đồng
cash_receipt          Phiếu thu
cash_payment          Phiếu chi
bank_statement        Sao kê ngân hàng
payroll               Bảng lương / BHXH
tax_return            Tờ khai thuế
financial_statement   Báo cáo tài chính
legal_policy          Luật / thông tư / quy định
unknown               Chưa phân loại được
```

---

## V56 — Checklist rủi ro thuế

```text
POST /ai/v56/tax-risk-checklist
```

Gọi bằng `review_id`:

```json
{
  "review_id": "REV000001"
}
```

Hoặc gọi trực tiếp:

```json
{
  "description": "Chi phí dịch vụ quảng cáo",
  "content": "Hóa đơn VAT 25.000.000 đồng, chưa thấy thanh toán ngân hàng",
  "document_type": "purchase_invoice",
  "total_amount": 25000000
}
```

API trả về:

```json
{
  "overall_risk": "high",
  "risks": [
    {
      "level": "high",
      "code": "vat_bank_payment",
      "message": "...",
      "required_evidence": []
    }
  ]
}
```

---

## V57 — Xuất Excel

### Xuất toàn bộ document reviews

```text
GET /ai/v57/document-reviews/export-excel
```

Frontend chỉ cần mở URL hoặc gọi fetch rồi download blob.

### Xuất rows tùy chỉnh

```text
POST /ai/v57/export-analysis-excel
```

Body:

```json
{
  "title": "Bang kiem tra chung tu",
  "rows": [
    {
      "ten_chung_tu": "Hoa don laptop",
      "so_tien": 18000000,
      "rui_ro": "medium",
      "ghi_chu": "Can kiem tra hoa don goc"
    }
  ]
}
```

---

## V58 — Kho luật/thông tư chuẩn hóa

### Xem knowledge map

```text
GET /ai/v58/knowledge-map
```

Danh mục khuyến nghị:

```text
knowledge_base/global/thue_gtgt/
knowledge_base/global/thue_tndn/
knowledge_base/global/hoa_don_chung_tu/
knowledge_base/global/tai_san_co_dinh/
knowledge_base/global/cong_cu_dung_cu/
knowledge_base/global/tien_luong_bhxh/
knowledge_base/global/bao_cao_tai_chinh/
knowledge_base/global/che_do_ke_toan/
```

### Upload text luật/thông tư vào RAG

```text
POST /ai/v58/legal-knowledge/upload-text
```

Body:

```json
{
  "title": "Quy định về hóa đơn chứng từ",
  "content": "Nội dung văn bản nguồn...",
  "category": "hoa_don_chung_tu",
  "source": "official_document",
  "tags": ["hoa_don"]
}
```

### Search luật/thông tư

```text
POST /ai/v58/legal-search
```

Body:

```json
{
  "query": "điều kiện khấu trừ VAT đầu vào",
  "category": "thue_gtgt",
  "limit": 5
}
```

---

## Flow frontend nên dùng

Flow xử lý chứng từ:

```text
1. POST /ai/v53/document-review/upload-file
2. Lấy review_id
3. Hiển thị review.classification, detected_fields, missing_info
4. Hiển thị journal_suggestion.suggested_lines
5. Hiển thị tax_risk.risks
6. Khi cần, GET /ai/v57/document-reviews/export-excel
```

Flow hỏi luật/thông tư:

```text
1. POST /ai/v58/legal-knowledge/upload-text để nạp văn bản nguồn
2. POST /ai/v58/legal-search để tìm căn cứ
3. POST /ai/v47/chat-with-vector-docs để hỏi đáp RAG an toàn
```

## Lưu ý

Đây vẫn là MVP backend local. AI chưa dùng OCR ảnh scan thật và chưa thay thế kế toán trưởng/tư vấn thuế. Với PDF scan dạng ảnh cần nâng thêm OCR riêng.

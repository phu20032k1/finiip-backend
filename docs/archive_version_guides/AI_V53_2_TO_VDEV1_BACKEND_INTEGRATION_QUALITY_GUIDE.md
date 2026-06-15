# AI kế toán - Backend integration quality upgrade

Bản này nâng cấp sâu các chức năng đã có, không thêm frontend. Mục tiêu là để frontend riêng dễ gọi API, dễ render form/bảng/checklist, có rule validation chắc hơn và có data mẫu để test.

## Chạy backend

```bash
cd copy
python -m pip install -r requirements.txt
uvicorn main:app --reload
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

Kiểm tra bản nâng:

```text
GET /ai/v53-2-vdev1/integration-quality-status
GET /api/health/deep
GET /api/enums
GET /api/schema/frontend
```

## Nhóm 1: File processing API

### Parse file

```text
POST /ai/file/parse
```

Input: multipart form `file`.

Dùng để backend đọc text cơ bản từ `.txt`, `.csv`, `.docx`, `.xlsx`, `.pdf` có text layer.

### Extract fields từ file

```text
POST /ai/file/extract-fields
```

Input: multipart form `file`, optional `document_type`.

Trả về các field như số hóa đơn, ngày hóa đơn, MST, tiền trước thuế, VAT, tổng tiền, phương thức thanh toán.

### Split documents

```text
POST /ai/file/split-documents
```

Dùng cho file có nhiều chứng từ trong một nội dung. Bản này tách ở mức heuristic.

Lưu ý: PDF scan/ảnh cần OCR chuyên dụng. API hiện tại có cảnh báo nếu không đọc được text.

## Nhóm 2: Extract document fields V53.2

```text
POST /ai/v53/extract-document-fields
```

Body mẫu:

```json
{
  "content": "HÓA ĐƠN GTGT số 0000123 ngày 30/05/2026 Người bán: ABC Co MST: 0101234567 Cộng tiền hàng: 18.000.000 Thuế GTGT 10%: 1.800.000 Tổng thanh toán: 19.800.000 Thanh toán chuyển khoản",
  "document_type": "invoice_input",
  "company_id": "COMP-00001"
}
```

Response có:

```text
document_type
fields
missing_fields
confidence
tax_validation_preview
warnings
```

Frontend nên render `fields` thành form để người dùng sửa trước khi ghi sổ.

## Nhóm 3: Validation engine V54.2

### Validate journal entry

```text
POST /accounting/validate/journal-entry
```

Kiểm tra:

```text
Tổng Nợ = Tổng Có
Tài khoản có tồn tại trong chart of accounts
Một dòng không vừa Nợ vừa Có
Số tiền không âm
Ngày chứng từ hợp lệ
```

### Validate document

```text
POST /accounting/validate/document
```

Kiểm tra field bắt buộc theo loại chứng từ.

### Validate tax

```text
POST /accounting/validate/tax
```

Kiểm tra:

```text
Tổng tiền = trước thuế + VAT
VAT rate phổ biến 0/5/8/10
Chứng từ >= 20 triệu cần kiểm tra chuyển khoản
Thiếu thông tin hóa đơn quan trọng
```

## Nhóm 4: Human correction V58.2

### Lưu correction

```text
POST /ai/corrections
```

Body mẫu:

```json
{
  "company_id": "COMP-00001",
  "document_id": "DOC-001",
  "field": "vat_amount",
  "ai_value": 180000,
  "correct_value": 1800000,
  "reason": "AI đọc thiếu một số 0",
  "actor": "frontend-user"
}
```

### Xem correction

```text
GET /ai/corrections?company_id=COMP-00001
```

### Apply correction

```text
POST /ai/corrections/apply
```

Bản MVP này lưu correction làm learning signal và audit log. Backend chưa tự sửa chứng từ gốc nếu chưa có mapping an toàn.

## Nhóm 5: API contract cho frontend

```text
GET /api/enums
GET /api/schema/frontend
GET /api/health/deep
```

Frontend dùng `/api/enums` để lấy:

```text
document_statuses
document_types
risk_levels
journal_statuses
accounting_modes
vat_rates
workflow_actions
```

## Nhóm 6: Export Excel V57.2

```text
GET /ai/v57/export-all-excel?company_id=COMP-00001
```

Xuất một file Excel nhiều sheet gồm:

```text
companies
accounts
journal_entries
trial_balance
corrections
```

Các export cũ vẫn dùng được:

```text
GET /ai/v57/journal-entries/export-excel
GET /ai/v57/reports/trial-balance/export-excel
GET /ai/v57/reports/general-ledger/export-excel
```

## Nhóm 7: Demo seed data cho frontend

### Seed data

```text
POST /dev/seed-demo-data
```

Body:

```json
{
  "company_id": "COMP-00001",
  "reset_first": true,
  "include_posted_entries": true,
  "actor": "dev-seed"
}
```

Tạo dữ liệu mẫu:

```text
Bán hàng có VAT
Mua laptop có VAT
Chi phí quảng cáo
Workflow demo
Audit log demo
```

### Xóa demo data

```text
DELETE /dev/clear-demo-data?company_id=COMP-00001
```

### Kịch bản demo

```text
GET /dev/demo-scenarios
```

## Flow frontend khuyên dùng

```text
1. GET /api/enums
2. POST /ai/file/extract-fields hoặc POST /ai/v53/extract-document-fields
3. Người dùng sửa fields trên frontend
4. POST /ai/v53/document-review/text
5. POST /ai/v54/journal-suggestion
6. POST /accounting/validate/journal-entry
7. POST /journal-entries
8. POST /documents/{document_id}/submit-review
9. POST /documents/{document_id}/approve
10. POST /documents/{document_id}/post-to-journal
11. GET /reports/trial-balance
12. GET /ai/v57/export-all-excel
```

## Ghi chú kỹ thuật

- Các API cũ vẫn giữ nguyên.
- Response vẫn theo format chuẩn V65: `success`, `data`, `message`, `errors`.
- Validation engine là rule-based, không phụ thuộc AI.
- File parser hiện là MVP, chưa thay thế OCR chuyên dụng cho PDF scan/ảnh hóa đơn.

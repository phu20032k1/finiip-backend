# AI kế toán V59-V65 Backend-only Guide

Bản này tiếp tục từ V53-V58 và chỉ nâng backend API. Không thêm frontend/UI.

## Mục tiêu

V53-V58 đã xử lý chứng từ bằng AI: kiểm tra chứng từ, đề xuất bút toán, phân loại tài liệu, checklist rủi ro thuế và xuất Excel.

V59-V65 biến backend thành workflow kế toán thật hơn:

- V59: Company / tenant management
- V60: Chart of Accounts theo công ty
- V61: Sổ nhật ký chung / journal entries
- V62: Quy trình duyệt chứng từ trước khi ghi sổ
- V63: Báo cáo kế toán cơ bản
- V64: Audit log
- V65: Chuẩn hóa response cho frontend

## Chạy server

```bash
cd copy
python -m pip install -r requirements.txt
uvicorn main:app --reload
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

Kiểm tra nâng cấp:

```text
GET /ai/v59-v65/upgrade-status
```

## Chuẩn response V65

Các API V59-V65 trả về dạng:

```json
{
  "success": true,
  "data": {},
  "message": "OK",
  "errors": []
}
```

Khi lỗi validation:

```json
{
  "detail": {
    "success": false,
    "data": null,
    "message": "Validation failed",
    "errors": [
      {"field": "lines", "message": "Tổng Nợ phải bằng tổng Có"}
    ]
  }
}
```

## V59 - Company / tenant

Tạo công ty:

```http
POST /companies
```

Body:

```json
{
  "company_name": "ABC Trading Co., Ltd",
  "tax_code": "010xxxxxxx",
  "accounting_mode": "TT200",
  "currency": "VND",
  "fiscal_year": 2026
}
```

Khi tạo company, backend tự seed chart of accounts mặc định cho company đó.

Danh sách:

```http
GET /companies
GET /companies?active_only=true
GET /companies/{company_id}
PUT /companies/{company_id}
```

## V60 - Chart of Accounts

Danh sách tài khoản:

```http
GET /accounting/accounts?company_id=COMP-00001
```

Tìm tài khoản:

```http
GET /accounting/accounts/search?q=chi phí&company_id=COMP-00001
```

Tạo tài khoản:

```http
POST /accounting/accounts
```

Body:

```json
{
  "company_id": "COMP-00001",
  "code": "6428",
  "name": "Chi phí bằng tiền khác",
  "type": "expense",
  "parent_code": "642",
  "is_active": true
}
```

Sửa tài khoản:

```http
PUT /accounting/accounts/{account_code}?company_id=COMP-00001
```

## V61 - Journal Entries

Tạo bút toán:

```http
POST /journal-entries
```

Body mẫu:

```json
{
  "company_id": "COMP-00001",
  "date": "2026-05-30",
  "description": "Mua laptop phục vụ văn phòng",
  "source_document_id": "DOC-00001",
  "lines": [
    {"account": "242", "debit": 18000000, "credit": 0, "description": "Ghi nhận chi phí trả trước"},
    {"account": "1331", "debit": 1800000, "credit": 0, "description": "VAT đầu vào"},
    {"account": "331", "debit": 0, "credit": 19800000, "description": "Phải trả nhà cung cấp"}
  ],
  "status": "draft",
  "actor": "frontend_user"
}
```

Backend kiểm tra:

- Có ít nhất 2 dòng
- Tổng Nợ = Tổng Có
- Tài khoản phải tồn tại trong chart of accounts của company
- Một dòng không được vừa Nợ vừa Có
- Không cho số âm

Danh sách/sửa/xóa:

```http
GET    /journal-entries?company_id=COMP-00001
GET    /journal-entries/{entry_id}
PUT    /journal-entries/{entry_id}
DELETE /journal-entries/{entry_id}
```

Không cho xóa/sửa trực tiếp bút toán đã `posted`.

## V62 - Workflow duyệt chứng từ

Luồng khuyến nghị:

```text
AI review chứng từ -> AI đề xuất bút toán -> frontend cho user sửa -> tạo journal draft -> submit review -> approve -> post to journal
```

API:

```http
POST /documents/{document_id}/submit-review
POST /documents/{document_id}/approve
POST /documents/{document_id}/reject
POST /documents/{document_id}/post-to-journal
```

Approve có thể gắn journal entry:

```json
{
  "company_id": "COMP-00001",
  "actor": "chief_accountant",
  "journal_entry_id": "JE-00001",
  "note": "Đã kiểm tra chứng từ và bút toán"
}
```

Post chỉ thành công nếu chứng từ đã `approved` và journal entry hợp lệ.

## V63 - Reports

Bảng cân đối phát sinh:

```http
GET /reports/trial-balance?company_id=COMP-00001
```

Sổ cái:

```http
GET /reports/general-ledger?company_id=COMP-00001
GET /reports/general-ledger?company_id=COMP-00001&account=642
```

Báo cáo kết quả kinh doanh MVP:

```http
GET /reports/income-statement?company_id=COMP-00001
```

Bảng cân đối kế toán MVP:

```http
GET /reports/balance-sheet?company_id=COMP-00001
```

Lưu ý: Đây là bản MVP dựa trên tài khoản đã posted. Production cần mapping báo cáo chi tiết hơn theo chế độ kế toán.

## V64 - Audit logs

```http
GET /audit-logs
GET /audit-logs?company_id=COMP-00001
GET /audit-logs?entry_id=JE-00001
GET /audit-logs?document_id=DOC-00001
GET /audit-logs?action=journal.post
```

Audit log ghi lại các thao tác như tạo company, sửa tài khoản, tạo/sửa/xóa/post journal, submit/approve/reject/post chứng từ.

## Gợi ý tích hợp frontend

Frontend nên gọi theo flow:

1. `GET /companies`
2. `GET /accounting/accounts?company_id=...`
3. Upload/chạy AI V53-V58 để lấy đề xuất
4. User sửa bút toán trên frontend
5. `POST /journal-entries` với status `draft`
6. `POST /documents/{document_id}/submit-review`
7. Chief accountant gọi `POST /documents/{document_id}/approve`
8. Ghi sổ bằng `POST /documents/{document_id}/post-to-journal`
9. Xem báo cáo bằng `/reports/trial-balance` và `/reports/general-ledger`

## Endpoint quan trọng nhất để test nhanh

```text
GET  /ai/v59-v65/upgrade-status
GET  /companies
GET  /accounting/accounts?company_id=COMP-00001
POST /journal-entries
GET  /reports/trial-balance?company_id=COMP-00001&posted_only=false
GET  /audit-logs
```

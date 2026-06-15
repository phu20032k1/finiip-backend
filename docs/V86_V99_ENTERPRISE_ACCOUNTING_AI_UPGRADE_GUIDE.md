# V86–V99 ENTERPRISE ACCOUNTING AI UPGRADE GUIDE

Bản này nâng Finiip từ V85 `core accounting AI` lên lớp `enterprise accounting AI` có thể chạy luồng thực chiến hơn:

- V86: RAG tài liệu thật theo workspace
- V87: đọc text/PDF/DOCX/XLSX/ảnh OCR best-effort và parse hóa đơn
- V88: tạo bút toán nháp, kiểm tra cân Nợ/Có, xuất CSV/XLSX
- V89: review queue để kế toán duyệt/sửa/ghi feedback
- V90: tax/accounting risk checker
- V91: AI hỏi lại khi thiếu dữ liệu
- V92: agent pipeline OCR/RAG → journal → risk → review
- V93: multi-company/workspace profile
- V94: quality/evaluation dashboard
- V95: blueprint PostgreSQL/Supabase schema
- V96: frontend API contract
- V97: monthly summary report + closing checklist
- V98: company memory theo workspace
- V99: production/security readiness check

## File mới/chính

```txt
services/accounting_ai_enterprise.py
tests/test_v86_v99_accounting_enterprise.py
docs/V86_V99_ENTERPRISE_ACCOUNTING_AI_UPGRADE_GUIDE.md
```

`main.py` đã được nối thêm endpoint V86–V99 nhưng không xóa endpoint cũ.

## Chạy test

```bash
cd copy
pip install -r requirements.txt
python -m pytest -q tests/test_v85_accounting_ai_full.py tests/test_v86_v99_accounting_enterprise.py
```

Kết quả khi build bản này:

```txt
16 passed
```

## Chạy backend

```bash
cd copy
uvicorn main:app --reload
```

Nếu backend yêu cầu API key, dùng header theo cấu hình guard hiện tại của project.

## Các endpoint quan trọng

### Capabilities

```http
GET /ai/v86-v99/capabilities
```

### V86 - Thêm tài liệu vào RAG

```bash
curl -X POST http://localhost:8000/ai/v86/documents \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_id":"demo",
    "title":"Quy trình VAT nội bộ",
    "source_type":"tax_legal",
    "content":"Điều 1. Hóa đơn đầu vào phải có chứng từ thanh toán chuyển khoản nếu giá trị lớn."
  }'
```

Upload file:

```bash
curl -X POST http://localhost:8000/ai/v86/documents/upload \
  -F "workspace_id=demo" \
  -F "file=@./your_document.pdf"
```

Hỏi RAG:

```bash
curl -X POST http://localhost:8000/ai/v86/rag/ask \
  -H "Content-Type: application/json" \
  -d '{"workspace_id":"demo","question":"VAT đầu vào cần điều kiện gì?"}'
```

### V87 - Parse hóa đơn/chứng từ

```bash
curl -X POST http://localhost:8000/ai/v87/invoices/parse \
  -H "Content-Type: application/json" \
  -d '{"text":"Số hóa đơn: 000123\nNgày 10/06/2026\nCộng tiền hàng: 10.000.000\nThuế suất GTGT: 10%\nTiền thuế GTGT: 1.000.000\nTổng cộng tiền thanh toán: 11.000.000"}'
```

### V88 - Tạo bút toán nháp

```bash
curl -X POST http://localhost:8000/ai/v88/journal/create \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_id":"demo",
    "description":"Mua hàng hóa nhập kho chuyển khoản VAT 10%",
    "amount":11000000,
    "vat_rate":0.1,
    "has_invoice":true
  }'
```

Xuất nhật ký chung:

```bash
curl -X POST http://localhost:8000/ai/v88/journal/export \
  -H "Content-Type: application/json" \
  -d '{"workspace_id":"demo","format":"csv"}'
```

Hoặc:

```bash
curl -X POST http://localhost:8000/ai/v88/journal/export \
  -H "Content-Type: application/json" \
  -d '{"workspace_id":"demo","format":"xlsx"}'
```

### V89 - Review queue

```http
GET /ai/v89/review-queue?workspace_id=demo
```

Cập nhật review:

```bash
curl -X POST http://localhost:8000/ai/v89/review-queue/<review_id> \
  -H "Content-Type: application/json" \
  -d '{"status":"corrected","reviewer_note":"Sửa tài khoản chi phí","correction":{"debit":"642"}}'
```

### V90 - Risk check

```bash
curl -X POST http://localhost:8000/ai/v90/risk-check \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_id":"demo",
    "transaction":{
      "description":"Chi tiếp khách bằng tiền mặt không hóa đơn",
      "amount":25000000,
      "has_invoice":false,
      "payment_method":"tiền mặt"
    }
  }'
```

### V91 - AI hỏi lại

```bash
curl -X POST http://localhost:8000/ai/v91/followup-questions \
  -H "Content-Type: application/json" \
  -d '{"workspace_id":"demo","transaction":{"description":"Mua máy tính 35 triệu có hóa đơn","amount":35000000}}'
```

### V92 - Agent pipeline

```bash
curl -X POST http://localhost:8000/ai/v92/agent/process-text \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_id":"demo",
    "filename":"invoice.txt",
    "text":"Số hóa đơn: 0001\nMua hàng hóa nhập kho VAT 10%\nTổng cộng tiền thanh toán: 11.000.000"
  }'
```

### V93 - Workspace công ty

```bash
curl -X POST http://localhost:8000/ai/v93/workspaces \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_id":"demo",
    "name":"Demo Co",
    "tax_code":"0101234567",
    "policy":{"asset_capitalization_threshold":30000000}
  }'
```

### V94 - Dashboard/evaluation

```http
POST /ai/v94/evaluate
GET  /ai/v94/dashboard?workspace_id=demo
```

### V95/V96 - Dev resources

```http
GET /ai/v95/database-schema
GET /ai/v96/frontend-contract
```

### V97 - Reports

```http
GET /ai/v97/reports/monthly-summary?workspace_id=demo
GET /ai/v97/reports/closing-checklist?workspace_id=demo
```

### V98 - Company memory

```bash
curl -X POST http://localhost:8000/ai/v98/company-memory \
  -H "Content-Type: application/json" \
  -d '{"workspace_id":"demo","category":"asset_policy","fact":"Máy tính từ 30 triệu trở lên phải review TSCĐ"}'
```

### V99 - Production readiness

```http
GET /ai/v99/production-readiness
```

## Lưu ý quan trọng

Bản này đã nâng mạnh phần backend/code. Nhưng để AI trả lời đúng nghiệp vụ thật, bạn vẫn cần nạp thủ công:

1. Thông tư/quy định thật đang áp dụng.
2. Quy trình nội bộ công ty.
3. Danh mục tài khoản thực tế.
4. Hóa đơn/chứng từ mẫu thật đã che thông tin nhạy cảm.
5. Feedback sửa sai từ kế toán.

AI hiện tạo draft/review, chưa nên cho tự ghi sổ thật nếu chưa có người duyệt.

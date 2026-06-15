# V100 — Backend RAG Admin UI

Mục tiêu: tạo một giao diện trắng, đơn giản, chạy ngay trong FastAPI backend để **Admin/Owner** upload và quản lý tài liệu RAG chính thức. Không cần frontend riêng.

## Nguyên tắc thiết kế

- Admin/Owner là người nạp tri thức RAG chính thức.
- User thường không được upload vào RAG knowledge base.
- User chỉ upload hóa đơn, báo cáo, sao kê, file OCR... để AI xử lý tạm thời theo workspace.
- File user không làm thay đổi tri thức chung của AI.

## File đã thêm

```txt
services/rag_admin_ui_v100.py
tests/test_v100_rag_admin_ui.py
docs/V100_BACKEND_RAG_ADMIN_UI_GUIDE.md
```

`main.py` đã được nối thêm các route HTML cho backend UI.

## Cách chạy local

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Mở:

```txt
http://localhost:8000/admin/rag-ui
```

Nếu chưa đặt `FINIIP_ADMIN_KEY` hoặc `FINIIP_API_KEY`, local dev sẽ mở thẳng để test nhanh.

## Cách bảo vệ khi deploy

Nên đặt biến môi trường:

```bash
FINIIP_ADMIN_KEY="your-strong-admin-key"
```

Sau đó mở:

```txt
https://your-backend-domain.com/admin/rag-ui?key=your-strong-admin-key&workspace_id=default
```

Hoặc dùng `FINIIP_API_KEY` sẵn có. `FINIIP_ADMIN_KEY` được ưu tiên hơn.

## Route UI chính

```txt
GET  /admin/rag-ui
POST /admin/rag-ui/upload
POST /admin/rag-ui/delete
POST /admin/rag-ui/reindex
POST /admin/rag-ui/ask
POST /admin/rag-ui/search
```

## API nhỏ cho admin UI

```txt
GET /admin/rag-ui/api/capabilities
GET /admin/rag-ui/api/documents
```

Khi deploy có key:

```txt
GET /admin/rag-ui/api/documents?key=YOUR_KEY&workspace_id=default
```

## Giao diện có gì?

- Nhập admin key và workspace
- Upload tài liệu RAG chính thức
- Chọn loại tài liệu:
  - `tax_legal`
  - `accounting_law`
  - `internal_process`
  - `chart_of_accounts`
  - `payroll_bhxh`
  - `invoice_policy`
  - `audit_policy`
  - `knowledge`
- Hỏi thử RAG
- Search chunk thô
- Danh sách tài liệu đã index
- Xem chi tiết chunks
- Re-index tài liệu
- Xóa tài liệu khỏi RAG

## File được phép upload vào Admin RAG

```txt
.pdf
.docx
.txt
.md
.csv
.json
.xlsx
.xlsm
.html
.htm
```

Giới hạn mặc định: 30MB.

Có thể chỉnh bằng biến môi trường:

```bash
FINIIP_ADMIN_RAG_MAX_MB=50
```

## Metadata tự gắn vào tài liệu Admin RAG

```json
{
  "document_scope": "global_knowledge",
  "uploaded_from": "v100_backend_rag_admin_ui",
  "can_train_ai": true,
  "can_use_for_global_rag": true
}
```

## Lưu ý triển khai

Hiện bản V100 dùng local JSON store/offline-first kế thừa V86-V99:

```txt
data/accounting_enterprise_store_v86_v99.json
data/accounting_uploads_v86/
```

Đủ cho local/MVP. Khi production thật, nên chuyển storage sang:

```txt
File gốc: Supabase Storage / S3 / Cloudflare R2
Metadata: Postgres
Chunks/vector: Postgres pgvector / Qdrant / Pinecone
```

Nhưng API và UI flow có thể giữ nguyên.

## Test

```bash
python -m pytest -q tests/test_v85_accounting_ai_full.py tests/test_v86_v99_accounting_enterprise.py tests/test_v100_rag_admin_ui.py
```

Kết quả khi build bản này:

```txt
20 passed
```

## Khuyến nghị dùng thật

1. Deploy backend.
2. Set `FINIIP_ADMIN_KEY`.
3. Mở `/admin/rag-ui?key=...`.
4. Upload thông tư/quy trình/danh mục tài khoản chuẩn.
5. Dùng form “Hỏi thử RAG” để kiểm tra AI lấy đúng nguồn.
6. User thường vẫn dùng các endpoint xử lý file riêng, không dùng màn này.

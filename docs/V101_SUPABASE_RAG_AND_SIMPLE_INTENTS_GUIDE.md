# V101 — Supabase RAG Storage + Simple Intent Router

## Mục tiêu

V101 nối giao diện backend `/admin/rag-ui` với Supabase để Admin nạp tài liệu RAG chính thức bền hơn khi deploy.

Thiết kế vẫn giữ đúng phân quyền:

- Admin/owner mới được upload tài liệu vào RAG chính thức.
- User thường chỉ upload hóa đơn, báo cáo, sao kê, OCR để xử lý tạm.
- File user upload không đi vào knowledge base chính.

Nếu chưa cấu hình Supabase, backend tự fallback về local store cũ để test.

---

## File mới/sửa

```txt
services/rag_storage_v101.py
services/simple_intents_v101.py
services/rag_admin_ui_v100.py
services/question_analyzer.py
ai_intents.json
tests/test_v101_supabase_intents.py
docs/V101_SUPABASE_RAG_AND_SIMPLE_INTENTS_GUIDE.md
main.py
```

---

## Biến môi trường cần thêm

Trong `.env` khi deploy backend:

```env
RAG_STORAGE_MODE=supabase
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_RAG_BUCKET=rag-knowledge
FINIIP_ADMIN_KEY=your-admin-key
```

Lưu ý:

- `SUPABASE_SERVICE_ROLE_KEY` chỉ đặt ở backend.
- Không đưa service role key ra frontend.
- Nếu thiếu `SUPABASE_URL` hoặc `SUPABASE_SERVICE_ROLE_KEY`, hệ thống tự dùng local.

---

## Tạo bucket Supabase Storage

Trong Supabase Dashboard tạo bucket:

```txt
rag-knowledge
```

Khuyến nghị:

```txt
Public: false
```

---

## Tạo bảng Supabase

Mở Supabase SQL Editor và chạy SQL dưới đây.


> Lưu ý schema: từ bản fix này, Admin UI dùng bảng `admin_rag_documents`, `admin_rag_document_chunks`, `admin_rag_audit_logs` để tránh đụng schema cũ V67/V68 (`rag_documents`, `rag_chunks`). Nếu Supabase của bạn đã từng chạy SQL V67/V68, **không cần xóa bảng cũ**; chỉ cần chạy SQL V101 mới dưới đây.

```sql
-- Finiip V101 Supabase RAG schema
-- Run in Supabase SQL Editor. Keep service_role key ONLY on the backend.

create table if not exists public.admin_rag_documents (
  document_id text primary key,
  workspace_id text not null default 'default',
  title text not null,
  source_type text not null default 'knowledge',
  content_sha256 text,
  metadata jsonb not null default '{}'::jsonb,
  status text not null default 'active',
  chunk_count integer not null default 0,
  char_count integer not null default 0,
  storage_bucket text,
  storage_path text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.admin_rag_document_chunks (
  chunk_id text primary key,
  document_id text not null references public.admin_rag_documents(document_id) on delete cascade,
  workspace_id text not null default 'default',
  title text not null,
  source_type text not null default 'knowledge',
  section integer,
  chunk_no integer,
  heading text,
  content text not null,
  tokens text[] not null default '{}',
  created_at timestamptz not null default now()
);

create table if not exists public.admin_rag_audit_logs (
  audit_id bigint generated always as identity primary key,
  event_type text not null,
  workspace_id text,
  document_id text,
  payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_admin_rag_documents_workspace_status
  on public.admin_rag_documents(workspace_id, status, updated_at desc);

create index if not exists idx_admin_rag_document_chunks_workspace_doc
  on public.admin_rag_document_chunks(workspace_id, document_id, chunk_no);

create index if not exists idx_admin_rag_document_chunks_tokens_gin
  on public.admin_rag_document_chunks using gin(tokens);
```

Có thể lấy SQL này từ API sau khi chạy backend:

```txt
GET /admin/rag-ui/api/supabase-schema?key=YOUR_ADMIN_KEY
```

---

## Kiểm tra Supabase đã active chưa

```txt
GET /ai/v101/supabase/status
```

Nếu đúng sẽ thấy:

```json
{
  "active_backend": "supabase",
  "configured": true,
  "bucket": "rag-knowledge"
}
```

Nếu chưa cấu hình sẽ thấy:

```json
{
  "active_backend": "local",
  "configured": false
}
```

---

## Giao diện Admin RAG

Mở:

```txt
/admin/rag-ui?key=YOUR_ADMIN_KEY&workspace_id=default
```

Khi Supabase active, các thao tác sau sẽ ghi/đọc Supabase:

- Upload & Index
- Danh sách tài liệu
- Xem chunks
- Re-index
- Xóa khỏi RAG
- Search chunk
- Hỏi thử RAG

Luồng lưu:

```txt
Admin upload file
  ↓
Supabase Storage bucket rag-knowledge
  ↓
admin_rag_documents
  ↓
admin_rag_document_chunks
  ↓
/admin/rag-ui search/ask đọc từ Supabase
```

---

## Endpoint V101 mới

```txt
GET  /ai/v101/capabilities
GET  /ai/v101/supabase/status
GET  /admin/rag-ui/api/storage-status?key=...
GET  /admin/rag-ui/api/supabase-schema?key=...
POST /ai/v101/intent/detect
GET  /ai/v101/intent/catalog
```

---

## Test intent đơn giản

```bash
curl -X POST http://localhost:8000/ai/v101/intent/detect \
  -H "Content-Type: application/json" \
  -d '{"message":"up tài liệu RAG ở đâu"}'
```

Kết quả mong muốn:

```json
{
  "intent": "admin_rag_upload",
  "requires_admin": true,
  "route_hint": "/admin/rag-ui"
}
```

Các nhóm intent V101 đã thêm nhiều hơn:

- Admin RAG upload/list/delete/reindex/search/ask
- Supabase status/schema/database
- User file upload/OCR/report analyze
- Hạch toán, phân loại giao dịch, kiểm tra bút toán
- VAT, hóa đơn, chi phí được trừ, tài khoản
- Lương/BHXH/TNCN
- TSCĐ/CCDC/phân bổ
- Kho/giá vốn/FIFO/bình quân
- Công nợ, ngân hàng, tiền mặt
- Khóa sổ, báo cáo, lợi nhuận, doanh thu, chi phí, dòng tiền
- Review queue, export/import
- Workspace, company memory, production/security

---

## Test local

```bash
python -m pytest -q tests/test_v85_accounting_ai_full.py tests/test_v86_v99_accounting_enterprise.py tests/test_v100_rag_admin_ui.py tests/test_v101_supabase_intents.py
```

Kết quả khi tớ build:

```txt
24 passed
```

---

## Ghi chú production

Bản V101 hiện dùng lexical search trên chunks trong Supabase để giữ đơn giản, chưa bắt buộc pgvector. Sau này có thể nâng tiếp:

- `V102`: pgvector embeddings cho RAG search tốt hơn.
- `V103`: auth role admin thực sự thay vì query key.
- `V104`: tách bucket `rag-knowledge` và `user-uploads` đầy đủ.

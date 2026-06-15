# V101 Admin RAG Supabase Fix

## Lỗi thường gặp

Khi upload tài liệu qua `/admin/rag-ui`, Supabase có thể trả về lỗi dạng:

```txt
Supabase REST lỗi 400: {"code":"PGRST204", ...}
Supabase REST lỗi 400: {"code":"23502", "details":"Failing row contains (null, doc_..., ...)"}
```

Nguyên nhân chính: project có 2 thế hệ schema RAG khác nhau.

- V67/V68 dùng bảng `rag_documents` / `rag_chunks` với cột `id uuid`.
- V101 Admin UI cần schema dạng `document_id text`, `workspace_id`, `source_type`, `metadata`, `storage_bucket`, `storage_path`.

Nếu dùng chung tên `rag_documents`, PostgREST sẽ insert vào bảng cũ và lỗi `id null`, thiếu cột, hoặc schema cache chưa đúng.

## Bản fix này thay đổi gì?

Admin UI V101 chuyển sang bảng riêng:

```txt
admin_rag_documents
admin_rag_document_chunks
admin_rag_audit_logs
```

Như vậy bạn không cần xóa bảng RAG cũ. V67/V68 vẫn giữ được, còn Admin UI dùng bảng mới ổn định hơn.

## Việc cần làm trên Supabase

1. Vào Supabase Dashboard → Storage → tạo bucket theo biến `SUPABASE_RAG_BUCKET`.
   - Mặc định: `rag-knowledge`
   - Nếu `.env` đang đặt `SUPABASE_RAG_BUCKET=rag-files`, hãy tạo bucket `rag-files`.
   - Public: nên để `false`.

2. Vào SQL Editor và chạy SQL từ endpoint:

```txt
GET /admin/rag-ui/api/supabase-schema?key=YOUR_ADMIN_KEY
```

Hoặc copy SQL trong `docs/V101_SUPABASE_RAG_AND_SIMPLE_INTENTS_GUIDE.md`.

3. Kiểm tra backend:

```txt
GET /ai/v101/supabase/status
```

Kết quả nên có:

```json
{
  "active_backend": "supabase",
  "configured": true,
  "tables": [
    "admin_rag_documents",
    "admin_rag_document_chunks",
    "admin_rag_audit_logs"
  ]
}
```

4. Mở Admin UI:

```txt
/admin/rag-ui?key=YOUR_ADMIN_KEY&workspace_id=default
```

Upload lại file RAG. Nếu thành công, danh sách tài liệu sẽ hiện `chunks > 0`.

## Biến môi trường cần có

```env
RAG_STORAGE_MODE=supabase
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_RAG_BUCKET=rag-knowledge
FINIIP_ADMIN_KEY=your-admin-key
```

Tuỳ chọn nếu muốn đổi tên bảng:

```env
SUPABASE_RAG_DOCUMENTS_TABLE=admin_rag_documents
SUPABASE_RAG_CHUNKS_TABLE=admin_rag_document_chunks
SUPABASE_RAG_AUDIT_TABLE=admin_rag_audit_logs
```

Không đưa `SUPABASE_SERVICE_ROLE_KEY` ra frontend.

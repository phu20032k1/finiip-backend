# V67 - Supabase RAG Storage

## Mục tiêu

V66 upload file đã đọc được text và lưu vào RAG local. V67 nâng cấp thêm bước ghi vào Supabase thật:

```text
POST /ai/v66/rag/upload-file
→ đọc file
→ lưu local RAG như cũ
→ insert vào Supabase rag_documents
→ insert chunks vào Supabase rag_chunks
```

## Biến môi trường cần có trong `.env`

```env
APP_ENV=local
API_KEY=123456

SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=sb_secret_xxxxx
DATABASE_URL=postgresql://postgres.xxxxx:password@aws-xxx.pooler.supabase.com:6543/postgres
RAG_BUCKET=rag-files
```

V67 có loader `.env` nhỏ tích hợp sẵn, nên chạy local trong VS Code vẫn đọc được `DATABASE_URL` mà không cần cài `python-dotenv`.

## SQL cần chạy trong Supabase

```sql
create extension if not exists vector;

create table if not exists rag_documents (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  document_type text,
  category text,
  source text,
  storage_path text,
  uploaded_by text,
  created_at timestamptz default now()
);

create table if not exists rag_chunks (
  id uuid primary key default gen_random_uuid(),
  document_id uuid references rag_documents(id) on delete cascade,
  chunk_index int not null,
  content text not null,
  metadata jsonb default '{}'::jsonb,
  embedding vector(1536),
  created_at timestamptz default now()
);

create index if not exists rag_chunks_embedding_idx
on rag_chunks
using ivfflat (embedding vector_cosine_ops)
with (lists = 100);
```

## API mới

### Kiểm tra kết nối Supabase RAG

```http
GET /ai/v67/supabase-rag/status
```

Kết quả đúng:

```json
{
  "database_url_configured": true,
  "rag_documents": 1,
  "rag_chunks": 1
}
```

### Search thử trong Supabase RAG

```http
POST /ai/v67/supabase-rag/search
```

Body:

```json
{
  "question": "mua hàng chưa thanh toán định khoản thế nào",
  "limit": 5
}
```

### Upload tài liệu vào RAG

Vẫn dùng endpoint V66 cũ:

```http
POST /ai/v66/rag/upload-file
```

Nếu Supabase ghi thành công, response sẽ có:

```json
"supabase": {
  "enabled": true,
  "saved": true,
  "document_id": "...",
  "chunks": 1
}
```

Nếu Supabase chưa cấu hình đúng, response vẫn upload local được nhưng sẽ có:

```json
"supabase": {
  "enabled": true,
  "saved": false,
  "error": "..."
}
```

## Lưu ý embedding

V67 đang dùng `v67_hash_fallback` để tạo vector 1536 chiều không cần OpenAI key. Mục tiêu là giúp bạn test production plumbing ngay: bảng có dòng, search có kết quả, deploy không phụ thuộc API key.

Sau này có thể thay bằng OpenAI embeddings thật để tìm kiếm ngữ nghĩa tốt hơn.

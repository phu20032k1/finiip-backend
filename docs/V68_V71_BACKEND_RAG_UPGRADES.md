# V68/V69/V70/V71 Backend RAG Upgrades

Bản này chưa làm frontend. Phần đã thêm là backend production-ready hơn cho RAG.

## Đã thêm

### V68 - Health, schema, embedding

```http
GET  /ai/v68/rag/health
POST /ai/v68/rag/init-schema
GET  /ai/v68/rag/embedding-status
```

- Tự tạo/nâng bảng `rag_documents`, `rag_chunks` nếu `DATABASE_URL` đúng.
- Hỗ trợ `pgvector`.
- Nếu có `OPENAI_API_KEY`, dùng embedding thật.
- Nếu chưa có `OPENAI_API_KEY`, dùng `deterministic_hash_v68` để test pipeline.

### V69 - Hỏi đáp RAG hoàn chỉnh

```http
POST /ai/v69/rag/answer
```

Body mẫu:

```json
{
  "question": "mua hàng chưa thanh toán định khoản thế nào",
  "limit": 6,
  "category": "che_do_ke_toan",
  "use_llm": false
}
```

- `use_llm=false`: trả lời dạng extractive, trích chunk nguồn.
- `use_llm=true`: nếu có `OPENAI_API_KEY`, backend gọi LLM để viết câu trả lời có căn cứ `[1]`, `[2]`.

### V70 - Quản lý tài liệu RAG

```http
GET    /ai/v70/rag/documents
GET    /ai/v70/rag/documents/{document_id}
DELETE /ai/v70/rag/documents/{document_id}
POST   /ai/v70/rag/documents/{document_id}/reindex
```

Dùng để xem tài liệu đã upload, xem chunks, xóa tài liệu sai, và reindex lại tài liệu.

### V71 - Security/deploy check

```http
GET /ai/v71/security/deploy-check
```

Đã thêm giới hạn file upload:

```env
RAG_MAX_UPLOAD_BYTES=20971520
```

Các định dạng cho phép:

```text
.txt, .md, .csv, .json, .pdf, .docx, .xlsx, .xlsm, .html, .xml
```

## SQL Supabase cần có

Endpoint `POST /ai/v68/rag/init-schema` sẽ cố tự tạo schema. Nếu muốn chạy thủ công trong SQL Editor:

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
  created_at timestamptz default now(),
  updated_at timestamptz default now()
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

create index if not exists rag_documents_category_idx on rag_documents(category);
create index if not exists rag_chunks_document_id_idx on rag_chunks(document_id);
create index if not exists rag_chunks_metadata_gin_idx on rag_chunks using gin(metadata);
create index if not exists rag_chunks_embedding_idx
on rag_chunks using ivfflat (embedding vector_cosine_ops) with (lists = 100);
```

## Cách test nhanh

```bash
cd copy
pip install -r requirements.txt
uvicorn main:app --reload
```

Mở docs:

```text
http://localhost:8000/docs
```

1. Gọi:

```http
GET /ai/v68/rag/health
```

2. Init schema:

```http
POST /ai/v68/rag/init-schema
```

Body:

```json
{"confirm": true}
```

3. Upload file RAG bằng endpoint cũ:

```http
POST /ai/v66/rag/upload-file
```

4. Hỏi đáp:

```http
POST /ai/v69/rag/answer
```

## Lưu ý production

- Set `FINIIP_API_KEY` để khóa API.
- Frontend/backend phải gửi header:

```text
X-API-Key: <FINIIP_API_KEY>
```

- Trước deploy thật, sửa CORS trong `main.py`:

```python
allow_origins=["https://your-frontend-domain.com"]
```

- Nếu muốn câu trả lời thông minh hơn, set `OPENAI_API_KEY`. Nếu không set, backend vẫn search và trả lời dạng trích đoạn.

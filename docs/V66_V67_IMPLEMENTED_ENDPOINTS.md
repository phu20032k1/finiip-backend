# V66/V67 đã được chèn vào backend

## File mới

- `services/rag_v66_v67.py`: đọc file, chunk text, local RAG, Supabase Postgres RAG, search RAG.

## File đã sửa

- `main.py`: thêm endpoint V66/V67.
- `requirements.txt`: thêm `python-docx` để đọc file `.docx`.
- `.env.example`, `.env.production.example`: thêm biến môi trường Supabase RAG.

## Endpoint đã có thật trong `main.py`

```http
GET  /ai/v66/file-upload-router/status
POST /ai/v66/rag/upload-file
POST /ai/v66/solve/upload-question-file
POST /ai/v66/file-upload-router
GET  /ai/v67/supabase-rag/status
POST /ai/v67/supabase-rag/search
```

## Chạy local

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Mở:

```text
http://localhost:8000/docs
```

## Test upload tài liệu RAG

```bash
curl -X POST http://localhost:8000/ai/v66/rag/upload-file \
  -F "file=@Thong-tu-200.pdf" \
  -F "title=Thông tư 200" \
  -F "category=che_do_ke_toan" \
  -F "document_type=thong_tu" \
  -F "tags=tt200,ke_toan"
```

Nếu chưa cấu hình Supabase, backend vẫn lưu local vào:

```text
data/v66_rag_store.json
```

## Test search RAG

```bash
curl -X POST http://localhost:8000/ai/v67/supabase-rag/search \
  -H "Content-Type: application/json" \
  -d '{"question":"mua hàng chưa thanh toán định khoản thế nào", "limit":5}'
```

## Cấu hình Supabase

Cần chạy SQL trong:

```text
docs/V67_SUPABASE_RAG_STORAGE_GUIDE.md
```

Sau đó set `.env`:

```env
DATABASE_URL=postgresql://postgres.xxxxx:password@aws-xxx.pooler.supabase.com:6543/postgres
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=...
RAG_BUCKET=rag-files
```

Kiểm tra:

```http
GET /ai/v67/supabase-rag/status
```

## Lưu ý

- Search hiện dùng keyword scoring ổn để test và demo.
- Embedding đang là `v67_hash_fallback` để không cần OpenAI key.
- Sau này có thể thay bằng OpenAI embedding thật để tìm kiếm ngữ nghĩa tốt hơn.

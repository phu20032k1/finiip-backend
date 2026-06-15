# V72-V75 Pro Backend RAG Upgrades

Bản này nâng backend RAG lên mức cao hơn nhưng **chưa làm frontend**.

## Tính năng mới

- V72: chunk tài liệu thông minh theo cấu trúc văn bản: PHẦN, CHƯƠNG, MỤC, ĐIỀU, KHOẢN, điểm a/b/c.
- V72: upload một file hoặc nhiều file cùng lúc.
- V72: pro schema cho Supabase/Postgres: tags, metadata, status, content_sha256, heading, section_path, lexical index.
- V73: hybrid search: pgvector + keyword scoring + phrase/legal/accounting boost + rerank.
- V74: answer endpoint có trích nguồn, section path, score.
- V74: quality-check để test nhanh nhiều câu hỏi.
- V75: audit log backend cho upload/search/answer.

## Endpoint mới

```txt
GET  /ai/v72/pro-rag/health
POST /ai/v72/pro-rag/init-schema
POST /ai/v72/pro-rag/upload-file
POST /ai/v72/pro-rag/upload-batch
POST /ai/v73/pro-rag/hybrid-search
POST /ai/v74/pro-rag/answer
POST /ai/v74/pro-rag/quality-check
GET  /ai/v75/pro-rag/audit-logs
```

## Chạy local

```bash
cd copy
pip install -r requirements.txt
uvicorn main:app --reload
```

Mở docs:

```txt
http://localhost:8000/docs
```

## Cấu hình môi trường

Tối thiểu để lưu Supabase/Postgres:

```env
DATABASE_URL=postgresql://...
```

Tùy chọn để embedding/trả lời tốt hơn:

```env
OPENAI_API_KEY=...
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_CHAT_MODEL=gpt-4o-mini
FINIIP_API_KEY=your-secure-key
RAG_MAX_UPLOAD_BYTES=20971520
RAG_MAX_BATCH_FILES=12
RAG_PRO_CHUNK_SIZE=1600
RAG_PRO_OVERLAP=220
```

## Init schema

```bash
curl -X POST http://localhost:8000/ai/v72/pro-rag/init-schema \
  -H "Content-Type: application/json" \
  -d '{"confirm": true}'
```

Nếu có `FINIIP_API_KEY`, thêm header:

```bash
-H "X-API-Key: your-secure-key"
```

## Upload một file

```bash
curl -X POST http://localhost:8000/ai/v72/pro-rag/upload-file \
  -F "file=@Thong-tu-200.pdf" \
  -F "category=che_do_ke_toan" \
  -F "document_type=thong_tu" \
  -F "tags=tt200,ke_toan,quy_dinh"
```

## Upload nhiều file

```bash
curl -X POST http://localhost:8000/ai/v72/pro-rag/upload-batch \
  -F "files=@Thong-tu-200.pdf" \
  -F "files=@Nghi-dinh.pdf" \
  -F "category=van_ban_phap_luat" \
  -F "document_type=quy_dinh" \
  -F "tags=luat,thong_tu,nghi_dinh"
```

## Hybrid search

```bash
curl -X POST http://localhost:8000/ai/v73/pro-rag/hybrid-search \
  -H "Content-Type: application/json" \
  -d '{
    "question": "mua hàng chưa thanh toán định khoản thế nào theo thông tư 200",
    "limit": 8,
    "category": "che_do_ke_toan"
  }'
```

## Hỏi đáp có nguồn

```bash
curl -X POST http://localhost:8000/ai/v74/pro-rag/answer \
  -H "Content-Type: application/json" \
  -d '{
    "question": "mua hàng chưa thanh toán định khoản thế nào",
    "limit": 8,
    "category": "che_do_ke_toan",
    "style": "detailed",
    "use_llm": false
  }'
```

## Quality check

```bash
curl -X POST http://localhost:8000/ai/v74/pro-rag/quality-check \
  -H "Content-Type: application/json" \
  -d '{
    "category": "che_do_ke_toan",
    "questions": [
      "mua hàng chưa thanh toán định khoản thế nào",
      "chi phí trả trước phân bổ ra sao",
      "thuế GTGT đầu vào được khấu trừ khi nào"
    ]
  }'
```

## Audit logs

```bash
curl http://localhost:8000/ai/v75/pro-rag/audit-logs?limit=50
```

## Ghi chú production

- Không để `allow_origins=["*"]` khi deploy public.
- Nên đặt `FINIIP_API_KEY` để khóa endpoint upload/xóa/reindex.
- Không dùng `SUPABASE_SERVICE_ROLE_KEY` ở frontend.
- Giới hạn file upload bằng `RAG_MAX_UPLOAD_BYTES`.
- Với tài liệu scan ảnh, cần thêm OCR riêng trước khi đưa vào RAG.

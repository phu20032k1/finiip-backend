# V81 - RAG Sources & Document Metadata Management

Bản này chỉ nâng cấp backend, frontend làm riêng.

## Mục tiêu

- RAG trả lời kèm nguồn/citations rõ hơn.
- Khi upload tài liệu có thể lưu metadata pháp lý/nghiệp vụ.
- Quản lý document: danh sách, xem chi tiết, xóa, reindex.
- Chuẩn bị cho frontend quản lý tài liệu sau này.

## Endpoint chính

### 1. Init schema Supabase

```bash
curl -X POST http://localhost:8000/ai/v68/rag/init-schema \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <FINIIP_API_KEY>" \
  -d '{"confirm": true}'
```

Schema sẽ tự tạo/nâng cấp:

- `rag_documents`
- `rag_chunks`
- metadata fields: `document_number`, `issued_date`, `effective_date`, `authority`, `status`, `version`, `workspace_id`, `user_id`, `tags`, `metadata`

### 2. Upload tài liệu vào RAG

```bash
curl -X POST http://localhost:8000/ai/v66/rag/upload-file \
  -H "X-API-Key: <FINIIP_API_KEY>" \
  -F "file=@./Thong-tu-01.pdf" \
  -F "title=Thông tư 01" \
  -F "category=legal" \
  -F "document_type=thong_tu" \
  -F "source=admin_upload" \
  -F "tags=thuế,hóa đơn" \
  -F "uploaded_by=admin" \
  -F "document_number=01/2026/TT-BTC" \
  -F "issued_date=2026-01-01" \
  -F "effective_date=2026-02-01" \
  -F "authority=Bộ Tài chính" \
  -F "status=active" \
  -F "version=2026.1" \
  -F "workspace_id=phap-che" \
  -F "user_id=admin"
```

Các field metadata là optional. Nếu chưa có thì có thể bỏ qua.

### 3. Hỏi RAG có nguồn

```bash
curl -X POST http://localhost:8000/ai/v69/rag/answer \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <FINIIP_API_KEY>" \
  -d '{
    "question": "Thông tư này quy định gì về hóa đơn?",
    "category": "legal",
    "limit": 6,
    "use_llm": false
  }'
```

Response chính:

```json
{
  "answer": "...",
  "citations": [
    {
      "ref": "[1]",
      "document_id": "...",
      "title": "Thông tư 01",
      "document_number": "01/2026/TT-BTC",
      "authority": "Bộ Tài chính",
      "effective_date": "2026-02-01",
      "chunk_index": 3,
      "score": 8.5
    }
  ],
  "sources": [
    {
      "document_id": "...",
      "chunk_id": "...",
      "title": "Thông tư 01",
      "filename": "Thong-tu-01.pdf",
      "document_number": "01/2026/TT-BTC",
      "content": "..."
    }
  ]
}
```

### 4. Danh sách tài liệu

```bash
curl "http://localhost:8000/ai/v70/rag/documents?category=legal&workspace_id=phap-che&status=active" \
  -H "X-API-Key: <FINIIP_API_KEY>"
```

### 5. Xem chi tiết tài liệu

```bash
curl "http://localhost:8000/ai/v70/rag/documents/<document_id>?include_chunks=true&chunk_limit=20" \
  -H "X-API-Key: <FINIIP_API_KEY>"
```

### 6. Xóa tài liệu khỏi RAG

```bash
curl -X DELETE http://localhost:8000/ai/v70/rag/documents/<document_id> \
  -H "X-API-Key: <FINIIP_API_KEY>"
```

### 7. Reindex tài liệu

```bash
curl -X POST http://localhost:8000/ai/v70/rag/documents/<document_id>/reindex \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <FINIIP_API_KEY>" \
  -d '{"chunk_size": 1200, "overlap": 180}'
```

## Gợi ý frontend sau này

Frontend riêng chỉ cần gọi các endpoint trên để làm màn:

- Upload tài liệu.
- Danh sách tài liệu.
- Xem nguồn/chunk.
- Xóa/reindex.
- Chat hỏi đáp RAG hiển thị citations.

## Lưu ý

- Local không có `DATABASE_URL` vẫn chạy được bằng JSON store, nhưng production nên dùng Supabase/Postgres.
- Nếu có `OPENAI_API_KEY`, đặt `use_llm=true` để câu trả lời diễn giải tốt hơn.
- Không upload `.env` thật lên GitHub hoặc gửi cho frontend.

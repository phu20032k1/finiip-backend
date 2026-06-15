# V76-V80 Full Pro Backend RAG

Bản này vẫn **không làm frontend**, chỉ nâng backend RAG lên mức production hơn.

## Tính năng mới

- V76: Multi-turn RAG chat session, giữ lịch sử hỏi đáp theo `session_id`.
- V77: Query cache TTL, advanced answer, confidence score, quality flags, metrics summary.
- V78: Job queue backend cho tác vụ dài như `quality_check`, `clear_cache`, `reindex_document`.
- V79: Soft delete/restore document, registry version tài liệu.
- V80: Full-pro health, full schema init, role/admin guard.

## Biến môi trường mới

```env
RAG_ADMIN_TOKEN=change-me-strong-admin-token
RAG_CACHE_TTL_SECONDS=900
RAG_MAX_SESSION_MESSAGES=20
RAG_JOB_AUTO_RUN=true
```

Khi set `RAG_ADMIN_TOKEN`, các endpoint full-pro cần header:

```txt
X-RAG-Admin-Token: change-me-strong-admin-token
X-User-Role: admin
```

Nếu trước đó đã set `FINIIP_API_KEY`, vẫn cần header:

```txt
X-API-Key: your-finiip-api-key
```

## Endpoint mới

```txt
GET  /ai/v80/full-pro-rag/health
POST /ai/v80/full-pro-rag/init-schema

POST   /ai/v76/full-pro-rag/chat/answer
GET    /ai/v76/full-pro-rag/chat/sessions
GET    /ai/v76/full-pro-rag/chat/sessions/{session_id}
DELETE /ai/v76/full-pro-rag/chat/sessions/{session_id}

POST /ai/v77/full-pro-rag/answer
POST /ai/v77/full-pro-rag/cache/clear
GET  /ai/v77/full-pro-rag/metrics

POST /ai/v78/full-pro-rag/jobs
GET  /ai/v78/full-pro-rag/jobs
GET  /ai/v78/full-pro-rag/jobs/{job_id}
POST /ai/v78/full-pro-rag/jobs/{job_id}/run

DELETE /ai/v79/full-pro-rag/documents/{document_id}
POST   /ai/v79/full-pro-rag/documents/{document_id}/restore
GET    /ai/v79/full-pro-rag/document-versions
POST   /ai/v79/full-pro-rag/documents/{document_id}/versions
```

## Test nhanh

### 1. Health

```bash
curl http://localhost:8000/ai/v80/full-pro-rag/health
```

### 2. Init schema

```bash
curl -X POST http://localhost:8000/ai/v80/full-pro-rag/init-schema \
  -H "Content-Type: application/json" \
  -d '{"confirm": true}'
```

### 3. Advanced answer có cache/confidence

```bash
curl -X POST http://localhost:8000/ai/v77/full-pro-rag/answer \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Chi phí trả trước phân bổ như thế nào?",
    "limit": 8,
    "style": "detailed"
  }'
```

### 4. Chat nhiều lượt

Lượt 1:

```bash
curl -X POST http://localhost:8000/ai/v76/full-pro-rag/chat/answer \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "demo-001",
    "question": "Mua hàng chưa thanh toán định khoản thế nào?",
    "limit": 8
  }'
```

Lượt 2:

```bash
curl -X POST http://localhost:8000/ai/v76/full-pro-rag/chat/answer \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "demo-001",
    "question": "Nếu có thuế VAT thì sao?",
    "limit": 8
  }'
```

### 5. Job queue

```bash
curl -X POST http://localhost:8000/ai/v78/full-pro-rag/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "job_type": "quality_check",
    "payload": {
      "questions": ["Mua hàng chưa thanh toán định khoản thế nào?", "Chi phí trả trước phân bổ ra sao?"],
      "limit": 5
    }
  }'
```

Hỗ trợ job_type:

```txt
clear_cache
quality_check
reindex_document
```

Với `reindex_document`:

```json
{
  "job_type": "reindex_document",
  "payload": {
    "document_id": "uuid-document",
    "chunk_size": 1600,
    "overlap": 220
  }
}
```

### 6. Soft delete / restore

```bash
curl -X DELETE http://localhost:8000/ai/v79/full-pro-rag/documents/DOCUMENT_ID \
  -H "Content-Type: application/json" \
  -d '{"reason":"replace with newer version"}'
```

```bash
curl -X POST http://localhost:8000/ai/v79/full-pro-rag/documents/DOCUMENT_ID/restore
```

## Ghi chú quan trọng

- Đây là full-pro backend layer, không thay frontend.
- Job queue hiện dùng local JSON để dễ chạy local; khi scale lớn có thể thay bằng Celery/RQ/Cloud Tasks.
- Cache dùng local JSON; khi deploy nhiều instance nên thay bằng Redis.
- Soft delete hoạt động tốt với Supabase/Postgres nếu đã init schema.
- Version registry hỗ trợ lưu lịch sử version, nhưng việc so sánh diff chi tiết giữa phiên bản có thể nâng tiếp nếu cần.

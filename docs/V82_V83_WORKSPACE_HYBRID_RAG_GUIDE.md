# V82/V83 - Workspace Isolation + Hybrid Search Backend

## Mục tiêu

Bản này nâng cấp tiếp từ V81, vẫn **backend only**, frontend làm riêng sau.

- **V82**: phân vùng dữ liệu theo `workspace_id`, `user_id`, `status`.
- **V83**: tìm kiếm hybrid: vector candidate + keyword candidate + rerank.

## Endpoint đã nâng cấp

### 1. Hỏi RAG có scope

```http
POST /ai/v69/rag/answer
```

Body ví dụ:

```json
{
  "question": "Điều kiện áp dụng quy trình này là gì?",
  "category": "legal",
  "workspace_id": "phap-che",
  "user_id": "user-001",
  "status": "active",
  "search_mode": "hybrid",
  "limit": 6,
  "use_llm": false
}
```

`search_mode` hỗ trợ:

- `hybrid`: vector + keyword, nên dùng mặc định.
- `keyword`: ưu tiên bắt điều/khoản/số văn bản/từ khóa chính xác.
- `vector`: ưu tiên ngữ nghĩa.

### 2. Danh sách tài liệu có scope

```http
GET /ai/v70/rag/documents?workspace_id=phap-che&user_id=user-001&status=active
```

### 3. Xem chi tiết tài liệu có scope

```http
GET /ai/v70/rag/documents/{document_id}?workspace_id=phap-che&user_id=user-001
```

### 4. Xóa tài liệu có scope

```http
DELETE /ai/v70/rag/documents/{document_id}?workspace_id=phap-che&user_id=user-001
```

Nếu document không thuộc scope truyền vào, backend sẽ không xóa.

### 5. Reindex có scope

```http
POST /ai/v70/rag/documents/{document_id}/reindex?workspace_id=phap-che&user_id=user-001
```

Body:

```json
{
  "chunk_size": 1200,
  "overlap": 180
}
```

## Luồng upload nên dùng

Khi upload, frontend/admin nên gửi đủ metadata:

```http
POST /ai/v66/rag/upload-file
```

Form fields quan trọng:

```text
category=legal
workspace_id=phap-che
user_id=user-001
status=active
document_number=TT-01/2026
authority=...
effective_date=2026-01-01
```

## Vì sao cần V82?

Nếu nhiều người dùng hoặc nhiều phòng ban cùng upload tài liệu, bắt buộc phải filter theo `workspace_id/user_id`. Nếu không, user A có thể hỏi nhầm tài liệu của user B.

## Vì sao cần V83?

Vector search tốt cho câu hỏi theo ý nghĩa, nhưng câu hỏi luật/thông tư thường có mã như `Điều 12`, `Khoản 3`, `Thông tư 22`. Hybrid search giúp bắt cả:

- ngữ nghĩa câu hỏi;
- mã điều/khoản/số văn bản;
- từ khóa chính xác trong tài liệu.

## Test nhanh

Sau khi chạy backend:

```bash
uvicorn main:app --reload
```

Gọi init schema nếu dùng Supabase:

```http
POST /ai/v68/rag/init-schema
```

Sau đó hỏi:

```json
{
  "question": "Tóm tắt tài liệu này theo căn cứ chính",
  "workspace_id": "phap-che",
  "status": "active",
  "search_mode": "hybrid"
}
```

## Gợi ý cho frontend riêng

Frontend nên luôn gửi `workspace_id` trong mọi request RAG. Khi có đăng nhập thật, backend nên lấy `user_id` từ JWT thay vì tin hoàn toàn vào body.

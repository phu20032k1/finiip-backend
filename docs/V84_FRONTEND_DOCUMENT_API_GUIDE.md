# V84 - Backend API cho frontend quản lý tài liệu RAG

V84 chuẩn hóa bộ API để frontend riêng có thể quản lý tài liệu mà không cần biết chi tiết bên trong RAG.

## API chính

### 1. Health/status dashboard

```http
GET /ai/v84/rag/dashboard/status?workspace_id=phap-che&user_id=user-001
```

Trả về tổng số tài liệu, tổng số chunk, thống kê theo `status`, `category`, `workspace_id`.

### 2. Upload tài liệu

```http
POST /ai/v84/rag/documents/upload
Content-Type: multipart/form-data
```

Form fields:

- `file`: file PDF/DOCX/XLSX/TXT/MD/CSV/JSON/HTML/XML
- `title`
- `category`
- `document_type`
- `source`
- `tags`
- `uploaded_by`
- `document_number`
- `issued_date`
- `effective_date`
- `authority`
- `status`
- `version`
- `workspace_id`
- `user_id`
- `language`
- `jurisdiction`
- `extra_metadata_json`

### 3. List tài liệu

```http
GET /ai/v84/rag/documents?workspace_id=phap-che&status=active&limit=20&offset=0&q=thông tư
```

Dùng cho table ở frontend.

### 4. Xem chi tiết

```http
GET /ai/v84/rag/documents/{document_id}?include_chunks=true&chunk_limit=50
```

### 5. Cập nhật metadata

```http
PATCH /ai/v84/rag/documents/{document_id}
Content-Type: application/json
```

Body ví dụ:

```json
{
  "title": "Thông tư mẫu",
  "status": "active",
  "workspace_id": "phap-che",
  "metadata": {"note": "đã kiểm tra"}
}
```

### 6. Đổi trạng thái nhanh

```http
POST /ai/v84/rag/documents/{document_id}/status
```

Body:

```json
{"status":"archived"}
```

Status hợp lệ: `active`, `draft`, `archived`, `replaced`, `inactive`.

### 7. Reindex

```http
POST /ai/v84/rag/documents/{document_id}/reindex
```

Body:

```json
{"chunk_size":1200,"overlap":180}
```

### 8. Xóa tài liệu

```http
DELETE /ai/v84/rag/documents/{document_id}?workspace_id=phap-che&user_id=user-001
```

## Header bảo mật

Nếu `.env` có `FINIIP_API_KEY`, frontend cần gửi:

```http
X-API-Key: your-key
```

## Gợi ý UI frontend

Trang quản lý tài liệu nên có:

- ô search `q`
- filter `workspace_id`, `category`, `status`
- table columns: title, filename, category, status, document_number, authority, chunk_count, updated_at
- actions: detail, edit metadata, archive, reindex, delete
